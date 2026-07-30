"""Distance-threshold marking (mirrors website/marking/distanceMarking.js defaults).

Defaults match the viewer with global filters off:
- live frames only
- outfield players only (goalkeepers excluded)
- Euclidean distance on pitch metres (parquet x, y)

Optional momentum_lambda adjusts the threshold distance:
  d' = d - λ * v_towards; reported length_m stays Euclidean.
"""

from __future__ import annotations

import numpy as np

from analysis.assignments.base import Edge
from analysis.assignments.momentum import pairwise_momentum_distance
from analysis.data import Frame


class DistanceThresholdAssignment:
    name = "distance_threshold"

    def __init__(
        self,
        threshold_m: float = 10.0,
        momentum_lambda: float = 0.0,
    ) -> None:
        if threshold_m <= 0:
            raise ValueError("threshold_m must be positive")
        self.threshold_m = float(threshold_m)
        self.momentum_lambda = float(momentum_lambda)

    def edges_for_frame(self, frame: Frame) -> list[Edge]:
        defending = frame.defending_team
        if defending is None:
            return []

        attacking = "away" if defending == "home" else "home"
        defenders = frame.outfield_players(defending)
        attackers = frame.outfield_players(attacking)
        if not defenders or not attackers:
            return []

        d_prime, d_euclid = pairwise_momentum_distance(
            defenders, attackers, self.momentum_lambda
        )
        i_idx, j_idx = np.nonzero(d_prime <= self.threshold_m)

        edges: list[Edge] = []
        for i, j in zip(i_idx.tolist(), j_idx.tolist()):
            edges.append(
                Edge(
                    defender_id=defenders[i].player_id,
                    attacker_id=attackers[j].player_id,
                    length_m=float(d_euclid[i, j]),
                )
            )
        return edges
