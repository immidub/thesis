"""Temporal stability of marking assignments (switches and durations).

Only live frames with a known defending team contribute. Spells and switch
sequences break across period boundaries, possession changes, and non-assigned
frames (no live ball / no possession) without counting those breaks as switches.
"""

from __future__ import annotations

import json
import statistics
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from analysis.analyses.base import AnalysisContext
from analysis.assignments.base import Edge
from analysis.assignments.meta import assignment_plot_label, assignment_summary_fields
from analysis.data import Frame

# Used only as fallback when gameClock does not advance.
FRAME_RATE_HZ = 50.0


@dataclass
class _OpenSpell:
    start_clock: float
    start_frame_idx: int
    period: int
    defending_team: str


class TemporalStabilityAnalysis:
    name = "temporal_stability"

    def run(
        self,
        frames: list[Frame],
        edges_by_frame: list[list[Edge]],
        ctx: AnalysisContext,
    ) -> dict:
        if len(frames) != len(edges_by_frame):
            raise ValueError("frames and edges_by_frame length mismatch")

        spells: list[dict] = []
        open_spells: dict[tuple[str, str], _OpenSpell] = {}

        # Per defender while continuously in an assigned defending context.
        prev_partners: dict[str, frozenset[str]] = {}
        prev_context: tuple[int, str] | None = None  # (period, defending_team)

        switches_by_defender: dict[str, int] = defaultdict(int)
        active_seconds_by_defender: dict[str, float] = defaultdict(float)
        switches_by_minute: dict[tuple[int, int], int] = defaultdict(int)

        prev_clock: float | None = None

        def close_spell(key: tuple[str, str], end_clock: float, end_frame_idx: int) -> None:
            spell = open_spells.pop(key, None)
            if spell is None:
                return
            duration = max(0.0, float(end_clock) - float(spell.start_clock))
            if duration <= 0.0 and end_frame_idx == spell.start_frame_idx:
                duration = 1.0 / FRAME_RATE_HZ
            defender_id, attacker_id = key
            spells.append(
                {
                    "defenderId": defender_id,
                    "attackerId": attacker_id,
                    "period": spell.period,
                    "defendingTeam": spell.defending_team,
                    "startFrameIdx": spell.start_frame_idx,
                    "endFrameIdx": end_frame_idx,
                    "startGameClock": spell.start_clock,
                    "endGameClock": end_clock,
                    "durationSec": duration,
                }
            )

        def flush_all(end_clock: float, end_frame_idx: int) -> None:
            for key in list(open_spells):
                close_spell(key, end_clock, end_frame_idx)
            prev_partners.clear()

        for frame, edges in zip(frames, edges_by_frame):
            defending = frame.defending_team
            context = (frame.period, defending) if defending is not None else None

            # Non-assigned / dead-ball: close everything, no switch credit.
            if defending is None:
                end_clock = frame.game_clock if prev_clock is None else prev_clock
                flush_all(end_clock, frame.frame_idx)
                prev_context = None
                prev_clock = frame.game_clock
                continue

            # Context break (period or possession): close spells, reset partners.
            if prev_context is not None and context != prev_context:
                flush_all(prev_clock if prev_clock is not None else frame.game_clock, frame.frame_idx)

            defenders = frame.outfield_players(defending)
            defender_ids = {p.player_id for p in defenders}

            partners_by_def: dict[str, set[str]] = {pid: set() for pid in defender_ids}
            current_edges: set[tuple[str, str]] = set()
            for edge in edges:
                if edge.defender_id not in defender_ids:
                    continue
                partners_by_def.setdefault(edge.defender_id, set()).add(edge.attacker_id)
                current_edges.add((edge.defender_id, edge.attacker_id))

            # Close ended edge spells; open new ones.
            end_clock_for_closed = prev_clock if prev_clock is not None else frame.game_clock
            for key in list(open_spells):
                if key not in current_edges:
                    close_spell(key, end_clock_for_closed, frame.frame_idx)
            for key in current_edges:
                if key not in open_spells:
                    open_spells[key] = _OpenSpell(
                        start_clock=frame.game_clock,
                        start_frame_idx=frame.frame_idx,
                        period=frame.period,
                        defending_team=defending,
                    )

            # Switches: partner-set change for defenders still on the pitch.
            dt = 0.0
            if prev_clock is not None and prev_context == context:
                dt = max(0.0, float(frame.game_clock) - float(prev_clock))

            minute = int(np.floor(frame.game_clock / 60.0))
            for defender_id in defender_ids:
                partners = frozenset(partners_by_def.get(defender_id, ()))
                if prev_context == context and defender_id in prev_partners:
                    if partners != prev_partners[defender_id]:
                        switches_by_defender[defender_id] += 1
                        switches_by_minute[(frame.period, minute)] += 1
                if dt > 0.0 and prev_context == context:
                    active_seconds_by_defender[defender_id] += dt
                prev_partners[defender_id] = partners

            # Defenders who left the outfield list drop from prev_partners.
            for defender_id in list(prev_partners):
                if defender_id not in defender_ids:
                    prev_partners.pop(defender_id, None)

            prev_context = context
            prev_clock = frame.game_clock

        # End of match: close remaining spells.
        if frames:
            last = frames[-1]
            flush_all(last.game_clock, last.frame_idx)

        spells_df = pd.DataFrame(spells)
        player_df = _player_switch_table(switches_by_defender, active_seconds_by_defender)
        minute_df = _minute_switch_table(switches_by_minute)

        out_dir = ctx.out_dir
        out_dir.mkdir(parents=True, exist_ok=True)

        spells_path = out_dir / "assignment_spells.csv"
        player_path = out_dir / "switches_per_player.csv"
        minute_path = out_dir / "switches_per_minute.csv"
        spells_df.to_csv(spells_path, index=False)
        player_df.to_csv(player_path, index=False)
        minute_df.to_csv(minute_path, index=False)

        summary = _build_summary(spells_df, player_df, minute_df, ctx)
        plot_paths = _write_plots(spells_df, player_df, minute_df, summary, out_dir)
        summary["outputs"].update(plot_paths)

        summary_path = out_dir / "temporal_stability_summary.json"
        summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
        return summary


def _player_switch_table(
    switches_by_defender: dict[str, int],
    active_seconds_by_defender: dict[str, float],
) -> pd.DataFrame:
    player_ids = sorted(set(switches_by_defender) | set(active_seconds_by_defender))
    rows: list[dict] = []
    for pid in player_ids:
        seconds = float(active_seconds_by_defender.get(pid, 0.0))
        switches = int(switches_by_defender.get(pid, 0))
        minutes = seconds / 60.0
        rows.append(
            {
                "playerId": pid,
                "role": "defender",
                "switches": switches,
                "activeSeconds": seconds,
                "activeMinutes": minutes,
                "switchesPerMinute": (switches / minutes) if minutes > 0 else None,
            }
        )
    return pd.DataFrame(rows)


def _minute_switch_table(switches_by_minute: dict[tuple[int, int], int]) -> pd.DataFrame:
    rows = [
        {
            "period": period,
            "minute": minute,
            "label": f"P{period} {minute}'",
            "switches": int(count),
        }
        for (period, minute), count in sorted(switches_by_minute.items())
    ]
    return pd.DataFrame(rows)


def _mean_or_none(values: list[float]) -> float | None:
    return statistics.fmean(values) if values else None


def _duration_stats(durations: list[float]) -> dict:
    if not durations:
        return {
            "nSpells": 0,
            "meanDurationSec": None,
            "medianDurationSec": None,
            "p95DurationSec": None,
            "maxDurationSec": None,
            "minDurationSec": None,
        }
    arr = np.asarray(durations, dtype=np.float64)
    return {
        "nSpells": int(arr.size),
        "meanDurationSec": float(arr.mean()),
        "medianDurationSec": float(np.median(arr)),
        "p95DurationSec": float(np.percentile(arr, 95)),
        "maxDurationSec": float(arr.max()),
        "minDurationSec": float(arr.min()),
    }


def _build_summary(
    spells_df: pd.DataFrame,
    player_df: pd.DataFrame,
    minute_df: pd.DataFrame,
    ctx: AnalysisContext,
) -> dict:
    assignment = ctx.assignment

    durations = (
        spells_df["durationSec"].astype(float).tolist() if not spells_df.empty else []
    )
    switch_rates = (
        player_df["switchesPerMinute"].dropna().astype(float).tolist()
        if not player_df.empty
        else []
    )
    switches_total = int(player_df["switches"].sum()) if not player_df.empty else 0
    active_minutes_total = (
        float(player_df["activeMinutes"].sum()) if not player_df.empty else 0.0
    )

    return {
        "analysis": "temporal_stability",
        **assignment_summary_fields(assignment),
        "definitions": {
            "spell": (
                "Maximal run of consecutive assigned frames with the same "
                "(defender, attacker) edge, same period and defending team."
            ),
            "switch": (
                "Change of a defender's partner set between consecutive assigned "
                "frames in the same period/possession. Context breaks are not switches."
            ),
            "activeTime": (
                "Seconds a player spends as an outfield defender during assigned play."
            ),
        },
        **_duration_stats(durations),
        "totalSwitches": switches_total,
        "playersWithSwitchData": int(len(player_df)),
        "meanSwitchesPerPlayer": (
            float(player_df["switches"].mean()) if not player_df.empty else None
        ),
        "medianSwitchesPerPlayer": (
            float(player_df["switches"].median()) if not player_df.empty else None
        ),
        "meanSwitchesPerMinutePerPlayer": _mean_or_none(switch_rates),
        "overallSwitchesPerActiveDefenderMinute": (
            switches_total / active_minutes_total if active_minutes_total > 0 else None
        ),
        "liveMinutesWithSwitches": int(len(minute_df)),
        "meanSwitchesPerLiveMinute": (
            float(minute_df["switches"].mean()) if not minute_df.empty else None
        ),
        "outputs": {
            "spellsCsv": str(Path("assignment_spells.csv")),
            "switchesPerPlayerCsv": str(Path("switches_per_player.csv")),
            "switchesPerMinuteCsv": str(Path("switches_per_minute.csv")),
            "summaryJson": str(Path("temporal_stability_summary.json")),
        },
    }


def _style_ax(ax) -> None:
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)


def _write_plots(
    spells_df: pd.DataFrame,
    player_df: pd.DataFrame,
    minute_df: pd.DataFrame,
    summary: dict,
    out_dir: Path,
) -> dict[str, str]:
    import matplotlib.pyplot as plt

    assignment_label = assignment_plot_label(summary)
    outputs: dict[str, str] = {}

    durations = (
        spells_df["durationSec"].to_numpy(dtype=np.float64) if not spells_df.empty else np.array([])
    )

    # 1) Duration histogram
    path = out_dir / "assignment_duration_histogram.png"
    fig, ax = plt.subplots(figsize=(8, 4.2))
    if durations.size:
        # Cap display binning for readability; long tail remains in last bin via clipping for plot only
        bins = [0, 0.5, 1, 2, 3, 5, 8, 12, 20, 30, 60, float("inf")]
        labels = ["0–0.5", "0.5–1", "1–2", "2–3", "3–5", "5–8", "8–12", "12–20", "20–30", "30–60", "60+"]
        finite = bins[:-1] + [max(float(durations.max()) + 1.0, 61.0)]
        counts, _ = np.histogram(durations, bins=finite)
        total = counts.sum()
        shares = [100.0 * c / total if total else 0.0 for c in counts]
        bars = ax.bar(labels, shares, color="#3d6b8c", edgecolor="white", linewidth=0.6)
        for bar, count in zip(bars, counts):
            if count <= 0:
                continue
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height(),
                f"{int(count):,}",
                ha="center",
                va="bottom",
                fontsize=7,
                color="#333333",
            )
        ax.set_ylim(0, max(shares) * 1.18 if shares else 1.0)
    ax.set_xlabel("Assignment duration (s)")
    ax.set_ylabel("Share of spells (%)")
    ax.set_title(f"Assignment duration distribution — {assignment_label}")
    _style_ax(ax)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    outputs["durationHistogramPng"] = str(Path(path.name))

    # 2) Duration CDF
    path = out_dir / "assignment_duration_cdf.png"
    fig, ax = plt.subplots(figsize=(7.5, 4.2))
    if durations.size:
        sorted_d = np.sort(durations)
        y = np.arange(1, sorted_d.size + 1) / sorted_d.size
        ax.plot(sorted_d, y, color="#3d6b8c", linewidth=1.6)
        mean_d = summary.get("meanDurationSec")
        median_d = summary.get("medianDurationSec")
        if median_d is not None:
            ax.axvline(median_d, color="#c0392b", linestyle="--", linewidth=1.2, label=f"median = {median_d:.2f}s")
        if mean_d is not None:
            ax.axvline(mean_d, color="#7f8c8d", linestyle=":", linewidth=1.2, label=f"mean = {mean_d:.2f}s")
        ax.legend(frameon=False, fontsize=8)
        ax.set_xlim(left=0)
        ax.set_ylim(0, 1.02)
    ax.set_xlabel("Assignment duration (s)")
    ax.set_ylabel("CDF")
    ax.set_title(f"Assignment duration CDF — {assignment_label}")
    _style_ax(ax)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    outputs["durationCdfPng"] = str(Path(path.name))

    # 3) Switches per player histogram
    path = out_dir / "switches_per_player_histogram.png"
    fig, ax = plt.subplots(figsize=(7.5, 4.2))
    if not player_df.empty:
        switches = player_df["switches"].astype(int).to_numpy()
        lo, hi = int(switches.min()), int(switches.max())
        bins = np.arange(lo, hi + 2) - 0.5
        ax.hist(switches, bins=bins, color="#5b8fd9", edgecolor="white", linewidth=0.6)
        if hi - lo <= 30:
            ax.set_xticks(range(lo, hi + 1))
    ax.set_xlabel("Switches per player (as defender)")
    ax.set_ylabel("Players")
    ax.set_title(f"Switches per defender — {assignment_label}")
    _style_ax(ax)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    outputs["switchesPerPlayerHistogramPng"] = str(Path(path.name))

    # 4) Switches/minute rate per player
    path = out_dir / "switches_per_minute_per_player_histogram.png"
    fig, ax = plt.subplots(figsize=(7.5, 4.2))
    if not player_df.empty and player_df["switchesPerMinute"].notna().any():
        rates = player_df["switchesPerMinute"].dropna().to_numpy(dtype=np.float64)
        ax.hist(rates, bins=20, color="#3d6b8c", edgecolor="white", linewidth=0.6)
        mean_rate = summary.get("meanSwitchesPerMinutePerPlayer")
        if mean_rate is not None:
            ax.axvline(
                mean_rate,
                color="#c0392b",
                linestyle="--",
                linewidth=1.2,
                label=f"mean = {mean_rate:.2f}/min",
            )
            ax.legend(frameon=False, fontsize=8)
    ax.set_xlabel("Switches per active defending minute")
    ax.set_ylabel("Players")
    ax.set_title(f"Switch rate per defender — {assignment_label}")
    _style_ax(ax)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    outputs["switchRatePerPlayerHistogramPng"] = str(Path(path.name))

    # 5) Switches per live clock-minute
    path = out_dir / "switches_per_minute.png"
    fig, ax = plt.subplots(figsize=(10, 4.2))
    if not minute_df.empty:
        x = np.arange(len(minute_df))
        ax.bar(x, minute_df["switches"], color="#3d6b8c", width=0.85, edgecolor="white")
        step = max(1, len(minute_df) // 12)
        tick_idx = list(range(0, len(minute_df), step))
        ax.set_xticks(tick_idx)
        ax.set_xticklabels(
            [minute_df.iloc[i]["label"] for i in tick_idx],
            rotation=45,
            ha="right",
            fontsize=8,
        )
        mean_line = summary.get("meanSwitchesPerLiveMinute")
        if mean_line is not None:
            ax.axhline(
                mean_line,
                color="#c0392b",
                linestyle="--",
                linewidth=1.2,
                label=f"mean = {mean_line:.1f}",
            )
            ax.legend(frameon=False, fontsize=8)
    ax.set_ylabel("Switches")
    ax.set_xlabel("Match clock minute (assigned play only)")
    ax.set_title(f"Switches per live minute — {assignment_label}")
    _style_ax(ax)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    outputs["switchesPerMinutePng"] = str(Path(path.name))

    return outputs
