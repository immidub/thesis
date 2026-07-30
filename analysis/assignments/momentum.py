"""Momentum-adjusted pairwise distances for marking assignments.

d'_ij = d_ij - λ * v_ij^towards

where v_ij^towards is the closing speed along the defender→attacker line
(positive when the pair is approaching). Direction uses atan2(dy, dx)
convention matching parquet kinematics (fix_tracking).
"""

from __future__ import annotations

import math

import numpy as np

from analysis.data import Player

_EPS = 1e-12


def velocity_xy(players: list[Player] | tuple[Player, ...]) -> np.ndarray:
    """(n, 2) velocity from speed (m/s) and direction (degrees). Missing → 0."""
    out = np.zeros((len(players), 2), dtype=np.float64)
    for i, p in enumerate(players):
        if p.speed is None or p.direction is None or p.speed <= 0:
            continue
        rad = math.radians(p.direction)
        out[i, 0] = p.speed * math.cos(rad)
        out[i, 1] = p.speed * math.sin(rad)
    return out


def pairwise_momentum_distance(
    defenders: list[Player] | tuple[Player, ...],
    attackers: list[Player] | tuple[Player, ...],
    momentum_lambda: float = 0.0,
) -> tuple[np.ndarray, np.ndarray]:
    """Return (d_prime, d_euclidean) with shape (n_def, n_att).

    With λ = 0, d_prime equals Euclidean distance.
    """
    def_xy = np.array([[p.x, p.y] for p in defenders], dtype=np.float64)
    att_xy = np.array([[p.x, p.y] for p in attackers], dtype=np.float64)
    delta = att_xy[None, :, :] - def_xy[:, None, :]  # def → att
    dist = np.sqrt(np.einsum("ijk,ijk->ij", delta, delta))

    lam = float(momentum_lambda)
    if lam == 0.0:
        return dist, dist

    # Closing speed: (v_def - v_att) · u_def→att  (>0 when approaching).
    unit = delta / np.maximum(dist, _EPS)[:, :, None]
    v_def = velocity_xy(defenders)
    v_att = velocity_xy(attackers)
    v_rel = v_def[:, None, :] - v_att[None, :, :]
    v_towards = np.einsum("ijk,ijk->ij", v_rel, unit)

    return dist - lam * v_towards, dist
