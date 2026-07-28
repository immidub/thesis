"""Goal-side oriented mutual kNN.

Variation of the both-mutual kNN assignment: neighbours are ranked by an
anisotropic cost instead of the plain Euclidean distance. For each attacker,
positions are decomposed along the axis from the attacker towards the defended
goal. The along-axis component is divided by alpha (>= 1) when the defender is
on the goal side of the attacker, so goal-side defenders appear closer in the
ranking. The iso-cost contour around an attacker is an ellipse stretched
towards the defended goal.

Two behind modes control the wrong side (defender farther from goal than the
attacker):
- "neutral":  along-axis scale 1 (plain Euclidean behind the attacker)
- "penalize": along-axis scale 1/alpha (wrong-side defenders appear farther)

With alpha = 1 both modes reduce to the plain both-mutual kNN.

The mutual selection uses one shared (defender x attacker) cost matrix for
both ranking directions. Reported edge lengths remain true Euclidean metres so
spatial statistics stay comparable across assignment families.
"""

from __future__ import annotations

from typing import Literal

import numpy as np

from analysis.assignments.base import Edge
from analysis.data import Frame
from analysis.pitch import defended_goal_center, home_goalkeeper_on_positive_x

BehindMode = Literal["neutral", "penalize"]

BEHIND_MODES: tuple[BehindMode, ...] = ("neutral", "penalize")

_EPS = 1e-9


class OrientedKnnAssignment:
    name = "oriented_knn"

    def __init__(
        self,
        k: int = 2,
        alpha: float = 2.0,
        behind_mode: BehindMode = "neutral",
    ) -> None:
        if k < 1:
            raise ValueError("k must be >= 1")
        if alpha < 1.0:
            raise ValueError("alpha must be >= 1")
        if behind_mode not in BEHIND_MODES:
            raise ValueError(f"behind_mode must be one of {BEHIND_MODES}, got {behind_mode!r}")
        self.k = int(k)
        self.alpha = float(alpha)
        self.behind_mode: BehindMode = behind_mode
        # Home-GK-on-+x flag cached per period (first frame seen of each half),
        # mirroring pitch.home_goalkeeper_on_positive_x_by_period.
        self._gk_flag_by_period: dict[int, bool] = {}

    # ---- summary/slug helpers ----

    def summary_fields(self) -> dict:
        return {
            "k": self.k,
            "orientedAlpha": self.alpha,
            "orientedBehindMode": self.behind_mode,
        }

    def slug(self) -> str:
        alpha_str = f"{self.alpha:g}".replace(".", "p")
        return f"oriented_knn__k{self.k}__a{alpha_str}__{self.behind_mode}"

    # ---- assignment ----

    def edges_for_frame(self, frame: Frame) -> list[Edge]:
        defending = frame.defending_team
        if defending is None:
            return []

        attacking = "away" if defending == "home" else "home"
        defenders = list(frame.outfield_players(defending))
        attackers = list(frame.outfield_players(attacking))
        if not defenders or not attackers:
            return []

        goal = self._defended_goal(frame)
        def_xy = np.array([[p.x, p.y] for p in defenders], dtype=np.float64)
        att_xy = np.array([[p.x, p.y] for p in attackers], dtype=np.float64)

        cost, dist = _oriented_cost_matrix(
            def_xy, att_xy, np.asarray(goal, dtype=np.float64),
            alpha=self.alpha, behind_mode=self.behind_mode,
        )

        pairs = _mutual_pairs(cost, self.k)

        edges: list[Edge] = []
        for i, j in pairs:
            edges.append(
                Edge(
                    defender_id=defenders[i].player_id,
                    attacker_id=attackers[j].player_id,
                    length_m=float(dist[i, j]),
                )
            )
        return edges

    def _defended_goal(self, frame: Frame) -> tuple[float, float]:
        flag = self._gk_flag_by_period.get(frame.period)
        if flag is None:
            flag = home_goalkeeper_on_positive_x(frame)
            self._gk_flag_by_period[frame.period] = flag
        return defended_goal_center(frame, home_goalkeeper_on_positive_x_flag=flag)


def _oriented_cost_matrix(
    def_xy: np.ndarray,
    att_xy: np.ndarray,
    goal_xy: np.ndarray,
    *,
    alpha: float,
    behind_mode: BehindMode,
) -> tuple[np.ndarray, np.ndarray]:
    """Return (cost, dist) matrices of shape (n_def, n_att).

    cost is the anisotropic ranking cost, dist the true Euclidean distance.
    Attackers standing (almost) on the goal centre have no defined goal axis
    and fall back to the Euclidean distance.
    """
    to_goal = goal_xy[None, :] - att_xy  # (n_att, 2)
    goal_dist = np.linalg.norm(to_goal, axis=1)  # (n_att,)
    safe_goal_dist = np.where(goal_dist < _EPS, 1.0, goal_dist)
    u = to_goal / safe_goal_dist[:, None]  # unit vectors attacker -> goal

    r = def_xy[:, None, :] - att_xy[None, :, :]  # (n_def, n_att, 2)
    r_par = np.einsum("ijk,jk->ij", r, u)  # signed along-axis component
    dist_sq = np.einsum("ijk,ijk->ij", r, r)
    dist = np.sqrt(dist_sq)
    r_perp_sq = np.maximum(dist_sq - r_par**2, 0.0)

    behind_scale = 1.0 if behind_mode == "neutral" else 1.0 / alpha
    scale = np.where(r_par > 0.0, alpha, behind_scale)  # (n_def, n_att)
    cost = np.sqrt((r_par / scale) ** 2 + r_perp_sq)

    # Degenerate goal axis: use plain distance for those attacker columns.
    degenerate = goal_dist < _EPS  # (n_att,)
    if degenerate.any():
        cost = np.where(degenerate[None, :], dist, cost)
    return cost, dist


def _mutual_pairs(cost: np.ndarray, k: int) -> list[tuple[int, int]]:
    """Mutual kNN pairs (defender_idx, attacker_idx) under a shared cost matrix."""
    n_def, n_att = cost.shape

    k_def = min(k, n_att)  # each defender ranks attackers (rows)
    def_choices = np.argpartition(cost, k_def - 1, axis=1)[:, :k_def]

    k_att = min(k, n_def)  # each attacker ranks defenders (columns)
    att_choices = np.argpartition(cost, k_att - 1, axis=0)[:k_att, :]

    def_pairs = {(i, j) for i in range(n_def) for j in def_choices[i].tolist()}
    att_pairs = {(i, j) for j in range(n_att) for i in att_choices[:, j].tolist()}
    return sorted(def_pairs & att_pairs)
