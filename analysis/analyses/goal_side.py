"""Goal-side orientation of marking edges."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

import pandas as pd

from analysis.analyses.base import AnalysisContext
from analysis.assignments.base import Edge
from analysis.data import Frame
from analysis.pitch import (
    defended_goal_center,
    home_attacks_right_by_period,
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

        attack_right_by_period = home_attacks_right_by_period(frames)

        rows: list[dict] = []
        total_edges = 0
        goal_side_edges = 0
        goal_side_by_period: dict[int, int] = defaultdict(int)
        edges_by_period: dict[int, int] = defaultdict(int)

        for frame, edges in zip(frames, edges_by_frame):
            frame_goal_side = 0
            if frame.defending_team is not None and edges:
                home_attacks_right_flag = attack_right_by_period[frame.period]
                goal = defended_goal_center(frame, home_attacks_right_flag=home_attacks_right_flag)

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
                    "lastTouch": frame.last_touch,
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
    threshold_m = getattr(assignment, "threshold_m", None)

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
        "assignment": assignment.name,
        "threshold_m": threshold_m,
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
