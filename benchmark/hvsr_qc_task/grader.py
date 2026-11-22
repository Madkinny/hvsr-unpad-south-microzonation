"""Automated grader for the HVSR QC & projection task (criteria A1–A7 in RUBRIC.md).

Usage:
    python benchmark/hvsr_qc_task/grader.py path/to/submission.csv [--markdown out.md]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
REFERENCE = ROOT / "data" / "processed" / "hvsr_south_clean.csv"
COLUMNS = ["station_id", "survey_date", "lon", "lat", "f0_hz", "a0", "t0_s", "kg",
           "easting", "northing"]
DUP_DATES = {f"JT{n}{s}": d for n in (224, 225, 226, 227)
             for s, d in (("a", "2025-03-12"), ("b", "2025-03-15"))}
REL_TOL = 1e-6
PROJ_TOL_M = 1.0


def diagnose_projection(sub: pd.DataFrame, ref: pd.DataFrame) -> str:
    """Guess the most likely cause of a projection failure."""
    de = (sub["easting"] - ref["easting"]).median()
    dn = (sub["northing"] - ref["northing"]).median()
    if sub["easting"].abs().max() < 200 and sub["northing"].abs().max() < 200:
        return "coordinates look like degrees: easting/northing were never projected"
    if abs(dn + 10_000_000) < 1_000:
        return "northing is ~10,000 km too small: southern-hemisphere false northing omitted (zone 48N used instead of 48S?)"
    if abs(de) > 100_000:
        return f"easting offset {de/1000:,.0f} km: wrong UTM zone (study area is in zone 48, 102–108°E)"
    if sub["easting"].between(9_000_000, 10_000_000).all():
        return "easting holds northing-sized values: lon/lat axes swapped"
    return f"median offset dE={de:.1f} m, dN={dn:.1f} m: check datum or projection formula"


def grade(sub_path: Path) -> tuple[float, list[tuple[str, int, float, str]]]:
    ref = pd.read_csv(REFERENCE)
    sub = pd.read_csv(sub_path, dtype={"station_id": str})
    results: list[tuple[str, int, float, str]] = []

    missing_cols = [c for c in COLUMNS if c not in sub.columns]
    results.append(("A1 Required columns", 5, 0.0 if missing_cols else 1.0,
                    f"missing: {missing_cols}" if missing_cols else "ok"))
    if missing_cols:
        return 0.0, results

    ref_ids, sub_ids = set(ref["station_id"]), set(sub["station_id"])
    extra, missing = sorted(sub_ids - ref_ids), sorted(ref_ids - sub_ids)
    ok_set = not extra and not missing and sub["station_id"].is_unique
    detail = "ok" if ok_set else f"extra={extra[:10]} missing={missing[:10]}"
    if not sub["station_id"].is_unique:
        detail += " (duplicate station_id rows)"
    results.append(("A2 Correct station set", 15, float(ok_set), detail))

    s = sub.drop_duplicates("station_id").set_index("station_id")
    r = ref.set_index("station_id")
    dup_ok = [k for k, d in DUP_DATES.items() if k in s.index and str(s.at[k, "survey_date"]) == d]
    results.append(("A3 Duplicate IDs resolved", 10, len(dup_ok) / len(DUP_DATES),
                    f"{len(dup_ok)}/{len(DUP_DATES)} relabelled correctly"))

    typo_ok = [k for k in ("JT251", "JT252")
               if k in s.index and np.isclose(float(s.at[k, "lat"]), r.at[k, "lat"], atol=1e-6)]
    results.append(("A4 Coordinate typos recovered", 5, len(typo_ok) / 2,
                    f"{len(typo_ok)}/2 recovered"))

    common = sorted(set(s.index) & set(r.index))
    s, r = s.loc[common], r.loc[common]

    vals = np.isclose(s["f0_hz"], r["f0_hz"], rtol=REL_TOL) & np.isclose(s["a0"], r["a0"], rtol=REL_TOL)
    results.append(("A5 Values preserved", 10, vals.mean(),
                    f"{vals.sum()}/{len(common)} stations match"))

    der = (np.isclose(s["t0_s"], 1 / s["f0_hz"], rtol=REL_TOL)
           & np.isclose(s["kg"], s["a0"] ** 2 / s["f0_hz"], rtol=REL_TOL))
    results.append(("A6 Derived values correct", 10, der.mean(),
                    f"{der.sum()}/{len(common)} stations correct"))

    dist = np.hypot(s["easting"] - r["easting"], s["northing"] - r["northing"])
    proj = dist <= PROJ_TOL_M
    detail = (f"{proj.sum()}/{len(common)} within {PROJ_TOL_M:g} m"
              + ("" if proj.all() else f"; diagnosis: {diagnose_projection(s, r)}"))
    results.append(("A7 Projection correct", 25, proj.mean(), detail))

    score = sum(points * frac for _, points, frac, _ in results)
    return score, results


def to_markdown(path: Path, score: float, results) -> str:
    lines = [f"# Automated grade: `{path.name}`", "",
             f"**Score: {score:.1f} / 80** (qualitative criteria Q1–Q3 are scored by a reviewer)", "",
             "| Criterion | Points | Earned | Detail |", "|---|---|---|---|"]
    lines += [f"| {name} | {pts} | {pts * frac:.1f} | {detail} |" for name, pts, frac, detail in results]
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("submission", type=Path)
    parser.add_argument("--markdown", type=Path)
    args = parser.parse_args()
    score, results = grade(args.submission)
    report = to_markdown(args.submission, score, results)
    print(report)
    if args.markdown:
        args.markdown.write_text(report, encoding="utf-8")
    sys.exit(0 if score == 80 else 1)


if __name__ == "__main__":
    main()
