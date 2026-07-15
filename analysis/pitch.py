"""Pitch geometry helpers for spatial analyses."""

from __future__ import annotations

import numpy as np

from analysis.data import Frame, Player

PITCH_LENGTH_M = 105.0
PITCH_WIDTH_M = 68.0
HALF_LENGTH_M = PITCH_LENGTH_M / 2.0
HALF_WIDTH_M = PITCH_WIDTH_M / 2.0


def goalkeeper(frame: Frame, team: str) -> Player | None:
    players = frame.home_players if team == "home" else frame.away_players
    for player in players:
        if player.is_goalie:
            return player
    return None


def home_goalkeeper_on_positive_x(frame: Frame) -> bool:
    """True when the home goalkeeper is on the +x side of the pitch.
    """
    home_gk = goalkeeper(frame, "home")
    away_gk = goalkeeper(frame, "away")
    if home_gk is not None and away_gk is not None and home_gk.x != away_gk.x:
        return away_gk.x < home_gk.x
    return True


def home_attacks_right_by_period(frames: list[Frame]) -> dict[int, bool]:
    """Attack-direction flag per period, from the first frame of each half."""
    by_period: dict[int, bool] = {}
    for frame in frames:
        if frame.period not in by_period:
            by_period[frame.period] = home_goalkeeper_on_positive_x(frame)
    return by_period


def defended_goal_center(frame: Frame, *, home_attacks_right_flag: bool) -> tuple[float, float]:
    """Centre of the goal defended by the team without possession.

    Matches website getTeamGoalLineH: when home GK is on +x, home's goal is at
    +half length and away's goal is at -half length.
    """
    defending = frame.defending_team
    if defending is None:
        raise ValueError("frame has no defending team")

    if defending == "home":
        goal_x = HALF_LENGTH_M if home_attacks_right_flag else -HALF_LENGTH_M
    else:
        goal_x = -HALF_LENGTH_M if home_attacks_right_flag else HALF_LENGTH_M
    return (goal_x, 0.0)


def player_by_id(frame: Frame, player_id: str) -> Player | None:
    for player in frame.home_players + frame.away_players:
        if player.player_id == player_id:
            return player
    return None


def is_defender_goal_side(
    goal: tuple[float, float],
    attacker_xy: tuple[float, float],
    defender_xy: tuple[float, float],
    *,
    eps: float = 1e-9,
) -> bool:
    """Return True when the defender is goal-side per the G–A line projection rule."""
    g = np.asarray(goal, dtype=np.float64)
    a = np.asarray(attacker_xy, dtype=np.float64)
    d = np.asarray(defender_xy, dtype=np.float64)

    ga = a - g
    ga_len_sq = float(np.dot(ga, ga))
    if ga_len_sq < eps:
        return False

    t = float(np.dot(d - g, ga) / ga_len_sq)
    if t < 0.0 or t > 1.0:
        return False

    projection = g + t * ga
    lateral = float(np.linalg.norm(d - projection))
    to_attacker = float(np.linalg.norm(a - projection))
    return lateral < to_attacker
