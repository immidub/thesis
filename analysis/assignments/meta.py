"""Assignment identity, params, slugs, and plot/summary labels.

Keeps distance_threshold / knn / perfect_match arg handling in one place so
every analysis can embed the same fields in summaries and plot titles.
"""

from __future__ import annotations

from typing import Any

from analysis.assignments.base import Assignment


def assignment_summary_fields(assignment: Assignment) -> dict[str, Any]:
    """Stable summary keys for every assignment type (unused args are None)."""
    name = assignment.name
    fields: dict[str, Any] = {
        "assignment": name,
        "threshold_m": None,
        "k": None,
        "knnMode": None,
    }
    if name == "distance_threshold":
        fields["threshold_m"] = float(getattr(assignment, "threshold_m"))
    elif name == "knn":
        fields["k"] = int(getattr(assignment, "k"))
        fields["knnMode"] = str(getattr(assignment, "mode"))
    return fields


def assignment_plot_label(source: Assignment | dict[str, Any]) -> str:
    """Human-readable label including key args, for plot titles."""
    if not isinstance(source, dict):
        fields = assignment_summary_fields(source)
    else:
        fields = source

    name = fields.get("assignment") or "assignment"
    if name == "distance_threshold":
        threshold = fields.get("threshold_m")
        if threshold is not None:
            return f"distance_threshold ({float(threshold):g} m)"
        return name
    if name == "knn":
        parts: list[str] = []
        k = fields.get("k")
        mode = fields.get("knnMode")
        if k is not None:
            parts.append(f"k={k}")
        if mode is not None:
            parts.append(str(mode))
        if parts:
            return f"knn ({', '.join(parts)})"
        return name
    return str(name)


def assignment_slug(assignment: Assignment) -> str:
    """Filesystem-safe folder name for one assignment configuration."""
    name = assignment.name
    if name == "distance_threshold":
        threshold = getattr(assignment, "threshold_m", None)
        if threshold is None:
            return "distance_threshold"
        threshold_str = f"{float(threshold):g}".replace(".", "p")
        return f"distance_threshold__t{threshold_str}m"
    if name == "knn":
        k = getattr(assignment, "k", 1)
        mode = str(getattr(assignment, "mode", "defender-to-attacker")).replace("-", "_")
        return f"knn__k{k}__{mode}"
    return name
