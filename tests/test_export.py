"""Checks on the GIS exports written by the pipeline (GeoPackage + NetCDF)."""
import tomllib
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

gpd = pytest.importorskip("geopandas")
xr = pytest.importorskip("xarray")

from hvsr_zonation import export  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
CFG = tomllib.loads((ROOT / "config.toml").read_text())
GIS = ROOT / CFG["paths"]["gis_dir"]
CLEAN = pd.read_csv(ROOT / CFG["paths"]["clean_csv"])


def test_numpy_projection_matches_pyproj():
    gdf = export.stations_geodataframe(CLEAN)
    assert export.projection_check(gdf) < 0.01  # metres


def test_geopackage_layer():
    gdf = gpd.read_file(GIS / "hvsr_south_stations.gpkg", layer="hvsr_stations")
    assert len(gdf) == len(CLEAN) == 190
    assert gdf.crs.to_epsg() == 32748
    assert set(gdf["station_id"]) == set(CLEAN["station_id"])


def test_netcdf_grids():
    ds = xr.open_dataset(GIS / "hvsr_south_grids.nc", engine="scipy")
    assert ds.attrs["crs"] == "EPSG:32748"
    assert set(ds.data_vars) == {"f0", "a0", "log10_kg"}
    assert ds["f0"].dims == ("y", "x")
    # Linear interpolation can never leave the range of the measured values.
    for var, col in (("f0", CLEAN["f0_hz"]), ("a0", CLEAN["a0"]),
                     ("log10_kg", np.log10(CLEAN["kg"]))):
        values = ds[var].values
        assert np.nanmin(values) >= col.min() - 1e-9
        assert np.nanmax(values) <= col.max() + 1e-9
        assert np.isfinite(values).any()
    ds.close()
