"""End-to-end run: raw CSV -> QC -> clean CSV + QC report + maps.

    python -m hvsr_zonation.pipeline            (from the repo root, with src/ on PYTHONPATH)
"""
from __future__ import annotations

import tomllib
from pathlib import Path

import pandas as pd

from . import maps
from .projection import lonlat_to_utm
from .qc import run_qc

ROOT = Path(__file__).resolve().parents[2]


def project(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    ok = df["lon"].notna() & df["lat"].notna()
    e, n, zone, south = lonlat_to_utm(df.loc[ok, "lon"], df.loc[ok, "lat"])
    df.loc[ok, "easting"], df.loc[ok, "northing"] = e, n
    df.attrs["crs"] = f"EPSG:{32700 + zone if south else 32600 + zone}"
    return df


def write_report(annotated, log, clean, path: Path, crs: str) -> None:
    counts = log.groupby(["rule", "action"]).size().reset_index(name="stations")
    stats = clean[["f0_hz", "a0", "t0_s", "kg"]].describe().T[
        ["count", "min", "50%", "max"]].round(3)
    classes = maps.kanai_class(clean["t0_s"]).value_counts().sort_index()

    lines = [
        "# QC report: HVSR south UNPAD Jatinangor",
        "",
        f"- Raw stations: **{len(annotated)}**",
        f"- Excluded: **{int(annotated['excluded'].sum())}**",
        f"- Clean stations: **{len(clean)}**",
        f"- Projected CRS: {crs} (WGS84 / UTM zone 48S)",
        "",
        "## Rules applied",
        "",
        counts.to_markdown(index=False),
        "",
        "## Per-station log",
        "",
        log.to_markdown(index=False),
        "",
        "## Clean dataset summary",
        "",
        stats.to_markdown(),
        "",
        "## Kanai site classes (clean stations)",
        "",
        "| Class | Stations |",
        "|---|---|",
        *[f"| {maps.KANAI_LABELS[c - 1]} | {n} |" for c, n in classes.items()],
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    cfg = tomllib.loads((ROOT / "config.toml").read_text())
    paths = {k: ROOT / v for k, v in cfg["paths"].items()}

    raw = pd.read_csv(paths["raw_csv"], dtype=str, keep_default_na=False)
    annotated, log = run_qc(raw, cfg["qc"])
    annotated = project(annotated)
    crs = annotated.attrs["crs"]

    clean = annotated[~annotated["excluded"]].drop(
        columns=["excluded", "exclusion_reason"]).reset_index(drop=True)
    clean.insert(clean.columns.get_loc("kg") + 1, "kanai_class",
                 maps.kanai_class(clean["t0_s"]))

    for key in ("clean_csv", "qc_log_csv", "qc_report"):
        paths[key].parent.mkdir(parents=True, exist_ok=True)
    clean.to_csv(paths["clean_csv"], index=False)
    log.to_csv(paths["qc_log_csv"], index=False)
    write_report(annotated, log, clean, paths["qc_report"], crs)

    out = paths["maps_dir"]
    out.mkdir(parents=True, exist_ok=True)
    step = cfg["maps"]["grid_spacing_m"]
    maps.interpolated_map(clean, "f0_hz", "Dominant frequency f0", "Hz",
                          "Blues", out / "f0_map.png", step)
    maps.interpolated_map(clean, "a0", "Amplification factor A0", "A0",
                          "Oranges", out / "a0_map.png", step)
    maps.interpolated_map(clean, "kg", "Seismic vulnerability index Kg", "Kg",
                          "Reds", out / "kg_map.png", step, log=True)
    maps.site_class_map(clean, out / "site_class_map.png")
    maps.qc_map(annotated, out / "qc_map.png")

    print(f"{len(annotated)} raw -> {len(clean)} clean stations ({crs})")


if __name__ == "__main__":
    main()
