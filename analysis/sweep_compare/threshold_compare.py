"""Aggregate distance-threshold sweep outputs into comparison tables and plots."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import pandas as pd

from analysis.analyses.ball_zones import BALL_ZONE_LABELS, BALL_ZONE_ORDER
from analysis.sweep_compare.sweep_common import (
    PITCH_THIRD_LABELS,
    PITCH_THIRD_ORDER,
    collect_summary_row,
    run_is_complete,
)

PLOT_STYLE = {
    "figsize": (8.0, 4.5),
    "dpi": 150,
    "marker": "o",
    "linewidth": 2.0,
    "markersize": 6,
    "color": "#3d6b8c",
}


def _threshold_slug(k: int) -> str:
    threshold_str = f"{float(k):g}".replace(".", "p")
    return f"distance_threshold__t{threshold_str}m"

# validate the runs for the sweep
def _validate_runs(k_values: list[int], out_dir: Path) -> tuple[list[int], list[int]]:
    present: list[int] = []
    missing: list[int] = []
    for k in k_values:
        slug = _threshold_slug(k)
        if run_is_complete(slug, out_dir):
            present.append(k)
        else:
            missing.append(k)
    return present, missing


def _style_ax(ax: plt.Axes) -> None:
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(True, alpha=0.25, linewidth=0.6)


def _line_plot( # plot a single line graph
    df: pd.DataFrame,
    *,
    y_col: str,
    title: str,
    ylabel: str,
    path: Path,
    ylim: tuple[float, float] | None = None,
) -> None:
    fig, ax = plt.subplots(figsize=PLOT_STYLE["figsize"])
    xs = df["k"].to_numpy()
    ys = df[y_col].to_numpy(dtype=float)
    ax.plot(
        xs,
        ys,
        color=PLOT_STYLE["color"],
        marker=PLOT_STYLE["marker"],
        linewidth=PLOT_STYLE["linewidth"],
        markersize=PLOT_STYLE["markersize"],
    )
    ax.set_xlabel("Distance threshold k (m)")
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    ax.set_xticks(xs)
    if ylim is not None:
        ax.set_ylim(*ylim)
    _style_ax(ax)
    fig.tight_layout()
    fig.savefig(path, dpi=PLOT_STYLE["dpi"])
    plt.close(fig)


def _multi_zone_line_plot( # plot a line graph for multiple zones
    df: pd.DataFrame,
    *,
    value_cols: list[str],
    labels: list[str],
    title: str,
    ylabel: str,
    path: Path,
    colors: list[str] | None = None,
) -> None:
    fig, ax = plt.subplots(figsize=PLOT_STYLE["figsize"])
    xs = df["k"].to_numpy()
    palette = colors or ["#3d6b8c", "#5b8fd9", "#1f3d52", "#c0392b", "#7f8c8d"]
    for i, (col, label) in enumerate(zip(value_cols, labels)):
        ys = df[col].to_numpy(dtype=float)
        ax.plot(
            xs,
            ys,
            label=label,
            color=palette[i % len(palette)],
            marker=PLOT_STYLE["marker"],
            linewidth=PLOT_STYLE["linewidth"],
            markersize=PLOT_STYLE["markersize"],
        )
    ax.set_xlabel("Distance threshold k (m)")
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    ax.set_xticks(xs)
    ax.legend(frameon=False, fontsize=8, loc="best")
    _style_ax(ax)
    fig.tight_layout()
    fig.savefig(path, dpi=PLOT_STYLE["dpi"])
    plt.close(fig)


def compare_threshold_sweep(
    *,
    k_values: list[int],
    out_dir: Path,
    comparison_dir: Path,
    statuses: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build comparison CSV and plots from completed sweep runs."""
    comparison_dir.mkdir(parents=True, exist_ok=True)
    plots_dir = comparison_dir / "plots"
    plots_dir.mkdir(parents=True, exist_ok=True)

    present, missing = _validate_runs(k_values, out_dir)
    if missing:
        print(
            f"Warning: missing or incomplete runs for k={missing}. "
            "Comparison will use available runs only.",
            flush=True,
        )
    if not present:
        raise RuntimeError("No complete sweep runs found; cannot build comparison.")

    # collect the summary rows for the completed runs
    rows = [
        collect_summary_row(_threshold_slug(k), out_dir, k=k) for k in sorted(present)
    ]
    df = pd.DataFrame(rows).sort_values("k").reset_index(drop=True)

    csv_path = comparison_dir / "threshold_sweep_summary.csv"
    df.to_csv(csv_path, index=False) # write the summary to a CSV file
    print(f"Wrote {csv_path}", flush=True)

    plot_paths: list[Path] = []

    # plot overall metrics like mean marking distance, median marking distance, goal-side assignments, ...
    single_plots = [
        ("meanMarkingDistance_m", "Mean marking distance by k", "Mean marking distance (m)"),
        ("medianMarkingDistance_m", "Median marking distance by k", "Median marking distance (m)"),
        ("goalSidePercent", "Goal-side assignments by k", "Goal-side share (%)"),
        ("meanAssignmentsPerFrame", "Mean assignments per frame by k", "Mean edges per frame"),
        ("meanDegree", "Mean degree overall by k", "Mean degree"),
        (
            "meanMaxAttackerDegreePerFrame",
            "Mean maximum attacker degree per frame by k",
            "Mean max attacker degree per frame",
        ),
        (
            "meanMaxDefenderDegreePerFrame",
            "Mean maximum defender degree per frame by k",
            "Mean max defender degree per frame",
        ),
        (
            "maxAttackerDegreeOverall",
            "Maximum attacker degree overall by k",
            "Max attacker degree (any frame)",
        ),
        (
            "pctUnmarkedAttackers",
            "Unmarked attackers by k",
            "Unmarked attackers (%)",
        ),
        (
            "pctDoubleMarkedAttackers",
            "Double-marked attackers by k",
            "Double-marked attackers (%)",
        ),
        (
            "pctTriplePlusMarkedAttackers",
            "3+-marked attackers by k",
            "3+-marked attackers (%)",
        ),
        (
            "meanAssignmentDurationSec",
            "Mean assignment duration by k",
            "Mean spell duration (s)",
        ),
        (
            "assignmentSwitchesPerMinute",
            "Assignment switches per minute by k",
            "Switches per active minute (per player)",
        ),
    ]

    for col, title, ylabel in single_plots:
        if col not in df.columns or df[col].isna().all():
            continue
        fname = col.replace("_m", "m").replace("Percent", "_pct").replace("Sec", "_sec")
        path = plots_dir / f"{fname}_by_k.png"
        _line_plot(df, y_col=col, title=title, ylabel=ylabel, path=path)
        plot_paths.append(path)

    # plot ball zone metrics like mean degree, mean edge length, unmarked attackers, double-marked attackers
    ball_metrics = [
        ("meanDegree", "Mean degree by k (ball zones)", "Mean degree"),
        ("meanEdgeLength_m", "Mean marking distance by k (ball zones)", "Mean edge length (m)"),
        ("pctUnmarkedAttackers", "Unmarked attackers by k (ball zones)", "Unmarked attackers (%)"),
        ("doubleMarkingRate", "Double-marked attackers by k (ball zones)", "Double-marking rate (%)"),
        ("tripleOrMoreMarkingRate", "3+-marked attackers by k (ball zones)", "3+-marking rate (%)"),
        ("goalSidePercent", "Goal-side assignments by k (ball zones)", "Goal-side share (%)"),
    ]
    for metric, title, ylabel in ball_metrics:
        cols = [f"ball_{z}_{metric}" for z in BALL_ZONE_ORDER]
        if not all(c in df.columns for c in cols):
            continue
        if all(df[c].isna().all() for c in cols):
            continue
        labels = [BALL_ZONE_LABELS[z] for z in BALL_ZONE_ORDER]
        path = plots_dir / f"ball_zones_{metric}_by_k.png"
        _multi_zone_line_plot(
            df, value_cols=cols, labels=labels, title=title, ylabel=ylabel, path=path
        )
        plot_paths.append(path)

    # plot pitch zone metrics like mean degree, mean edge length, unmarked attackers, double-marked attackers
    pitch_metrics = [
        ("meanDegree", "Mean degree by k (pitch thirds)", "Mean degree"),
        ("meanEdgeLength_m", "Mean marking distance by k (pitch thirds)", "Mean edge length (m)"),
        ("pctUnmarkedAttackers", "Unmarked attackers by k (pitch thirds)", "Unmarked attackers (%)"),
        ("doubleMarkingRate", "Double-marked attackers by k (pitch thirds)", "Double-marking rate (%)"),
        ("tripleOrMoreMarkingRate", "3+-marked attackers by k (pitch thirds)", "3+-marking rate (%)"),
    ]
    for metric, title, ylabel in pitch_metrics:
        cols = [f"{third}_{metric}" for third in PITCH_THIRD_ORDER]
        if not all(c in df.columns for c in cols):
            continue
        if all(df[c].isna().all() for c in cols):
            continue
        labels = [PITCH_THIRD_LABELS[t] for t in PITCH_THIRD_ORDER]
        path = plots_dir / f"pitch_thirds_{metric}_by_k.png"
        _multi_zone_line_plot(
            df, value_cols=cols, labels=labels, title=title, ylabel=ylabel, path=path
        )
        plot_paths.append(path)

    result = {
        "present": present,
        "missing": missing,
        "csv": str(csv_path),
        "plots": [str(p) for p in plot_paths],
    }
    manifest_path = comparison_dir / "comparison_manifest.json"
    manifest_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result
