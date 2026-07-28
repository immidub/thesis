"""Marking assignment algorithms (Python ports of website/marking)."""

from __future__ import annotations

from typing import Callable

from analysis.assignments.base import Assignment, Edge
from analysis.assignments.distance_threshold import DistanceThresholdAssignment
from analysis.assignments.dynamic_threshold import DynamicThresholdAssignment
from analysis.assignments.knn import KNN_MODES, KnnAssignment
from analysis.assignments.oriented_knn import BEHIND_MODES, OrientedKnnAssignment
from analysis.assignments.meta import (
    assignment_plot_label,
    assignment_slug,
    assignment_summary_fields,
)
from analysis.assignments.perfect_match import PerfectMatchAssignment

ASSIGNMENTS: dict[str, Callable[..., Assignment]] = {
    "distance_threshold": DistanceThresholdAssignment,
    "dynamic_threshold": DynamicThresholdAssignment,
    "perfect_match": PerfectMatchAssignment,
    "knn": KnnAssignment,
    "oriented_knn": OrientedKnnAssignment,
}


def create_assignment(name: str, **kwargs) -> Assignment:
    try:
        cls = ASSIGNMENTS[name]
    except KeyError as exc:
        known = ", ".join(sorted(ASSIGNMENTS))
        raise ValueError(f"Unknown assignment {name!r}. Known: {known}") from exc
    return cls(**kwargs)


__all__ = [
    "ASSIGNMENTS",
    "Assignment",
    "BEHIND_MODES",
    "OrientedKnnAssignment",
    "DistanceThresholdAssignment",
    "DynamicThresholdAssignment",
    "Edge",
    "KNN_MODES",
    "KnnAssignment",
    "PerfectMatchAssignment",
    "assignment_plot_label",
    "assignment_slug",
    "assignment_summary_fields",
    "create_assignment",
]
