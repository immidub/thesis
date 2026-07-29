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
        "dynScale": None,
        "dynMinThreshold_m": None,
        "dynMaxThreshold_m": None,
        "orientedAlpha": None,
        "orientedBehindMode": None,
        "pmMaxLength_m": None,
        "pmRestrict": None,
    }
    if name == "distance_threshold":
        fields["threshold_m"] = float(getattr(assignment, "threshold_m"))
    elif name == "dynamic_threshold":
        fields["dynScale"] = float(getattr(assignment, "scale"))
        fields["dynMinThreshold_m"] = float(getattr(assignment, "min_threshold_m"))
        fields["dynMaxThreshold_m"] = float(getattr(assignment, "max_threshold_m"))
    elif name == "knn":
        fields["k"] = int(getattr(assignment, "k"))
        fields["knnMode"] = str(getattr(assignment, "mode"))
    elif name == "oriented_knn":
        fields.update(assignment.summary_fields())
    elif name == "perfect_match":
        fields.update(assignment.summary_fields())
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
    if name == "dynamic_threshold":
        scale = fields.get("dynScale")
        lo = fields.get("dynMinThreshold_m")
        hi = fields.get("dynMaxThreshold_m")
        if scale is not None and lo is not None and hi is not None:
            return (
                f"dynamic_threshold (x{float(scale):g}, "
                f"{float(lo):g}-{float(hi):g} m)"
            )
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
    if name == "oriented_knn":
        k = fields.get("k")
        alpha = fields.get("orientedAlpha")
        behind = fields.get("orientedBehindMode")
        if k is not None and alpha is not None and behind is not None:
            return f"oriented_knn (k={k}, a={float(alpha):g}, {behind})"
        return name
    if name == "perfect_match":
        restrict = fields.get("pmRestrict") or "none"
        if restrict == "knn":
            k = fields.get("k")
            mode = fields.get("knnMode")
            if k is not None and mode is not None:
                return f"perfect_match (knn k={k}, {mode})"
            return "perfect_match (knn)"
        if restrict == "delaunay":
            return "perfect_match (delaunay)"
        max_len = fields.get("pmMaxLength_m")
        if max_len is not None:
            return f"perfect_match (max {float(max_len):g} m)"
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
    if name == "dynamic_threshold":
        scale = getattr(assignment, "scale", None)
        lo = getattr(assignment, "min_threshold_m", None)
        hi = getattr(assignment, "max_threshold_m", None)
        if scale is None or lo is None or hi is None:
            return "dynamic_threshold"
        scale_str = f"{float(scale):g}".replace(".", "p")
        lo_str = f"{float(lo):g}".replace(".", "p")
        hi_str = f"{float(hi):g}".replace(".", "p")
        return f"dynamic_threshold__s{scale_str}__{lo_str}to{hi_str}m"
    if name == "knn":
        k = getattr(assignment, "k", 1)
        mode = str(getattr(assignment, "mode", "defender-to-attacker")).replace("-", "_")
        return f"knn__k{k}__{mode}"
    if name == "oriented_knn":
        return assignment.slug()
    if name == "perfect_match":
        return assignment.slug()
    return name
