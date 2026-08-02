"""Aggregate oriented mutual-2NN alpha sweeps into comparison tables and plots.

Collects a broad metric table (goal-side, lengths, counts, temporal), but only
plots the primary curves vs alpha:
  - goal-side share
  - mean edge length
  - overall max edge length
  - mean of per-frame max edge length
  - mean edges per frame

Plain mutual 2NN (`knn__k2__both_mutual`) is included as a baseline reference
on the plots (horizontal line) and as a row in the summary CSV.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from analysis.assignments.oriented_knn import BEHIND_MODES
from analysis.sweep_compare.sweep_common import (
    load_json,
    mean_degree_from_per_frame,
    mean_max_distance_per_frame,
    summary_path,
)

DEFAULT_ALPHAS = (1.0, 1.25, 1.5, 1.75, 2.0, 2.5, 3.0)
DEFAULT_K = 2
BASELINE_SLUG = "knn__k2__both_mutual"
BASELINE_LABEL = "plain mutual 2NN"

REQUIRED_ANALYSES = [
    "edge_counts",
    "edge_lengths",
    "goal_side",
    "temporal_stability",
]

LENGTH_SHARE_THRESHOLDS_M = (5, 10, 15, 20, 25)

MODE_COLORS = {
    "neutral": "#3d6b8c",
    "penalize": "#c0392b",
}
MODE_MARKERS = {
    "neutral": "o",
    "penalize": "s",
}
BASELINE_STYLE = {
    "color": "#7f8c8d",
    "linestyle": "--",
    "linewidth": 1.4,
}

PLOT_STYLE = {
    "figsize": (8.5, 4.8),
    "dpi": 150,
    "linewidth": 2.0,
    "markersize": 6,
}

# Primary plots only (CSV still carries the wider metric set).
PRIMARY_PLOTS = [
    ("goalSidePercent", "Goal-side assignments", "Goal-side share (%)", "goal_side_pct_vs_alpha.png"),
    (
        "meanMarkingDistance_m",
        "Mean marking distance",
        "Mean edge length (m)",
        "mean_edge_length_vs_alpha.png",
    ),
    (
        "maxMarkingDistanceOverall_m",
        "Maximum marking-edge distance overall",
        "Max edge distance (m)",
        "max_edge_length_vs_alpha.png",
    ),
    (
        "meanMaxMarkingDistancePerFrame_m",
        "Mean maximum marking-edge distance per frame",
        "Mean max edge distance per frame (m)",
        "mean_max_edge_length_per_frame_vs_alpha.png",
    ),
    (
        "meanAssignmentsPerFrame",
        "Mean assignments per frame",
        "Mean edges per frame",
        "mean_edges_per_frame_vs_alpha.png",
    ),
]


def oriented_slug(k: int, alpha: float, behind_mode: str) -> str:
    alpha_str = f"{float(alpha):g}".replace(".", "p")
    return f"oriented_knn__k{int(k)}__a{alpha_str}__{behind_mode}"


def config_label(alpha: float, behind_mode: str) -> str:
    return f"α={float(alpha):g} ({behind_mode})"


def expand_configs(
    *,
    alphas: list[float] | None = None,
    behind_modes: list[str] | None = None,
    k: int = DEFAULT_K,
) -> list[dict[str, Any]]:
    alpha_list = list(alphas) if alphas is not None else list(DEFAULT_ALPHAS)
    modes = list(behind_modes) if behind_modes is not None else list(BEHIND_MODES)
    configs: list[dict[str, Any]] = []
    for mode in modes:
        for alpha in alpha_list:
            configs.append(
                {
                    "k": int(k),
                    "alpha": float(alpha),
                    "behind_mode": mode,
                    "slug": oriented_slug(k, alpha, mode),
                    "label": config_label(alpha, mode),
                    "family": "oriented_knn",
                }
            )
    return configs


def run_is_complete(slug: str, out_dir: Path) -> bool:
    ok = all(summary_path(out_dir, analysis, slug).is_file() for analysis in REQUIRED_ANALYSES)
    manifest = out_dir / "edge_counts" / slug / "run_manifest.json"
    return ok and manifest.is_file()


def collect_oriented_summary_row(slug: str, out_dir: Path, **extra: Any) -> dict[str, Any]:
    """Collect metrics from the four analyses used in this sweep."""
    row: dict[str, Any] = {"slug": slug, **extra}

    edge_counts = load_json(out_dir / "edge_counts" / slug / "edge_counts_summary.json")
    edge_lengths = load_json(out_dir / "edge_lengths" / slug / "edge_lengths_summary.json")
    goal_side = load_json(out_dir / "goal_side" / slug / "goal_side_summary.json")
    temporal = load_json(
        out_dir / "temporal_stability" / slug / "temporal_stability_summary.json"
    )

    att_shares = edge_counts.get("attackerDegreeShares") or {}
    def_shares = edge_counts.get("defenderDegreeShares") or {}
    threshold_shares = edge_lengths.get("thresholdShares") or {}

    per_frame_counts = out_dir / "edge_counts" / slug / "edge_counts_per_frame.csv"
    per_frame_lengths = out_dir / "edge_lengths" / slug / "edge_lengths_per_frame.csv"
    mean_deg = edge_counts.get("meanDegree")
    if mean_deg is None:
        mean_deg = mean_degree_from_per_frame(per_frame_counts)
    mean_max_dist = mean_max_distance_per_frame(per_frame_lengths)

    row.update(
        {
            "meanMarkingDistance_m": edge_lengths.get("meanDistance"),
            "medianMarkingDistance_m": edge_lengths.get("medianDistance"),
            "p95MarkingDistance_m": edge_lengths.get("p95Distance"),
            "meanMaxMarkingDistancePerFrame_m": mean_max_dist,
            "maxMarkingDistanceOverall_m": edge_lengths.get("maxDistance"),
            "goalSidePercent": goal_side.get("goalSidePercent"),
            "meanAssignmentsPerFrame": edge_counts.get("meanEdgesPerAssignedFrame"),
            "medianAssignmentsPerFrame": edge_counts.get("medianEdgesPerAssignedFrame"),
            "minAssignmentsPerFrame": edge_counts.get("minEdgesPerAssignedFrame"),
            "maxAssignmentsPerFrame": edge_counts.get("maxEdgesPerAssignedFrame"),
            "meanDegree": mean_deg,
            "meanMaxAttackerDegreePerFrame": edge_counts.get("meanMaxAttackerDegreePerFrame"),
            "meanMaxDefenderDegreePerFrame": edge_counts.get("meanMaxDefenderDegreePerFrame"),
            "maxAttackerDegreeOverall": edge_counts.get("maxAttackerDegreeAcrossFrames"),
            "maxDefenderDegreeOverall": edge_counts.get("maxDefenderDegreeAcrossFrames"),
            "pctUnmarkedAttackers": att_shares.get("pctDegree0"),
            "pctSingleMarkedAttackers": att_shares.get("pctDegree1"),
            "pctDoubleMarkedAttackers": att_shares.get("pctDegree2"),
            "pctTriplePlusMarkedAttackers": att_shares.get("pctDegree3Plus"),
            "pctUnmarkedDefenders": def_shares.get("pctDegree0"),
            "meanAssignmentDurationSec": temporal.get("meanDurationSec"),
            "medianAssignmentDurationSec": temporal.get("medianDurationSec"),
            "assignmentSwitchesPerMinute": temporal.get(
                "meanSwitchesPerActiveMinutePerPlayer"
            ),
            "nSpells": temporal.get("nSpells"),
            "totalEdges": edge_counts.get("totalEdges"),
            "nEdgesLengths": edge_lengths.get("nEdges"),
            "assignedFrames": edge_counts.get("assignedFrames"),
        }
    )

    for thr in LENGTH_SHARE_THRESHOLDS_M:
        key = str(thr)
        share = threshold_shares.get(key)
        # Summaries store fraction of edges longer than the threshold.
        row[f"shareEdgesLongerThan_{thr}m"] = (
            float(share) if share is not None else None
        )

    return row


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
    ax.grid(True, alpha=0.25, linewidth=0.6)


def _line_plot_by_mode(
    df: pd.DataFrame,
    *,
    y_col: str,
    title: str,
    ylabel: str,
    path: Path,
    baseline_value: float | None = None,
) -> None:
    fig, ax = plt.subplots(figsize=PLOT_STYLE["figsize"])
    for mode in BEHIND_MODES:
        sub = df.loc[df["behind_mode"] == mode].sort_values("alpha")
        if sub.empty:
            continue
        ax.plot(
            sub["alpha"].to_numpy(dtype=float),
            sub[y_col].to_numpy(dtype=float),
            color=MODE_COLORS.get(mode, "#7f8c8d"),
            marker=MODE_MARKERS.get(mode, "o"),
            linewidth=PLOT_STYLE["linewidth"],
            markersize=PLOT_STYLE["markersize"],
            label=mode,
        )

    if baseline_value is not None and np.isfinite(baseline_value):
        ax.axhline(
            float(baseline_value),
            color=BASELINE_STYLE["color"],
            linestyle=BASELINE_STYLE["linestyle"],
            linewidth=BASELINE_STYLE["linewidth"],
            label=BASELINE_LABEL,
        )

    alphas = sorted(df["alpha"].dropna().unique().tolist())
    ax.set_xlabel("Orientation stretch α")
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    if alphas:
        ax.set_xticks(alphas)
    ax.legend(frameon=False, fontsize=9, loc="best")
    _style_ax(ax)
    fig.tight_layout()
    fig.savefig(path, dpi=PLOT_STYLE["dpi"])
    plt.close(fig)


def compare_oriented_knn_sweep(
    *,
    out_dir: Path,
    comparison_dir: Path,
    alphas: list[float] | None = None,
    behind_modes: list[str] | None = None,
    k: int = DEFAULT_K,
    include_baseline: bool = True,
    statuses: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build comparison CSV and primary line plots for oriented mutual-2NN."""
    del statuses  # retained for API parity with other sweeps
    comparison_dir.mkdir(parents=True, exist_ok=True)
    plots_dir = comparison_dir / "plots"
    plots_dir.mkdir(parents=True, exist_ok=True)

    configs = expand_configs(alphas=alphas, behind_modes=behind_modes, k=k)
    present, missing = _validate_configs(configs, out_dir)
    if missing:
        print(
            "Warning: missing or incomplete runs for "
            f"{[c['label'] for c in missing]}. "
            "Comparison will use available runs only.",
            flush=True,
        )
    if not present:
        raise RuntimeError(
            "No complete oriented kNN sweep runs found; cannot build comparison."
        )

    present_slugs = {c["slug"] for c in present}
    ordered = [c for c in configs if c["slug"] in present_slugs]

    rows = [
        collect_oriented_summary_row(
            cfg["slug"],
            out_dir,
            k=cfg["k"],
            alpha=cfg["alpha"],
            behind_mode=cfg["behind_mode"],
            label=cfg["label"],
            family=cfg["family"],
        )
        for cfg in ordered
    ]

    baseline_row: dict[str, Any] | None = None
    if include_baseline:
        if run_is_complete(BASELINE_SLUG, out_dir):
            baseline_row = collect_oriented_summary_row(
                BASELINE_SLUG,
                out_dir,
                k=k,
                alpha=None,
                behind_mode=None,
                label=BASELINE_LABEL,
                family="knn",
            )
            rows.append(baseline_row)
        else:
            print(
                f"Warning: baseline {BASELINE_SLUG} incomplete or missing; "
                "plots will omit the reference line.",
                flush=True,
            )

    df = pd.DataFrame(rows)
    csv_path = comparison_dir / "oriented_knn_sweep_summary.csv"
    df.to_csv(csv_path, index=False)
    print(f"Wrote {csv_path}", flush=True)

    oriented_df = df.loc[df["family"] == "oriented_knn"].copy()
    plot_paths: list[Path] = []
    for col, title, ylabel, fname in PRIMARY_PLOTS:
        if col not in oriented_df.columns or oriented_df[col].isna().all():
            continue
        baseline_value = None
        if baseline_row is not None and baseline_row.get(col) is not None:
            baseline_value = float(baseline_row[col])
        path = plots_dir / fname
        _line_plot_by_mode(
            oriented_df,
            y_col=col,
            title=title,
            ylabel=ylabel,
            path=path,
            baseline_value=baseline_value,
        )
        plot_paths.append(path)
        print(f"Wrote {path}", flush=True)

    result = {
        "present": [c["label"] for c in ordered],
        "missing": [c["label"] for c in missing],
        "baseline": BASELINE_LABEL if baseline_row is not None else None,
        "csv": str(csv_path),
        "plots": [str(p) for p in plot_paths],
    }
    manifest_path = comparison_dir / "comparison_manifest.json"
    manifest_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {manifest_path}", flush=True)
    return result
