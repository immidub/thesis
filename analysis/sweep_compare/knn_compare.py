"""Aggregate kNN parameter-sweep outputs into comparison tables and bar plots."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from analysis.analyses.ball_zones import BALL_ZONE_LABELS, BALL_ZONE_ORDER
from analysis.assignments.knn import KNN_MODES
from analysis.sweep_compare.sweep_common import (
    PITCH_THIRD_LABELS,
    PITCH_THIRD_ORDER,
    collect_summary_row,
    run_is_complete,
)

# Stable ordering: mode outer, k inner (matches KNN_MODES registry order).
DEFAULT_K_VALUES = (1, 2, 3)

MODE_COLORS = {
    "defender-to-attacker": "#3d6b8c",
    "attacker-to-defender": "#5b8fd9",
    "both-mutual": "#1f3d52",
    "both-all": "#7a9e7e",
}

ZONE_COLORS = ["#3d6b8c", "#5b8fd9", "#1f3d52", "#c0392b", "#7f8c8d"]

PLOT_STYLE = {
    "figsize": (11.5, 5.0),
    "dpi": 150,
}


def knn_slug(k: int, mode: str) -> str:
    mode_slug = str(mode).replace("-", "_")
    return f"knn__k{k}__{mode_slug}"


def config_label(mode: str, k: int) -> str:
    return f"{mode}-k{k}"


def expand_configs( # create the kNN configurations set
    k_values: list[int] | None = None,
    modes: list[str] | None = None,
) -> list[dict[str, Any]]:
    ks = list(k_values) if k_values is not None else list(DEFAULT_K_VALUES)
    mode_list = list(modes) if modes is not None else list(KNN_MODES)
    configs: list[dict[str, Any]] = []
    for mode in mode_list:
        for k in ks:
            configs.append(
                {
                    "k": k,
                    "mode": mode,
                    "slug": knn_slug(k, mode),
                    "label": config_label(mode, k),
                }
            )
    return configs

# validate the kNN configurations
def _validate_configs(
    configs: list[dict[str, Any]], out_dir: Path
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    present: list[dict[str, Any]] = []
    missing: list[dict[str, Any]] = []
    for cfg in configs:
        if run_is_complete(cfg["slug"], out_dir):
            present.append(cfg)
        else:
            missing.append(cfg)
    return present, missing


def _style_ax(ax: plt.Axes) -> None:
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(True, axis="y", alpha=0.25, linewidth=0.6)


def _bar_colors(df: pd.DataFrame) -> list[str]:
    return [MODE_COLORS.get(str(m), "#7f8c8d") for m in df["mode"]]

# plot a single bar graph
def _bar_plot(
    df: pd.DataFrame,
    *,
    y_col: str,
    title: str,
    ylabel: str,
    path: Path,
) -> None:
    fig, ax = plt.subplots(figsize=PLOT_STYLE["figsize"])
    labels = df["label"].tolist()
    ys = df[y_col].to_numpy(dtype=float)
    x = np.arange(len(labels))
    colors = _bar_colors(df)
    ax.bar(x, ys, color=colors, edgecolor="white", linewidth=0.5, width=0.8)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=55, ha="right", fontsize=8)
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    _style_ax(ax)

    fig.tight_layout()
    fig.savefig(path, dpi=PLOT_STYLE["dpi"])
    plt.close(fig)


# plot a bar graph for multiple zones
def _grouped_zone_bar_plot(
    df: pd.DataFrame,
    *,
    value_cols: list[str],
    zone_labels: list[str],
    title: str,
    ylabel: str,
    path: Path,
) -> None:
    fig, ax = plt.subplots(figsize=PLOT_STYLE["figsize"])
    n_cfg = len(df)
    n_zones = len(value_cols)
    x = np.arange(n_cfg)
    width = 0.8 / n_zones
    for i, (col, zlabel) in enumerate(zip(value_cols, zone_labels)):
        ys = df[col].to_numpy(dtype=float)
        offset = (i - (n_zones - 1) / 2.0) * width
        ax.bar(
            x + offset,
            ys,
            width=width,
            label=zlabel,
            color=ZONE_COLORS[i % len(ZONE_COLORS)],
            edgecolor="white",
            linewidth=0.4,
        )
    ax.set_xticks(x)
    ax.set_xticklabels(df["label"].tolist(), rotation=55, ha="right", fontsize=8)
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    ax.legend(frameon=False, fontsize=8, loc="best")
    _style_ax(ax)
    fig.tight_layout()
    fig.savefig(path, dpi=PLOT_STYLE["dpi"])
    plt.close(fig)


def compare_knn_sweep(
    *,
    out_dir: Path,
    comparison_dir: Path,
    k_values: list[int] | None = None,
    modes: list[str] | None = None,
    statuses: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build comparison CSV and bar plots for kNN mode × k configurations."""
    comparison_dir.mkdir(parents=True, exist_ok=True)
    plots_dir = comparison_dir / "plots"
    plots_dir.mkdir(parents=True, exist_ok=True)

    configs = expand_configs(k_values=k_values, modes=modes)
    present, missing = _validate_configs(configs, out_dir)
    if missing:
        print(
            "Warning: missing or incomplete runs for "
            f"{[c['label'] for c in missing]}. "
            "Comparison will use available runs only.",
            flush=True,
        )
    if not present:
        raise RuntimeError("No complete kNN sweep runs found; cannot build comparison.")

    # Keep canonical order (mode outer, k inner); drop missing.
    present_slugs = {c["slug"] for c in present}
    ordered = [c for c in configs if c["slug"] in present_slugs]

    # collect the summary rows for the completed runs
    rows = [
        collect_summary_row(
            cfg["slug"],
            out_dir,
            k=cfg["k"],
            mode=cfg["mode"],
            label=cfg["label"],
        )
        for cfg in ordered
    ]
    df = pd.DataFrame(rows)
    # Preserve expand_configs order
    df["_order"] = range(len(df))
    df = df.sort_values("_order").drop(columns=["_order"]).reset_index(drop=True)

    csv_path = comparison_dir / "knn_sweep_summary.csv"
    df.to_csv(csv_path, index=False) # write the summary to a CSV file
    print(f"Wrote {csv_path}", flush=True)

    plot_paths: list[Path] = []

    # plot the single metrics like mean marking distance, median marking distance, ...
    single_plots = [
        ("meanMarkingDistance_m", "Mean marking distance", "Mean marking distance (m)"),
        ("medianMarkingDistance_m", "Median marking distance", "Median marking distance (m)"),
        (
            "meanMaxMarkingDistancePerFrame_m",
            "Mean maximum marking-edge distance per frame",
            "Mean max edge distance per frame (m)",
        ),
        (
            "maxMarkingDistanceOverall_m",
            "Maximum marking-edge distance overall",
            "Max edge distance (m)",
        ),
        ("goalSidePercent", "Goal-side assignments", "Goal-side share (%)"),
        ("meanAssignmentsPerFrame", "Mean assignments per frame", "Mean edges per frame"),
        ("meanDegree", "Mean degree overall", "Mean degree"),
        (
            "meanMaxAttackerDegreePerFrame",
            "Mean maximum attacker degree per frame",
            "Mean max attacker degree per frame",
        ),
        (
            "meanMaxDefenderDegreePerFrame",
            "Mean maximum defender degree per frame",
            "Mean max defender degree per frame",
        ),
        (
            "maxAttackerDegreeOverall",
            "Maximum attacker degree overall",
            "Max attacker degree (any frame)",
        ),
        (
            "maxDefenderDegreeOverall",
            "Maximum defender degree overall",
            "Max defender degree (any frame)",
        ),
        ("pctUnmarkedAttackers", "Unmarked attackers", "Unmarked attackers (%)"),
        ("pctDoubleMarkedAttackers", "Double-marked attackers", "Double-marked attackers (%)"),
        (
            "pctTriplePlusMarkedAttackers",
            "3+-marked attackers",
            "3+-marked attackers (%)",
        ),
        (
            "meanAssignmentDurationSec",
            "Mean assignment duration",
            "Mean spell duration (s)",
        ),
        (
            "assignmentSwitchesPerMinute",
            "Assignment switches per minute",
            "Switches per active minute (per player)",
        ),
    ]

    for col, title, ylabel in single_plots:
        if col not in df.columns or df[col].isna().all():
            continue
        fname = (
            col.replace("_m", "m")
            .replace("Percent", "_pct")
            .replace("Sec", "_sec")
        )
        path = plots_dir / f"{fname}_by_config.png"
        _bar_plot(df, y_col=col, title=title, ylabel=ylabel, path=path)
        plot_paths.append(path)

    # plot ball zone metrics like mean degree, mean edge length, unmarked attackers, double-marked attackers
    ball_metrics = [
        ("meanDegree", "Mean degree (ball zones)", "Mean degree"),
        ("meanEdgeLength_m", "Mean marking distance (ball zones)", "Mean edge length (m)"),
        ("pctUnmarkedAttackers", "Unmarked attackers (ball zones)", "Unmarked attackers (%)"),
        ("doubleMarkingRate", "Double-marked attackers (ball zones)", "Double-marking rate (%)"),
        ("tripleOrMoreMarkingRate", "3+-marked attackers (ball zones)", "3+-marking rate (%)"),
        ("goalSidePercent", "Goal-side assignments (ball zones)", "Goal-side share (%)"),
    ]
    for metric, title, ylabel in ball_metrics:
        cols = [f"ball_{z}_{metric}" for z in BALL_ZONE_ORDER]
        if not all(c in df.columns for c in cols):
            continue
        if all(df[c].isna().all() for c in cols):
            continue
        labels = [BALL_ZONE_LABELS[z] for z in BALL_ZONE_ORDER]
        path = plots_dir / f"ball_zones_{metric}_by_config.png"
        _grouped_zone_bar_plot(
            df,
            value_cols=cols,
            zone_labels=labels,
            title=title,
            ylabel=ylabel,
            path=path,
        )
        plot_paths.append(path)

    # plot pitch zone metrics like mean degree, mean edge length, unmarked attackers, double-marked attackers
    pitch_metrics = [
        ("meanDegree", "Mean degree (pitch thirds)", "Mean degree"),
        ("meanEdgeLength_m", "Mean marking distance (pitch thirds)", "Mean edge length (m)"),
        ("pctUnmarkedAttackers", "Unmarked attackers (pitch thirds)", "Unmarked attackers (%)"),
        ("doubleMarkingRate", "Double-marked attackers (pitch thirds)", "Double-marking rate (%)"),
        ("tripleOrMoreMarkingRate", "3+-marked attackers (pitch thirds)", "3+-marking rate (%)"),
    ]
    for metric, title, ylabel in pitch_metrics:
        cols = [f"{third}_{metric}" for third in PITCH_THIRD_ORDER]
        if not all(c in df.columns for c in cols):
            continue
        if all(df[c].isna().all() for c in cols):
            continue
        labels = [PITCH_THIRD_LABELS[t] for t in PITCH_THIRD_ORDER]
        path = plots_dir / f"pitch_thirds_{metric}_by_config.png"
        _grouped_zone_bar_plot(
            df,
            value_cols=cols,
            zone_labels=labels,
            title=title,
            ylabel=ylabel,
            path=path,
        )
        plot_paths.append(path)

    result = {
        "present": [c["label"] for c in ordered],
        "missing": [c["label"] for c in missing],
        "csv": str(csv_path),
        "plots": [str(p) for p in plot_paths],
    }
    manifest_path = comparison_dir / "comparison_manifest.json"
    manifest_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result
