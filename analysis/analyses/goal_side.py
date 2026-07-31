"""Goal-side orientation of marking edges."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

from analysis.analyses.base import AnalysisContext
from analysis.assignments.base import Edge
from analysis.assignments.meta import assignment_plot_label, assignment_summary_fields
from analysis.data import Frame
from analysis.pitch import (
    defended_goal_center,
    home_goalkeeper_on_positive_x_by_period,
    is_defender_goal_side,
    player_by_id,
)


class GoalSideAnalysis:
    name = "goal_side"

    def run(
        self,
        frames: list[Frame],
        edges_by_frame: list[list[Edge]],
        ctx: AnalysisContext,
    ) -> dict:
        if len(frames) != len(edges_by_frame):
            raise ValueError("frames and edges_by_frame length mismatch")

        gk_on_positive_x_by_period = home_goalkeeper_on_positive_x_by_period(frames)

        rows: list[dict] = []
        total_edges = 0
        goal_side_edges = 0
        goal_side_by_period: dict[int, int] = defaultdict(int)
        edges_by_period: dict[int, int] = defaultdict(int)

        for frame, edges in zip(frames, edges_by_frame):
            frame_goal_side = 0
            if frame.defending_team is not None and edges:
                home_gk_on_positive_x = gk_on_positive_x_by_period[frame.period]
                goal = defended_goal_center(
                    frame, home_goalkeeper_on_positive_x_flag=home_gk_on_positive_x
                )

                for edge in edges:
                    defender = player_by_id(frame, edge.defender_id)
                    attacker = player_by_id(frame, edge.attacker_id)
                    if defender is None or attacker is None:
                        continue

                    goal_side = is_defender_goal_side(
                        goal,
                        (attacker.x, attacker.y),
                        (defender.x, defender.y),
                    )
                    if goal_side:
                        frame_goal_side += 1

            edge_count = len(edges)
            total_edges += edge_count
            goal_side_edges += frame_goal_side
            if frame.defending_team is not None and edge_count:
                edges_by_period[frame.period] += edge_count
                goal_side_by_period[frame.period] += frame_goal_side

            rows.append(
                {
                    "period": frame.period,
                    "frameIdx": frame.frame_idx,
                    "gameClock": frame.game_clock,
                    "live": frame.live,
                    "attacking": frame.attacking,
                    "defendingTeam": frame.defending_team,
                    "edgeCount": edge_count,
                    "hasAssignment": frame.defending_team is not None,
                    "goalSideCount": frame_goal_side,
                    "goalSideShare": (
                        frame_goal_side / edge_count if edge_count else None
                    ),
                    "notGoalSideCount": edge_count - frame_goal_side if edge_count else None,
                    "notGoalSideShare": (
                        (edge_count - frame_goal_side) / edge_count if edge_count else None
                    ),
                }
            )

        per_frame = pd.DataFrame(rows)
        out_dir = ctx.out_dir
        out_dir.mkdir(parents=True, exist_ok=True)

        per_frame_path = out_dir / "goal_side_per_frame.csv"
        per_frame.to_csv(per_frame_path, index=False)

        summary = _build_summary(
            per_frame,
            total_edges,
            goal_side_edges,
            edges_by_period,
            goal_side_by_period,
            ctx,
        )

        plot_paths = _write_plots(per_frame, summary, out_dir)
        summary["outputs"].update(plot_paths)

        summary_path = out_dir / "goal_side_summary.json"
        summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

        return summary


def _orientation_stats(total_edges: int, goal_side_edges: int) -> dict:
    if total_edges == 0:
        return {
            "nEdges": 0,
            "goalSideCount": 0,
            "notGoalSideCount": 0,
            "goalSideShare": None,
            "notGoalSideShare": None,
            "goalSidePercent": None,
            "notGoalSidePercent": None,
        }

    not_goal_side = total_edges - goal_side_edges
    goal_side_share = goal_side_edges / total_edges
    return {
        "nEdges": total_edges,
        "goalSideCount": goal_side_edges,
        "notGoalSideCount": not_goal_side,
        "goalSideShare": goal_side_share,
        "notGoalSideShare": not_goal_side / total_edges,
        "goalSidePercent": 100.0 * goal_side_share,
        "notGoalSidePercent": 100.0 * not_goal_side / total_edges,
    }


def _build_summary(
    per_frame: pd.DataFrame,
    total_edges: int,
    goal_side_edges: int,
    edges_by_period: dict[int, int],
    goal_side_by_period: dict[int, int],
    ctx: AnalysisContext,
) -> dict:
    assignment = ctx.assignment

    total_frames = int(len(per_frame))
    live_mask = per_frame["live"] == True
    assigned_mask = per_frame["hasAssignment"] == True
    live_frames = int(live_mask.sum())
    assigned_frames = int(assigned_mask.sum())
    frames_with_edges = (
        int((per_frame.loc[assigned_mask, "edgeCount"] > 0).sum()) if assigned_frames else 0
    )

    by_period: dict[str, dict] = {}
    for period in sorted(edges_by_period):
        period_edges = edges_by_period[period]
        period_goal_side = goal_side_by_period.get(period, 0)
        by_period[str(period)] = _orientation_stats(period_edges, period_goal_side)

    return {
        "analysis": "goal_side",
        **assignment_summary_fields(assignment),
        "totalFrames": total_frames,
        "liveFrames": live_frames,
        "assignedFrames": assigned_frames,
        "framesWithAtLeastOneEdge": frames_with_edges,
        **_orientation_stats(total_edges, goal_side_edges),
        "byPeriod": by_period,
        "outputs": {
            "perFrameCsv": str(Path("goal_side_per_frame.csv")),
            "summaryJson": str(Path("goal_side_summary.json")),
        },
    }


def _write_plots(per_frame: pd.DataFrame, summary: dict, out_dir: Path) -> dict[str, str]:
    import matplotlib.pyplot as plt

    assignment_label = assignment_plot_label(summary)
    outputs: dict[str, str] = {}

    # Match-level goal-side vs not
    path = out_dir / "goal_side_share.png"
    fig, ax = plt.subplots(figsize=(5.5, 4.2))
    goal_pct = summary.get("goalSidePercent")
    not_pct = summary.get("notGoalSidePercent")
    if goal_pct is not None and not_pct is not None:
        labels = ["Goal-side", "Not goal-side"]
        vals = [goal_pct, not_pct]
        colors = ["#3d6b8c", "#c0392b"]
        bars = ax.bar(labels, vals, color=colors, edgecolor="white", width=0.55)
        for bar, v in zip(bars, vals):
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height(),
                f"{v:.1f}%",
                ha="center",
                va="bottom",
                fontsize=11,
                fontweight="bold",
                color="#333333",
            )
        ax.set_ylim(0, max(vals) * 1.2)
    ax.set_ylabel("Share of marking edges (%)")
    ax.set_title(f"Goal-side assignments — {assignment_label}")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    outputs["sharePng"] = str(Path(path.name))

    # Per-frame goal-side share histogram (10% bins)
    path = out_dir / "goal_side_per_frame_share_histogram.png"
    fig, ax = plt.subplots(figsize=(7.5, 4.2))
    assigned = per_frame.loc[
        (per_frame["hasAssignment"] == True) & (per_frame["edgeCount"] > 0)
    ]
    if not assigned.empty:
        shares = (100.0 * assigned["goalSideShare"].dropna()).to_numpy(dtype=float)
        bin_edges = list(range(0, 110, 10))
        counts, _ = np.histogram(shares, bins=bin_edges)
        total = int(counts.sum())
        fractions = [c / total if total else 0.0 for c in counts]
        labels = [f"{bin_edges[i]}–{bin_edges[i + 1]}" for i in range(len(counts))]
        bars = ax.bar(labels, fractions, color="#3d6b8c", edgecolor="white", linewidth=0.6)
        for bar, frac in zip(bars, fractions):
            if frac <= 0:
                continue
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height(),
                f"{frac:.2f}",
                ha="center",
                va="bottom",
                fontsize=7.5,
                color="#333333",
            )
        ax.set_ylim(0, max(fractions) * 1.18 if fractions else 1.0)
        ax.text(
            0.99,
            0.97,
            f"mean frame share = {shares.mean():.1f}%",
            transform=ax.transAxes,
            ha="right",
            va="top",
            fontsize=8,
            color="#c0392b",
        )
        ax.tick_params(axis="x", labelrotation=45)
    ax.set_xlabel("Goal-side share in frame (%)")
    ax.set_ylabel("Fraction of frames")
    ax.set_title(f"Per-frame goal-side share — {assignment_label}")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    outputs["perFrameShareHistogramPng"] = str(Path(path.name))

    return outputs
