"""Min-cost perfect matching over all outfield players.

Uses scipy's linear_sum_assignment to minimize total Euclidean distance.
Optional edge restrictions (mirroring website/marking/hungarianMarking.js):
- max_length_m: forbid pairs farther than this distance
- restrict=\"knn\": only pairs that appear in a kNN allow-list
- restrict=\"delaunay\": only bipartite Delaunay opponent edges

Disallowed pairs get an infeasible cost and are dropped after matching if
still selected (incomplete cover when the allow-graph is too sparse).
"""

from __future__ import annotations

from typing import Literal

import numpy as np
from scipy.optimize import linear_sum_assignment

from analysis.assignments.base import Edge
from analysis.assignments.delaunay_graph import DelaunayAssignment
from analysis.assignments.knn import KNN_MODES, KnnAssignment, KnnMode
from analysis.data import Frame

PerfectMatchRestrict = Literal["none", "knn", "delaunay"]

PERFECT_MATCH_RESTRICT_MODES: tuple[PerfectMatchRestrict, ...] = (
    "none",
    "knn",
    "delaunay",
)

_INFEASIBLE = 1e9


class PerfectMatchAssignment:
    name = "perfect_match"

    def __init__(
        self,
        max_length_m: float | None = None,
        restrict: PerfectMatchRestrict = "none",
        k: int = 2,
        knn_mode: KnnMode = "both-all",
    ) -> None:
        if max_length_m is not None and max_length_m <= 0:
            raise ValueError("max_length_m must be positive when set")
        if restrict not in PERFECT_MATCH_RESTRICT_MODES:
            raise ValueError(
                f"restrict must be one of {PERFECT_MATCH_RESTRICT_MODES}, got {restrict!r}"
            )
        if restrict == "knn":
            if k < 1:
                raise ValueError("k must be >= 1")
            if knn_mode not in KNN_MODES:
                raise ValueError(f"knn_mode must be one of {KNN_MODES}, got {knn_mode!r}")

        self.max_length_m = float(max_length_m) if max_length_m is not None else None
        self.restrict: PerfectMatchRestrict = restrict
        self.k = int(k)
        self.knn_mode: KnnMode = knn_mode

        self._knn_mask: KnnAssignment | None = None
        self._delaunay_mask: DelaunayAssignment | None = None
        if restrict == "knn":
            self._knn_mask = KnnAssignment(k=self.k, mode=self.knn_mode)
        elif restrict == "delaunay":
            self._delaunay_mask = DelaunayAssignment()

    def summary_fields(self) -> dict:
        return {
            "pmMaxLength_m": self.max_length_m,
            "pmRestrict": self.restrict,
            "k": self.k if self.restrict == "knn" else None,
            "knnMode": self.knn_mode if self.restrict == "knn" else None,
        }

    def slug(self) -> str:
        if self.restrict == "knn":
            mode = self.knn_mode.replace("-", "_")
            return f"perfect_match__knn_k{self.k}_{mode}"
        if self.restrict == "delaunay":
            return "perfect_match__delaunay"
        if self.max_length_m is not None:
            t = f"{self.max_length_m:g}".replace(".", "p")
            return f"perfect_match__max{t}m"
        return "perfect_match"

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

        allowed = self._allowed_mask(frame, defenders, attackers, cost)
        if allowed is not None:
            cost = np.where(allowed, cost, _INFEASIBLE)

        row_ind, col_ind = linear_sum_assignment(cost)

        edges: list[Edge] = []
        for i, j in zip(row_ind.tolist(), col_ind.tolist()):
            length = float(cost[i, j])
            if length >= _INFEASIBLE:
                continue
            edges.append(
                Edge(
                    defender_id=defenders[i].player_id,
                    attacker_id=attackers[j].player_id,
                    length_m=length,
                )
            )
        return edges

    def _allowed_mask(
        self,
        frame: Frame,
        defenders,
        attackers,
        cost: np.ndarray,
    ) -> np.ndarray | None:
        """Return a boolean (n_def, n_att) allow mask, or None if unrestricted."""
        n_def, n_att = cost.shape
        mask: np.ndarray | None = None

        if self.max_length_m is not None:
            mask = cost <= self.max_length_m

        if self._knn_mask is not None or self._delaunay_mask is not None:
            source = self._knn_mask if self._knn_mask is not None else self._delaunay_mask
            assert source is not None
            pairs = {
                (e.defender_id, e.attacker_id) for e in source.edges_for_frame(frame)
            }
            allow = np.zeros((n_def, n_att), dtype=bool)
            def_index = {p.player_id: i for i, p in enumerate(defenders)}
            att_index = {p.player_id: j for j, p in enumerate(attackers)}
            for def_id, att_id in pairs:
                i = def_index.get(def_id)
                j = att_index.get(att_id)
                if i is not None and j is not None:
                    allow[i, j] = True
            mask = allow if mask is None else (mask & allow)

        return mask
