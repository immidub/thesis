"""Count marking edges and node degrees per frame (collective coverage)."""

from __future__ import annotations

import json
import statistics
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd

from analysis.analyses.base import AnalysisContext
from analysis.assignments.base import Edge
from analysis.assignments.meta import assignment_plot_label, assignment_summary_fields
from analysis.data import Frame


class EdgeCountsAnalysis:
    name = "edge_counts"

    def run(
        self,
        frames: list[Frame],
        edges_by_frame: list[list[Edge]],
        ctx: AnalysisContext,
    ) -> dict:
        if len(frames) != len(edges_by_frame):
            raise ValueError("frames and edges_by_frame length mismatch")

        rows: list[dict] = []
        for frame, edges in zip(frames, edges_by_frame):
            rows.append(_frame_row(frame, edges))

        per_frame = pd.DataFrame(rows)
        out_dir = ctx.out_dir
        out_dir.mkdir(parents=True, exist_ok=True)

        per_frame_path = out_dir / "edge_counts_per_frame.csv"
        per_frame.to_csv(per_frame_path, index=False)

        summary = _build_summary(per_frame, ctx)

        plot_paths = _write_plots(per_frame, summary, out_dir)
        summary["outputs"].update(plot_paths)

        summary_path = out_dir / "edge_counts_summary.json"
        summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

        return summary


# Helper function to compute the share of players in each degree bucket
def _degree_bucket_shares(degrees: list[int]) -> dict[str, float | None]:
    n = len(degrees)
    if n == 0:
        return {
            "pctDegree0": None,
            "pctDegree1": None,
            "pctDegree2": None,
            "pctDegree3Plus": None,
        }
    c0 = sum(1 for d in degrees if d == 0)
    c1 = sum(1 for d in degrees if d == 1)
    c2 = sum(1 for d in degrees if d == 2)
    c3 = sum(1 for d in degrees if d >= 3)
    return {
        "pctDegree0": 100.0 * c0 / n,
        "pctDegree1": 100.0 * c1 / n,
        "pctDegree2": 100.0 * c2 / n,
        "pctDegree3Plus": 100.0 * c3 / n,
    }


# Helper function to compute the edge counts for a frame
def _frame_row(frame: Frame, edges: list[Edge]) -> dict:
    defending = frame.defending_team
    base = {
        "period": frame.period,
        "frameIdx": frame.frame_idx,
        "gameClock": frame.game_clock,
        "live": frame.live,
        "lastTouch": frame.last_touch,
        "defendingTeam": defending,
        "edgeCount": len(edges),
        "hasAssignment": defending is not None,
        "nDefenders": None,
        "nAttackers": None,
        "maxDegree": None,
        "maxDefenderDegree": None,
        "maxAttackerDegree": None,
        "attackerPctDegree0": None,
        "attackerPctDegree1": None,
        "attackerPctDegree2": None,
        "attackerPctDegree3Plus": None,
        "defenderPctDegree0": None,
        "defenderPctDegree1": None,
        "defenderPctDegree2": None,
        "defenderPctDegree3Plus": None,
    }
    if defending is None:
        return base

    attacking = "away" if defending == "home" else "home"
    defenders = frame.outfield_players(defending)
    attackers = frame.outfield_players(attacking)
    defender_ids = [p.player_id for p in defenders]
    attacker_ids = [p.player_id for p in attackers]

    def_deg: Counter[str] = Counter()
    att_deg: Counter[str] = Counter()
    for edge in edges:
        def_deg[edge.defender_id] += 1
        att_deg[edge.attacker_id] += 1

    defender_degrees = [def_deg[pid] for pid in defender_ids]
    attacker_degrees = [att_deg[pid] for pid in attacker_ids]
    all_degrees = defender_degrees + attacker_degrees

    n_def = len(defender_degrees)
    n_att = len(attacker_degrees)

    att_shares = _degree_bucket_shares(attacker_degrees)
    def_shares = _degree_bucket_shares(defender_degrees)

    max_def = max(defender_degrees) if defender_degrees else None
    max_att = max(attacker_degrees) if attacker_degrees else None
    max_all = max(all_degrees) if all_degrees else None

    base.update(
        {
            "nDefenders": n_def,
            "nAttackers": n_att,
            "maxDegree": max_all,
            "maxDefenderDegree": max_def,
            "maxAttackerDegree": max_att,
            "attackerPctDegree0": att_shares["pctDegree0"],
            "attackerPctDegree1": att_shares["pctDegree1"],
            "attackerPctDegree2": att_shares["pctDegree2"],
            "attackerPctDegree3Plus": att_shares["pctDegree3Plus"],
            "defenderPctDegree0": def_shares["pctDegree0"],
            "defenderPctDegree1": def_shares["pctDegree1"],
            "defenderPctDegree2": def_shares["pctDegree2"],
            "defenderPctDegree3Plus": def_shares["pctDegree3Plus"],
        }
    )
    return base


def _mean_or_none(values: list[float]) -> float | None:
    return statistics.fmean(values) if values else None

# Helper function to aggregate maximum degree values and degree shares
def _agg_degree_block(group: pd.DataFrame) -> dict:
    max_degree_vals = group["maxDegree"].dropna().tolist()
    max_def_vals = group["maxDefenderDegree"].dropna().tolist()
    max_att_vals = group["maxAttackerDegree"].dropna().tolist()

    return {
        "meanMaxDegreePerFrame": _mean_or_none(max_degree_vals),
        "meanMaxDefenderDegreePerFrame": _mean_or_none(max_def_vals),
        "meanMaxAttackerDegreePerFrame": _mean_or_none(max_att_vals),
        "maxDegreeAcrossFrames": int(max(max_degree_vals)) if max_degree_vals else None,
        "maxDefenderDegreeAcrossFrames": int(max(max_def_vals)) if max_def_vals else None,
        "maxAttackerDegreeAcrossFrames": int(max(max_att_vals)) if max_att_vals else None,
        "attackerDegreeShares": {
            "pctDegree0": _mean_or_none(group["attackerPctDegree0"].dropna().tolist()),
            "pctDegree1": _mean_or_none(group["attackerPctDegree1"].dropna().tolist()),
            "pctDegree2": _mean_or_none(group["attackerPctDegree2"].dropna().tolist()),
            "pctDegree3Plus": _mean_or_none(
                group["attackerPctDegree3Plus"].dropna().tolist()
            ),
        },
        "defenderDegreeShares": {
            "pctDegree0": _mean_or_none(group["defenderPctDegree0"].dropna().tolist()),
            "pctDegree1": _mean_or_none(group["defenderPctDegree1"].dropna().tolist()),
            "pctDegree2": _mean_or_none(group["defenderPctDegree2"].dropna().tolist()),
            "pctDegree3Plus": _mean_or_none(
                group["defenderPctDegree3Plus"].dropna().tolist()
            ),
        },
    }


def _build_summary(
    per_frame: pd.DataFrame,
    ctx: AnalysisContext,
) -> dict:
    assignment = ctx.assignment

    total_frames = int(len(per_frame))
    live_mask = per_frame["live"] == True
    assigned_mask = per_frame["hasAssignment"] == True
    live_frames = int(live_mask.sum())
    assigned_frames = int(assigned_mask.sum())

    assigned = per_frame.loc[assigned_mask]
    counts = assigned["edgeCount"].tolist()
    if counts:
        mean_edges = statistics.fmean(counts)
        median_edges = float(statistics.median(counts))
        max_edges = int(max(counts))
        min_edges = int(min(counts))
        frames_with_edges = sum(1 for c in counts if c > 0)
        total_edges = int(sum(counts))
    else:
        mean_edges = median_edges = 0.0
        max_edges = min_edges = total_edges = frames_with_edges = 0

    degree_block = (
        _agg_degree_block(assigned) if assigned_frames else _agg_degree_block(per_frame.iloc[0:0])
    )

    by_period: dict[str, dict] = {}
    if assigned_frames:
        for period, group in assigned.groupby("period"):
            period_counts = group["edgeCount"].tolist()
            by_period[str(int(period))] = {
                "assignedFrames": int(len(period_counts)),
                "totalEdges": int(sum(period_counts)),
                "meanEdges": statistics.fmean(period_counts) if period_counts else 0.0,
                "medianEdges": float(statistics.median(period_counts)) if period_counts else 0.0,
                "maxEdges": int(max(period_counts)) if period_counts else 0,
                "framesWithAtLeastOneEdge": sum(1 for c in period_counts if c > 0),
                **_agg_degree_block(group),
            }

    return {
        "analysis": "edge_counts",
        **assignment_summary_fields(assignment),
        "totalFrames": total_frames,
        "liveFrames": live_frames,
        "assignedFrames": assigned_frames,
        "totalEdges": total_edges,
        "meanEdgesPerAssignedFrame": mean_edges,
        "medianEdgesPerAssignedFrame": median_edges,
        "minEdgesPerAssignedFrame": min_edges,
        "maxEdgesPerAssignedFrame": max_edges,
        "framesWithAtLeastOneEdge": frames_with_edges,
        "shareAssignedFramesWithAtLeastOneEdge": (
            frames_with_edges / assigned_frames if assigned_frames else 0.0
        ),
        **degree_block,
        "byPeriod": by_period,
        "outputs": {
            "perFrameCsv": str(Path("edge_counts_per_frame.csv")),
            "summaryJson": str(Path("edge_counts_summary.json")),
        },
    }


def _style_ax(ax) -> None:
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)


def _ticks_0_or_5(lo: int, hi: int) -> list[int]:
    """Integer axis ticks that are multiples of 5 (or 10 for wide spans)."""
    span = max(hi - lo, 0)
    step = 5 if span <= 50 else 10
    start = (lo // step) * step
    end = ((hi + step - 1) // step) * step
    if start == end:
        return [start]
    return list(range(start, end + 1, step))


def _write_plots(
    per_frame: pd.DataFrame,
    summary: dict,
    out_dir: Path,
) -> dict[str, str]:
    import matplotlib.pyplot as plt

    assignment_label = assignment_plot_label(summary)
    assigned = per_frame.loc[per_frame["hasAssignment"] == True]
    outputs: dict[str, str] = {}

    # 1) Histogram of edge counts per frame
    path = out_dir / "edge_counts_histogram.png"
    fig, ax = plt.subplots(figsize=(8, 4.2))
    if not assigned.empty:
        values = assigned["edgeCount"].to_numpy(dtype=int)
        lo, hi = int(values.min()), int(values.max())
        bins = np.arange(lo, hi + 2) - 0.5
        # Unit-width bins → density heights are fractions of frames.
        ax.hist(
            values,
            bins=bins,
            density=True,
            color="#3d6b8c",
            edgecolor="white",
            linewidth=0.6,
        )
        ax.set_xticks(_ticks_0_or_5(lo, hi))
    ax.set_xlabel("Marking edges")
    ax.set_ylabel("Frames")
    ax.set_title(f"Frequency of edge counts across frames — {assignment_label}")
    _style_ax(ax)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    outputs["edgeCountHistogramPng"] = str(Path(path.name))

    # 2) Histogram of max degree per frame
    path = out_dir / "edge_counts_max_degree_histogram.png"
    fig, ax = plt.subplots(figsize=(7, 4.2))
    if not assigned.empty and assigned["maxDegree"].notna().any():
        values = assigned["maxDegree"].dropna().astype(int).to_numpy()
        lo, hi = int(values.min()), int(values.max())
        bins = np.arange(lo, hi + 2) - 0.5
        ax.hist(
            values,
            bins=bins,
            density=True,
            color="#5b8fd9",
            edgecolor="white",
            linewidth=0.6,
        )
        ax.set_xticks(_ticks_0_or_5(lo, hi))
    ax.set_xlabel("Maximum node degree in frame")
    ax.set_ylabel("Frames")
    ax.set_title(f"Max degree per frame — {assignment_label}")
    _style_ax(ax)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    outputs["maxDegreeHistogramPng"] = str(Path(path.name))

    # 3) Stacked bar: degree shares for attackers / defenders
    path = out_dir / "edge_counts_degree_shares.png"
    fig, ax = plt.subplots(figsize=(7.2, 4.5))
    att = summary.get("attackerDegreeShares") or {}
    defn = summary.get("defenderDegreeShares") or {}
    categories = ["Attackers", "Defenders"]
    buckets = [
        ("pctDegree0", "degree 0", "#d9d9d9"),
        ("pctDegree1", "degree 1", "#6fa8c9"),
        ("pctDegree2", "degree 2", "#3d6b8c"),
        ("pctDegree3Plus", "degree 3+", "#1f3d52"),
    ]
    bottoms = [0.0, 0.0]
    x = np.arange(len(categories))
    for key, label, color in buckets:
        heights = [
            float(att.get(key) or 0.0),
            float(defn.get(key) or 0.0),
        ]
        ax.bar(x, heights, bottom=bottoms, color=color, edgecolor="white", width=0.55, label=label)
        for xi, height, bottom in zip(x, heights, bottoms):
            if height < 4.0:
                continue
            # Dark segments get light text; light segments get dark text.
            text_color = "white" if key in ("pctDegree2", "pctDegree3Plus") else "#1f3d52"
            ax.text(
                xi,
                bottom + height / 2.0,
                f"{height:.1f}%",
                ha="center",
                va="center",
                fontsize=8,
                color=text_color,
            )
        bottoms = [b + h for b, h in zip(bottoms, heights)]
    ax.set_xticks(x)
    ax.set_xticklabels(categories)
    ax.set_ylabel("Share of players (%)")
    ax.set_ylim(0, 100)
    ax.set_title(f"Degree distribution by role — {assignment_label}")
    ax.legend(
        frameon=False,
        fontsize=8,
        loc="upper left",
        bbox_to_anchor=(1.02, 1.0),
        borderaxespad=0.0,
    )
    _style_ax(ax)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    outputs["degreeSharesPng"] = str(Path(path.name))

    return outputs
