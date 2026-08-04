#!/usr/bin/env python3
"""FIFA enriched tracking → tracking.jsonl + metaData.json (Mode A only)."""

from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path

from config import DEFAULT_TEAM_COLORS, FRAME_RATE, PITCH_LENGTH_M, PITCH_WIDTH_M

PLAYER_POSITIONS = {"Outfielder", "Goalkeeper"}


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


def has_enriched_input(input_dir: Path) -> bool:
    """True if input/ looks like a FIFA enriched delivery (meta and/or *_Enriched)."""
    if not input_dir.is_dir():
        return False
    try:
        has_meta = any(input_dir.glob("*Metadata.json"))
        has_enriched = any(
            path.is_dir() and path.name.endswith("_Enriched") for path in input_dir.iterdir()
        )
    except OSError:
        return False
    return has_meta or has_enriched


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


def derive_attacking(
    enriched_model: list[dict],
    home_team_id: int,
    away_team_id: int,
) -> str | None:
    """Map enriched player `attacking` flags to JSONL attacking (home/away team in possession)."""
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
    enriched_model = sample["enrichedModel"]

    for entity in enriched_model:
        position = entity.get("position")
        if position == "BALL":
            ball_xyz = convert_coords(entity["x"], entity["y"], entity["z"])
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

    attacking = derive_attacking(enriched_model, home_team_id, away_team_id)
    if attacking is not None:
        frame["attacking"] = attacking

    if ball_xyz is not None:
        # speed/direction filled later by fix_tracking.recompute_ball_kinematics
        frame["ball"] = {"xyz": ball_xyz}
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
                # Ball speed/direction come from forward position deltas in
                # fix_tracking.recompute_ball_kinematics (enriched ball kinematics were unreliable).

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


def convert_enriched_to_jsonl(input_dir: Path, output_dir: Path) -> int:
    """Mode A: write tracking.jsonl + metaData.json from FIFA enriched input. Returns frame count."""
    enriched_dir, metadata_path = find_input_paths(input_dir)
    enriched_files = list_enriched_files(enriched_dir)

    with metadata_path.open("r", encoding="utf-8") as handle:
        match_metadata = json.load(handle)

    print("Mode: FIFA enriched → tracking.jsonl")
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
    print(f"  wrote {frames_written} frames")

    print("Writing metaData.json...")
    write_metadata_json(match_metadata, goalkeepers, metadata_output_path)
    return frames_written
