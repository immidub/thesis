#!/usr/bin/env python3
"""
Validate tracking.jsonl for missing values and live-ball sanity checks.

Usage (from repo root):
    python3 preprocess/validate_tracking.py
    python3 preprocess/validate_tracking.py data/tracking.jsonl
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from config import (
    FRAME_RATE,
    MAX_BALL_SPEED_MPS,
    MAX_BALL_STEP_M,
    MAX_PLAYER_SPEED_MPS,
    MAX_PLAYER_STEP_M,
    SPEED_MISMATCH_REPORT_MPS,
)

PLAYERS_PER_SIDE = 11
MAX_EXAMPLES = 5  # max number of examples to show for each issue


@dataclass
class ValidationReport:
    total_frames: int = 0
    live_frames: int = 0
    issue_counts: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    examples: dict[str, list[str]] = field(default_factory=lambda: defaultdict(list))

    def add(self, issue: str, detail: str) -> None:
        self.issue_counts[issue] += 1
        if len(self.examples[issue]) < MAX_EXAMPLES:
            self.examples[issue].append(detail)


def is_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def frame_label(frame: dict) -> str:
    period = frame.get("period", "?")
    clock = frame.get("gameClock", "?")
    frame_idx = frame.get("frameIdx", "?")
    return f"frameIdx={frame_idx} period={period} gameClock={clock}"


def check_xyz(label: str, xyz: object, report: ValidationReport) -> bool:
    if not isinstance(xyz, list) or len(xyz) != 3:
        report.add("missing_or_invalid_xyz", f"{label}: xyz={xyz!r}")
        return False

    if not all(is_number(value) for value in xyz):
        report.add("missing_or_invalid_xyz", f"{label}: xyz={xyz!r}")
        return False

    return True


def check_speed_direction(label: str, speed: object, direction: object, max_speed: float, report: ValidationReport) -> None:
    if speed is None:
        report.add("missing_speed", label)
    elif not is_number(speed) or speed < 0 or speed > max_speed:
        report.add("invalid_speed", f"{label}: speed={speed!r}")

    if direction is None:
        report.add("missing_direction", label)
    elif not is_number(direction) or direction < -180 or direction > 180:
        report.add("invalid_direction", f"{label}: direction={direction!r}")


def step_distance(prev_xyz: list[float], xyz: list[float]) -> float:
    dx = xyz[0] - prev_xyz[0]
    dy = xyz[1] - prev_xyz[1]
    return math.hypot(dx, dy)


def validate_player(
    player: dict,
    side: str,
    frame: dict,
    prev_players: dict[str, list[float]] | None,
    report: ValidationReport,
) -> None:
    player_id = player.get("playerId")
    number = player.get("number")
    label = f"{frame_label(frame)} {side} playerId={player_id!r} number={number!r}"

    if player_id is None or number is None:
        report.add("missing_player_fields", label)
        return

    xyz = player.get("xyz")
    if not check_xyz(label, xyz, report):
        return

    check_speed_direction(label, player.get("speed"), player.get("direction"), MAX_PLAYER_SPEED_MPS, report)

    if prev_players is not None and player_id in prev_players:
        step = step_distance(prev_players[player_id], xyz)
        if step > MAX_PLAYER_STEP_M:
            report.add(
                "large_player_jump",
                f"{label}: step={step:.2f} m (max {MAX_PLAYER_STEP_M:.2f} m)",
            )

        prev_speed = step * FRAME_RATE
        reported_speed = player.get("speed")
        if is_number(reported_speed) and abs(prev_speed - reported_speed) > SPEED_MISMATCH_REPORT_MPS:
            report.add(
                "player_speed_mismatch",
                f"{label}: reported={reported_speed:.1f} m/s, implied={prev_speed:.1f} m/s",
            )


def validate_frame(
    frame: dict,
    prev_frame: dict | None,
    prev_home: dict[str, list[float]] | None,
    prev_away: dict[str, list[float]] | None,
    report: ValidationReport,
) -> tuple[dict[str, list[float]] | None, dict[str, list[float]] | None]:
    report.total_frames += 1
    live = frame.get("live") is True
    if live:
        report.live_frames += 1

    home_players = frame.get("homePlayers")
    away_players = frame.get("awayPlayers")
    ball = frame.get("ball")

    if not isinstance(home_players, list):
        report.add("missing_home_players", frame_label(frame))
        home_players = []
    if not isinstance(away_players, list):
        report.add("missing_away_players", frame_label(frame))
        away_players = []

    if live:
        if ball is None:
            report.add("missing_ball", frame_label(frame))
        elif not isinstance(ball, dict):
            report.add("missing_ball", f"{frame_label(frame)} ball={ball!r}")
        else:
            ball_label = f"{frame_label(frame)} ball"
            ball_xyz = ball.get("xyz")
            if check_xyz(ball_label, ball_xyz, report):
                check_speed_direction(
                    ball_label,
                    ball.get("speed"),
                    ball.get("direction"),
                    MAX_BALL_SPEED_MPS,
                    report,
                )

                prev_ball = None
                if (
                    prev_frame is not None
                    and prev_frame.get("live") is True
                    and prev_frame.get("period") == frame.get("period")
                    and isinstance(prev_frame.get("ball"), dict)
                ):
                    prev_ball = prev_frame["ball"].get("xyz")

                if isinstance(prev_ball, list) and len(prev_ball) == 3 and all(is_number(v) for v in prev_ball):
                    step = step_distance(prev_ball, ball_xyz)
                    if step > MAX_BALL_STEP_M:
                        report.add(
                            "large_ball_jump",
                            f"{ball_label}: step={step:.2f} m (max {MAX_BALL_STEP_M:.2f} m)",
                        )

        if len(home_players) != PLAYERS_PER_SIDE:
            report.add(
                "unexpected_player_count",
                f"{frame_label(frame)} home={len(home_players)} (expected {PLAYERS_PER_SIDE})",
            )
        if len(away_players) != PLAYERS_PER_SIDE:
            report.add(
                "unexpected_player_count",
                f"{frame_label(frame)} away={len(away_players)} (expected {PLAYERS_PER_SIDE})",
            )

        use_prev_positions = (
            prev_frame is not None
            and prev_frame.get("live") is True
            and prev_frame.get("period") == frame.get("period")
        )
        prev_home_positions = prev_home if use_prev_positions else None
        prev_away_positions = prev_away if use_prev_positions else None

        seen_ids: set[str] = set()
        for player in home_players:
            if not isinstance(player, dict):
                report.add("missing_player_fields", f"{frame_label(frame)} home player={player!r}")
                continue
            player_id = player.get("playerId")
            if player_id in seen_ids:
                report.add("duplicate_player_id", f"{frame_label(frame)} home playerId={player_id!r}")
            elif player_id is not None:
                seen_ids.add(player_id)
            validate_player(player, "home", frame, prev_home_positions, report)

        seen_ids.clear()
        for player in away_players:
            if not isinstance(player, dict):
                report.add("missing_player_fields", f"{frame_label(frame)} away player={player!r}")
                continue
            player_id = player.get("playerId")
            if player_id in seen_ids:
                report.add("duplicate_player_id", f"{frame_label(frame)} away playerId={player_id!r}")
            elif player_id is not None:
                seen_ids.add(player_id)
            validate_player(player, "away", frame, prev_away_positions, report)

    next_home = {
        player["playerId"]: player["xyz"]
        for player in home_players
        if isinstance(player, dict) and player.get("playerId") is not None and isinstance(player.get("xyz"), list)
    }
    next_away = {
        player["playerId"]: player["xyz"]
        for player in away_players
        if isinstance(player, dict) and player.get("playerId") is not None and isinstance(player.get("xyz"), list)
    }
    return next_home, next_away


def validate_tracking_jsonl(path: Path) -> ValidationReport:
    report = ValidationReport()
    prev_frame: dict | None = None
    prev_home: dict[str, list[float]] | None = None
    prev_away: dict[str, list[float]] | None = None

    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                frame = json.loads(line)
            except json.JSONDecodeError as error:
                report.add("invalid_json_line", f"line {line_number}: {error}")
                continue

            prev_home, prev_away = validate_frame(frame, prev_frame, prev_home, prev_away, report)
            prev_frame = frame

    return report


def print_report(report: ValidationReport, path: Path) -> None:
    print(f"Validation report: {path}")
    print(f"  Frames: {report.total_frames} total, {report.live_frames} live")
    print()

    if not report.issue_counts:
        print("  No issues found.")
        return

    print("  Issues:")
    for issue in sorted(report.issue_counts):
        count = report.issue_counts[issue]
        print(f"    {issue}: {count}")
        for example in report.examples[issue]:
            print(f"      - {example}")
    print()
    print(f"  Total issue occurrences: {sum(report.issue_counts.values())}")


def main() -> int:
    repo_root = Path(__file__).resolve().parent.parent
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

    report = validate_tracking_jsonl(tracking_path)
    print_report(report, tracking_path)
    return 1 if report.issue_counts else 0


if __name__ == "__main__":
    raise SystemExit(main())
