#!/usr/bin/env python3
"""
Fix easy tracking jumps and player speed mismatches; mask severe teleports.

Small single-frame spikes are interpolated. Large jumps (or multi-player
teleports) set live=false so analysis that only uses live ball skips them.
When reported player speed disagrees with position deltas by more than 5 m/s,
speed is replaced by the value implied from consecutive positions.

Usage:
    python3 fix_tracking.py
    python3 fix_tracking.py data/tracking.jsonl
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

FRAME_RATE = 50.0
MAX_PLAYER_SPEED_MPS = 14.0 # max speed of a player in m/s
MAX_BALL_SPEED_MPS = 50.0 # max speed of a ball in m/s
MAX_PLAYER_STEP_M = MAX_PLAYER_SPEED_MPS / FRAME_RATE + 0.05 # max step of a player in m per frame
MAX_BALL_STEP_M = MAX_BALL_SPEED_MPS / FRAME_RATE + 0.05 # max step of a ball in m per frame
SPEED_MISMATCH_FIX_MPS = 5.0  # overwrite speed from positions only if gap is larger than this

# Jumps up to these sizes may be interpolated if they look like a 1-frame spike.
BALL_FIX_MAX_M = 5.0
PLAYER_FIX_MAX_M = 3.0

# At least this many simultaneous player jumps → treat as systemic and mask.
SYSTEMIC_PLAYER_JUMP_COUNT = 4


def is_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def step_distance(prev_xyz: list[float], xyz: list[float]) -> float:
    return math.hypot(xyz[0] - prev_xyz[0], xyz[1] - prev_xyz[1])


def valid_xyz(xyz: object) -> bool:
    return isinstance(xyz, list) and len(xyz) == 3 and all(is_number(v) for v in xyz)


def direction_from_positions(prev_xyz: list[float], xyz: list[float]) -> float | None:
    dx = xyz[0] - prev_xyz[0]
    dy = xyz[1] - prev_xyz[1]
    if abs(dx) < 1e-9 and abs(dy) < 1e-9:
        return None
    return round(math.degrees(math.atan2(dy, dx)), 2)


def interpolate_xyz(prev_xyz: list[float], next_xyz: list[float]) -> list[float]:
    return [
        round((prev_xyz[0] + next_xyz[0]) / 2, 2),
        round((prev_xyz[1] + next_xyz[1]) / 2, 2),
        round((prev_xyz[2] + next_xyz[2]) / 2, 2),
    ]


def is_single_frame_spike(
    prev_xyz: list[float],
    curr_xyz: list[float],
    next_xyz: list[float],
    max_step: float,
    fix_max: float,
) -> bool:
    """True when curr is far from prev, but prev→next looks continuous."""
    jump_in = step_distance(prev_xyz, curr_xyz)
    if jump_in <= max_step or jump_in > fix_max:
        return False
    bridge = step_distance(prev_xyz, next_xyz)
    return bridge <= max_step * 2.5


def player_map(players: object) -> dict[str, dict]:
    result: dict[str, dict] = {}
    if not isinstance(players, list):
        return result
    for player in players:
        if isinstance(player, dict) and player.get("playerId") is not None and valid_xyz(player.get("xyz")):
            result[str(player["playerId"])] = player
    return result


def correct_player_speed_mismatches(frames: list[dict]) -> int:
    """Replace reported speed with position-implied speed when they disagree."""
    corrected = 0
    for index in range(1, len(frames)):
        prev_frame = frames[index - 1]
        frame = frames[index]

        if frame.get("live") is not True or prev_frame.get("live") is not True:
            continue
        if prev_frame.get("period") != frame.get("period"):
            continue

        prev_home = player_map(prev_frame.get("homePlayers"))
        prev_away = player_map(prev_frame.get("awayPlayers"))
        curr_home = player_map(frame.get("homePlayers"))
        curr_away = player_map(frame.get("awayPlayers"))

        for prev_players, curr_players in ((prev_home, curr_home), (prev_away, curr_away)):
            for player_id, player in curr_players.items():
                if player_id not in prev_players:
                    continue
                implied_speed = round(
                    step_distance(prev_players[player_id]["xyz"], player["xyz"]) * FRAME_RATE,
                    1,
                )
                reported = player.get("speed")
                if (
                    reported is None
                    or not is_number(reported)
                    or abs(implied_speed - float(reported)) > SPEED_MISMATCH_FIX_MPS
                ):
                    player["speed"] = implied_speed
                    corrected += 1
    return corrected


def recompute_ball_directions(frames: list[dict]) -> None:
    prev_xyz: list[float] | None = None
    prev_direction = 0.0
    for frame in frames:
        ball = frame.get("ball")
        if isinstance(ball, dict) and valid_xyz(ball.get("xyz")):
            xyz = ball["xyz"]
            if prev_xyz is None:
                direction = 0.0
            else:
                direction = direction_from_positions(prev_xyz, xyz)
                if direction is None:
                    direction = prev_direction
            ball["direction"] = direction
            prev_xyz = xyz
            prev_direction = direction
        else:
            prev_xyz = None
            prev_direction = 0.0


def fix_tracking_frames(frames: list[dict]) -> dict[str, int]:
    stats = {
        "ball_interpolated": 0,
        "player_interpolated": 0,
        "masked_not_live": 0,
        "player_speed_corrected": 0,
    }

    for index in range(1, len(frames) - 1):
        prev_frame = frames[index - 1]
        frame = frames[index]
        next_frame = frames[index + 1]

        if frame.get("live") is not True:
            continue
        if prev_frame.get("live") is not True:
            continue
        if prev_frame.get("period") != frame.get("period"):
            continue

        ball = frame.get("ball") if isinstance(frame.get("ball"), dict) else None
        prev_ball = prev_frame.get("ball") if isinstance(prev_frame.get("ball"), dict) else None
        next_ball = next_frame.get("ball") if isinstance(next_frame.get("ball"), dict) else None

        ball_step = 0.0
        if ball and prev_ball and valid_xyz(ball.get("xyz")) and valid_xyz(prev_ball.get("xyz")):
            ball_step = step_distance(prev_ball["xyz"], ball["xyz"])

        prev_home = player_map(prev_frame.get("homePlayers"))
        prev_away = player_map(prev_frame.get("awayPlayers"))
        curr_home = player_map(frame.get("homePlayers"))
        curr_away = player_map(frame.get("awayPlayers"))
        next_home = player_map(next_frame.get("homePlayers"))
        next_away = player_map(next_frame.get("awayPlayers"))

        jumping_players: list[tuple[dict, list[float], list[float] | None, float]] = []
        for side_prev, side_curr, side_next in (
            (prev_home, curr_home, next_home),
            (prev_away, curr_away, next_away),
        ):
            for player_id, player in side_curr.items():
                if player_id not in side_prev:
                    continue
                step = step_distance(side_prev[player_id]["xyz"], player["xyz"])
                if step > MAX_PLAYER_STEP_M:
                    next_xyz = side_next[player_id]["xyz"] if player_id in side_next else None
                    jumping_players.append((player, side_prev[player_id]["xyz"], next_xyz, step))

        # Severe ball teleport, many players jumping together, or a huge single-player
        # teleport → mask as not live (analysis skips these frames).
        severe_ball = ball_step > BALL_FIX_MAX_M
        systemic_players = len(jumping_players) >= SYSTEMIC_PLAYER_JUMP_COUNT
        severe_player = any(step > PLAYER_FIX_MAX_M for _player, _prev, _next, step in jumping_players)

        if severe_ball or systemic_players or severe_player:
            frame["live"] = False
            stats["masked_not_live"] += 1
            continue

        # Easy ball spike: interpolate.
        if (
            ball_step > MAX_BALL_STEP_M
            and ball
            and prev_ball
            and next_ball
            and valid_xyz(next_ball.get("xyz"))
            and is_single_frame_spike(
                prev_ball["xyz"],
                ball["xyz"],
                next_ball["xyz"],
                MAX_BALL_STEP_M,
                BALL_FIX_MAX_M,
            )
        ):
            ball["xyz"] = interpolate_xyz(prev_ball["xyz"], next_ball["xyz"])
            stats["ball_interpolated"] += 1
        elif ball_step > MAX_BALL_STEP_M:
            # Jump is elevated but not a clean 1-frame spike → mask.
            frame["live"] = False
            stats["masked_not_live"] += 1
            continue

        # Easy player spikes: interpolate individually.
        for player, prev_xyz, next_xyz, _step in jumping_players:
            if next_xyz is None:
                frame["live"] = False
                stats["masked_not_live"] += 1
                break
            if is_single_frame_spike(prev_xyz, player["xyz"], next_xyz, MAX_PLAYER_STEP_M, PLAYER_FIX_MAX_M):
                player["xyz"] = interpolate_xyz(prev_xyz, next_xyz)
                stats["player_interpolated"] += 1
            else:
                frame["live"] = False
                stats["masked_not_live"] += 1
                break

    # After positions are settled, fix speed only where it disagrees with movement.
    stats["player_speed_corrected"] = correct_player_speed_mismatches(frames)
    recompute_ball_directions(frames)
    return stats


def load_frames(path: Path) -> list[dict]:
    frames: list[dict] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            frames.append(json.loads(line))
    return frames


def write_frames(path: Path, frames: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for frame in frames:
            handle.write(json.dumps(frame, separators=(",", ":")))
            handle.write("\n")


def fix_tracking_jsonl(path: Path) -> dict[str, int]:
    frames = load_frames(path)
    stats = fix_tracking_frames(frames)
    write_frames(path, frames)
    return stats


def print_fix_stats(stats: dict[str, int], path: Path) -> None:
    print(f"Jump fix: {path}")
    print(f"  Ball positions interpolated:   {stats['ball_interpolated']}")
    print(f"  Player positions interpolated: {stats['player_interpolated']}")
    print(f"  Player speeds corrected:       {stats['player_speed_corrected']}")
    print(f"  Frames masked live=false:      {stats['masked_not_live']}")


def main() -> int:
    repo_root = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "tracking_path",
        nargs="?",
        type=Path,
        default=repo_root / "data" / "tracking.jsonl",
        help="Path to tracking.jsonl (default: data/tracking.jsonl)",
    )
    args = parser.parse_args()
    tracking_path = args.tracking_path.resolve()

    if not tracking_path.is_file():
        print(f"Error: file not found: {tracking_path}", file=sys.stderr)
        return 1

    try:
        stats = fix_tracking_jsonl(tracking_path)
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1

    print_fix_stats(stats, tracking_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
