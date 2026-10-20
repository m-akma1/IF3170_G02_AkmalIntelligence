from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

SERIES = [
    "#3c0005",  # maroon
    "#8f0f0d",
    "#c81e14",  # red
    "#f27532",
    "#ffdc50",  # yellow
    "#ffb020",
    "#ff9600",  # orange
    "#190500",  # near-black
]
TEXT, MUTED, GRID, SURFACE = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"

plt.rcParams.update({
    "figure.facecolor": SURFACE,
    "axes.facecolor": SURFACE,
    "axes.edgecolor": MUTED,
    "axes.labelcolor": TEXT,
    "axes.titlesize": 11,
    "axes.labelsize": 10,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.grid": True,
    "grid.color": GRID,
    "grid.linewidth": 0.6,
    "xtick.color": MUTED,
    "ytick.color": MUTED,
    "legend.frameon": False,
    "lines.linewidth": 1.5,
    "savefig.dpi": 150,
    "savefig.bbox": "tight",
})


def _x_label(algorithm: str) -> str:
    return "Generasi" if algorithm == "ga" else "Iterasi"


def _finish(ax, fig, path: Path, title: str, algorithm: str, legend: bool, outside: bool = False):
    ax.set_title(title, loc="left", color=TEXT)
    ax.set_xlabel(_x_label(algorithm))
    ax.set_ylabel("Nilai objective function")
    if legend and outside:
        ax.legend(loc="upper left", bbox_to_anchor=(1.01, 1.0))
    elif legend:
        ax.legend(loc="best")
    fig.savefig(path)
    plt.close(fig)


def _spans(flags: list[bool]):
    """Rentang indeks berurutan yang bernilai True."""
    start = None
    for i, flag in enumerate(flags + [False]):
        if flag and start is None:
            start = i
        elif not flag and start is not None:
            yield start, i - 1
            start = None


def plot_objective(history: dict[str, list], algorithm: str, path: Path, title: str):
    """Objective terhadap iterasi untuk satu run (bentuk plot menyesuaikan algoritma)."""
    fig, ax = plt.subplots(figsize=(7, 3.8))
    x = history["iteration"]
    legend = False

    if algorithm == "ga":
        ax.plot(x, history["max"], color=SERIES[0], label="Maksimum populasi")
        ax.plot(x, history["mean"], color=SERIES[1], label="Rata-rata populasi")
        legend = True
    elif "best" in history:  # random restart, SA
        ax.plot(x, history["value"], color=SERIES[0], label="Saat ini", zorder=3)
        ax.plot(x, history["best"], color=SERIES[1], label="Terbaik", zorder=2)
        legend = True
        if "restart" in history:
            restart = history["restart"]
            for i in range(1, len(restart)):
                if restart[i] != restart[i - 1]:
                    ax.axvline(x[i], color=MUTED, linewidth=0.8, linestyle="--", alpha=0.6)
    else:
        ax.plot(x, history["value"], color=SERIES[0])
        if "sideways" in history:
            for a, b in _spans([s > 0 for s in history["sideways"]]):
                ax.axvspan(x[max(a - 1, 0)], x[b], color=GRID, alpha=0.9, linewidth=0, zorder=0)
            ax.plot([], [], color=SERIES[0], label="Objective")
            ax.fill_between([], [], color=GRID, label="Sideways steps")
            legend = True

    _finish(ax, fig, path, title, algorithm, legend)


def plot_accept_prob(history: dict[str, list], path: Path, title: str):
    points = [(i, p) for i, p in zip(history["iteration"], history["accept_prob"]) if p is not None]
    fig, ax = plt.subplots(figsize=(7, 3.8))
    if points:
        xs, ys = zip(*points)
        ax.scatter(xs, ys, s=4, color=SERIES[0], alpha=0.35, linewidths=0)
    ax.set_ylim(-0.02, 1.02)
    ax.set_title(title, loc="left", color=TEXT)
    ax.set_xlabel("Iterasi")
    ax.set_ylabel(r"$e^{\Delta E / T}$")
    fig.savefig(path)
    plt.close(fig)


def plot_overlay(histories: list[dict[str, list]], algorithm: str, path: Path, title: str):
    if len(histories) > len(SERIES):
        raise ValueError(f"Overlay maksimal {len(SERIES)} run")
    fig, ax = plt.subplots(figsize=(7, 3.8))
    for k, history in enumerate(histories):
        color = SERIES[k]
        if algorithm == "ga":
            ax.plot(history["iteration"], history["max"], color=color, label=f"Run {k + 1} maks")
            ax.plot(history["iteration"], history["mean"], color=color, linestyle="--", linewidth=1.0,
                    label=f"Run {k + 1} rata-rata")
        else:
            ax.plot(history["iteration"], history["value"], color=color, label=f"Run {k + 1}")
    _finish(ax, fig, path, title, algorithm, legend=len(histories) > 1, outside=True)
