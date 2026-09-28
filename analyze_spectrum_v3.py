"""Spectral analysis extractor for par-text-frame-format files (v3).

Outputs:
  - amplitude-weighted average frequency
  - average amplitude
  - traditional harmonic ratio
  - harmonicity on an expanded ranking scale, 1:1 = highest level
  - raw, octave-folded and labelled ratios for every partial
  - per-reference ratio columns in the final pitch table

Usage:  py analyze_spectrum_v3.py <input.txt> [output.csv] [--ref fund1|fund2|both]

  --ref          fundamental reference used for the harmonicity ratios:
                   fund1 -> fundPartial1 : lowest frequency above amp floor
                   fund2 -> fundPartial2 : second-lowest frequency above amp floor
                   both  -> both sets (default)

If output is omitted, <input>_analysis_v3_results.csv is written next to the input.
"""

import math
import sys
from pathlib import Path

AMP_FLOOR = 0.0001
HARM_TOL_CENTS = 30.0
QUARTER_TONE_CENTS = 50
NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

SCALE = [
    (1, 1), (2, 1), (3, 2), (4, 3), (5, 4), (7, 4),
    (6, 5), (8, 5), (5, 3), (9, 8), (11, 8), (13, 8),
    (7, 6), (8, 7), (10, 9), (11, 10), (15, 8), (12, 11),
    (13, 12), (14, 13), (15, 14), (16, 15),
]
SCALE_RATIOS = [n / d for n, d in SCALE]
SCALE_MAX = len(SCALE)
SCALE_REPRESENTATIONS = {
    (2, 1): (("1:1", 1.0), ("2:1", 2.0)),
    (7, 4): (("7:1", 7.0), ("3.5:1", 3.5), ("7:4", 1.75)),
    (9, 8): (("9:1", 9.0), ("4.5:1", 4.5), ("9:8", 1.125)),
    (11, 8): (("11:1", 11.0), ("5.5:1", 5.5), ("11:8", 1.375)),
    (13, 8): (("13:1", 13.0), ("6.5:1", 6.5), ("13:8", 1.625)),
    (15, 8): (("15:1", 15.0), ("7.5:1", 7.5), ("15:8", 1.875)),
}


def parse_file(path):
    with open(path, "r", encoding="utf-8") as fh:
        lines = fh.read().splitlines()
    start = 0
    for i, line in enumerate(lines):
        if line.strip() == "frame-data":
            start = i + 1
            break
    frames = []
    for line in lines[start:]:
        parts = line.split()
        if len(parts) < 2:
            continue
        t = float(parts[0])
        n = int(parts[1])
        vals = parts[2:]
        partials = []
        for k in range(n):
            base = k * 3
            if base + 2 >= len(vals):
                break
            idx = int(vals[base])
            freq = float(vals[base + 1])
            amp = float(vals[base + 2])
            partials.append((idx, freq, amp))
        frames.append((t, partials))
    return frames


def cents(f1, f2):
    if f1 <= 0 or f2 <= 0:
        return None
    return 1200.0 * (math.log2(f1) - math.log2(f2))


def fold_into_octave(ratio):
    if ratio is None or ratio <= 0 or not math.isfinite(ratio):
        return None
    return ratio / (2.0 ** math.floor(math.log2(ratio)))


def ratio_label(numerator, denominator):
    return f"{numerator}:{denominator}"


def nearest_scale(ratio):
    """Return (label, base_score, cents_offset) for the nearest scale ratio."""
    folded = fold_into_octave(ratio)
    if folded is None:
        return None, None, None
    offsets = [cents(folded, target) for target in SCALE_RATIOS]
    best_i = min(range(len(offsets)), key=lambda i: abs(offsets[i]))
    if best_i == 0 and abs(cents(ratio, 1.0)) > abs(cents(ratio, 2.0)):
        best_i = 1
        offset = offsets[best_i] + 1200.0
    else:
        offset = offsets[best_i]
    canonical = SCALE[best_i]
    representations = SCALE_REPRESENTATIONS.get(
        canonical,
        ((ratio_label(canonical[0], canonical[1]), canonical[0] / canonical[1]),),
    )
    label, _representation = min(
        representations,
        key=lambda item: abs(cents(ratio, item[1])),
    )
    return label, SCALE_MAX - best_i, offset


def match_ratio(ratio):
    """Return (label, mixed_score, cents_offset); score is zero outside tolerance."""
    label, base_score, offset = nearest_scale(ratio)
    if label is None:
        return None, 0.0, None
    if abs(offset) > HARM_TOL_CENTS:
        return label, 0.0, offset
    purity = 1.0 - abs(offset) / (2.0 * HARM_TOL_CENTS)
    return label, base_score * purity, offset


def note_name(midi_rounded):
    steps = int(round(midi_rounded * 2)) % 24
    octave = int(math.floor(midi_rounded / 12.0)) - 1
    name = NOTE_NAMES[steps // 2]
    if steps % 2:
        return f"{name}{octave}+"
    return f"{name}{octave}"


def ref_candidates(partials):
    return sorted(
        [(i, f, a) for i, f, a in partials if a >= AMP_FLOOR and f > 0],
        key=lambda item: item[1],
    )


def frame_harmonicity(partials, ref_idx):
    cands = ref_candidates(partials)
    if ref_idx >= len(cands):
        return None, None
    f_ref = cands[ref_idx][1]
    matched = 0
    total = 0
    score_sum = 0.0
    amp_sum = 0.0
    for _idx, freq, amp in cands:
        total += 1
        _label, score, offset = match_ratio(freq / f_ref)
        if offset is not None and abs(offset) <= HARM_TOL_CENTS:
            matched += 1
        score_sum += score * amp
        amp_sum += amp
    pct = (matched / total * 100.0) if total else 0.0
    weighted = (score_sum / amp_sum) if amp_sum else 0.0
    return pct, weighted


def analyze(frames):
    total_amp = 0.0
    weighted_freq = 0.0
    amp_count = 0
    frame_ratios = []
    partial_sums = {}

    for _time, partials in frames:
        h_count = 0
        t_count = 0
        f0 = None
        candidates = ref_candidates(partials)
        if candidates:
            f0 = candidates[0][1]
        for idx, freq, amp in partials:
            weighted_freq += freq * amp
            total_amp += amp
            amp_count += 1
            sums = partial_sums.get(idx, [0.0, 0.0, 0])
            partial_sums[idx] = [sums[0] + freq, sums[1] + amp, sums[2] + 1]
            if amp < AMP_FLOOR or f0 is None:
                continue
            t_count += 1
            ratio = freq / f0
            if ratio <= 0:
                continue
            nearest = round(ratio)
            offset = cents(freq, nearest * f0) if nearest >= 1 else None
            if offset is not None and abs(offset) <= HARM_TOL_CENTS:
                h_count += 1
        if t_count:
            frame_ratios.append(h_count / t_count)

    avg_freq = weighted_freq / total_amp if total_amp else 0.0
    avg_amp = (total_amp / amp_count) if amp_count else 0.0
    harm_ratio = sum(frame_ratios) / len(frame_ratios) if frame_ratios else 0.0

    part_means = []
    for idx in sorted(partial_sums):
        sum_freq, sum_amp, count = partial_sums[idx]
        part_means.append((idx, sum_freq / count, sum_amp / count))

    ordered = sorted(part_means, key=lambda item: item[1])
    clusters = []
    for idx, freq, _amp in ordered:
        if clusters:
            prev_mean = sum(part_means[i][1] for i in clusters[-1]) / len(clusters[-1])
            offset = cents(freq, prev_mean)
            if offset is not None and abs(offset) <= QUARTER_TONE_CENTS:
                clusters[-1].append(idx)
                continue
        clusters.append([idx])

    note_rows = []
    for group in clusters:
        cluster_freq = sum(part_means[i][1] for i in group) / len(group)
        cluster_amp = sum(part_means[i][2] for i in group) / len(group)
        midi = 69.0 + 12.0 * math.log2(cluster_freq / 440.0)
        midi_q = round(midi * 2) / 2.0
        note_rows.append(
            (cluster_freq, midi, midi_q, note_name(midi_q), tuple(group), cluster_amp)
        )

    return avg_freq, avg_amp, harm_ratio, note_rows, part_means


def collect_partial_details(frames, ref_idx):
    """Return per-partial accumulators plus median and amplitude-weighted reference."""
    acc = {}
    ref_freqs = []
    ref_amps = []
    for _time, partials in frames:
        cands = ref_candidates(partials)
        if ref_idx >= len(cands):
            continue
        _idx_ref, f_ref, a_ref = cands[ref_idx]
        ref_freqs.append(f_ref)
        ref_amps.append(a_ref)
        for idx, freq, amp in cands:
            label, score, offset = match_ratio(freq / f_ref)
            if label is None:
                continue
            entry = acc.setdefault(idx, [0.0, 0.0, 0, 0])
            entry[0] += score * amp
            entry[1] += amp
            entry[2] += 1 if abs(offset) <= HARM_TOL_CENTS else 0
            entry[3] += 1
    median_ref = sorted(ref_freqs)[len(ref_freqs) // 2] if ref_freqs else None
    amp_ref = (
        sum(f * a for f, a in zip(ref_freqs, ref_amps)) / sum(ref_amps)
        if ref_amps
        else None
    )
    return acc, median_ref, amp_ref


def format_detail_rows(ref_label, ref_freq, acc, part_means):
    rows = []
    idx_info = {idx: (freq, amp) for idx, freq, amp in part_means}
    for idx in sorted(idx_info):
        freq, amp = idx_info[idx]
        entry = acc.get(idx)
        if ref_freq and ref_freq > 0 and freq > 0:
            ratio = freq / ref_freq
            folded = fold_into_octave(ratio)
            interval, _base_score, offset = nearest_scale(ratio)
            ratio_s = f"{ratio:.4f}"
            folded_s = f"{folded:.4f}" if folded is not None else "0.0000"
            interval_s = interval if interval is not None else "-"
            offset_s = f"{offset:.1f}" if offset is not None else "-"
        else:
            ratio_s = "0.0000"
            folded_s = "0.0000"
            interval_s = "-"
            offset_s = "-"
        if entry:
            mean_score = entry[0] / entry[1] if entry[1] else 0.0
            matches = f"{entry[2]}/{entry[3]}"
        else:
            mean_score = 0.0
            matches = "0/0"
        rows.append(
            f"{ref_label},{idx},{freq:.4f},{amp:.6f},{ratio_s},{folded_s},"
            f"{interval_s},{offset_s},{mean_score:.4f},{matches}"
        )
    return rows


def cluster_ratio_label(indices, ref_freq, part_means):
    if not ref_freq or ref_freq <= 0:
        return "-"
    idx_info = {idx: freq for idx, freq, _amp in part_means}
    labels = []
    for idx in indices:
        freq = idx_info[idx]
        if freq <= 0:
            continue
        interval, _base_score, _offset = nearest_scale(freq / ref_freq)
        if interval and interval not in labels:
            labels.append(interval)
    return " | ".join(labels) if labels else "-"


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    ref_mode = "both"
    args = []
    i = 1
    while i < len(sys.argv):
        if sys.argv[i] == "--ref" and i + 1 < len(sys.argv):
            ref_mode = sys.argv[i + 1]
            i += 2
        else:
            args.append(sys.argv[i])
            i += 1
    if ref_mode not in ("fund1", "fund2", "both"):
        print(
            f"Unknown --ref mode '{ref_mode}' (use fund1, fund2 or both).",
            file=sys.stderr,
        )
        sys.exit(1)
    if not args:
        print(__doc__)
        sys.exit(1)

    src = Path(args[0])
    if len(args) >= 2:
        out = Path(args[1])
    else:
        out = src.with_name(src.stem + "_analysis_v3_results.csv")

    frames = parse_file(src)
    if not frames:
        print("No frame data found.", file=sys.stderr)
        sys.exit(1)

    avg_freq, avg_amp, traditional_ratio, note_rows, part_means = analyze(frames)
    refs = (0, 1) if ref_mode == "both" else ((0,) if ref_mode == "fund1" else (1,))
    ref_names = {0: "fundPartial1", 1: "fundPartial2"}

    harm_agg = {r: [[], []] for r in refs}
    for _time, partials in frames:
        for r in refs:
            pct, weighted = frame_harmonicity(partials, r)
            if pct is None:
                continue
            harm_agg[r][0].append(pct)
            harm_agg[r][1].append(weighted)

    details = {r: collect_partial_details(frames, r) for r in refs}

    scale_order = ",".join(ratio_label(n, d) for n, d in SCALE)
    lines = [
        f"# Analysis results v3,{src.name}",
        f"average frequency (amplitude-weighted),{avg_freq:.4f}",
        f"average amplitude,{avg_amp:.6f}",
        f"traditional harmonic ratio % (integer multiples of f0),{traditional_ratio * 100:.2f}",
        "",
        "# Harmonicity (expanded ranking scale, 1:1 = highest level)",
        f"# interval order: {scale_order}",
        "# equivalent aliases: 7:1,3.5:1=7:4; 9:1,4.5:1=9:8; 11:1,5.5:1=11:8; 13:1,6.5:1=13:8; 15:1,7.5:1=15:8",
        "# mixed score: rank score x (1 - |cents error| / 60), zero beyond +/-30 cents",
    ]
    for r in refs:
        pcts, scores = harm_agg[r]
        pct = sum(pcts) / len(pcts) if pcts else 0.0
        score = sum(scores) / len(scores) if scores else 0.0
        lines.append(f"harmonic matching % ({ref_names[r]}),{pct:.2f}")
        lines.append(f"harmonicity score amplitude-weighted ({ref_names[r]}),{score:.4f}")

    lines.append("")
    lines.append("# reference frequency per frame; median and amplitude-weighted mean")
    for r in refs:
        _acc, median_ref, amp_ref = details[r]
        median_s = f"{median_ref:.4f}" if median_ref is not None else ""
        amp_s = f"{amp_ref:.4f}" if amp_ref is not None else ""
        lines.append(f"{ref_names[r]} reference frequency median (Hz),{median_s}")
        lines.append(f"{ref_names[r]} reference frequency amplitude-weighted (Hz),{amp_s}")

    lines.append("")
    lines.append("# Per-partial detail (time-averaged, ratio vs reference)")
    lines.append(
        "reference,partial index,mean freq (Hz),mean amplitude,ratio,folded ratio,"
        "nearest interval,cents offset,(mean) score,match/total frames"
    )
    for r in refs:
        acc, median_ref, _amp_ref = details[r]
        lines += format_detail_rows(ref_names[r], median_ref, acc, part_means)

    lines.append("")
    pitch_header = "cluster mean freq (Hz),MIDI (continuous),MIDI (quarter-tone),note,partials merged,amplitude"
    for r in refs:
        pitch_header += f",{ref_names[r]} nearest ratio"
    lines.append(pitch_header)
    for cluster_freq, midi, midi_q, name, group, cluster_amp in note_rows:
        row = (
            f"{cluster_freq:.4f},{midi:.3f},{midi_q:.1f},{name},{len(group)},"
            f"{cluster_amp:.6f}"
        )
        for r in refs:
            _acc, median_ref, _amp_ref = details[r]
            label = cluster_ratio_label(group, median_ref, part_means)
            row += f",{label}"
        lines.append(row)

    out.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"frames:                {len(frames)}")
    print(f"reference mode:        {ref_mode}")
    for r in refs:
        _acc, median_ref, amp_ref = details[r]
        median_s = f"{median_ref:.4f}" if median_ref is not None else "-"
        amp_s = f"{amp_ref:.4f}" if amp_ref is not None else "-"
        print(f"{ref_names[r]} ref (median/amp-wtd): {median_s} / {amp_s} Hz")
    print(f"average frequency:     {avg_freq:.4f} Hz (amplitude-weighted)")
    print(f"average amplitude:     {avg_amp:.6f}")
    print(f"traditional harmonic ratio (integer mult of f0): {traditional_ratio * 100:.2f} %")
    for r in refs:
        pcts, scores = harm_agg[r]
        if pcts:
            print(f"harmonic matching % ({ref_names[r]}):      {sum(pcts) / len(pcts):.2f} %")
            print(f"harmonicity score ({ref_names[r]}):          {sum(scores) / len(scores):.4f}")
    print(f"distinct quarter-tone pitches: {len(note_rows)}")
    print()
    console_header = "cluster mean (Hz) | MIDI  | note  | merged | amplitude"
    for r in refs:
        console_header += f" | {ref_names[r]} ratio"
    print(console_header)
    for row in note_rows:
        cluster_freq, _midi, midi_q, name, group, cluster_amp = row
        line = f"{cluster_freq:15.4f} | {midi_q:5.1f} | {name:5s} | {len(group):6d} | {cluster_amp:.6f}"
        for r in refs:
            _acc, median_ref, _amp_ref = details[r]
            line += f" | {cluster_ratio_label(group, median_ref, part_means)}"
        print(line)
    print(f"\nwritten: {out}")


if __name__ == "__main__":
    main()
