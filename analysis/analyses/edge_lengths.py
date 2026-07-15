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
        "byPeriod": by_period,
        "outputs": {
            "perFrameCsv": str(Path("edge_lengths_per_frame.csv")),
            "summaryJson": str(Path("edge_lengths_summary.json")),
        },
    }
