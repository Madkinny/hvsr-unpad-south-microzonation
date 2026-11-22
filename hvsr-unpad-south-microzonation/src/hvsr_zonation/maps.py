"""Gridding and map figures for the cleaned HVSR dataset (static PNGs)."""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.colors import BoundaryNorm, ListedColormap  # noqa: E402
from scipy.interpolate import griddata  # noqa: E402

INK = "#2b2b2b"
MUTED = "#8a8a8a"

# Site classes by dominant period T0 (Kanai, 1983), as commonly applied in
# Indonesian HVSR microzonation studies.
KANAI_BOUNDS = [0.0, 0.15, 0.25, 0.40, np.inf]
KANAI_LABELS = [
    "I: T0 < 0.15 s (hard / rock)",
    "II: 0.15-0.25 s (medium)",
    "III: 0.25-0.40 s (soft)",
    "IV: T0 > 0.40 s (very soft)",
]


def kanai_class(t0: pd.Series) -> pd.Series:
    return pd.cut(t0, KANAI_BOUNDS, labels=[1, 2, 3, 4], right=False).astype(int)


def _style(ax, title: str) -> None:
    ax.set_title(title, loc="left", fontsize=12, color=INK, pad=10)
    ax.set_xlabel("Easting (m, UTM 48S)", color=MUTED, fontsize=9)
    ax.set_ylabel("Northing (m, UTM 48S)", color=MUTED, fontsize=9)
    ax.tick_params(colors=MUTED, labelsize=8)
    ax.ticklabel_format(useOffset=False, style="plain")
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color("#d0d0d0")
    ax.set_aspect("equal")


def _grid(df: pd.DataFrame, spacing: float):
    x = np.arange(df["easting"].min(), df["easting"].max() + spacing, spacing)
    y = np.arange(df["northing"].min(), df["northing"].max() + spacing, spacing)
    return np.meshgrid(x, y)


def interpolated_map(df, column, title, unit, cmap, out: Path, spacing: float, log=False):
    """Linear interpolation inside the convex hull of stations (no extrapolation)."""
    gx, gy = _grid(df, spacing)
    values = np.log10(df[column]) if log else df[column]
    gz = griddata(df[["easting", "northing"]].to_numpy(), values, (gx, gy), method="linear")

    fig, ax = plt.subplots(figsize=(7.5, 7))
    mesh = ax.pcolormesh(gx, gy, gz, cmap=cmap, shading="auto")
    ax.scatter(df["easting"], df["northing"], s=10, c="white", edgecolors=INK,
               linewidths=0.6, zorder=3, label="HVSR station")
    cbar = fig.colorbar(mesh, ax=ax, shrink=0.75, pad=0.02)
    cbar.set_label(f"log10({unit})" if log else unit, color=INK, fontsize=9)
    cbar.outline.set_visible(False)
    cbar.ax.tick_params(colors=MUTED, labelsize=8)
    _style(ax, title)
    ax.legend(loc="lower left", frameon=False, fontsize=8)
    fig.text(0.01, 0.01, "Linear interpolation within station hull; "
             f"{len(df)} stations after QC.", color=MUTED, fontsize=7)
    fig.tight_layout()
    fig.savefig(out, dpi=200)
    plt.close(fig)


def site_class_map(df, out: Path) -> None:
    classes = kanai_class(df["t0_s"])
    colors = ["#c6dbef", "#6baed6", "#2171b5", "#08306b"]  # one hue, light -> dark
    cmap = ListedColormap(colors)
    norm = BoundaryNorm([0.5, 1.5, 2.5, 3.5, 4.5], cmap.N)

    fig, ax = plt.subplots(figsize=(7.5, 7))
    ax.scatter(df["easting"], df["northing"], c=classes, cmap=cmap, norm=norm,
               s=42, edgecolors="white", linewidths=1.0, zorder=3)
    counts = classes.value_counts().reindex([1, 2, 3, 4], fill_value=0)
    handles = [
        plt.Line2D([], [], marker="o", ls="", markersize=8, markerfacecolor=c,
                   markeredgecolor="white", label=f"{lab}  (n={counts[i + 1]})")
        for i, (c, lab) in enumerate(zip(colors, KANAI_LABELS))
    ]
    ax.legend(handles=handles, loc="upper center", bbox_to_anchor=(0.5, -0.1),
              ncol=2, frameon=False, fontsize=8, title="Kanai site class",
              title_fontsize=8)
    _style(ax, "Site classification from dominant period T0")
    fig.tight_layout()
    fig.savefig(out, dpi=200)
    plt.close(fig)


def qc_map(annotated: pd.DataFrame, out: Path) -> None:
    """Where QC removed or warned about stations."""
    kept = annotated[~annotated["excluded"]]
    fig, ax = plt.subplots(figsize=(7.5, 7))
    ax.scatter(kept["easting"], kept["northing"], s=14, c="#9ecae1",
               edgecolors="none", label=f"Kept (n={len(kept)})")
    warn = kept[kept["low_precision_coords"]]
    ax.scatter(warn["easting"], warn["northing"], s=40, facecolors="none",
               edgecolors="#08519c", linewidths=1.2,
               label=f"Kept, low-precision coordinates (n={len(warn)})")
    a0 = annotated[annotated["exclusion_reason"].str.startswith("A0")]
    ax.scatter(a0["easting"], a0["northing"], s=46, marker="X", c="#d94801",
               edgecolors="white", linewidths=0.6,
               label=f"Excluded: A0 outlier (n={len(a0)})")
    miss = annotated[annotated["exclusion_reason"].str.startswith("missing")
                     & annotated["easting"].notna()]
    ax.scatter(miss["easting"], miss["northing"], s=40, marker="s", c=INK,
               label=f"Excluded: no H/V result (n={len(miss)})")
    for _, r in pd.concat([a0, miss]).iterrows():
        ax.annotate(r["station_id"], (r["easting"], r["northing"]), xytext=(4, 4),
                    textcoords="offset points", fontsize=7, color=INK)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.1), ncol=2,
              frameon=False, fontsize=8)
    _style(ax, "Quality-control outcome per station")
    fig.tight_layout()
    fig.savefig(out, dpi=200)
    plt.close(fig)
