"""One-off export: field workbook -> anonymized raw CSV.

The original workbook (Studi_Mandiri.xlsx) is NOT published because it
contains field-crew names. This script documents exactly how the public
raw CSV was derived from it, so the provenance is auditable.

Usage:
    python scripts/export_from_excel.py path/to/Studi_Mandiri.xlsx
"""
from __future__ import annotations

import re
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

MONTHS_ID = {
    "januari": 1, "februari": 2, "maret": 3, "april": 4, "mei": 5, "juni": 6,
    "juli": 7, "agustus": 8, "september": 9, "oktober": 10, "november": 11,
    "desember": 12,
}

OUT = Path(__file__).resolve().parents[1] / "data" / "raw" / "hvsr_south_raw.csv"


def parse_date(value) -> str:
    """Parse Indonesian-language or datetime survey dates to ISO format."""
    if isinstance(value, (datetime, pd.Timestamp)):
        return value.strftime("%Y-%m-%d")
    day, month, year = str(value).strip().split()
    return f"{int(year):04d}-{MONTHS_ID[month.lower()]:02d}-{int(day):02d}"


def parse_minutes(value):
    """'30 menit' / '30 mnt' / 30 -> 30; missing -> <NA>."""
    if pd.isna(value):
        return pd.NA
    match = re.search(r"\d+", str(value))
    return int(match.group()) if match else pd.NA


def main(xlsx: str) -> None:
    log = pd.read_excel(xlsx, sheet_name="data gabung")
    log = log[log["Titik"].astype(str).str.startswith("JT")].copy()
    res = pd.read_excel(xlsx, sheet_name="Data Pengolahan Selatan")
    res.columns = ["station_id", "lon", "lat", "f0_hz", "a0", "t0_s", "kg"]

    # The two sheets are row-aligned; verify instead of assuming.
    if len(log) != len(res) or not (
        log["Titik"].astype(str).values == res["station_id"].astype(str).values
    ).all():
        raise ValueError("Field log and results sheet are not row-aligned")

    out = pd.DataFrame({
        "station_id": res["station_id"].astype(str).values,
        "survey_date": log["Hari/Tanggal"].ffill().map(parse_date).values,
        "device": log["Device"].astype(str).str.strip().str.lower().values,
        "duration_min": log["Durasi"].map(parse_minutes).astype("Int64").values,
        # Kept exactly as recorded (as text) so QC decisions stay visible.
        "lon": res["lon"].astype(str).values,
        "lat": res["lat"].astype(str).values,
        "f0_hz": res["f0_hz"].astype(str).values,
        "a0": res["a0"].astype(str).values,
        "t0_s": res["t0_s"].astype(str).values,
        "kg": res["kg"].astype(str).values,
    })
    # Operator names and free-text site descriptions are intentionally dropped.
    out = out.replace({"nan": ""})
    OUT.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT, index=False)
    print(f"Wrote {len(out)} rows to {OUT}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
