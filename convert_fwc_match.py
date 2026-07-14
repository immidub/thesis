#!/usr/bin/env python3
"""
Convert FIFA enriched tracking + unified match metadata into the formats
expected by the website (tracking.jsonl and metaData.json), plus an analysis
parquet (tracking.parquet) with one row per entity per frame.

Usage (from repo root):
    python3 convert_fwc_match.py
    python3 convert_fwc_match.py --input-dir input --output-dir data

Parquet writing requires pyarrow (see requirements.txt).
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from collections import defaultdict
from pathlib import Path

from validate_tracking import print_report, validate_tracking_jsonl
from fix_tracking import fix_tracking_jsonl, print_fix_stats

try:
    import pyarrow as pa
    import pyarrow.parquet as pq
except ImportError:  # pragma: no cover - validated at write time
    pa = None
    pq = None

PITCH_LENGTH_M = 105.0
PITCH_WIDTH_M = 68.0
FRAME_RATE = 50.0
PLAYER_POSITIONS = {"Outfielder", "Goalkeeper"}

DEFAULT_TEAM_COLORS = {
    "home": {"colorShirt": "#B73B92", "colorNumber": "#fff"},
    "away": {"colorShirt": "#3395AB", "colorNumber": "#fff"},
}


def parse_enriched_filename(path: Path) -> tuple[int, int, int] | None:
    match = re.search(r"_(\d+)_(\d+)_(\d+)\.football", path.name)
    if not match:
        return None
    return tuple(int(part) for part in match.groups())


def title_case_team(name: str) -> str:
    return " ".join(part.capitalize() for part in name.strip().split())


def parse_wall_clock_time(value: str | None) -> int | None:
    """Parse HH:MM:SS (or MM:SS) into seconds"""
    if not value or not isinstance(value, str):
        return None

    parts = value.strip().split(":")
    try:
        if len(parts) == 3:
            hours, minutes, seconds = (int(part) for part in parts)
        elif len(parts) == 2:
            hours = 0
            minutes, seconds = (int(part) for part in parts)
        else:
            return None
    except ValueError:
        return None

    if minutes < 0 or minutes >= 60 or seconds < 0 or seconds >= 60 or hours < 0:
        return None

    return hours * 3600 + minutes * 60 + seconds


def find_phase(phases: list[dict] | None, phase_id: int) -> dict | None:
    if not phases:
        return None

    for phase in phases:
        if phase.get("phase_id") == phase_id:
            return phase
    return None


def build_video_sync(match_metadata: dict) -> dict[str, int]:
    """Map FIFA video_kickoff_time + phase anchors to MP4 wall-clock seconds."""
    kickoff_sec = parse_wall_clock_time(match_metadata.get("video_kickoff_time"))
    if kickoff_sec is None:
        return {}

    phases = match_metadata.get("phases")
    phase_one = find_phase(phases, 1)
    phase_two = find_phase(phases, 2)

    video_sync: dict[str, int] = {
        "firstHalfStartSec": kickoff_sec,
    }

    if phase_one:
        phase_one_start = parse_wall_clock_time(phase_one.get("phase_start"))
        phase_one_end = parse_wall_clock_time(phase_one.get("phase_end"))
        if phase_one_end is not None:
            phase_one_start_sec = phase_one_start if phase_one_start is not None else 0
            video_sync["firstHalfEndSec"] = kickoff_sec + (phase_one_end - phase_one_start_sec)

    if phase_two:
        phase_two_start = parse_wall_clock_time(phase_two.get("phase_start"))
        phase_two_end = parse_wall_clock_time(phase_two.get("phase_end"))
        if phase_two_start is not None:
            video_sync["secondHalfStartSec"] = kickoff_sec + phase_two_start
        if phase_two_end is not None:
            video_sync["secondHalfEndSec"] = kickoff_sec + phase_two_end

    return video_sync


def build_player_id_map(match_metadata: dict) -> dict[int, str]:
    """Map enriched numeric playerId to metadata player_id strings."""
    player_ids: dict[int, str] = {}
    for player in match_metadata["home_team_players"] + match_metadata["away_team_players"]:
        player_ids[player["player_id"]] = str(player["player_id"])
    return player_ids


def convert_coords(x_cm: float, y_cm: float, z_cm: float) -> list[float]:
    return [
        round(x_cm / 100.0 - PITCH_LENGTH_M / 2, 2),
        round(y_cm / 100.0 - PITCH_WIDTH_M / 2, 2),
        round(z_cm / 100.0, 2),
    ]


def find_input_paths(input_dir: Path) -> tuple[Path, Path]:
    metadata_files = sorted(input_dir.glob("*Metadata.json"))
    enriched_dirs = sorted(
        path for path in input_dir.iterdir() if path.is_dir() and path.name.endswith("_Enriched")
    )

    if len(metadata_files) != 1:
        raise FileNotFoundError(
            f"Expected exactly one *Metadata.json in {input_dir}, found {len(metadata_files)}"
        )
    if len(enriched_dirs) != 1:
        raise FileNotFoundError(
            f"Expected exactly one *_Enriched folder in {input_dir}, found {len(enriched_dirs)}"
        )

    return enriched_dirs[0], metadata_files[0]


def list_enriched_files(enriched_dir: Path) -> list[Path]:
    files = [path for path in enriched_dir.glob("*.enriched") if parse_enriched_filename(path)]
    files.sort(key=lambda path: parse_enriched_filename(path))
    if not files:
        raise FileNotFoundError(f"No .enriched files found in {enriched_dir}")
    return files


def scan_enriched_files(enriched_files: list[Path]) -> tuple[dict[int, tuple[Path, int]], set[int], int | None]:
    frame_refs: dict[int, tuple[Path, int]] = {}
    goalkeepers: set[int] = set()
    period_two_start: int | None = None

    for file_index, enriched_path in enumerate(enriched_files):
        with enriched_path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)

        for sample_index, sample in enumerate(payload["samples"]):
            entities = sample["enrichedModel"]
            frame_count = min(entity["frameCount"] for entity in entities)

            if frame_count not in frame_refs:
                frame_refs[frame_count] = (enriched_path, sample_index)

            for entity in entities:
                if entity.get("position") == "Goalkeeper" and entity.get("teamId", 0) > 0:
                    goalkeepers.add(entity["playerId"])
                if entity.get("halfId") == 2 and period_two_start is None:
                    period_two_start = frame_count

        if (file_index + 1) % 10 == 0 or file_index + 1 == len(enriched_files):
            print(f"  scanned {file_index + 1}/{len(enriched_files)} enriched files", flush=True)

    if period_two_start is None:
        raise ValueError("Could not determine the start frame for period 2")

    return frame_refs, goalkeepers, period_two_start


def build_player_entry(entity: dict, player_id_map: dict[int, str]) -> dict | None:
    enriched_id = entity["playerId"]
    player_id = player_id_map.get(enriched_id)
    if player_id is None:
        return None

    speed = entity.get("speed")
    direction = entity.get("direction")
    return {
        "playerId": player_id,
        "number": entity["jerseyNumber"],
        "xyz": convert_coords(entity["x"], entity["y"], entity["z"]),
        "speed": round(float(speed), 1) if speed is not None else 0.0,
        "direction": round(float(direction), 2) if direction is not None else 0.0,
    }


def derive_last_touch(
    enriched_model: list[dict],
    home_team_id: int,
    away_team_id: int,
) -> str | None:
    """Map enriched player `attacking` flags to JSONL lastTouch (home/away team in possession)."""
    attacking_team_ids = {
        entity["teamId"]
        for entity in enriched_model
        if entity.get("position") in PLAYER_POSITIONS and entity.get("attacking") is True
    }
    if len(attacking_team_ids) != 1:
        return None

    team_id = next(iter(attacking_team_ids))
    if team_id == home_team_id:
        return "home"
    if team_id == away_team_id:
        return "away"
    return None


def derive_live(enriched_model: list[dict]) -> bool:
    """Map enriched ball `ballAlive` to JSONL live (ball in play)."""
    ball = next((entity for entity in enriched_model if entity.get("position") == "BALL"), None)
    if ball is None:
        return False
    return bool(ball.get("ballAlive"))


def direction_from_positions(prev_xyz: list[float], xyz: list[float]) -> float | None:
    """Infer direction degrees (-180..180) from frame-to-frame position delta."""
    dx = xyz[0] - prev_xyz[0]
    dy = xyz[1] - prev_xyz[1]
    if abs(dx) < 1e-9 and abs(dy) < 1e-9:
        return None
    return round(math.degrees(math.atan2(dy, dx)), 2)


def sample_to_frame(
    sample: dict,
    frame_idx: int,
    frame_count: int,
    home_team_id: int,
    away_team_id: int,
    period_two_start: int,
    player_id_map: dict[int, str],
) -> dict:
    period = 1 if frame_count < period_two_start else 2
    period_start = 1 if period == 1 else period_two_start
    game_clock = round((frame_count - period_start) / FRAME_RATE, 2)

    home_players: list[dict] = []
    away_players: list[dict] = []
    ball_xyz: list[float] | None = None
    ball_speed: float | None = None
    enriched_model = sample["enrichedModel"]

    for entity in enriched_model:
        position = entity.get("position")
        if position == "BALL":
            ball_xyz = convert_coords(entity["x"], entity["y"], entity["z"])
            speed = entity.get("speed")
            ball_speed = round(float(speed), 1) if speed is not None else None
            continue
        if position not in PLAYER_POSITIONS:
            continue

        team_id = entity.get("teamId")
        player_entry = build_player_entry(entity, player_id_map)
        if player_entry is None:
            continue
        if team_id == home_team_id:
            home_players.append(player_entry)
        elif team_id == away_team_id:
            away_players.append(player_entry)

    home_players.sort(key=lambda player: player["number"])
    away_players.sort(key=lambda player: player["number"])

    frame = {
        "period": period,
        "frameIdx": frame_idx,
        "gameClock": game_clock,
        "live": derive_live(enriched_model),
        "homePlayers": home_players,
        "awayPlayers": away_players,
    }

    last_touch = derive_last_touch(enriched_model, home_team_id, away_team_id)
    if last_touch is not None:
        frame["lastTouch"] = last_touch

    if ball_xyz is not None:
        ball: dict = {"xyz": ball_xyz}
        if ball_speed is not None:
            ball["speed"] = ball_speed
        frame["ball"] = ball
    return frame


def write_tracking_jsonl(
    enriched_files: list[Path],
    frame_refs: dict[int, tuple[Path, int]],
    output_path: Path,
    match_metadata: dict,
    period_two_start: int,
) -> int:
    home_team_id = match_metadata["home_team_id"]
    away_team_id = match_metadata["away_team_id"]
    player_id_map = build_player_id_map(match_metadata)
    samples_by_file: dict[Path, list[tuple[int, int]]] = defaultdict(list)

    for frame_count in sorted(frame_refs):
        enriched_path, sample_index = frame_refs[frame_count]
        samples_by_file[enriched_path].append((frame_count, sample_index))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    frame_total = len(frame_refs)
    frames_written = 0
    prev_ball_xyz: list[float] | None = None
    prev_ball_direction: float = 0.0

    with output_path.open("w", encoding="utf-8") as output_handle:
        for file_index, enriched_path in enumerate(enriched_files):
            pending = samples_by_file.get(enriched_path)
            if not pending:
                continue

            with enriched_path.open("r", encoding="utf-8") as handle:
                payload = json.load(handle)

            for frame_count, sample_index in pending:
                frame = sample_to_frame(
                    payload["samples"][sample_index],
                    frame_idx=frames_written,
                    frame_count=frame_count,
                    home_team_id=home_team_id,
                    away_team_id=away_team_id,
                    period_two_start=period_two_start,
                    player_id_map=player_id_map,
                )
                # Infer ball direction from position deltas; enriched direction values for the ball were unreliable.
                # Uses previous-frame coords even when that frame was not live. No prior ball track → 0;
                # stationary ball → reuse previous direction.
                ball = frame.get("ball")
                if isinstance(ball, dict) and isinstance(ball.get("xyz"), list):
                    if prev_ball_xyz is None:
                        direction = 0.0
                    else:
                        direction = direction_from_positions(prev_ball_xyz, ball["xyz"])
                        if direction is None:
                            direction = prev_ball_direction
                    ball["direction"] = direction
                    prev_ball_xyz = ball["xyz"]
                    prev_ball_direction = direction
                else:
                    prev_ball_xyz = None
                    prev_ball_direction = 0.0

                output_handle.write(json.dumps(frame, separators=(",", ":")))
                output_handle.write("\n")
                frames_written += 1

                if frames_written % 10000 == 0 or frames_written == frame_total:
                    print(f"  wrote {frames_written}/{frame_total} frames", flush=True)

            if (file_index + 1) % 10 == 0 or file_index + 1 == len(enriched_files):
                print(f"  processed {file_index + 1}/{len(enriched_files)} enriched files", flush=True)

    return frames_written


def build_team_metadata(players: list[dict], goalkeepers: set[int], colors: dict[str, str]) -> dict:
    roster = []
    for player in sorted(players, key=lambda entry: entry["player_shirt_number"]):
        player_id = player["player_id"]
        roster.append(
            {
                "id": str(player_id),
                "shirtNumber": player["player_shirt_number"],
                "isGoalie": player_id in goalkeepers,
            }
        )

    return {
        "colorShirt": colors["colorShirt"],
        "colorNumber": colors["colorNumber"],
        "players": roster,
    }

## --------- PARQUET WRITING --------- ##

PARQUET_BATCH_FRAMES = 2000


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
        "lastTouch": frame.get("lastTouch"),
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
            ("lastTouch", pa.string()),
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


## --------- METADATA WRITING --------- ##

def write_metadata_json(
    match_metadata: dict,
    goalkeepers: set[int],
    output_path: Path,
) -> None:
    metadata = {
        "homeTeam": {
            "name": title_case_team(match_metadata["home_team_name"]),
            **build_team_metadata(
                match_metadata["home_team_players"],
                goalkeepers,
                DEFAULT_TEAM_COLORS["home"],
            ),
        },
        "awayTeam": {
            "name": title_case_team(match_metadata["away_team_name"]),
            **build_team_metadata(
                match_metadata["away_team_players"],
                goalkeepers,
                DEFAULT_TEAM_COLORS["away"],
            ),
        },
    }

    video_sync = build_video_sync(match_metadata)
    if video_sync:
        metadata["videoSync"] = video_sync

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(metadata, handle, indent=2)
        handle.write("\n")


def convert_match(input_dir: Path, output_dir: Path) -> None:
    enriched_dir, metadata_path = find_input_paths(input_dir)
    enriched_files = list_enriched_files(enriched_dir)

    with metadata_path.open("r", encoding="utf-8") as handle:
        match_metadata = json.load(handle)

    print(f"Input enriched dir: {enriched_dir}")
    print(f"Input metadata:     {metadata_path}")
    print(f"Output dir:         {output_dir}")
    print("Scanning enriched files...")
    frame_refs, goalkeepers, period_two_start = scan_enriched_files(enriched_files)
    print(f"Unique frames: {len(frame_refs)}")
    print(f"Period 2 starts at frameCount {period_two_start}")
    print(f"Goalkeepers detected: {len(goalkeepers)}")

    tracking_path = output_dir / "tracking.jsonl"
    metadata_output_path = output_dir / "metaData.json"

    print("Writing tracking.jsonl...")
    frames_written = write_tracking_jsonl(
        enriched_files,
        frame_refs,
        tracking_path,
        match_metadata,
        period_two_start,
    )

    print("Writing metaData.json...")
    write_metadata_json(match_metadata, goalkeepers, metadata_output_path)

    print("Fixing tracking jumps...")
    fix_stats = fix_tracking_jsonl(tracking_path)
    print_fix_stats(fix_stats, tracking_path)

    print("Validating tracking.jsonl...")
    validation_report = validate_tracking_jsonl(tracking_path)
    print_report(validation_report, tracking_path)

    parquet_path = output_dir / "tracking.parquet"
    print("Writing tracking.parquet...")
    parquet_rows = write_tracking_parquet(tracking_path, parquet_path, metadata_output_path)

    print("Done.")
    print(f"  {tracking_path} ({frames_written} frames)")
    print(f"  {metadata_output_path}")
    print(f"  {parquet_path} ({parquet_rows} rows)")


def main() -> int:
    repo_root = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=repo_root / "input",
        help="Directory containing enriched tracking and unified metadata JSON",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=repo_root / "data",
        help="Directory for tracking.jsonl, metaData.json, and tracking.parquet",
    )
    args = parser.parse_args()

    try:
        convert_match(args.input_dir.resolve(), args.output_dir.resolve())
    except (FileNotFoundError, ValueError, KeyError, json.JSONDecodeError, ImportError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
