"""Shared helpers for aggregating existing analysis summaries across parameter sweeps."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from analysis.analyses.ball_zones import BALL_ZONE_ORDER

REQUIRED_ANALYSES = [
    "edge_counts",
    "edge_lengths",
    "goal_side",
    "temporal_stability",
    "ball_zones",
]

PITCH_THIRD_ORDER = ["pitch_defensive_third", "pitch_middle_third", "pitch_attacking_third"]
PITCH_THIRD_LABELS = {
    "pitch_defensive_third": "Defensive third (cols 0–3)",
    "pitch_middle_third": "Middle third (cols 4–7)",
    "pitch_attacking_third": "Attacking third (cols 8–11)",
}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def summary_path(out_dir: Path, analysis: str, slug: str) -> Path:
    return out_dir / analysis / slug / f"{analysis}_summary.json"


def mean_max_distance_per_frame(path: Path) -> float | None:
    """Mean of per-frame max edge length (frames with at least one edge)."""
    if not path.is_file():
        return None
    df = pd.read_csv(path, usecols=["maxDistance", "hasAssignment", "edgeCount"])
    vals = df.loc[
        (df["hasAssignment"] == True) & (df["edgeCount"] > 0), "maxDistance"
    ].dropna()
    if vals.empty:
        return None
    return float(vals.mean())


def mean_degree_from_per_frame(path: Path) -> float | None:
    """Mean node degree over assigned frames: 2 * edges / (attackers + defenders)."""
    if not path.is_file():
        return None
    df = pd.read_csv(
        path, usecols=["edgeCount", "nAttackers", "nDefenders", "hasAssignment"]
    )
    assigned = df.loc[df["hasAssignment"] == True].dropna(
        subset=["edgeCount", "nAttackers", "nDefenders"]
    )
    if assigned.empty:
        return None
    n_players = assigned["nAttackers"] + assigned["nDefenders"]
    valid = assigned.loc[n_players > 0]
    if valid.empty:
        return None
    per_frame = (2.0 * valid["edgeCount"]) / (valid["nAttackers"] + valid["nDefenders"])
    return float(per_frame.mean())


def pitch_col_from_zone_id(zone_id: str) -> int | None:
    if not zone_id.startswith("c") or "_r" not in zone_id:
        return None
    try:
        return int(zone_id.split("_")[0][1:])
    except ValueError:
        return None


def pitch_third(col: int) -> str:
    if col <= 3:
        return "pitch_defensive_third"
    if col <= 7:
        return "pitch_middle_third"
    return "pitch_attacking_third"


def aggregate_pitch_thirds(
    zones: list[dict[str, Any]],
) -> dict[str, dict[str, float | None]]:
    buckets: dict[str, dict[str, float]] = {
        name: {
            "attackerObservations": 0.0,
            "degreeSum": 0.0,
            "unmarked": 0.0,
            "doubleMarked": 0.0,
            "tripleOrMoreMarked": 0.0,
            "edges": 0.0,
            "lengthSum": 0.0,
        }
        for name in PITCH_THIRD_ORDER
    }
    for zone in zones:
        col = pitch_col_from_zone_id(str(zone.get("zone", "")))
        if col is None:
            continue
        third = pitch_third(col)
        n_att = float(zone.get("attackerObservations") or 0)
        mean_deg = zone.get("meanDegree")
        pct_unmarked = zone.get("pctUnmarkedAttackers")
        double_rate = zone.get("doubleMarkingRate")
        triple_rate = zone.get("tripleOrMoreMarkingRate")
        mean_len = zone.get("meanEdgeLength")
        n_edges = float(zone.get("totalAssignments") or 0)

        b = buckets[third]
        b["attackerObservations"] += n_att
        if mean_deg is not None and n_att:
            b["degreeSum"] += float(mean_deg) * n_att
        if pct_unmarked is not None and n_att:
            b["unmarked"] += float(pct_unmarked) / 100.0 * n_att
        if double_rate is not None and n_att:
            b["doubleMarked"] += float(double_rate) / 100.0 * n_att
        if triple_rate is not None and n_att:
            b["tripleOrMoreMarked"] += float(triple_rate) / 100.0 * n_att
        if mean_len is not None and n_edges:
            b["lengthSum"] += float(mean_len) * n_edges
            b["edges"] += n_edges

    out: dict[str, dict[str, float | None]] = {}
    for third, b in buckets.items():
        n_att = b["attackerObservations"]
        n_edges = b["edges"]
        out[third] = {
            "meanDegree": (b["degreeSum"] / n_att) if n_att else None,
            "pctUnmarkedAttackers": (100.0 * b["unmarked"] / n_att) if n_att else None,
            "doubleMarkingRate": (100.0 * b["doubleMarked"] / n_att) if n_att else None,
            "tripleOrMoreMarkingRate": (
                (100.0 * b["tripleOrMoreMarked"] / n_att) if n_att else None
            ),
            "meanEdgeLength": (b["lengthSum"] / n_edges) if n_edges else None,
        }
    return out


def zone_lookup(zones: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(z["zone"]): z for z in zones}


def collect_summary_row(slug: str, out_dir: Path, **extra: Any) -> dict[str, Any]:
    """Collect summary metrics from existing analysis outputs for one assignment slug."""
    row: dict[str, Any] = {"slug": slug, **extra}

    #load the summary files for the analyses
    edge_counts = load_json(out_dir / "edge_counts" / slug / "edge_counts_summary.json")
    edge_lengths = load_json(out_dir / "edge_lengths" / slug / "edge_lengths_summary.json")
    goal_side = load_json(out_dir / "goal_side" / slug / "goal_side_summary.json")
    temporal = load_json(
        out_dir / "temporal_stability" / slug / "temporal_stability_summary.json"
    )
    ball_zones = load_json(out_dir / "ball_zones" / slug / "ball_zones_summary.json")
    pitch_path = out_dir / "pitch_zones" / slug / "pitch_zones_summary.json"
    pitch_zones = load_json(pitch_path) if pitch_path.is_file() else {"zones": []}

    att_shares = edge_counts.get("attackerDegreeShares") or {}

    per_frame_counts = out_dir / "edge_counts" / slug / "edge_counts_per_frame.csv"
    per_frame_lengths = out_dir / "edge_lengths" / slug / "edge_lengths_per_frame.csv"
    mean_deg = edge_counts.get("meanDegree")
    if mean_deg is None:
        mean_deg = mean_degree_from_per_frame(per_frame_counts)
    mean_max_dist = mean_max_distance_per_frame(per_frame_lengths)

    # update the row for each analysis configuration
    row.update(
        {
            "meanMarkingDistance_m": edge_lengths.get("meanDistance"),
            "medianMarkingDistance_m": edge_lengths.get("medianDistance"),
            "p95MarkingDistance_m": edge_lengths.get("p95Distance"),
            "meanMaxMarkingDistancePerFrame_m": mean_max_dist,
            "maxMarkingDistanceOverall_m": edge_lengths.get("maxDistance"),
            "goalSidePercent": goal_side.get("goalSidePercent"),
            "meanAssignmentsPerFrame": edge_counts.get("meanEdgesPerAssignedFrame"),
            "meanDegree": mean_deg,
            "meanMaxAttackerDegreePerFrame": edge_counts.get("meanMaxAttackerDegreePerFrame"),
            "meanMaxDefenderDegreePerFrame": edge_counts.get("meanMaxDefenderDegreePerFrame"),
            "maxAttackerDegreeOverall": edge_counts.get("maxAttackerDegreeAcrossFrames"),
            "maxDefenderDegreeOverall": edge_counts.get("maxDefenderDegreeAcrossFrames"),
            "pctUnmarkedAttackers": att_shares.get("pctDegree0"),
            "pctDoubleMarkedAttackers": att_shares.get("pctDegree2"),
            "pctTriplePlusMarkedAttackers": att_shares.get("pctDegree3Plus"),
            "meanAssignmentDurationSec": temporal.get("meanDurationSec"),
            "medianAssignmentDurationSec": temporal.get("medianDurationSec"),
            "assignmentSwitchesPerMinute": temporal.get(
                "meanSwitchesPerActiveMinutePerPlayer"
            ),
            "totalEdges": edge_counts.get("totalEdges"),
            "assignedFrames": edge_counts.get("assignedFrames"),
        }
    )

    # update the row with the ball zone metrics
    ball_lookup = zone_lookup(ball_zones.get("zones") or [])
    for zone_id in BALL_ZONE_ORDER:
        z = ball_lookup.get(zone_id, {})
        prefix = f"ball_{zone_id}"
        row[f"{prefix}_meanDegree"] = z.get("meanDegree")
        row[f"{prefix}_meanEdgeLength_m"] = z.get("meanEdgeLength")
        row[f"{prefix}_pctUnmarkedAttackers"] = z.get("pctUnmarkedAttackers")
        row[f"{prefix}_doubleMarkingRate"] = z.get("doubleMarkingRate")
        row[f"{prefix}_tripleOrMoreMarkingRate"] = z.get("tripleOrMoreMarkingRate")

    #update the row with the pitch zone metrics
    pitch_thirds = aggregate_pitch_thirds(pitch_zones.get("zones") or [])
    for third in PITCH_THIRD_ORDER:
        z = pitch_thirds.get(third, {})
        prefix = f"{third}"
        row[f"{prefix}_meanDegree"] = z.get("meanDegree")
        row[f"{prefix}_meanEdgeLength_m"] = z.get("meanEdgeLength")
        row[f"{prefix}_pctUnmarkedAttackers"] = z.get("pctUnmarkedAttackers")
        row[f"{prefix}_doubleMarkingRate"] = z.get("doubleMarkingRate")
        row[f"{prefix}_tripleOrMoreMarkingRate"] = z.get("tripleOrMoreMarkingRate")

    return row


def run_is_complete(slug: str, out_dir: Path) -> bool:
    ok = all(summary_path(out_dir, analysis, slug).is_file() for analysis in REQUIRED_ANALYSES)
    manifest = out_dir / "edge_counts" / slug / "run_manifest.json"
    return ok and manifest.is_file()
