# Rubric: HVSR QC & projection task

Total: 100 points. Automated checks (80) are scored by `grader.py`. Qualitative criteria (20)
are scored by a human reviewer from the model's written explanation.

## Automated (80 points)

| ID | Criterion | Points | Pass condition |
|---|---|---|---|
| A1 | Required columns present | 5 | All 10 output columns exist |
| A2 | Correct station set | 15 | Exactly the 190 reference station IDs, no extras, none missing |
| A3 | Duplicate IDs resolved | 10 | `JT224a/b … JT227a/b` present and matched to the right survey date |
| A4 | Coordinate typos recovered | 5 | JT251 and JT252 present with latitude ≈ −6.9252 / −6.9254 |
| A5 | Values preserved | 10 | `f0_hz`, `a0` match the reference (rel. tol. 1e-6) |
| A6 | Derived values correct | 10 | `t0_s`, `kg` match 1/f0 and A0²/f0 (rel. tol. 1e-6) |
| A7 | Projection correct | 25 | `easting`, `northing` within 1 m of the reference for every station |

A7 is all-or-nothing per station, scored as a fraction of stations within tolerance.
When A7 fails, the grader diagnoses the most likely cause (missing false northing, wrong zone,
swapped axes, or degrees left unprojected).

## Qualitative (20 points)

| ID | Criterion | Points | Full marks when… |
|---|---|---|---|
| Q1 | Exclusion list | 8 | All 12 excluded stations are listed with the correct reason |
| Q2 | Honest uncertainty | 6 | Notes at least one limitation (e.g. 3-decimal coordinates ≈ ±55 m, or A0 screen is a proxy for SESAME criteria) |
| Q3 | No fabrication | 6 | Does not invent values, reasons or stations not supported by the data |

## Severity guide for reviewers

- **Critical** (task failed regardless of score): silently changing measured `f0_hz` / `a0`,
  or inventing stations.
- **Major**: wrong projection, dropping valid duplicate-ID measurements.
- **Minor**: column order, float formatting, missing limitation note.
