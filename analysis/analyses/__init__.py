"""Per-match analyses over marking edges.

Planned (not yet implemented):
- node_degrees
- ball_zone
- assignment_switches
- assignment_durations
"""

from __future__ import annotations

from typing import Callable

from analysis.analyses.base import Analysis, AnalysisContext
from analysis.analyses.edge_counts import EdgeCountsAnalysis
from analysis.analyses.edge_lengths import EdgeLengthsAnalysis
from analysis.analyses.goal_side import GoalSideAnalysis

ANALYSES: dict[str, Callable[..., Analysis]] = {
    "edge_counts": EdgeCountsAnalysis,
    "edge_lengths": EdgeLengthsAnalysis,
    "goal_side": GoalSideAnalysis,
}


def create_analysis(name: str, **kwargs) -> Analysis:
    try:
        cls = ANALYSES[name]
    except KeyError as exc:
        known = ", ".join(sorted(ANALYSES))
        raise ValueError(f"Unknown analysis {name!r}. Known: {known}") from exc
    return cls(**kwargs)


__all__ = [
    "ANALYSES",
    "Analysis",
    "AnalysisContext",
    "EdgeCountsAnalysis",
    "EdgeLengthsAnalysis",
    "GoalSideAnalysis",
    "create_analysis",
]
