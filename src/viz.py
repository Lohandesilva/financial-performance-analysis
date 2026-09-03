"""Shared chart styling.

One place for the visual language so every figure across the analysis reads as a
single document rather than a pile of defaults. Muted grid, no chart junk,
categorical hues assigned in a fixed order and never cycled.
"""

from __future__ import annotations

import matplotlib as mpl
import matplotlib.pyplot as plt

# Categorical slots, assigned in order. A ninth series folds into "Other".
SERIES = [
    "#2a78d6",  # blue
    "#eb6834",  # orange
    "#1baf7a",  # aqua
    "#eda100",  # yellow
    "#e87ba4",  # magenta
    "#008300",  # green
    "#4a3aa7",  # violet
    "#e34948",  # red
]

# Single-hue ramp for magnitude encoding (light to dark).
SEQUENTIAL = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#2a78d6", "#1c5cab", "#104281"]

STATUS = {
    "good": "#0ca30c",
    "warning": "#fab219",
    "serious": "#ec835a",
    "critical": "#d03b3b",
}

INK = "#0b0b0b"
INK_SECONDARY = "#52514e"
INK_MUTED = "#898781"
GRID = "#e1e0d9"
AXIS = "#c3c2b7"
SURFACE = "#ffffff"


def apply_house_style() -> None:
    """Set the rcParams every figure in this project inherits."""
    mpl.rcParams.update(
        {
            "figure.facecolor": SURFACE,
            "axes.facecolor": SURFACE,
            "savefig.facecolor": SURFACE,
            "savefig.dpi": 200,
            "savefig.bbox": "tight",
            "figure.dpi": 110,
            "font.family": "sans-serif",
            "font.sans-serif": ["DejaVu Sans", "Helvetica", "Arial"],
            "font.size": 9.5,
            "axes.titlesize": 11,
            "axes.titleweight": "semibold",
            "axes.titlecolor": INK,
            "axes.titlelocation": "left",
            "axes.titlepad": 12,
            "axes.labelsize": 9,
            "axes.labelcolor": INK_SECONDARY,
            "axes.edgecolor": AXIS,
            "axes.linewidth": 0.8,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.grid": True,
            "axes.axisbelow": True,
            "grid.color": GRID,
            "grid.linewidth": 0.7,
            "xtick.color": INK_MUTED,
            "ytick.color": INK_MUTED,
            "xtick.labelsize": 8.5,
            "ytick.labelsize": 8.5,
            "xtick.direction": "out",
            "ytick.direction": "out",
            "legend.frameon": False,
            "legend.fontsize": 8.5,
            "legend.labelcolor": INK_SECONDARY,
            "lines.linewidth": 2.0,
            "lines.markersize": 4.5,
            "patch.linewidth": 0,
        }
    )


def finish(ax, *, title: str, subtitle: str | None = None, source: str | None = None,
           xlabel: str | None = None, ylabel: str | None = None, ygrid_only: bool = True):
    """Apply the standard title block, grid discipline and source line."""
    if ygrid_only:
        ax.grid(axis="x", visible=False)
        ax.grid(axis="y", visible=True)
    if subtitle:
        ax.set_title(subtitle, fontsize=9, color=INK_SECONDARY, fontweight="normal",
                     loc="left", pad=8)
        ax.figure.suptitle(title, x=ax.get_position().x0, ha="left", fontsize=11.5,
                           fontweight="semibold", color=INK, y=1.02)
    else:
        ax.set_title(title)
    if xlabel is not None:
        ax.set_xlabel(xlabel)
    if ylabel is not None:
        ax.set_ylabel(ylabel)
    if source:
        ax.figure.text(0.0, -0.06, source, fontsize=7.5, color=INK_MUTED,
                       ha="left", transform=ax.transAxes)
    return ax


def save(fig, path) -> None:
    fig.savefig(path)
    plt.close(fig)
