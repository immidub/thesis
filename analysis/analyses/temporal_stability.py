"""Assignment-spell durations and defender marking switches.

Spell: maximal run of the same (defender, attacker) edge while period and
defending team stay the same and consecutive processed frames are within
MAX_FRAME_GAP frameIdx steps.

Switch: within continuous defending possession, a defender's partner set
(the attackers they mark, possibly empty) changes vs the previous continuous
frame. Period ends, non-live / non-assigned gaps, and possession changes reset
context and do not count as switches.
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

FRAME_RATE_HZ = 50.0
# Same-period frames are continuous if frameIdx advances by at most this much.
MAX_FRAME_GAP = 2

DURATION_HIST_EDGES = (0.0, 0.5, 1.0, 2.0, 3.0, 5.0, 8.0, 12.0, 20.0, 30.0, 60.0, float("inf"))
DURATION_HIST_LABELS = (
    "0–0.5",
    "0.5–1",
    "1–2",
    "2–3",
    "3–5",
    "5–8",
    "8–12",
    "12–20",
    "20–30",
    "30–60",
    "60+",
)


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

        switches_by_defender: dict[str, int] = defaultdict(int)
        active_seconds_by_defender: dict[str, float] = defaultdict(float)
        prev_partners: dict[str, frozenset[str]] = {}

        prev_clock: float | None = None
        prev_frame_idx: int | None = None
        prev_period: int | None = None
        prev_defending: str | None = None

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

        def flush_spells(end_clock: float, end_frame_idx: int) -> None:
            for key in list(open_spells):
                close_spell(key, end_clock, end_frame_idx)

        def reset_switch_context() -> None:
            prev_partners.clear()

        # Iterate through all frames and corresponding edges
        for frame, edges in zip(frames, edges_by_frame):
            defending = frame.defending_team

            # Determine if possession, period, and frame sequence is still "continuous"
            continuous = (
                prev_frame_idx is not None
                and prev_period == frame.period
                and prev_defending is not None
                and defending == prev_defending
                and frame.frame_idx - prev_frame_idx <= MAX_FRAME_GAP
            )

            # If break in possession or context, close all open spells and reset partner-switch context
            if not continuous:
                flush_spells(
                    prev_clock if prev_clock is not None else frame.game_clock,
                    prev_frame_idx if prev_frame_idx is not None else frame.frame_idx,
                )
                reset_switch_context()

            # If no defending team, update previous context and skip
            if defending is None:
                prev_clock = frame.game_clock
                prev_frame_idx = frame.frame_idx
                prev_period = frame.period
                prev_defending = None
                continue

            # Generate set of (defender, attacker) edges present in this frame
            current_edges = {(e.defender_id, e.attacker_id) for e in edges}
            end_clock_for_closed = prev_clock if prev_clock is not None else frame.game_clock

            # Close any spells that ended (edges that disappeared in current frame)
            for key in list(open_spells):
                if key not in current_edges:
                    close_spell(key, end_clock_for_closed, frame.frame_idx)

            # For new edges, open new spells (initialize tracking for this assignment)
            for key in current_edges:
                if key not in open_spells:
                    open_spells[key] = _OpenSpell(
                        start_clock=frame.game_clock,
                        start_frame_idx=frame.frame_idx,
                        period=frame.period,
                        defending_team=defending,
                    )

            # Switch detection: Track changes in partners for each defender
            defenders = frame.outfield_players(defending)
            defender_ids = {p.player_id for p in defenders}
            # Initialize partner sets for all defenders
            partners_by_def: dict[str, frozenset[str]] = {
                pid: frozenset() for pid in defender_ids
            }
            # Build up set of attackers each defender is marking this frame
            for defender_id, attacker_id in current_edges:
                if defender_id in partners_by_def:
                    partners_by_def[defender_id] = partners_by_def[defender_id] | {
                        attacker_id
                    }

            # Calculate time delta since previous frame if continuous context
            dt = 0.0
            if continuous and prev_clock is not None:
                dt = max(0.0, float(frame.game_clock) - float(prev_clock))

            # For each defender: log switch (partner change) and accumulate active defending seconds
            for defender_id in defender_ids:
                partners = partners_by_def[defender_id]
                if continuous and defender_id in prev_partners:
                    if partners != prev_partners[defender_id]:
                        switches_by_defender[defender_id] += 1
                if continuous and dt > 0.0:
                    active_seconds_by_defender[defender_id] += dt
                prev_partners[defender_id] = partners

            # Clean up defenders no longer active (remove from previous partners tracking)
            for defender_id in list(prev_partners):
                if defender_id not in defender_ids:
                    prev_partners.pop(defender_id, None)

            # Update previous context to current
            prev_clock = frame.game_clock
            prev_frame_idx = frame.frame_idx
            prev_period = frame.period
            prev_defending = defending

        # After processing all frames, flush any remaining open spells (those still open at the end)
        if frames:
            last = frames[-1]
            flush_spells(last.game_clock, last.frame_idx)

        spells_df = pd.DataFrame(spells)
        spells_by_defender: dict[str, int] = defaultdict(int)
        for spell in spells:
            spells_by_defender[str(spell["defenderId"])] += 1
        player_df = _player_table(
            switches_by_defender, active_seconds_by_defender, spells_by_defender
        )

        out_dir = ctx.out_dir
        out_dir.mkdir(parents=True, exist_ok=True)

        spells_path = out_dir / "assignment_spells.csv"
        player_path = out_dir / "switches_per_player.csv"
        spells_df.to_csv(spells_path, index=False)
        player_df.to_csv(player_path, index=False)

        summary = _build_summary(spells_df, player_df, ctx)
        plot_paths = _write_plots(spells_df, summary, out_dir)
        summary["outputs"].update(plot_paths)

        summary_path = out_dir / "temporal_stability_summary.json"
        summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
        return summary


def _player_table(
    switches_by_defender: dict[str, int],
    active_seconds_by_defender: dict[str, float],
    spells_by_defender: dict[str, int],
) -> pd.DataFrame:
    player_ids = sorted(
        set(switches_by_defender) | set(active_seconds_by_defender) | set(spells_by_defender)
    )
    rows: list[dict] = []
    for pid in player_ids:
        seconds = float(active_seconds_by_defender.get(pid, 0.0))
        switches = int(switches_by_defender.get(pid, 0))
        n_spells = int(spells_by_defender.get(pid, 0))
        minutes = seconds / 60.0
        rows.append(
            {
                "playerId": pid,
                "spells": n_spells,
                "switches": switches,
                "activeSeconds": seconds,
                "activeMinutes": minutes,
                "spellsPerActiveMinute": (n_spells / minutes) if minutes > 0 else None,
                "switchesPerActiveMinute": (switches / minutes) if minutes > 0 else None,
            }
        )
    return pd.DataFrame(rows)


def _mean_or_none(values: list[float]) -> float | None:
    return statistics.fmean(values) if values else None


def _duration_stats(durations: list[float]) -> dict:
    if not durations:
        return {
            "nSpells": 0,
            "meanDurationSec": None,
            "medianDurationSec": None,
        }
    arr = np.asarray(durations, dtype=np.float64)
    return {
        "nSpells": int(arr.size),
        "meanDurationSec": float(arr.mean()),
        "medianDurationSec": float(np.median(arr)),
    }


def _duration_histogram(durations: list[float]) -> list[dict]:
    empty = [
        {
            "binStart": DURATION_HIST_EDGES[i],
            "binEnd": None if DURATION_HIST_EDGES[i + 1] == float("inf") else DURATION_HIST_EDGES[i + 1],
            "count": 0,
            "share": 0.0,
        }
        for i in range(len(DURATION_HIST_EDGES) - 1)
    ]
    if not durations:
        return empty

    arr = np.asarray(durations, dtype=np.float64)
    finite_edges = list(DURATION_HIST_EDGES[:-1]) + [
        max(float(arr.max()) + 1.0, DURATION_HIST_EDGES[-2] + 1.0)
    ]
    counts, _ = np.histogram(arr, bins=finite_edges)
    total = int(counts.sum())
    bins: list[dict] = []
    for i, count in enumerate(counts):
        bin_end = DURATION_HIST_EDGES[i + 1]
        bins.append(
            {
                "binStart": DURATION_HIST_EDGES[i],
                "binEnd": None if bin_end == float("inf") else bin_end,
                "count": int(count),
                "share": float(count / total) if total else 0.0,
            }
        )
    return bins


def _build_summary(
    spells_df: pd.DataFrame,
    player_df: pd.DataFrame,
    ctx: AnalysisContext,
) -> dict:
    durations = (
        spells_df["durationSec"].astype(float).tolist() if not spells_df.empty else []
    )
    switch_counts = (
        player_df["switches"].astype(float).tolist() if not player_df.empty else []
    )
    switch_rates = (
        player_df["switchesPerActiveMinute"].dropna().astype(float).tolist()
        if not player_df.empty
        else []
    )
    spell_rates = (
        player_df["spellsPerActiveMinute"].dropna().astype(float).tolist()
        if not player_df.empty
        else []
    )
    total_switches = int(player_df["switches"].sum()) if not player_df.empty else 0

    return {
        "analysis": "temporal_stability",
        **assignment_summary_fields(ctx.assignment),
        "definitions": {
            "spell": (
                "Maximal run of the same (defender, attacker) edge while period "
                "and defending team stay the same and consecutive processed "
                f"frames are within {MAX_FRAME_GAP} frameIdx steps."
            ),
            "switch": (
                "Within continuous defending possession, a change in a defender's "
                "partner set (attackers marked; may be empty) vs the previous "
                "continuous frame. Period / possession / gap breaks are not switches."
            ),
            "activeTime": (
                "Game-clock seconds a player spends as an outfield defender during "
                "continuous defending possession."
            ),
        },
        **_duration_stats(durations),
        "durationHistogram": _duration_histogram(durations),
        "totalSwitches": total_switches,
        "playersWithSwitchData": int(len(player_df)),
        "meanSwitchesPerPlayer": _mean_or_none(switch_counts),
        "meanSwitchesPerActiveMinutePerPlayer": _mean_or_none(switch_rates),
        "meanSpellsPerActiveMinutePerPlayer": _mean_or_none(spell_rates),
        "outputs": {
            "spellsCsv": str(Path("assignment_spells.csv")),
            "switchesPerPlayerCsv": str(Path("switches_per_player.csv")),
            "summaryJson": str(Path("temporal_stability_summary.json")),
        },
    }


def _style_ax(ax) -> None:
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)


def _write_plots(spells_df: pd.DataFrame, summary: dict, out_dir: Path) -> dict[str, str]:
    import matplotlib.pyplot as plt

    assignment_label = assignment_plot_label(summary)
    outputs: dict[str, str] = {}

    path = out_dir / "assignment_duration_histogram.png"
    fig, ax = plt.subplots(figsize=(8, 4.2))
    hist = summary.get("durationHistogram") or []
    if hist:
        shares = [100.0 * float(b.get("share") or 0.0) for b in hist]
        bars = ax.bar(
            DURATION_HIST_LABELS,
            shares,
            color="#3d6b8c",
            edgecolor="white",
            linewidth=0.6,
        )
        for bar, share in zip(bars, shares):
            if share <= 0:
                continue
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height(),
                f"{share:.1f}%",
                ha="center",
                va="bottom",
                fontsize=7,
                color="#333333",
            )
        ax.set_ylim(0, max(shares) * 1.18 if shares else 1.0)

        mean_d = summary.get("meanDurationSec")
        median_d = summary.get("medianDurationSec")
        parts = []
        if mean_d is not None:
            parts.append(f"mean = {mean_d:.2f}s")
        if median_d is not None:
            parts.append(f"median = {median_d:.2f}s")
        if parts:
            ax.text(
                0.99,
                0.97,
                "  ·  ".join(parts),
                transform=ax.transAxes,
                ha="right",
                va="top",
                fontsize=8,
                color="#555555",
            )

    ax.set_xlabel("Assignment duration (s)")
    ax.set_ylabel("Share of spells (%)")
    ax.set_title(f"Assignment duration distribution — {assignment_label}")
    _style_ax(ax)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    outputs["durationHistogramPng"] = str(Path(path.name))

    return outputs
