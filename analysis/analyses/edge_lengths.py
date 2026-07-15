"""Marking-edge distance statistics (spatial plausibility)."""

from __future__ import annotations

import json
import statistics
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

from analysis.analyses.base import AnalysisContext
from analysis.assignments.base import Edge
from analysis.data import Frame

# Fixed metre bins for the distance histogram (last bin is open-ended).
HIST_EDGES_M = (0.0, 2.0, 4.0, 6.0, 8.0, 10.0, 12.0, 15.0, 20.0, 25.0, float("inf"))


class EdgeLengthsAnalysis:
    name = "edge_lengths"

    def run(
        self,
        frames: list[Frame],
        edges_by_frame: list[list[Edge]],
        ctx: AnalysisContext,
    ) -> dict:
        if len(frames) != len(edges_by_frame):
            raise ValueError("frames and edges_by_frame length mismatch")

        rows: list[dict] = []
        all_lengths: list[float] = []
        lengths_by_period: dict[int, list[float]] = defaultdict(list)

        for frame, edges in zip(frames, edges_by_frame):
            lengths = [e.length_m for e in edges]
            all_lengths.extend(lengths)
            if frame.defending_team is not None and lengths:
                lengths_by_period[frame.period].extend(lengths)

            rows.append(
                {
                    "period": frame.period,
                    "frameIdx": frame.frame_idx,
                    "gameClock": frame.game_clock,
                    "live": frame.live,
                    "lastTouch": frame.last_touch,
                    "defendingTeam": frame.defending_team,
                    "edgeCount": len(lengths),
                    "hasAssignment": frame.defending_team is not None,
                    "meanDistance": statistics.fmean(lengths) if lengths else None,
                    "medianDistance": float(statistics.median(lengths)) if lengths else None,
                    "p95Distance": float(np.percentile(lengths, 95)) if lengths else None,
                    "maxDistance": max(lengths) if lengths else None,
                    "minDistance": min(lengths) if lengths else None,
                }
            )

        per_frame = pd.DataFrame(rows)
        out_dir = ctx.out_dir
        out_dir.mkdir(parents=True, exist_ok=True)

        per_frame_path = out_dir / "edge_lengths_per_frame.csv"
        per_frame.to_csv(per_frame_path, index=False)

        summary = _build_summary(per_frame, all_lengths, lengths_by_period, ctx)

        plot_paths = _write_plots(per_frame, summary, out_dir)
        summary["outputs"].update(plot_paths)

        summary_path = out_dir / "edge_lengths_summary.json"
        summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

        return summary


def _distance_stats(lengths: list[float] | np.ndarray) -> dict:
    if len(lengths) == 0:
        return {
            "nEdges": 0,
            "meanDistance": None,
            "medianDistance": None,
            "p95Distance": None,
            "maxDistance": None,
            "minDistance": None,
        }
    arr = np.asarray(lengths, dtype=np.float64)
    return {
        "nEdges": int(arr.size),
        "meanDistance": float(arr.mean()),
        "medianDistance": float(np.median(arr)),
        "p95Distance": float(np.percentile(arr, 95)),
        "maxDistance": float(arr.max()),
        "minDistance": float(arr.min()),
    }


def _histogram(lengths: list[float]) -> list[dict]:
    empty_bins = [
        {
            "binStart": HIST_EDGES_M[i],
            "binEnd": None if HIST_EDGES_M[i + 1] == float("inf") else HIST_EDGES_M[i + 1],
            "count": 0,
            "share": 0.0,
        }
        for i in range(len(HIST_EDGES_M) - 1)
    ]
    if not lengths:
        return empty_bins

    arr = np.asarray(lengths, dtype=np.float64)
    # np.histogram needs a finite right edge; map +inf above the observed max.
    finite_edges = list(HIST_EDGES_M[:-1]) + [max(float(arr.max()) + 1.0, HIST_EDGES_M[-2] + 1.0)]
    counts, _ = np.histogram(arr, bins=finite_edges)
    total = int(counts.sum())
    bins: list[dict] = []
    for i, count in enumerate(counts):
        bin_end = HIST_EDGES_M[i + 1]
        bins.append(
            {
                "binStart": HIST_EDGES_M[i],
                "binEnd": None if bin_end == float("inf") else bin_end,
                "count": int(count),
                "share": float(count / total) if total else 0.0,
            }
        )
    return bins


def _bin_label(bin_start: float, bin_end: float | None) -> str:
    if bin_end is None:
        return f"{bin_start:.0f}+"
    return f"{bin_start:.0f}–{bin_end:.0f}"


def _style_ax(ax) -> None:
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)


def _write_plots(per_frame: pd.DataFrame, summary: dict, out_dir: Path) -> dict[str, str]:
    import matplotlib.pyplot as plt

    assignment = summary.get("assignment", "assignment")
    assigned = per_frame.loc[
        (per_frame["hasAssignment"] == True) & (per_frame["edgeCount"] > 0)
    ]
    outputs: dict[str, str] = {}

    # 1) All-edge distance histogram (existing)
    path = out_dir / "edge_lengths_histogram.png"
    _write_distance_histogram_plot(summary, path)
    outputs["histogramPng"] = str(Path(path.name))

    # 2) Histogram of per-frame max marking distance
    path = out_dir / "edge_lengths_max_histogram.png"
    fig, ax = plt.subplots(figsize=(8.5, 4.2))
    if not assigned.empty:
        maxima = assigned["maxDistance"].dropna().to_numpy(dtype=np.float64)
        finite_edges = list(HIST_EDGES_M[:-1]) + [
            max(float(maxima.max()) + 1.0, HIST_EDGES_M[-2] + 1.0)
        ]
        counts, _ = np.histogram(maxima, bins=finite_edges)
        labels = [
            _bin_label(
                HIST_EDGES_M[i],
                None if HIST_EDGES_M[i + 1] == float("inf") else HIST_EDGES_M[i + 1],
            )
            for i in range(len(HIST_EDGES_M) - 1)
        ]
        total = int(counts.sum())
        shares = [100.0 * c / total if total else 0.0 for c in counts]
        bars = ax.bar(labels, shares, color="#5b8fd9", edgecolor="white", linewidth=0.6)
        for bar, count in zip(bars, counts):
            if count <= 0:
                continue
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height(),
                f"{int(count):,}",
                ha="center",
                va="bottom",
                fontsize=7.5,
                color="#333333",
            )
        ax.set_ylim(0, max(shares) * 1.18 if shares else 1.0)
    ax.set_xlabel("Max marking distance in frame (m)")
    ax.set_ylabel("Share of frames (%)")
    ax.set_title(f"Per-frame maximum distance — {assignment}")
    _style_ax(ax)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    outputs["maxHistogramPng"] = str(Path(path.name))

    # 3) Mean / p95 / max distance per live clock-minute
    path = out_dir / "edge_lengths_per_minute.png"
    fig, ax = plt.subplots(figsize=(10, 4.2))
    per_minute = _per_minute_distance_table(per_frame)
    if not per_minute.empty:
        x = np.arange(len(per_minute))
        ax.plot(x, per_minute["meanDistance"], color="#3d6b8c", linewidth=1.6, label="mean")
        ax.plot(x, per_minute["p95Distance"], color="#c0392b", linewidth=1.2, linestyle="--", label="p95")
        ax.plot(x, per_minute["maxDistance"], color="#7f8c8d", linewidth=1.0, alpha=0.8, label="max")
        step = max(1, len(per_minute) // 12)
        tick_idx = list(range(0, len(per_minute), step))
        ax.set_xticks(tick_idx)
        ax.set_xticklabels(
            [per_minute.iloc[i]["label"] for i in tick_idx],
            rotation=45,
            ha="right",
            fontsize=8,
        )
        ax.legend(frameon=False, fontsize=8)
        per_minute.to_csv(out_dir / "edge_lengths_per_minute.csv", index=False)
        outputs["perMinuteCsv"] = str(Path("edge_lengths_per_minute.csv"))
    ax.set_ylabel("Distance (m)")
    ax.set_xlabel("Match clock minute (live / assigned only)")
    ax.set_title(f"Marking distance over live minutes — {assignment}")
    _style_ax(ax)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    outputs["perMinutePng"] = str(Path(path.name))

    # 4) Share of edges above distance thresholds
    path = out_dir / "edge_lengths_threshold_shares.png"
    fig, ax = plt.subplots(figsize=(7, 4.2))
    thresholds = [5, 10, 15, 20, 25]
    n_edges = summary.get("nEdges") or 0
    if n_edges and assigned is not None:
        # recompute from summary histogram approximately? Better use all lengths via hist bins —
        # we only have summary histogram. Use per-frame isn't all edges.
        # Reconstruct from summary histogram is approximate for inequality.
        # Store threshold shares in summary during build; plot from summary.
        shares = summary.get("thresholdShares") or {}
        labels = [f">{t}" for t in thresholds]
        vals = [100.0 * float(shares.get(str(t), 0.0)) for t in thresholds]
        ax.bar(labels, vals, color="#3d6b8c", edgecolor="white", linewidth=0.6)
        for i, v in enumerate(vals):
            ax.text(i, v, f"{v:.1f}%", ha="center", va="bottom", fontsize=8, color="#333333")
        ax.set_ylim(0, max(vals) * 1.2 if vals else 1.0)
    ax.set_xlabel("Distance threshold (m)")
    ax.set_ylabel("Share of edges longer than threshold (%)")
    ax.set_title(f"Long marking edges — {assignment}")
    _style_ax(ax)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    outputs["thresholdSharesPng"] = str(Path(path.name))

    return outputs


def _per_minute_distance_table(per_frame: pd.DataFrame) -> pd.DataFrame:
    assigned = per_frame.loc[
        (per_frame["hasAssignment"] == True) & (per_frame["edgeCount"] > 0)
    ].copy()
    if assigned.empty:
        return pd.DataFrame(
            columns=["period", "minute", "label", "assignedFrames", "meanDistance", "p95Distance", "maxDistance"]
        )
    assigned["minute"] = np.floor(assigned["gameClock"].to_numpy(dtype=np.float64) / 60.0).astype(int)
    rows: list[dict] = []
    for (period, minute), group in assigned.groupby(["period", "minute"], sort=True):
        # Frame-level aggregates: mean of frame means; max of frame maxes; mean of frame p95s
        rows.append(
            {
                "period": int(period),
                "minute": int(minute),
                "label": f"P{int(period)} {int(minute)}'",
                "assignedFrames": int(len(group)),
                "meanDistance": float(group["meanDistance"].mean()),
                "p95Distance": float(group["p95Distance"].mean()),
                "maxDistance": float(group["maxDistance"].max()),
            }
        )
    return pd.DataFrame(rows)


def _write_distance_histogram_plot(summary: dict, path: Path) -> None:
    import matplotlib.pyplot as plt

    bins = summary.get("histogram") or []
    labels = [_bin_label(b["binStart"], b.get("binEnd")) for b in bins]
    shares = [100.0 * float(b.get("share") or 0.0) for b in bins]
    counts = [int(b.get("count") or 0) for b in bins]

    assignment = summary.get("assignment", "assignment")
    n_edges = summary.get("nEdges") or 0
    mean_d = summary.get("meanDistance")
    median_d = summary.get("medianDistance")
    p95_d = summary.get("p95Distance")

    fig, ax = plt.subplots(figsize=(9, 4.5))
    bars = ax.bar(labels, shares, color="#3d6b8c", edgecolor="white", linewidth=0.6)
    ax.set_xlabel("Marking distance (m)")
    ax.set_ylabel("Share of edges (%)")
    ax.set_title(f"Marking distance distribution — {assignment}")
    ax.set_ylim(0, max(shares) * 1.18 if shares else 1.0)
    _style_ax(ax)

    for bar, count in zip(bars, counts):
        if count <= 0:
            continue
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height(),
            f"{count:,}",
            ha="center",
            va="bottom",
            fontsize=7.5,
            color="#333333",
        )

    stats_parts = [f"n = {n_edges:,}"]
    if mean_d is not None:
        stats_parts.append(f"mean = {mean_d:.2f} m")
    if median_d is not None:
        stats_parts.append(f"median = {median_d:.2f} m")
    if p95_d is not None:
        stats_parts.append(f"p95 = {p95_d:.2f} m")
    ax.text(
        0.99,
        0.97,
        "  ·  ".join(stats_parts),
        transform=ax.transAxes,
        ha="right",
        va="top",
        fontsize=8,
        color="#555555",
    )

    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def _threshold_shares(lengths: list[float], thresholds: tuple[int, ...] = (5, 10, 15, 20, 25)) -> dict[str, float]:
    if not lengths:
        return {str(t): 0.0 for t in thresholds}
    arr = np.asarray(lengths, dtype=np.float64)
    n = float(arr.size)
    return {str(t): float(np.mean(arr > t)) for t in thresholds}


def _build_summary(
    per_frame: pd.DataFrame,
    all_lengths: list[float],
    lengths_by_period: dict[int, list[float]],
    ctx: AnalysisContext,
) -> dict:
    assignment = ctx.assignment
    threshold_m = getattr(assignment, "threshold_m", None)

    total_frames = int(len(per_frame))
    live_mask = per_frame["live"] == True
    assigned_mask = per_frame["hasAssignment"] == True
    live_frames = int(live_mask.sum())
    assigned_frames = int(assigned_mask.sum())
    frames_with_edges = (
        int((per_frame.loc[assigned_mask, "edgeCount"] > 0).sum()) if assigned_frames else 0
    )

    by_period: dict[str, dict] = {
        str(period): _distance_stats(lengths)
        for period, lengths in sorted(lengths_by_period.items())
    }

    max_per_frame = (
        per_frame.loc[assigned_mask & (per_frame["edgeCount"] > 0), "maxDistance"]
        .dropna()
        .tolist()
    )

    return {
        "analysis": "edge_lengths",
        "assignment": assignment.name,
        "threshold_m": threshold_m,
        "totalFrames": total_frames,
        "liveFrames": live_frames,
        "assignedFrames": assigned_frames,
        "framesWithAtLeastOneEdge": frames_with_edges,
        **_distance_stats(all_lengths),
        "histogram": _histogram(all_lengths),
        "maxDistanceHistogram": _histogram(max_per_frame),
        "thresholdShares": _threshold_shares(all_lengths),
        "byPeriod": by_period,
        "outputs": {
            "perFrameCsv": str(Path("edge_lengths_per_frame.csv")),
            "summaryJson": str(Path("edge_lengths_summary.json")),
        },
    }
