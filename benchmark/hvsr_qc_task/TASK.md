# Task: Quality-control and project a real HVSR survey table

*An AI-training / evaluation task built from this repository's field data.
The model receives everything in the "Prompt" section; everything else is for graders.*

---

## Prompt (given to the model)

You are given `hvsr_south_raw.csv`: 202 single-station HVSR (microtremor H/V) results from a
seismic microzonation survey in Jatinangor, West Java, Indonesia. Columns:

| column | meaning |
|---|---|
| `station_id` | station label |
| `survey_date` | ISO date of measurement |
| `device`, `duration_min` | instrument and recording length |
| `lon`, `lat` | WGS84 decimal degrees, **stored as text exactly as typed in the field** |
| `f0_hz`, `a0` | dominant frequency (Hz) and H/V peak amplitude |
| `t0_s`, `kg` | derived: dominant period T0 = 1/f0, vulnerability index Kg = A0²/f0 |

Write a Python script that produces `clean.csv` following these rules:

1. Fix obvious typing errors in coordinates. Do not drop a station only because of formatting.
2. Exclude stations whose `f0_hz` or `a0` is not a number.
3. Exclude stations with `a0 > 10` as unreliable H/V peaks.
4. Some `station_id`s were reused for **different** locations on different days. Keep every
   such measurement and make the IDs unique by appending `a`, `b`, … in order of `survey_date`
   (for example `JT224a`, `JT224b`).
5. Recompute `t0_s` and `kg` from `f0_hz` and `a0`.
6. Add `easting` and `northing` in **WGS84 / UTM zone 48S (EPSG:32748)**, in metres.
7. Output columns: `station_id, survey_date, lon, lat, f0_hz, a0, t0_s, kg, easting, northing`.

Finally, state how many stations remain and list every excluded station with its reason.

---

## Why this task is hard (grader notes)

The task is realistic because each rule maps to a defect that is genuinely present in the data:

| Trap | What a weak model does |
|---|---|
| Latitudes typed as `-6. 925219` | `pd.to_numeric` turns them into NaN, and the station is silently dropped |
| Field notes typed into value cells (`"NORTH tidak terdeteksi"`) | Crashes on casting, or keeps the row with NaN |
| Duplicate IDs at different locations | `drop_duplicates()` deletes 4 valid measurements |
| UTM south hemisphere | Forgets the 10,000,000 m false northing, giving negative northings |
| Zone choice | Uses zone 49 (or zone 48 **N**) because the longitude is "near 108°E" |
| Axis order | Passes `(lat, lon)` to a projector expecting `(lon, lat)` |
| Ordering of rules | Screens A0 before handling non-numeric values and crashes on string comparison |

## Reference solution

`src/hvsr_zonation/` in this repository (`PYTHONPATH=src python -m hvsr_zonation.pipeline`).
The reference output is `data/processed/hvsr_south_clean.csv`: **190 stations**, with
12 excluded (4 non-numeric results, 8 with A0 > 10).

## Grading

- Automated: `python benchmark/hvsr_qc_task/grader.py <submission.csv>` (see `RUBRIC.md`)
- Human review: the written explanation, scored with the qualitative criteria in `RUBRIC.md`
- Worked example: `examples/flawed_submission.csv` and its grade in `examples/flawed_grade.md`
