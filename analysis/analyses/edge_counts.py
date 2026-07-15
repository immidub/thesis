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

        per_minute = _per_minute_table(per_frame)
        per_minute_path = out_dir / "edge_counts_per_minute.csv"
        per_minute.to_csv(per_minute_path, index=False)

        summary = _build_summary(per_frame, per_minute, ctx)

        plot_paths = _write_plots(per_frame, per_minute, summary, out_dir)
        summary["outputs"].update(plot_paths)

        summary_path = out_dir / "edge_counts_summary.json"
        summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

        return summary


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
        "meanDegree": None,
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
    n_nodes = n_def + n_att

    att_shares = _degree_bucket_shares(attacker_degrees)
    def_shares = _degree_bucket_shares(defender_degrees)

    if n_nodes:
        mean_degree = 2.0 * len(edges) / n_nodes
    else:
        mean_degree = None

    max_def = max(defender_degrees) if defender_degrees else None
    max_att = max(attacker_degrees) if attacker_degrees else None
    max_all = max(all_degrees) if all_degrees else None

    base.update(
        {
            "nDefenders": n_def,
            "nAttackers": n_att,
            "meanDegree": mean_degree,
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


def _per_minute_table(per_frame: pd.DataFrame) -> pd.DataFrame:
    """Mean assignments per clock minute, using assigned (live + possession) frames only.

    Clock minutes with no assigned frames are omitted (stoppages / no-possession gaps).
    """
    assigned = per_frame.loc[per_frame["hasAssignment"] == True].copy()
    if assigned.empty:
        return pd.DataFrame(
            columns=[
                "period",
                "minute",
                "label",
                "assignedFrames",
                "meanEdges",
                "totalEdges",
                "meanDegree",
                "meanMaxDegree",
            ]
        )

    assigned["minute"] = np.floor(assigned["gameClock"].to_numpy(dtype=np.float64) / 60.0).astype(
        int
    )
    rows: list[dict] = []
    for (period, minute), group in assigned.groupby(["period", "minute"], sort=True):
        rows.append(
            {
                "period": int(period),
                "minute": int(minute),
                "label": f"P{int(period)} {int(minute)}'",
                "assignedFrames": int(len(group)),
                "meanEdges": float(group["edgeCount"].mean()),
                "totalEdges": int(group["edgeCount"].sum()),
                "meanDegree": float(group["meanDegree"].mean())
                if group["meanDegree"].notna().any()
                else None,
                "meanMaxDegree": float(group["maxDegree"].mean())
                if group["maxDegree"].notna().any()
                else None,
            }
        )
    return pd.DataFrame(rows)


def _agg_degree_block(group: pd.DataFrame) -> dict:
    mean_degree_vals = group["meanDegree"].dropna().tolist()
    max_degree_vals = group["maxDegree"].dropna().tolist()
    max_def_vals = group["maxDefenderDegree"].dropna().tolist()
    max_att_vals = group["maxAttackerDegree"].dropna().tolist()

    return {
        "meanDegree": _mean_or_none(mean_degree_vals),
        "meanMaxDegreePerFrame": _mean_or_none(max_degree_vals),
        "maxDegreeAcrossFrames": int(max(max_degree_vals)) if max_degree_vals else None,
        "meanMaxDefenderDegreePerFrame": _mean_or_none(max_def_vals),
        "meanMaxAttackerDegreePerFrame": _mean_or_none(max_att_vals),
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


def _integer_histogram(values: list[int]) -> list[dict]:
    if not values:
        return []
    counts = Counter(values)
    total = len(values)
    return [
        {
            "value": int(v),
            "count": int(counts[v]),
            "share": float(counts[v] / total),
        }
        for v in sorted(counts)
    ]


def _build_summary(
    per_frame: pd.DataFrame,
    per_minute: pd.DataFrame,
    ctx: AnalysisContext,
) -> dict:
    assignment = ctx.assignment
    threshold_m = getattr(assignment, "threshold_m", None)

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

    max_degrees = (
        assigned["maxDegree"].dropna().astype(int).tolist() if assigned_frames else []
    )
    edge_hist = _integer_histogram([int(c) for c in counts])
    max_degree_hist = _integer_histogram(max_degrees)

    minute_means = per_minute["meanEdges"].dropna().tolist() if not per_minute.empty else []
    mean_edges_per_live_minute = _mean_or_none(minute_means)

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
        "assignment": assignment.name,
        "threshold_m": threshold_m,
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
        "edgeCountHistogram": edge_hist,
        "maxDegreeHistogram": max_degree_hist,
        "perMinute": {
            "liveMinutes": int(len(per_minute)),
            "meanAssignmentsPerLiveMinute": mean_edges_per_live_minute,
            "note": (
                "Each row is a (period, clock-minute) with ≥1 assigned frame "
                "(live ball + known possession). Minutes with only non-live play "
                "or no possession are omitted."
            ),
        },
        "byPeriod": by_period,
        "outputs": {
            "perFrameCsv": str(Path("edge_counts_per_frame.csv")),
            "perMinuteCsv": str(Path("edge_counts_per_minute.csv")),
            "summaryJson": str(Path("edge_counts_summary.json")),
        },
    }


def _style_ax(ax) -> None:
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)


def _write_plots(
    per_frame: pd.DataFrame,
    per_minute: pd.DataFrame,
    summary: dict,
    out_dir: Path,
) -> dict[str, str]:
    import matplotlib.pyplot as plt

    assignment = summary.get("assignment", "assignment")
    assigned = per_frame.loc[per_frame["hasAssignment"] == True]
    outputs: dict[str, str] = {}

    # 1) Histogram of edge counts per frame
    path = out_dir / "edge_counts_histogram.png"
    fig, ax = plt.subplots(figsize=(8, 4.2))
    if not assigned.empty:
        values = assigned["edgeCount"].to_numpy(dtype=int)
        lo, hi = int(values.min()), int(values.max())
        bins = np.arange(lo, hi + 2) - 0.5
        ax.hist(values, bins=bins, color="#3d6b8c", edgecolor="white", linewidth=0.6)
        ax.set_xticks(range(lo, hi + 1))
    ax.set_xlabel("Marking assignments per frame")
    ax.set_ylabel("Frames")
    ax.set_title(f"Assignments per frame — {assignment}")
    _style_ax(ax)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    outputs["edgeCountHistogramPng"] = str(Path(path.name))

    # 2) Mean assignments per live clock-minute
    path = out_dir / "edge_counts_per_minute.png"
    fig, ax = plt.subplots(figsize=(10, 4.2))
    if not per_minute.empty:
        x = np.arange(len(per_minute))
        ax.bar(x, per_minute["meanEdges"], color="#3d6b8c", width=0.85, edgecolor="white")
        step = max(1, len(per_minute) // 12)
        tick_idx = list(range(0, len(per_minute), step))
        ax.set_xticks(tick_idx)
        ax.set_xticklabels(
            [per_minute.iloc[i]["label"] for i in tick_idx],
            rotation=45,
            ha="right",
            fontsize=8,
        )
        mean_line = summary.get("perMinute", {}).get("meanAssignmentsPerLiveMinute")
        if mean_line is not None:
            ax.axhline(
                mean_line,
                color="#c0392b",
                linewidth=1.2,
                linestyle="--",
                label=f"mean over live minutes = {mean_line:.2f}",
            )
            ax.legend(frameon=False, fontsize=8)
    ax.set_ylabel("Mean assignments")
    ax.set_xlabel("Match clock minute (live / assigned only)")
    ax.set_title(f"Mean assignments per live minute — {assignment}")
    _style_ax(ax)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    outputs["perMinutePng"] = str(Path(path.name))

    # 3) Histogram of max degree per frame
    path = out_dir / "edge_counts_max_degree_histogram.png"
    fig, ax = plt.subplots(figsize=(7, 4.2))
    if not assigned.empty and assigned["maxDegree"].notna().any():
        values = assigned["maxDegree"].dropna().astype(int).to_numpy()
        lo, hi = int(values.min()), int(values.max())
        bins = np.arange(lo, hi + 2) - 0.5
        ax.hist(values, bins=bins, color="#5b8fd9", edgecolor="white", linewidth=0.6)
        ax.set_xticks(range(lo, hi + 1))
    ax.set_xlabel("Maximum node degree in frame")
    ax.set_ylabel("Frames")
    ax.set_title(f"Max degree per frame — {assignment}")
    _style_ax(ax)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    outputs["maxDegreeHistogramPng"] = str(Path(path.name))

    # 4) Stacked bar: degree shares for attackers / defenders
    path = out_dir / "edge_counts_degree_shares.png"
    fig, ax = plt.subplots(figsize=(6.5, 4.5))
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
        bottoms = [b + h for b, h in zip(bottoms, heights)]
    ax.set_xticks(x)
    ax.set_xticklabels(categories)
    ax.set_ylabel("Share of players (%)")
    ax.set_ylim(0, 100)
    ax.set_title(f"Degree distribution by role — {assignment}")
    ax.legend(frameon=False, fontsize=8, loc="upper right")
    _style_ax(ax)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    outputs["degreeSharesPng"] = str(Path(path.name))

    return outputs
