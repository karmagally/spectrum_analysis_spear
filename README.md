[analyze_spectrum_README.md](https://github.com/user-attachments/files/32740733/analyze_spectrum_README.md)
# analyze\_spectrum — User Guide

Extracts summary metrics from partial-tracking spectral analysis files
(`par-text-frame-format`, as exported by tools such as SPEAR):

* **Average frequency** (amplitude-weighted)
* **Average amplitude**
* **Harmonic ratio** (% of partials within ±30 cents of integer multiples of f₀)
* **Frequency → note conversion** (quarter-tone clustering)

\---

## Requirements

* Windows with **Python 3** launcher (`py`). No third-party libraries needed.

Check availability:

```powershell
py --version
```

\---

## Quick start

Open PowerShell (or CMD) and run:

```powershell
py analyze\_spectrum.py "C:\\path\\to\\your\_analysis.txt"
```

The result CSV is written **next to the input file** as
`<input>\_analysis\_results.csv`, and a summary is printed to the console.

To choose the output path explicitly:

```powershell
py analyze\_spectrum.py "input.txt" "my\_results.csv"
```

### Running from any folder

Either `cd` into the folder that contains the script first:

```powershell
cd "your_directory\\frequency\_Analisys"
py analyze\_spectrum.py "18-14\_Jean-Claude-Risset\_...txt"
```

or give the full path to the script:

```powershell
py "...\\frequency\_Analisys\\analyze\_spectrum.py" "D:\\data\\file.txt" "D:\\data\\out.csv"
```

### Analyzing a whole folder (batch)

```powershell
Get-ChildItem "\*.txt" | ForEach-Object { py analyze\_spectrum.py $\_.FullName }
```

Each `.txt` gets its own `\_analysis\_results.csv`.

\---

## Importing data for analysis

### 1\. What input format is accepted?

Plain-text `.txt` files in **`par-text-frame-format`**:

```
par-text-frame-format
point-type index frequency amplitude
partials-count 57
frame-count 5875
frame-data
0.274875 1 0 46.626141 0.000121
0.354875 2 0 14.543242 0.005164 1 998.038147 0.000141
...
```

Layout of each frame line:

|field|meaning|
|-|-|
|`time`|frame time in seconds|
|`count`|number of partials in this frame|
|then `count` triplets|`index` `frequency(Hz)` `amplitude`|

The script skips everything before the line `frame-data`, so extra header lines
are harmless.

### 2\. Exporting from common tools

|Source|How to get a compatible .txt|
|-|-|
|**SPEAR**|File → Export → *partials text file* (ensure frequency/amplitude columns are present)|
|**IaaC / analysis spreadsheets**|Save/Export as tab- or space-separated text with the header above|
|**Python / MATLAB**|Write rows: `time count idx1 f1 a1 idx2 f2 a2 ...` and prepend the 5 header lines|
|**Existing table in this folder**|Any `\*\_0-0\_50.txt` style file already matches — pass it directly|

**Rule of thumb:** if your file contains a line `frame-data` followed by rows
starting with a timestamp and an integer count, it will parse.

### 3\. Files with different names/encoding

The script reads UTF-8 (and ASCII). Rename or keep any extension; the path is
taken verbatim:

```powershell
py analyze\_spectrum.py "my spectral data.txt"
```

\---

## Output description

Console + CSV contain:

```
frames,5875
average frequency (amplitude-weighted),741.4153
average amplitude,0.001610
harmonic ratio (%),37.04

cluster mean freq (Hz),MIDI (continuous),MIDI (quarter-tone),note,partials merged
362.6020,65.651,65.5,F4+,4
...
```

|Column|Meaning|
|-|-|
|cluster mean freq|mean of time-averaged partial frequencies merged within ±50 cents|
|MIDI (continuous)|exact MIDI value of the cluster mean|
|MIDI (quarter-tone)|rounded to nearest 0.5 semitone|
|note|note name; suffix `+` = quarter-tone sharp (e.g. `F4+`)|
|partials merged|how many partial indices were combined into this pitch|

Open the CSV in Excel/LibreOffice: **Data → From Text** (delimiter: comma),
or just double-click if your CSV association is set.

\---

## Method / parameters

Constants at the top of `analyze\_spectrum.py` — edit and re-run to tune:

|Constant|Default|Effect|
|-|-|-|
|`AMP\_FLOOR`|`0.0001`|partials below this amplitude are ignored when choosing f₀ and counting harmonics|
|`HARM\_TOL\_CENTS`|`30`|a partial is "harmonic" if within ±30 cents of n·f₀|
|`QUARTER\_TONE\_CENTS`|`50`|clustering radius for note conversion (quarter tone = 50 cents)|

Definitions:

* **Average frequency** = Σ(f·amp) / Σ(amp) over every partial of every frame.
* **Average amplitude** = plain mean of all partial amplitudes.
* **Harmonic ratio** = per frame, count partials near integer multiples of the
lowest partial above the amplitude floor; average of those percentages.
* **Note conversion** = each partial index is averaged over time first, then
values within ±50 cents are merged (mean taken), then mapped to the
quarter-tone grid (A4 = 440 Hz, MIDI 69).

\---

## Troubleshooting

|Symptom|Fix|
|-|-|
|`Python was not found`|Install Python 3 from python.org, or use `python` instead of `py`|
|`No frame data found`|File lacks a `frame-data` line, or is empty — check format above|
|Wrong-looking notes near 0 Hz|Very low opening frames (e.g. pitch sweeps) produce sub-audio clusters; ignore rows below \~20 Hz|
|garbled characters|re-save the input as UTF-8|

\---

## Command reference (cheat sheet)

```powershell
# basic
py analyze\_spectrum.py "input.txt"

# explicit output
py analyze\_spectrum.py "input.txt" "results.csv"

# batch folder
Get-ChildItem "\*.txt" | ForEach-Object { py analyze\_spectrum.py $\_.FullName }
```

\---

## analyze\_spectrum\_v2.py (harmonicity version)

`analyze\_spectrum\_v2.py` does everything the original does, plus:

* **Harmonicity** based on a just-intonation scale where **2:1 (octave) is the
highest level of harmonicity**, down to **16:15 (minor second) = lowest**.
* **Amplitude column for every partial** in the note/cluster table.
* **Per-partial detail table** (mean freq, mean amplitude, ratio, matched
interval, score).
* **Choice of fundamental reference** for the harmonicity ratios.

```powershell
# default: both references computed
py analyze\_spectrum\_v2.py "input.txt"

# explicit output + reference choice
py analyze\_spectrum\_v2.py "input.txt" "results.csv" --ref fund1

# batch folder
Get-ChildItem "\*.txt" | ForEach-Object { py analyze\_spectrum\_v2.py $\_.FullName }
```

### `--ref` reference modes

|Mode|Ratios computed|
|-|-|
|`fund1`|fundPartial1 : all other partials (lowest frequency above amp floor)|
|`fund2`|fundPartial2 : all other partials (2nd-lowest frequency above amp floor)|
|`both`|both of the above (default)|

### The harmonicity scale

Intervals are ordered from **highest** annotation:

```
2:1, 3:2, 4:3, 5:4, 6:5, 7:6, 8:7, 9:8, 10:9,
11:10, 12:11, 13:12, 14:13, 15:14, 16:15
```

* Each partial's frequency ratio `f / f\_ref` is **folded into the octave**
(`1 ≤ r < 2`), so e.g. 3:1 → 3:2, 5:2 → 5:4, 4:1 → 2:1.
* The folded ratio is matched to the nearest interval in the scale; within
±30 cents it is a *harmonic match*.
* **Score:** 2:1 = 15 … 16:15 = 1 (highest to lowest harmonicity);
unmatched partials score 0.

### New metrics in output

|Metric|Meaning|
|-|-|
|`harmonic matching % (ref)`|% of partials (per frame, averaged) that match any scale interval|
|`harmonicity score (ref)`|amplitude-weighted mean of the interval scores (2:1 = 15 … 16:15 = 1, unmatched = 0)|

### New columns

* **Per-partial detail:** `reference, partial index, mean freq (Hz), mean amplitude, ratio, folded ratio, matched interval, (mean) score, match/total frames`
* **Note/cluster table** now ends with an extra **`amplitude`** column
(time-averaged amplitude of the merged partials).

Constants (`AMP\_FLOOR`, `HARM\_TOL\_CENTS`, `QUARTER\_TONE\_CENTS`, `SCALE`) are at
the top of the script — edit and re-run to tune.

---

## analyze\_spectrum\_v3.py (expanded ratio analysis)

`analyze_spectrum_v3.py` keeps the v2 metrics and adds a complete ratio for every
partial, an expanded harmonic ranking, and mixed rank/purity scoring.

```powershell
# default: both references, CSV written next to the input
py analyze_spectrum_v3.py "input.txt"

# explicit output and reference
py analyze_spectrum_v3.py "input.txt" "results.csv" --ref fund1

# batch folder
Get-ChildItem "*.txt" | ForEach-Object { py analyze_spectrum_v3.py $_.FullName }
```

The default output name is `<input>_analysis_v3_results.csv`.

### Ranking scale

Intervals are ranked from highest to lowest harmonicity:

```
1:1, 2:1, 3:2, 4:3, 5:4, 7:4, 6:5, 8:5, 5:3, 9:8, 11:8, 13:8,
7:6, 8:7, 10:9, 11:10, 15:8, 12:11, 13:12, 14:13, 15:14, 16:15
```

* `1:1` is the highest rank (22 points); `2:1` is next.
* `13:8` is ranked directly between `11:8` and `7:6`.
* The exact scores are exposed as `SCALE` at the top of the script.

### Octave-equivalent aliases

The octave representation closest to the measured ratio is exported, so these are
reported separately while sharing the same scale rank:

|Ratio|Equivalent folded ratio|
|-|-|
|`7:1`, `3.5:1`|`7:4`|
|`9:1`, `4.5:1`|`9:8`|
|`11:1`, `5.5:1`|`11:8`|
|`13:1`, `6.5:1`|`13:8`|
|`15:1`, `7.5:1`|`15:8`|

`1:1` and `2:1` are also treated as octave equivalents when they are the closest
representation of the measured ratio.

### Mixed score and matching

* An exact ratio receives its full rank score.
* Within the ±30-cent tolerance, the score is reduced with tuning error:
  `score = rank × (1 - |cents| / 60)`.
* At ±30 cents it is half the rank score; beyond ±30 cents it is zero.
* The **nearest ratio label is always exported**, even outside the tolerance.
  The `match/total frames` column shows how many frames were within ±30 cents.

### Output columns

**Per-partial detail**

```
reference, partial index, mean freq (Hz), mean amplitude, ratio, folded ratio,
nearest interval, cents offset, (mean) score, match/total frames
```

The raw and folded ratio columns are numeric for every valid partial; they are not
left as `-` when a partial acts as the reference.

**Final pitch table**

The pitch table adds one column per selected reference:

```
..., fundPartial1 nearest ratio, fundPartial2 nearest ratio
```

If a pitch cluster merges partials with different labels, the distinct labels are
listed with ` | ` between them.

### CSV changes compared with v2

* `frames` and `reference mode` are no longer written to the CSV.
* They are still printed in the console summary.
* The final pitch table contains the per-reference ratio columns.

---

## License

Released under the [MIT License](LICENSE).

Copyright (c) 2026 Simone De Benedetto. Permission is granted, free of charge, to any
person obtaining a copy of this software and associated documentation files
(the "Software"), to use, copy, modify, merge, publish, distribute,
sublicense, and/or sell copies of the Software, subject to the conditions in
`LICENSE`.

