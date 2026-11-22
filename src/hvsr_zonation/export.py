"""GIS exports: stations as a GeoPackage (GeoPandas) and gridded maps as NetCDF (xarray).

GeoPandas/pyproj also provide an independent check of the NumPy UTM projection used
in the rest of the pipeline.
"""
from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import xarray as xr
from scipy.interpolate import griddata

CRS_GEOGRAPHIC = "EPSG:4326"
CRS_UTM = "EPSG:32748"  # WGS84 / UTM zone 48S


def stations_geodataframe(clean: pd.DataFrame) -> gpd.GeoDataFrame:
    """Clean stations as points, projected to UTM 48S by pyproj."""
    gdf = gpd.GeoDataFrame(
        clean.copy(),
        geometry=gpd.points_from_xy(clean["lon"], clean["lat"]),
        crs=CRS_GEOGRAPHIC,
    )
    return gdf.to_crs(CRS_UTM)


def projection_check(gdf: gpd.GeoDataFrame) -> float:
    """Max distance (m) between the NumPy projection and pyproj's."""
    dx = gdf.geometry.x - gdf["easting"]
    dy = gdf.geometry.y - gdf["northing"]
    return float(np.hypot(dx, dy).max())


def write_geopackage(gdf: gpd.GeoDataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    gdf.to_file(path, layer="hvsr_stations", driver="GPKG")


def gridded_dataset(clean: pd.DataFrame, spacing: float) -> xr.Dataset:
    """Linear interpolation of f0, A0 and log10(Kg) on a regular UTM grid.

    Cells outside the convex hull of the stations are NaN (no extrapolation).
    """
    x = np.arange(clean["easting"].min(), clean["easting"].max() + spacing, spacing)
    y = np.arange(clean["northing"].min(), clean["northing"].max() + spacing, spacing)
    gx, gy = np.meshgrid(x, y)
    pts = clean[["easting", "northing"]].to_numpy()

    def interp(values) -> np.ndarray:
        return griddata(pts, np.asarray(values, dtype=float), (gx, gy), method="linear")

    ds = xr.Dataset(
        data_vars={
            "f0": (("y", "x"), interp(clean["f0_hz"]),
                   {"long_name": "dominant frequency", "units": "Hz"}),
            "a0": (("y", "x"), interp(clean["a0"]),
                   {"long_name": "H/V peak amplification", "units": "1"}),
            "log10_kg": (("y", "x"), interp(np.log10(clean["kg"])),
                         {"long_name": "log10 of seismic vulnerability index Kg",
                          "units": "1"}),
        },
        coords={
            "x": ("x", x, {"standard_name": "projection_x_coordinate",
                           "long_name": "easting", "units": "m"}),
            "y": ("y", y, {"standard_name": "projection_y_coordinate",
                           "long_name": "northing", "units": "m"}),
        },
        attrs={
            "title": "HVSR microzonation grids, south campus UNPAD Jatinangor",
            "crs": CRS_UTM,
            "grid_spacing_m": float(spacing),
            "interpolation": "linear (Delaunay), inside station convex hull only",
            "n_stations": int(len(clean)),
            "source": "https://doi.org/10.5281/zenodo.24447972",
        },
    )
    return ds


def write_netcdf(ds: xr.Dataset, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # NetCDF3 via SciPy: no compiled netCDF4 library needed.
    ds.to_netcdf(path, engine="scipy")
