"""Pitch geometry helpers for spatial analyses.

Consists of pitch zone and ball zone definitions

Also includes helpers for finding the direction of play and goal side marking edges.

"""

from __future__ import annotations

import numpy as np

from analysis.data import Frame, Player

PITCH_LENGTH_M = 105.0
PITCH_WIDTH_M = 68.0
HALF_LENGTH_M = PITCH_LENGTH_M / 2.0
HALF_WIDTH_M = PITCH_WIDTH_M / 2.0

PITCH_ZONE_COLS = 12  # along length (x)
PITCH_ZONE_ROWS = 8   # along width (y)
CELL_LENGTH_M = PITCH_LENGTH_M / PITCH_ZONE_COLS
CELL_WIDTH_M = PITCH_WIDTH_M / PITCH_ZONE_ROWS

BALL_ZONE_NEAR_M = 5.0
BALL_ZONE_COOPERATION_M = 20.0


def pitch_cell(x: float, y: float) -> tuple[int, int]:
    """Return (col, row) on a 12×8 grid. col along x, row along y; origin = bottom-left of pitch."""
    col = int(np.floor((x + HALF_LENGTH_M) / CELL_LENGTH_M))
    row = int(np.floor((y + HALF_WIDTH_M) / CELL_WIDTH_M))
    col = int(np.clip(col, 0, PITCH_ZONE_COLS - 1))
    row = int(np.clip(row, 0, PITCH_ZONE_ROWS - 1))
    return col, row


def pitch_cell_id(col: int, row: int) -> str:
    return f"c{col}_r{row}"


def pitch_cell_center(col: int, row: int) -> tuple[float, float]:
    x = -HALF_LENGTH_M + (col + 0.5) * CELL_LENGTH_M
    y = -HALF_WIDTH_M + (row + 0.5) * CELL_WIDTH_M
    return x, y


def ball_zone(distance_m: float) -> str:
    """Mutually exclusive ball zones around the ball.

    - zone1_near: ≤ 5 m
    - zone2_cooperation: (5 m, 20 m]
    - zone3_far: > 20 m
    """
    if distance_m <= BALL_ZONE_NEAR_M:
        return "zone1_near"
    if distance_m <= BALL_ZONE_COOPERATION_M:
        return "zone2_cooperation"
    return "zone3_far"


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
