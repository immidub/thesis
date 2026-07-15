"""Shared attacker-centric zone aggregations for pitch/ball zone analyses."""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Callable

import numpy as np
import pandas as pd

from analysis.assignments.base import Edge
from analysis.data import Frame


def attacker_degrees(edges: list[Edge]) -> Counter[str]:
    degrees: Counter[str] = Counter()
    for edge in edges:
        degrees[edge.attacker_id] += 1
    return degrees


def edge_lengths_by_attacker(edges: list[Edge]) -> dict[str, list[float]]:
    lengths: dict[str, list[float]] = defaultdict(list)
    for edge in edges:
        lengths[edge.attacker_id].append(edge.length_m)
    return lengths


def accumulate_zone_frame(
    *,
    zone_of_attacker: dict[str, str],
    degrees: Counter[str],
    lengths_by_attacker: dict[str, list[float]],
    totals: dict[str, dict],
) -> None:
    """Update pooled zone totals from one frame's attackers.

    totals[zone] keys:
      attackers, degreeSum, unmarked, doubleMarked, edges, lengthSum, framesPresent
    """
    zones_seen: set[str] = set()
    for attacker_id, zone in zone_of_attacker.items():
        bucket = totals.setdefault(
            zone,
            {
                "attackers": 0,
                "degreeSum": 0,
                "unmarked": 0,
                "doubleMarked": 0,
                "edges": 0,
                "lengthSum": 0.0,
                "framesPresent": 0,
            },
        )
        deg = int(degrees.get(attacker_id, 0))
        bucket["attackers"] += 1
        bucket["degreeSum"] += deg
        if deg == 0:
            bucket["unmarked"] += 1
        if deg >= 2:
            bucket["doubleMarked"] += 1
        edge_lengths = lengths_by_attacker.get(attacker_id, [])
        bucket["edges"] += len(edge_lengths)
        bucket["lengthSum"] += float(sum(edge_lengths))
        zones_seen.add(zone)

    for zone in zones_seen:
        totals[zone]["framesPresent"] += 1


def finalize_zone_stats(
    totals: dict[str, dict],
    *,
    assigned_frames: int,
    zone_order: list[str] | None = None,
) -> list[dict]:
    zones = zone_order if zone_order is not None else sorted(totals)
    rows: list[dict] = []
    for zone in zones:
        b = totals.get(zone)
        if b is None:
            rows.append(
                {
                    "zone": zone,
                    "attackerObservations": 0,
                    "framesWithAttackerInZone": 0,
                    "meanAttackerDegree": None,
                    "pctUnmarkedAttackers": None,
                    "doubleMarkingRate": None,
                    "totalAssignments": 0,
                    "meanAssignmentsPerAssignedFrame": 0.0,
                    "meanAssignmentsPerFrameWithAttackerInZone": None,
                    "meanEdgeLength": None,
                }
            )
            continue

        n_att = int(b["attackers"])
        n_edges = int(b["edges"])
        frames_present = int(b["framesPresent"])
        rows.append(
            {
                "zone": zone,
                "attackerObservations": n_att,
                "framesWithAttackerInZone": frames_present,
                "meanAttackerDegree": (b["degreeSum"] / n_att) if n_att else None,
                "pctUnmarkedAttackers": (
                    100.0 * b["unmarked"] / n_att if n_att else None
                ),
                "doubleMarkingRate": (
                    100.0 * b["doubleMarked"] / n_att if n_att else None
                ),
                "totalAssignments": n_edges,
                "meanAssignmentsPerAssignedFrame": (
                    n_edges / assigned_frames if assigned_frames else 0.0
                ),
                "meanAssignmentsPerFrameWithAttackerInZone": (
                    n_edges / frames_present if frames_present else None
                ),
                "meanEdgeLength": (
                    b["lengthSum"] / n_edges if n_edges else None
                ),
            }
        )
    return rows


def style_ax(ax) -> None:
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)


ZoneFn = Callable[[Frame, list[Edge]], dict[str, str] | None]
