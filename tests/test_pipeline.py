import tomllib
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from hvsr_zonation.maps import kanai_class
from hvsr_zonation.projection import lonlat_to_utm
from hvsr_zonation.qc import run_qc

ROOT = Path(__file__).resolve().parents[1]
CFG = tomllib.loads((ROOT / "config.toml").read_text())


# ---------- projection ----------

def test_central_meridian_maps_to_false_easting():
    e, n, zone, south = lonlat_to_utm([105.0], [-6.9])
    assert zone == 48 and south
    assert e[0] == pytest.approx(500_000.0, abs=1e-6)


def test_equator_scale_matches_k0():
    # 0.001 deg of longitude on the equator at the central meridian
    e, _, _, _ = lonlat_to_utm([105.0, 105.001], [0.0, 0.0], zone=48, south=False)
    expected = 0.9996 * 6378137.0 * np.radians(0.001)
    assert e[1] - e[0] == pytest.approx(expected, rel=1e-6)


def test_symmetry_about_central_meridian():
    e, n, _, _ = lonlat_to_utm([104.0, 106.0], [-6.9, -6.9], zone=48, south=True)
    assert e[0] + e[1] == pytest.approx(1_000_000.0, abs=1e-6)
    assert n[0] == pytest.approx(n[1], abs=1e-6)


# ---------- QC ----------

def _row(sid, date="2025-03-08", lon="107.7731", lat="-6.9250", f0="5.0", a0="3.0"):
    f, a = float(f0) if f0[0].isdigit() else np.nan, float(a0) if a0[0].isdigit() else np.nan
    return {"station_id": sid, "survey_date": date, "device": "sph01", "duration_min": "30",
            "lon": lon, "lat": lat, "f0_hz": f0, "a0": a0,
            "t0_s": "" if np.isnan(f) else str(1 / f),
            "kg": "" if np.isnan(f) else str(a**2 / f)}


def test_qc_rules():
    raw = pd.DataFrame([
        _row("JT1"),
        _row("JT2", lat="-6. 925100"),                 # typo -> fixed
        _row("JT3", f0="NORTH tidak terdeteksi", a0="x"),  # -> excluded
        _row("JT4", a0="52.0"),                          # A0 outlier -> excluded
        _row("JT5", date="2025-03-08"),
        _row("JT5", date="2025-03-15", lon="107.7741"),  # duplicate id -> a/b
        _row("JT6", lon="107.772"),                      # low precision -> warned
    ])
    df, log = run_qc(raw, CFG["qc"])
    kept = df[~df["excluded"]]
    assert set(kept["station_id"]) == {"JT1", "JT2", "JT5a", "JT5b", "JT6"}
    assert kept.set_index("station_id").at["JT2", "lat"] == pytest.approx(-6.9251)
    assert bool(kept.set_index("station_id").at["JT6", "low_precision_coords"])
    assert set(log["rule"]) == {"coord_typo", "missing_result", "a0_outlier",
                                "duplicate_id", "coord_precision"}


def test_kanai_boundaries():
    t0 = pd.Series([0.10, 0.15, 0.2499, 0.25, 0.40, 1.5])
    assert kanai_class(t0).tolist() == [1, 2, 2, 3, 4, 4]


# ---------- published dataset ----------

def test_clean_dataset_is_consistent():
    clean = pd.read_csv(ROOT / CFG["paths"]["clean_csv"])
    assert len(clean) == 190
    assert clean["station_id"].is_unique
    assert (clean["a0"] <= CFG["qc"]["max_a0"]).all()
    np.testing.assert_allclose(clean["t0_s"], 1 / clean["f0_hz"], rtol=1e-5)
    np.testing.assert_allclose(clean["kg"], clean["a0"] ** 2 / clean["f0_hz"], rtol=1e-5)
