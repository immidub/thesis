"""Per-match analyses over marking edges.

Planned (not yet implemented):
- node_degrees
- goal_side
- ball_zone
- assignment_switches
- assignment_durations
"""

from __future__ import annotations

from typing import Callable

from analysis.analyses.base import Analysis, AnalysisContext
from analysis.analyses.edge_counts import EdgeCountsAnalysis
from analysis.analyses.edge_lengths import EdgeLengthsAnalysis

ANALYSES: dict[str, Callable[..., Analysis]] = {
    "edge_counts": EdgeCountsAnalysis,
    "edge_lengths": EdgeLengthsAnalysis,
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
    "create_analysis",
]
