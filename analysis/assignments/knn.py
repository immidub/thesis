"""k-NN marking (mirrors website/marking/knnMarking.js direction modes).

Modes:
- defender-to-attacker: each defender links to their k nearest attackers
- attacker-to-defender: each attacker links to their k nearest defenders
- both-mutual: both directions, keep only pairs that appear in both
- both-all: both directions, keep the union of all pairs

Optional momentum_lambda ranks neighbours by d' = d - λ * v_towards;
reported length_m stays Euclidean.
"""

from __future__ import annotations

from typing import Literal

import numpy as np

from analysis.assignments.base import Edge
from analysis.assignments.momentum import pairwise_momentum_distance
from analysis.data import Frame, Player

KnnMode = Literal[
    "defender-to-attacker",
    "attacker-to-defender",
    "both-mutual",
    "both-all",
]

KNN_MODES: tuple[KnnMode, ...] = (
    "defender-to-attacker",
    "attacker-to-defender",
    "both-mutual",
    "both-all",
)


class KnnAssignment:
    name = "knn"

    def __init__(
        self,
        k: int = 1,
        mode: KnnMode = "defender-to-attacker",
        momentum_lambda: float = 0.0,
    ) -> None:
        if k < 1:
            raise ValueError("k must be >= 1")
        if mode not in KNN_MODES:
            raise ValueError(f"mode must be one of {KNN_MODES}, got {mode!r}")
        self.k = int(k)
        self.mode: KnnMode = mode
        self.momentum_lambda = float(momentum_lambda)

    def edges_for_frame(self, frame: Frame) -> list[Edge]:
        defending = frame.defending_team
        if defending is None:
            return []

        attacking = "away" if defending == "home" else "home"
        defenders = list(frame.outfield_players(defending))
        attackers = list(frame.outfield_players(attacking))
        if not defenders or not attackers:
            return []

        rank, euclid = pairwise_momentum_distance(
            defenders, attackers, self.momentum_lambda
        )

        if self.mode == "defender-to-attacker":
            return _directed_knn(
                defenders, attackers, self.k,
                source_is_defender=True, rank=rank, length=euclid,
            )
        if self.mode == "attacker-to-defender":
            return _directed_knn(
                attackers, defenders, self.k,
                source_is_defender=False, rank=rank.T, length=euclid.T,
            )

        def_to_att = _pair_set(
            _directed_knn(
                defenders, attackers, self.k,
                source_is_defender=True, rank=rank, length=euclid,
            )
        )
        att_to_def = _pair_set(
            _directed_knn(
                attackers, defenders, self.k,
                source_is_defender=False, rank=rank.T, length=euclid.T,
            )
        )

        if self.mode == "both-mutual":
            keys = def_to_att.keys() & att_to_def.keys()
        else:  # both-all
            keys = def_to_att.keys() | att_to_def.keys()

        edges: list[Edge] = []
        for key in keys:
            length = def_to_att.get(key)
            if length is None:
                length = att_to_def[key]
            defender_id, attacker_id = key
            edges.append(
                Edge(
                    defender_id=defender_id,
                    attacker_id=attacker_id,
                    length_m=length,
                )
            )
        return edges


def _directed_knn(
    sources: list[Player],
    targets: list[Player],
    k: int,
    *,
    source_is_defender: bool,
    rank: np.ndarray,
    length: np.ndarray,
) -> list[Edge]:
    count = min(k, len(targets))
    nearest = np.argpartition(rank, count - 1, axis=1)[:, :count]

    edges: list[Edge] = []
    for i, source in enumerate(sources):
        for j in nearest[i].tolist():
            edge_len = float(length[i, j])
            if source_is_defender:
                edges.append(
                    Edge(
                        defender_id=source.player_id,
                        attacker_id=targets[j].player_id,
                        length_m=edge_len,
                    )
                )
            else:
                edges.append(
                    Edge(
                        defender_id=targets[j].player_id,
                        attacker_id=source.player_id,
                        length_m=edge_len,
                    )
                )
    return edges


def _pair_set(edges: list[Edge]) -> dict[tuple[str, str], float]:
    return {(e.defender_id, e.attacker_id): e.length_m for e in edges}
