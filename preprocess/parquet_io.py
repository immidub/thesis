#!/usr/bin/env python3
"""Write tracking.parquet from tracking.jsonl (+ optional metaData.json)."""

from __future__ import annotations

import json
from pathlib import Path

from config import PARQUET_BATCH_FRAMES

try:
    import pyarrow as pa
    import pyarrow.parquet as pq
except ImportError:  # pragma: no cover
    pa = None
    pq = None


def _build_goalie_lookup(metadata_path: Path | None) -> dict[str, bool]:
    if metadata_path is None or not metadata_path.is_file():
        return {}

    with metadata_path.open("r", encoding="utf-8") as handle:
        metadata = json.load(handle)

    goalies: dict[str, bool] = {}
    for team_key in ("homeTeam", "awayTeam"):
        team = metadata.get(team_key) or {}
        for player in team.get("players") or []:
            player_id = player.get("id")
            if player_id is None:
                continue
            goalies[str(player_id)] = bool(player.get("isGoalie"))
    return goalies


def _entity_row(
    frame: dict,
    team: str,
    player_id: str | None,
    number: int | None,
    xyz: list[float],
    speed: float | None,
    direction: float | None,
    is_goalie: bool | None,
) -> dict:
    return {
        "period": frame["period"],
        "frameIdx": frame["frameIdx"],
        "gameClock": frame["gameClock"],
        "live": bool(frame.get("live")),
        "attacking": frame.get("attacking"),
        "team": team,
        "playerId": player_id,
        "number": number,
        "isGoalie": is_goalie,
        "x": xyz[0],
        "y": xyz[1],
        "z": xyz[2],
        "speed": speed,
        "direction": direction,
    }


def _frame_to_parquet_rows(frame: dict, goalies: dict[str, bool]) -> list[dict]:
    rows: list[dict] = []

    for team_key, team_name in (("homePlayers", "home"), ("awayPlayers", "away")):
        for player in frame.get(team_key) or []:
            xyz = player.get("xyz")
            if not isinstance(xyz, list) or len(xyz) != 3:
                continue
            player_id = str(player["playerId"]) if player.get("playerId") is not None else None
            is_goalie = goalies.get(player_id) if player_id is not None else None
            rows.append(
                _entity_row(
                    frame,
                    team=team_name,
                    player_id=player_id,
                    number=player.get("number"),
                    xyz=xyz,
                    speed=player.get("speed"),
                    direction=player.get("direction"),
                    is_goalie=is_goalie,
                )
            )

    ball = frame.get("ball")
    if isinstance(ball, dict) and isinstance(ball.get("xyz"), list) and len(ball["xyz"]) == 3:
        rows.append(
            _entity_row(
                frame,
                team="ball",
                player_id=None,
                number=None,
                xyz=ball["xyz"],
                speed=ball.get("speed"),
                direction=ball.get("direction"),
                is_goalie=None,
            )
        )

    return rows


def write_tracking_parquet(
    tracking_path: Path,
    parquet_path: Path,
    metadata_path: Path | None = None,
) -> int:
    """Flatten tracking.jsonl (all frames, live and not) into an entity-per-row parquet."""
    if pa is None or pq is None:
        raise ImportError(
            "pyarrow is required to write parquet. "
            "Install with: python3 -m venv .venv && .venv/bin/pip install pyarrow"
        )

    schema = pa.schema(
        [
            ("period", pa.int8()),
            ("frameIdx", pa.int32()),
            ("gameClock", pa.float64()),
            ("live", pa.bool_()),
            ("attacking", pa.string()),
            ("team", pa.string()),  # home | away | ball
            ("playerId", pa.string()),
            ("number", pa.int16()),
            ("isGoalie", pa.bool_()),
            ("x", pa.float64()),
            ("y", pa.float64()),
            ("z", pa.float64()),
            ("speed", pa.float64()),
            ("direction", pa.float64()),
        ]
    )

    goalies = _build_goalie_lookup(metadata_path)
    parquet_path.parent.mkdir(parents=True, exist_ok=True)

    frames_read = 0
    rows_written = 0
    batch_rows: list[dict] = []

    with pq.ParquetWriter(parquet_path, schema, compression="zstd") as writer:
        with tracking_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                frame = json.loads(line)
                batch_rows.extend(_frame_to_parquet_rows(frame, goalies))
                frames_read += 1

                if frames_read % PARQUET_BATCH_FRAMES == 0:
                    table = pa.Table.from_pylist(batch_rows, schema=schema)
                    writer.write_table(table)
                    rows_written += len(batch_rows)
                    batch_rows = []
                    print(f"  parquet {frames_read} frames ({rows_written} rows)", flush=True)

            if batch_rows:
                table = pa.Table.from_pylist(batch_rows, schema=schema)
                writer.write_table(table)
                rows_written += len(batch_rows)

    print(f"  parquet complete: {frames_read} frames → {rows_written} rows", flush=True)
    return rows_written
