"""Count inferred marking edges per frame (and aggregate statistics)."""

from __future__ import annotations

import json
import statistics
from pathlib import Path

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
            rows.append(
                {
                    "period": frame.period,
                    "frameIdx": frame.frame_idx,
                    "gameClock": frame.game_clock,
                    "live": frame.live,
                    "lastTouch": frame.last_touch,
                    "defendingTeam": frame.defending_team,
                    "edgeCount": len(edges),
                    "hasAssignment": frame.defending_team is not None,
                }
            )

        per_frame = pd.DataFrame(rows)
        out_dir = ctx.out_dir
        out_dir.mkdir(parents=True, exist_ok=True)

        per_frame_path = out_dir / "edge_counts_per_frame.csv"
        per_frame.to_csv(per_frame_path, index=False)

        summary = _build_summary(per_frame, ctx)
        summary_path = out_dir / "edge_counts_summary.json"
        summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

        return summary


def _build_summary(per_frame: pd.DataFrame, ctx: AnalysisContext) -> dict:
    assignment = ctx.assignment
    threshold_m = getattr(assignment, "threshold_m", None)

    total_frames = int(len(per_frame))
    live_mask = per_frame["live"] == True
    assigned_mask = per_frame["hasAssignment"] == True
    live_frames = int(live_mask.sum())
    assigned_frames = int(assigned_mask.sum())

    counts = per_frame.loc[assigned_mask, "edgeCount"].tolist()
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

    by_period: dict[str, dict] = {}
    if assigned_frames:
        for period, group in per_frame.loc[assigned_mask].groupby("period"):
            period_counts = group["edgeCount"].tolist()
            by_period[str(int(period))] = {
                "assignedFrames": int(len(period_counts)),
                "totalEdges": int(sum(period_counts)),
                "meanEdges": statistics.fmean(period_counts) if period_counts else 0.0,
                "medianEdges": float(statistics.median(period_counts)) if period_counts else 0.0,
                "maxEdges": int(max(period_counts)) if period_counts else 0,
                "framesWithAtLeastOneEdge": sum(1 for c in period_counts if c > 0),
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
        "byPeriod": by_period,
        "outputs": {
            "perFrameCsv": str(Path("edge_counts_per_frame.csv")),
            "summaryJson": str(Path("edge_counts_summary.json")),
        },
    }
