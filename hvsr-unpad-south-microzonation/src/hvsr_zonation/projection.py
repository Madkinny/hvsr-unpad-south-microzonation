"""WGS84 geographic -> UTM projection (Krüger series, Karney 2011).

Implemented with NumPy so the pipeline has no compiled GIS dependency.
Accurate to well below 1 mm inside a UTM zone. The study area lies in
UTM zone 48S (EPSG:32748; central meridian 105°E).
"""
from __future__ import annotations

import numpy as np

A = 6378137.0                # WGS84 semi-major axis [m]
F = 1 / 298.257223563        # WGS84 flattening
K0 = 0.9996                  # UTM scale factor on the central meridian
FALSE_EASTING = 500_000.0
FALSE_NORTHING_SOUTH = 10_000_000.0


def utm_zone(lon_deg: float) -> int:
    return int((lon_deg + 180) // 6) + 1


def lonlat_to_utm(lon, lat, zone: int | None = None, south: bool | None = None):
    """Project WGS84 lon/lat (degrees) to UTM easting/northing (metres).

    Returns (easting, northing, zone, south).
    """
    lon = np.asarray(lon, dtype=float)
    lat = np.asarray(lat, dtype=float)
    if zone is None:
        zone = utm_zone(float(np.nanmean(lon)))
    if south is None:
        south = bool(np.nanmean(lat) < 0)

    n = F / (2 - F)
    a_hat = A / (1 + n) * (1 + n**2 / 4 + n**4 / 64)
    alpha = (
        n / 2 - 2 * n**2 / 3 + 5 * n**3 / 16,
        13 * n**2 / 48 - 3 * n**3 / 5,
        61 * n**3 / 240,
    )

    lon0 = np.radians(-183 + 6 * zone)
    phi = np.radians(lat)
    dlam = np.radians(lon) - lon0

    e = 2 * np.sqrt(n) / (1 + n)
    t = np.sinh(np.arctanh(np.sin(phi)) - e * np.arctanh(e * np.sin(phi)))
    xi_p = np.arctan2(t, np.cos(dlam))
    eta_p = np.arctanh(np.sin(dlam) / np.sqrt(1 + t**2))

    xi, eta = xi_p.copy(), eta_p.copy()
    for j, a_j in enumerate(alpha, start=1):
        xi += a_j * np.sin(2 * j * xi_p) * np.cosh(2 * j * eta_p)
        eta += a_j * np.cos(2 * j * xi_p) * np.sinh(2 * j * eta_p)

    easting = FALSE_EASTING + K0 * a_hat * eta
    northing = K0 * a_hat * xi + (FALSE_NORTHING_SOUTH if south else 0.0)
    return easting, northing, zone, south
