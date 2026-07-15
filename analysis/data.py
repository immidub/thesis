"""Load tracking parquet and iterate match frames and players for analysis."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class Player:
    player_id: str
    number: int | None
    x: float
    y: float
    z: float
    speed: float | None = None
    direction: float | None = None
    is_goalie: bool = False


@dataclass(frozen=True)
class Frame:
    period: int
    frame_idx: int
    game_clock: float
    live: bool
    last_touch: str | None
    home_players: tuple[Player, ...]
    away_players: tuple[Player, ...]
    ball: Player | None = None

    @property
    def defending_team(self) -> str | None:
        """Team without possession (mirrors website getDefendingTeam)."""
        if not self.live or self.last_touch not in ("home", "away"):
            return None
        return "away" if self.last_touch == "home" else "home"

    def outfield_players(self, team: str) -> tuple[Player, ...]:
        players = self.home_players if team == "home" else self.away_players
        return tuple(p for p in players if not p.is_goalie)


def load_tracking(parquet_path: Path | str) -> pd.DataFrame:
    path = Path(parquet_path)
    if not path.is_file():
        raise FileNotFoundError(f"Tracking parquet not found: {path}")
    return pd.read_parquet(path)


def iter_frames(
    df: pd.DataFrame,
    *,
    live_only: bool = False,
) -> Iterator[Frame]:
    """Yield frames grouped by (period, frameIdx) in match order."""
    required = {"period", "frameIdx", "gameClock", "live", "team", "x", "y", "z"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Parquet missing columns: {sorted(missing)}")

    work = df
    if live_only:
        work = work.loc[work["live"] == True]
    if work.empty:
        return

    work = work.sort_values(["period", "frameIdx"], kind="mergesort")

    period = work["period"].to_numpy(dtype=np.int32, copy=False)
    frame_idx = work["frameIdx"].to_numpy(dtype=np.int32, copy=False)
    game_clock = work["gameClock"].to_numpy(dtype=np.float64, copy=False)
    live = work["live"].to_numpy(dtype=bool, copy=False)
    last_touch = (
        work["lastTouch"].to_numpy(copy=False)
        if "lastTouch" in work.columns
        else np.full(len(work), None, dtype=object)
    )
    team = work["team"].to_numpy(copy=False)
    player_id = (
        work["playerId"].astype("string").to_numpy(copy=False)
        if "playerId" in work.columns
        else np.full(len(work), "", dtype=object)
    )
    number = (
        work["number"].to_numpy(copy=False)
        if "number" in work.columns
        else np.full(len(work), np.nan)
    )
    is_goalie = (
        work["isGoalie"].fillna(False).to_numpy(dtype=bool, copy=False)
        if "isGoalie" in work.columns
        else np.zeros(len(work), dtype=bool)
    )
    x = work["x"].to_numpy(dtype=np.float64, copy=False)
    y = work["y"].to_numpy(dtype=np.float64, copy=False)
    z = work["z"].to_numpy(dtype=np.float64, copy=False)
    speed = (
        work["speed"].to_numpy(copy=False)
        if "speed" in work.columns
        else np.full(len(work), np.nan)
    )
    direction = (
        work["direction"].to_numpy(copy=False)
        if "direction" in work.columns
        else np.full(len(work), np.nan)
    )

    n = len(work)
    start = 0
    while start < n:
        end = start + 1
        while end < n and period[end] == period[start] and frame_idx[end] == frame_idx[start]:
            end += 1

        home: list[Player] = []
        away: list[Player] = []
        ball: Player | None = None

        for i in range(start, end):
            player = Player(
                player_id="" if player_id[i] is pd.NA else str(player_id[i]),
                number=None if _is_na(number[i]) else int(number[i]),
                x=float(x[i]),
                y=float(y[i]),
                z=float(z[i]),
                speed=None if _is_na(speed[i]) else float(speed[i]),
                direction=None if _is_na(direction[i]) else float(direction[i]),
                is_goalie=bool(is_goalie[i]),
            )
            team_name = str(team[i])
            if team_name == "home":
                home.append(player)
            elif team_name == "away":
                away.append(player)
            elif team_name == "ball":
                ball = player

        touch = last_touch[start]
        if _is_na(touch):
            touch_value = None
        else:
            touch_value = str(touch)

        yield Frame(
            period=int(period[start]),
            frame_idx=int(frame_idx[start]),
            game_clock=float(game_clock[start]),
            live=bool(live[start]),
            last_touch=touch_value,
            home_players=tuple(home),
            away_players=tuple(away),
            ball=ball,
        )
        start = end


def _is_na(value: object) -> bool:
    if value is None or value is pd.NA:
        return True
    try:
        return bool(pd.isna(value))
    except (TypeError, ValueError):
        return False
