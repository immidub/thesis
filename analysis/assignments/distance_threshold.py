"""Distance-threshold marking (mirrors website/marking/distanceMarking.js defaults).

Defaults match the viewer with global filters off:
- live frames only
- outfield players only (goalkeepers excluded)
- Euclidean distance on pitch metres (parquet x, y)
"""

from __future__ import annotations

import math

import numpy as np

from analysis.assignments.base import Edge
from analysis.data import Frame


class DistanceThresholdAssignment:
    name = "distance_threshold"

    def __init__(self, threshold_m: float = 10.0) -> None:
        if threshold_m <= 0:
            raise ValueError("threshold_m must be positive")
        self.threshold_m = float(threshold_m)

    def edges_for_frame(self, frame: Frame) -> list[Edge]:
        defending = frame.defending_team
        if defending is None:
            return []

        attacking = "away" if defending == "home" else "home"
        defenders = frame.outfield_players(defending)
        attackers = frame.outfield_players(attacking)
        if not defenders or not attackers:
            return []

        def_xy = np.array([[p.x, p.y] for p in defenders], dtype=np.float64)
        att_xy = np.array([[p.x, p.y] for p in attackers], dtype=np.float64)
        # (n_def, n_att) squared distances
        delta = def_xy[:, None, :] - att_xy[None, :, :]
        dist_sq = np.einsum("ijk,ijk->ij", delta, delta)

        threshold_sq = self.threshold_m * self.threshold_m
        i_idx, j_idx = np.nonzero(dist_sq <= threshold_sq)

        edges: list[Edge] = []
        for i, j in zip(i_idx.tolist(), j_idx.tolist()):
            edges.append(
                Edge(
                    defender_id=defenders[i].player_id,
                    attacker_id=attackers[j].player_id,
                    length_m=math.sqrt(float(dist_sq[i, j])),
                )
            )
        return edges
