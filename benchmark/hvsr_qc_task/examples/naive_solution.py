"""An intentionally flawed solution, written to illustrate typical model failures.

This is NOT real model output. It reproduces three common mistakes so the
grader's diagnostics can be demonstrated:
  1. pd.to_numeric + dropna silently drops stations with typed coordinates
  2. drop_duplicates on station_id deletes valid re-used-ID measurements
  3. UTM projected without the southern-hemisphere false northing
"""
from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))
from hvsr_zonation.projection import lonlat_to_utm  # noqa: E402

df = pd.read_csv(ROOT / "data" / "raw" / "hvsr_south_raw.csv")
for col in ["lon", "lat", "f0_hz", "a0"]:
    df[col] = pd.to_numeric(df[col], errors="coerce")
df = df.dropna(subset=["lon", "lat", "f0_hz", "a0"])            # mistake 1
df = df[df["a0"] <= 10]
df = df.drop_duplicates("station_id")                            # mistake 2
df["t0_s"] = 1 / df["f0_hz"]
df["kg"] = df["a0"] ** 2 / df["f0_hz"]
df["easting"], df["northing"], _, _ = lonlat_to_utm(df["lon"], df["lat"], zone=48, south=False)  # mistake 3

cols = ["station_id", "survey_date", "lon", "lat", "f0_hz", "a0", "t0_s", "kg", "easting", "northing"]
df[cols].to_csv(Path(__file__).with_name("flawed_submission.csv"), index=False)
print(f"wrote {len(df)} stations")
