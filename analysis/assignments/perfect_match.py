"""Min-cost perfect matching over all outfield players.

Uses scipy's linear_sum_assignment to minimize total Euclidean distance.
Unlike the viewer's hungarianMarking.js, this has no attacker selection,
ball-radius filter, knn/delaunay restrictions, or global edge filters —
just all defending outfield vs all attacking outfield.
"""

from __future__ import annotations

import numpy as np
from scipy.optimize import linear_sum_assignment

from analysis.assignments.base import Edge
from analysis.data import Frame


class PerfectMatchAssignment:
    name = "perfect_match"

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
        delta = def_xy[:, None, :] - att_xy[None, :, :]
        cost = np.sqrt(np.einsum("ijk,ijk->ij", delta, delta))

        row_ind, col_ind = linear_sum_assignment(cost)

        edges: list[Edge] = []
        for i, j in zip(row_ind.tolist(), col_ind.tolist()):
            edges.append(
                Edge(
                    defender_id=defenders[i].player_id,
                    attacker_id=attackers[j].player_id,
                    length_m=float(cost[i, j]),
                )
            )
        return edges
