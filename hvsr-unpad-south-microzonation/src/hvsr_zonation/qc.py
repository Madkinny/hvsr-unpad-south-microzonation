"""Quality control for tabulated HVSR results.

Every rule records what it did in a QC log, so the cleaned dataset can be
traced back, row by row, to the raw table.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

NUMERIC = ["lon", "lat", "f0_hz", "a0", "t0_s", "kg"]


@dataclass
class QCLog:
    rows: list[dict] = field(default_factory=list)

    def add(self, station: str, rule: str, action: str, detail: str) -> None:
        self.rows.append(
            {"station_id": station, "rule": rule, "action": action, "detail": detail}
        )

    def frame(self) -> pd.DataFrame:
        return pd.DataFrame(self.rows, columns=["station_id", "rule", "action", "detail"])


def _decimals(text: str) -> int:
    text = str(text).strip()
    return len(text.split(".")[1]) if "." in text else 0


def fix_coordinate_typos(df: pd.DataFrame, log: QCLog) -> pd.DataFrame:
    """Remove stray whitespace inside numbers, e.g. '-6. 925219'."""
    df = df.copy()
    for col in ("lon", "lat"):
        stripped = df[col].astype(str).str.replace(r"\s+", "", regex=True)
        changed = stripped != df[col].astype(str)
        for idx in df.index[changed]:
            log.add(df.at[idx, "station_id"], "coord_typo", "fixed",
                    f"{col}: '{df.at[idx, col]}' -> '{stripped[idx]}'")
        df[col] = stripped
    return df


def flag_low_precision(df: pd.DataFrame, log: QCLog, min_decimals: int) -> pd.DataFrame:
    df = df.copy()
    low = df["lon"].map(_decimals).lt(min_decimals) | df["lat"].map(_decimals).lt(min_decimals)
    df["low_precision_coords"] = low
    for idx in df.index[low]:
        log.add(df.at[idx, "station_id"], "coord_precision", "warned",
                f"lon={df.at[idx, 'lon']}, lat={df.at[idx, 'lat']} "
                f"(< {min_decimals} decimals)")
    return df


def relabel_duplicate_ids(df: pd.DataFrame, log: QCLog) -> pd.DataFrame:
    """Station IDs reused on different days -> suffix a, b, ... by survey date."""
    df = df.copy()
    df["original_id"] = df["station_id"]
    dup = df["station_id"].duplicated(keep=False)
    for sid, group in df[dup].groupby("station_id"):
        for k, idx in enumerate(group.sort_values("survey_date").index):
            new = f"{sid}{chr(ord('a') + k)}"
            log.add(sid, "duplicate_id", "relabelled",
                    f"{new} (surveyed {df.at[idx, 'survey_date']}, "
                    f"lon={df.at[idx, 'lon']}, lat={df.at[idx, 'lat']})")
            df.at[idx, "station_id"] = new
    return df


def coerce_numeric(df: pd.DataFrame, log: QCLog) -> pd.DataFrame:
    """Non-numeric result fields (field notes typed into value cells) -> excluded."""
    df = df.copy()
    df["excluded"] = False
    df["exclusion_reason"] = ""
    for col in NUMERIC:
        values = pd.to_numeric(df[col], errors="coerce")
        bad = values.isna() & df["excluded"].eq(False)
        if col in ("f0_hz", "a0", "lon", "lat"):
            for idx in df.index[bad]:
                note = df.at[idx, col] or "empty"
                log.add(df.at[idx, "station_id"], "missing_result", "excluded",
                        f"{col} not numeric: '{note}'")
                df.at[idx, "excluded"] = True
                df.at[idx, "exclusion_reason"] = f"missing {col}"
        df[col] = values
    return df


def check_bbox(df: pd.DataFrame, log: QCLog, bbox) -> pd.DataFrame:
    lon_min, lon_max, lat_min, lat_max = bbox
    out = ~df["lon"].between(lon_min, lon_max) | ~df["lat"].between(lat_min, lat_max)
    out &= ~df["excluded"]
    for idx in df.index[out]:
        log.add(df.at[idx, "station_id"], "outside_bbox", "excluded",
                f"lon={df.at[idx, 'lon']}, lat={df.at[idx, 'lat']}")
        df.loc[idx, ["excluded", "exclusion_reason"]] = [True, "outside study area"]
    return df


def check_derived(df: pd.DataFrame, log: QCLog, rel_tol: float) -> pd.DataFrame:
    """T0 and Kg are derived from f0 and A0; recompute and compare."""
    ok = ~df["excluded"]
    t0 = 1 / df["f0_hz"]
    kg = df["a0"] ** 2 / df["f0_hz"]
    bad = ok & (
        ~np.isclose(df["t0_s"], t0, rtol=rel_tol) | ~np.isclose(df["kg"], kg, rtol=rel_tol)
    )
    for idx in df.index[bad]:
        log.add(df.at[idx, "station_id"], "derived_mismatch", "recomputed",
                f"t0={df.at[idx, 't0_s']} vs {t0[idx]:.6g}; kg={df.at[idx, 'kg']} vs {kg[idx]:.6g}")
    df.loc[ok, "t0_s"] = t0[ok]
    df.loc[ok, "kg"] = kg[ok]
    return df


def screen_amplitude(df: pd.DataFrame, log: QCLog, max_a0: float) -> pd.DataFrame:
    high = ~df["excluded"] & (df["a0"] > max_a0)
    for idx in df.index[high]:
        log.add(df.at[idx, "station_id"], "a0_outlier", "excluded",
                f"A0={df.at[idx, 'a0']:.2f} > {max_a0} (f0={df.at[idx, 'f0_hz']:.2f} Hz, "
                f"Kg={df.at[idx, 'kg']:.1f})")
        df.loc[idx, ["excluded", "exclusion_reason"]] = [True, f"A0 > {max_a0}"]
    return df


def run_qc(raw: pd.DataFrame, cfg: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Apply all rules in order. Returns (annotated table, QC log)."""
    log = QCLog()
    df = raw.fillna("").astype({c: str for c in NUMERIC})
    df = fix_coordinate_typos(df, log)
    df = flag_low_precision(df, log, cfg["min_coord_decimals"])
    df = relabel_duplicate_ids(df, log)
    df = coerce_numeric(df, log)
    df = check_bbox(df, log, cfg["bbox"])
    df = check_derived(df, log, cfg["rel_tol"])
    df = screen_amplitude(df, log, cfg["max_a0"])
    return df, log.frame()
