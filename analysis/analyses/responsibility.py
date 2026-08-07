"""Single analysis for the hybrid responsibility algorithm.

Categories: contestant | near_ball | space | collective
Plus: overlap vs oriented mutual 2-NN (α=1.5), residual zone load, near-ball size.

Only complete frames are analysed: possession known, non-empty contestants,
non-empty near-ball set, and residual space zones computed for that exact frame.

Category metrics use the matching player pools (near-ball attackers/defenders,
residual zone owners, etc.), not all outfield players. Space edges exclude
attackers inside the near-ball set.

Requires --assignment responsibility. CLI: --analyses responsibility
Output: analysis/output/responsibility/
"""

from __future__ import annotations

import json
import statistics
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

from analysis.analyses.base import AnalysisContext
from analysis.assignments.meta import assignment_plot_label, assignment_summary_fields
from analysis.assignments.oriented_knn import OrientedKnnAssignment
from analysis.assignments.responsibility import ResponsibilityAssignment
from analysis.data import Frame
from analysis.pitch import (
    PITCH_LENGTH_M,
    PITCH_WIDTH_M,
    defended_goal_center,
    home_goalkeeper_on_positive_x_by_period,
    is_defender_goal_side,
    player_by_id,
)
from analysis.zone_metrics import style_ax
from preprocess.config import FRAME_RATE, MARKING_ALPHA, MARKING_K, ZONES_STRIDE

CATS = ["contestant", "near_ball", "space", "collective"]
LABELS = {
    "contestant": "Carrier / contestant",
    "near_ball": "Near-ball 2-NN",
    "space": "Space-derived",
    "collective": "Collective",
}
COLORS = ["#b45309", "#1d4ed8", "#047857", "#374151"]
FPS = float(FRAME_RATE)
# Complete frames follow the zone stride, so allow at least that gap.
MAX_GAP = max(2, int(ZONES_STRIDE))
LEN_BINS = (0, 3, 6, 9, 12, 15, 18, 21, 24, 27, 30, float("inf"))
LEN_THRESH = (5, 10, 15, 20, 25)
# Overlap baseline: same k/α as preprocess near-ball marking (full-pitch attackers).
ORIENTED = OrientedKnnAssignment(k=MARKING_K, alpha=MARKING_ALPHA, behind_mode="neutral")


class ResponsibilityAnalysis:
    name = "responsibility"

    def run(self, frames, edges_by_frame, ctx: AnalysisContext) -> dict:
        asg = ctx.assignment
        if not isinstance(asg, ResponsibilityAssignment):
            raise TypeError("requires --assignment responsibility")

        gk = home_goalkeeper_on_positive_x_by_period(frames)
        track = {c: _Cat(c) for c in CATS}
        n_coll = n_ori = n_inter = assigned = skipped_incomplete = 0
        zone_loads: list[int] = []
        near_n: list[int] = []
        near_def: list[int] = []
        near_att: list[int] = []
        near_a: list[float] = []
        prev_clock = prev_idx = prev_period = prev_def = None

        for frame, _ in zip(frames, edges_by_frame):
            defending = frame.defending_team
            complete = defending is not None and asg.is_complete_frame(frame)

            if not complete:
                if defending is not None:
                    skipped_incomplete += 1
                # Keep the last complete frame as the continuity cursor so strided
                # zone frames can still form spells. Hard-break only on unknown
                # possession or when the gap from the last complete frame is too large.
                if defending is None or (
                    prev_idx is not None and frame.frame_idx - prev_idx > MAX_GAP
                ):
                    for t in track.values():
                        t.flush(
                            prev_clock if prev_clock is not None else frame.game_clock,
                            prev_idx if prev_idx is not None else frame.frame_idx,
                        )
                        t.prev.clear()
                    prev_clock, prev_idx, prev_period, prev_def = (
                        frame.game_clock, frame.frame_idx, frame.period, None
                    )
                continue

            cont = (
                prev_idx is not None
                and prev_period == frame.period
                and prev_def is not None
                and defending == prev_def
                and frame.frame_idx - prev_idx <= MAX_GAP
            )
            if not cont:
                for t in track.values():
                    t.flush(
                        prev_clock if prev_clock is not None else frame.game_clock,
                        prev_idx if prev_idx is not None else frame.frame_idx,
                    )
                    t.prev.clear()

            assigned += 1
            cats = asg.categories_for_frame(frame)
            elig = _eligible(asg, frame)
            defs_by_cat = _defenders_by_category(asg, frame)
            goal = defended_goal_center(frame, home_goalkeeper_on_positive_x_flag=gk[frame.period])
            dt = max(0.0, float(frame.game_clock) - float(prev_clock)) if cont and prev_clock else 0.0
            end_c = prev_clock if prev_clock is not None else frame.game_clock

            for c in CATS:
                track[c].add(frame, cats[c], elig[c], defs_by_cat[c], goal, cont, dt, end_c)

            coll = {(e.defender_id, e.attacker_id) for e in cats["collective"]}
            ori = {(e.defender_id, e.attacker_id) for e in ORIENTED.edges_for_frame(frame)}
            n_coll += len(coll)
            n_ori += len(ori)
            n_inter += len(coll & ori)

            zs = asg.zone_stats(frame, space_edges=cats["space"])
            if zs["loads"]:
                zone_loads.extend(zs["loads"])
            if zs["nearPlayers"] is not None:
                near_n.append(int(zs["nearPlayers"]))
            if zs["nearDefenders"] is not None:
                near_def.append(int(zs["nearDefenders"]))
            if zs["nearAttackers"] is not None:
                near_att.append(int(zs["nearAttackers"]))
            if zs["nearArea_m2"] is not None:
                near_a.append(float(zs["nearArea_m2"]))

            prev_clock, prev_idx, prev_period, prev_def = (
                frame.game_clock, frame.frame_idx, frame.period, defending
            )

        if frames:
            for t in track.values():
                t.flush(frames[-1].game_clock, frames[-1].frame_idx)

        rows = [track[c].finish(assigned) for c in CATS]
        overlap = {
            "baseline": ORIENTED.slug(),
            "nCollectiveEdges": n_coll,
            "nOrientedEdges": n_ori,
            "nIntersection": n_inter,
            "shareOrientedInCollective": (n_inter / n_ori) if n_ori else None,
            "shareCollectiveInOriented": (n_inter / n_coll) if n_coll else None,
            "jaccard": (n_inter / (n_coll + n_ori - n_inter)) if (n_coll + n_ori > n_inter) else None,
        }
        occupied_loads = [x for x in zone_loads if x > 0]
        zone_load = {
            "n": len(zone_loads),
            "nOccupied": len(occupied_loads),
            **_dist(zone_loads),
            **_load_shares(zone_loads),
            "meanOccupied": (
                float(sum(occupied_loads) / len(occupied_loads)) if occupied_loads else None
            ),
        }
        pitch = PITCH_LENGTH_M * PITCH_WIDTH_M
        near_ball = {
            "players": _dist(near_n),
            "defenders": _dist(near_def),
            "attackers": _dist(near_att),
            "area_m2": _dist(near_a),
            "meanAreaShareOfPitch": (
                _dist(near_a)["mean"] / pitch if near_a else None
            ),
            "p95AreaShareOfPitch": (
                _dist(near_a)["p95"] / pitch if near_a else None
            ),
        }

        for r in rows:
            r.update({
                "overlapJaccard": overlap["jaccard"] if r["category"] == "collective" else None,
                "overlapOrientedInCollective": (
                    overlap["shareOrientedInCollective"] if r["category"] == "collective" else None
                ),
            })

        out = ctx.out_dir
        out.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(rows).to_csv(out / "summary.csv", index=False)

        summary = {
            "analysis": self.name,
            **assignment_summary_fields(asg),
            **asg.summary_fields(),
            "assignedFrames": assigned,
            "skippedIncompleteFrames": skipped_incomplete,
            "completeFrameRule": (
                "possession known; non-empty contestantIds; non-empty nearBallIds; "
                "residual space zones present for the exact frame"
            ),
            "categories": rows,
            "overlapWithOrientedMutual2nn": overlap,
            "spaceZoneAttackerLoad": zone_load,
            "nearBallRegion": near_ball,
            "outputs": {"summaryCsv": "summary.csv", "summaryJson": "summary.json"},
        }
        summary["outputs"].update(_plots(rows, summary, out, overlap, zone_load, near_ball))
        (out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
        return summary


# --- category tracker -------------------------------------------------------

@dataclass
class _Spell:
    t0: float
    i0: int
    period: int
    team: str


@dataclass
class _Cat:
    cat: str
    counts: list[int] = field(default_factory=list)
    lengths: list[float] = field(default_factory=list)
    gs: int = 0
    gs_n: int = 0
    att_sum: int = 0
    att_obs: int = 0
    unmarked: int = 0
    double: int = 0
    open: dict = field(default_factory=dict)
    durs: list[float] = field(default_factory=list)
    switches: dict = field(default_factory=lambda: defaultdict(int))
    active: dict = field(default_factory=lambda: defaultdict(float))
    prev: dict = field(default_factory=dict)

    def flush(self, t: float, idx: int) -> None:
        for k in list(self.open):
            self._close(k, t, idx)

    def _close(self, key, t, idx) -> None:
        sp = self.open.pop(key, None)
        if sp is None:
            return
        dur = max(0.0, float(t) - float(sp.t0))
        if dur <= 0 and idx == sp.i0:
            dur = 1.0 / FPS
        self.durs.append(dur)

    def add(self, frame, edges, attackers, defenders, goal, cont, dt, end_c) -> None:
        n = len(edges)
        self.counts.append(n)
        att_deg: Counter[str] = Counter()
        partners = {p.player_id: set() for p in defenders}
        pairs = set()
        for e in edges:
            self.lengths.append(e.length_m)
            att_deg[e.attacker_id] += 1
            pairs.add((e.defender_id, e.attacker_id))
            if e.defender_id in partners:
                partners[e.defender_id].add(e.attacker_id)
            d = player_by_id(frame, e.defender_id)
            a = player_by_id(frame, e.attacker_id)
            if d and a:
                self.gs_n += 1
                if is_defender_goal_side(goal, (a.x, a.y), (d.x, d.y)):
                    self.gs += 1

        if attackers:
            degs = [att_deg[p.player_id] for p in attackers]
            self.att_obs += len(attackers)
            self.att_sum += sum(degs)
            self.unmarked += sum(d == 0 for d in degs)
            self.double += sum(d >= 2 for d in degs)

        for key in list(self.open):
            if key not in pairs:
                self._close(key, end_c, frame.frame_idx)
        for key in pairs:
            if key not in self.open:
                self.open[key] = _Spell(
                    frame.game_clock, frame.frame_idx, frame.period, frame.defending_team or ""
                )

        ids = {p.player_id for p in defenders}
        for did in ids:
            pset = frozenset(partners.get(did, ()))
            if cont and did in self.prev and pset != self.prev[did]:
                self.switches[did] += 1
            if cont and dt > 0:
                self.active[did] += dt
            self.prev[did] = pset
        for did in list(self.prev):
            if did not in ids:
                self.prev.pop(did, None)

    def finish(self, assigned: int) -> dict:
        c, L = self.counts, self.lengths
        arr = np.asarray(L, dtype=float) if L else None
        darr = np.asarray(self.durs, dtype=float) if self.durs else None
        n_e = int(sum(c)) if c else 0
        rates = [
            self.switches[pid] / (sec / 60.0)
            for pid, sec in self.active.items()
            if sec > 0
        ]
        return {
            "category": self.cat,
            "label": LABELS[self.cat],
            "meanEdgesPerFrame": n_e / assigned if assigned else 0.0,
            "medianEdgesPerFrame": float(statistics.median(c)) if c else 0.0,
            "minEdgesPerFrame": int(min(c)) if c else 0,
            "maxEdgesPerFrame": int(max(c)) if c else 0,
            "meanLength": float(arr.mean()) if arr is not None else None,
            "medianLength": float(np.median(arr)) if arr is not None else None,
            "p95Length": float(np.percentile(arr, 95)) if arr is not None else None,
            "maxLength": float(arr.max()) if arr is not None else None,
            "goalSidePercent": (100.0 * self.gs / self.gs_n) if self.gs_n else None,
            "meanAttackerDegree": self.att_sum / self.att_obs if self.att_obs else None,
            "pctUnmarkedAttackers": 100.0 * self.unmarked / self.att_obs if self.att_obs else None,
            "doubleMarkingRate": 100.0 * self.double / self.att_obs if self.att_obs else None,
            "nSpells": len(self.durs),
            "meanSpellDurationSec": float(darr.mean()) if darr is not None else None,
            "medianSpellDurationSec": float(np.median(darr)) if darr is not None else None,
            "meanSwitchesPerActiveMinute": float(statistics.fmean(rates)) if rates else None,
            "lengthBinShares": _hist_shares(L, LEN_BINS),
            "lengthThresholdShares": {
                str(t): float(np.mean(arr > t)) if arr is not None else 0.0 for t in LEN_THRESH
            },
            "edgeCountHistShares": _count_hist(c),
        }


def _eligible(asg: ResponsibilityAssignment, frame: Frame) -> dict[str, list]:
    """Attackers who belong to each responsibility category on this frame."""
    att = "away" if frame.defending_team == "home" else "home"
    all_att = list(frame.outfield_players(att))
    row = asg.result_row(frame.frame_idx) or {}
    cont = {str(x) for x in (row.get("contestantIds") or [])}
    near = {str(x) for x in (row.get("nearBallIds") or [])}
    return {
        "contestant": [p for p in all_att if p.player_id in cont],
        "near_ball": [p for p in all_att if p.player_id in near],
        "space": [p for p in all_att if p.player_id not in near],
        "collective": all_att,
    }


def _defenders_by_category(asg: ResponsibilityAssignment, frame: Frame) -> dict[str, list]:
    """Defenders relevant to each category (for switches / active time).

    Previously every category tracked all ten outfield defenders, which diluted
    near-ball / contestant switch rates with players outside the region.
    """
    all_defs = list(frame.outfield_players(frame.defending_team))
    row = asg.result_row(frame.frame_idx) or {}
    near = {str(x) for x in (row.get("nearBallIds") or [])}
    near_defs = [p for p in all_defs if p.player_id in near]
    space_owners = set(asg.residual_zone_owner_ids(frame))
    space_defs = [p for p in all_defs if p.player_id in space_owners]
    return {
        "contestant": near_defs,
        "near_ball": near_defs,
        "space": space_defs,
        "collective": all_defs,
    }


def _dist(vals: list) -> dict:
    if not vals:
        return {"mean": None, "median": None, "p90": None, "p95": None, "max": None}
    a = np.asarray(vals, dtype=float)
    return {
        "mean": float(a.mean()),
        "median": float(np.median(a)),
        "p90": float(np.percentile(a, 90)),
        "p95": float(np.percentile(a, 95)),
        "max": float(a.max()) if not np.issubdtype(a.dtype, np.integer) else int(a.max()),
    }


def _load_shares(loads: list[int]) -> dict:
    if not loads:
        return {k: None for k in ("share0", "share1", "share2Plus", "share3Plus")}
    n = len(loads)
    return {
        "share0": sum(x == 0 for x in loads) / n,
        "share1": sum(x == 1 for x in loads) / n,
        "share2Plus": sum(x >= 2 for x in loads) / n,
        "share3Plus": sum(x >= 3 for x in loads) / n,
    }


def _hist_shares(vals: list[float], edges) -> list[dict]:
    bins = []
    if not vals:
        for i in range(len(edges) - 1):
            bins.append({"binStart": edges[i], "binEnd": None if edges[i + 1] == float("inf") else edges[i + 1], "share": 0.0})
        return bins
    arr = np.asarray(vals, dtype=float)
    finite = list(edges[:-1]) + [max(float(arr.max()) + 1.0, edges[-2] + 1.0)]
    hist, _ = np.histogram(arr, bins=finite)
    total = max(int(hist.sum()), 1)
    for i, cnt in enumerate(hist):
        end = edges[i + 1]
        bins.append({"binStart": edges[i], "binEnd": None if end == float("inf") else end, "share": float(cnt / total)})
    return bins


def _count_hist(counts: list[int], width: int = 5) -> list[dict]:
    if not counts:
        return []
    lo, hi = min(counts), max(counts)
    start = (lo // width) * width
    end = ((hi // width) + 1) * width
    edges = list(range(start, end + width, width))
    hist, _ = np.histogram(np.asarray(counts, dtype=int), bins=edges)
    total = max(int(hist.sum()), 1)
    return [
        {"binStart": int(edges[i]), "binEnd": int(edges[i + 1]), "share": float(hist[i] / total)}
        for i in range(len(hist))
    ]


def _f(v) -> float:
    return 0.0 if v is None or (isinstance(v, float) and np.isnan(v)) else float(v)


def _bars(path: Path, labels, vals, title, ylabel, colors=None) -> None:
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(7.5, 4.0))
    cols = colors or COLORS[: len(labels)]
    bars = ax.bar(labels, vals, color=cols, edgecolor="white", width=0.65)
    for b, v in zip(bars, vals):
        ax.text(b.get_x() + b.get_width() / 2, b.get_height(), f"{v:.2f}", ha="center", va="bottom", fontsize=8)
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    style_ax(ax)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def _grouped(ax, bin_labels, series, ylabel, title) -> None:
    x = np.arange(len(bin_labels))
    n = len(series)
    w = min(0.8 / max(n, 1), 0.22)
    for i, (cat, vals) in enumerate(series.items()):
        ax.bar(x + (i - (n - 1) / 2) * w, vals, w, label=LABELS[cat], color=COLORS[CATS.index(cat)])
    ax.set_xticks(x)
    ax.set_xticklabels(bin_labels, rotation=45 if len(bin_labels) > 6 else 0,
                       ha="right" if len(bin_labels) > 6 else "center")
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    ax.legend(frameon=False, fontsize=8)
    style_ax(ax)


def _plots(rows, summary, out: Path, overlap, zone_load, near_ball) -> dict[str, str]:
    import matplotlib.pyplot as plt

    label = assignment_plot_label(summary)
    out_map = {}
    labels = [r["label"] for r in rows]

    for key, ylab, fname in (
        ("meanEdgesPerFrame", "Mean edges / frame", "cmp_mean_edges.png"),
        ("maxEdgesPerFrame", "Max edges / frame", "cmp_max_edges.png"),
        ("meanLength", "Mean length (m)", "cmp_mean_length.png"),
        ("medianLength", "Median length (m)", "cmp_median_length.png"),
        ("p95Length", "P95 length (m)", "cmp_p95_length.png"),
        ("goalSidePercent", "Goal-side (%)", "cmp_goal_side.png"),
        ("pctUnmarkedAttackers", "Unmarked eligible (%)", "cmp_unmarked.png"),
        ("meanAttackerDegree", "Mean attacker degree", "cmp_att_degree.png"),
        ("doubleMarkingRate", "Double-mark (%)", "cmp_double_mark.png"),
        ("meanSpellDurationSec", "Mean spell (s)", "cmp_spell_duration.png"),
        ("meanSwitchesPerActiveMinute", "Switches / active min", "cmp_switch_rate.png"),
    ):
        _bars(out / fname, labels, [_f(r.get(key)) for r in rows], f"{ylab} — {label}", ylab)
        out_map[key] = fname

    by = {r["category"]: r for r in rows}
    ref = by["collective"]["lengthBinShares"]
    bin_labs = [f"{b['binStart']:.0f}+" if b["binEnd"] is None else f"{b['binStart']:.0f}–{b['binEnd']:.0f}" for b in ref]
    series = {c: [100 * _f(by[c]["lengthBinShares"][i]["share"]) for i in range(len(ref))] for c in CATS}
    fig, ax = plt.subplots(figsize=(11, 4.5))
    _grouped(ax, bin_labs, series, "Share of edges (%)", f"Edge length distribution — {label}")
    fig.tight_layout()
    fig.savefig(out / "cmp_length_bins.png", dpi=150)
    plt.close(fig)
    out_map["lengthBins"] = "cmp_length_bins.png"

    t_labs = [f">{t}" for t in LEN_THRESH]
    series = {c: [100 * _f(by[c]["lengthThresholdShares"].get(str(t))) for t in LEN_THRESH] for c in CATS}
    fig, ax = plt.subplots(figsize=(8, 4.2))
    _grouped(ax, t_labs, series, "Share longer than T (%)", f"Long edges — {label}")
    fig.tight_layout()
    fig.savefig(out / "cmp_length_thresholds.png", dpi=150)
    plt.close(fig)
    out_map["lengthThresholds"] = "cmp_length_thresholds.png"

    starts = sorted({b["binStart"] for r in rows for b in r.get("edgeCountHistShares") or []})
    if starts:
        labs = [f"{s}–{s + 5}" for s in starts]
        series = {}
        for c in CATS:
            lookup = {b["binStart"]: b["share"] for b in by[c].get("edgeCountHistShares") or []}
            series[c] = [100 * _f(lookup.get(s)) for s in starts]
        fig, ax = plt.subplots(figsize=(10, 4.5))
        _grouped(ax, labs, series, "Share of frames (%)", f"Edges per frame — {label}")
        fig.tight_layout()
        fig.savefig(out / "cmp_edge_counts.png", dpi=150)
        plt.close(fig)
        out_map["edgeCounts"] = "cmp_edge_counts.png"

    # Overlap
    _bars(
        out / "cmp_overlap_oriented2nn.png",
        ["Oriented ⊆ coll.", "Coll. ⊆ oriented", "Jaccard"],
        [
            100 * _f(overlap.get("shareOrientedInCollective")),
            100 * _f(overlap.get("shareCollectiveInOriented")),
            100 * _f(overlap.get("jaccard")),
        ],
        f"Collective vs {overlap.get('baseline')} — {label}",
        "Share (%)",
        colors=["#1d4ed8", "#047857", "#374151"],
    )
    out_map["overlap"] = "cmp_overlap_oriented2nn.png"

    # Residual zone attacker load
    zl = zone_load
    _bars(
        out / "cmp_zone_load.png",
        ["mean", "median", "p90", "p95", "max"],
        [_f(zl.get(k)) for k in ("mean", "median", "p90", "p95", "max")],
        f"Attackers per residual defender zone — {label}",
        "Attackers",
        colors=["#047857"] * 5,
    )
    out_map["zoneLoad"] = "cmp_zone_load.png"
    _bars(
        out / "cmp_zone_load_shares.png",
        ["load 0", "load 1", "load ≥2", "load ≥3"],
        [100 * _f(zl.get(k)) for k in ("share0", "share1", "share2Plus", "share3Plus")],
        f"Residual zone load shares — {label}",
        "Share of zones (%)",
        colors=["#94a3b8", "#047857", "#b45309", "#7f1d1d"],
    )
    out_map["zoneLoadShares"] = "cmp_zone_load_shares.png"

    # Near-ball players + area
    nb_p, nb_a = near_ball.get("players") or {}, near_ball.get("area_m2") or {}
    nb_d, nb_att = near_ball.get("defenders") or {}, near_ball.get("attackers") or {}
    _bars(
        out / "cmp_near_ball_players.png",
        ["mean", "median", "p90", "p95", "max"],
        [_f(nb_p.get(k)) for k in ("mean", "median", "p90", "p95", "max")],
        f"Players in near-ball region — {label}",
        "Players",
        colors=["#1d4ed8"] * 5,
    )
    out_map["nearBallPlayers"] = "cmp_near_ball_players.png"
    _bars(
        out / "cmp_near_ball_defenders.png",
        ["mean", "median", "p90", "p95", "max"],
        [_f(nb_d.get(k)) for k in ("mean", "median", "p90", "p95", "max")],
        f"Defenders in near-ball region — {label}",
        "Defenders",
        colors=["#1d4ed8"] * 5,
    )
    out_map["nearBallDefenders"] = "cmp_near_ball_defenders.png"
    _bars(
        out / "cmp_near_ball_attackers.png",
        ["mean", "median", "p90", "p95", "max"],
        [_f(nb_att.get(k)) for k in ("mean", "median", "p90", "p95", "max")],
        f"Attackers in near-ball region — {label}",
        "Attackers",
        colors=["#b45309"] * 5,
    )
    out_map["nearBallAttackers"] = "cmp_near_ball_attackers.png"
    _bars(
        out / "cmp_near_ball_area.png",
        ["mean", "median", "p90", "p95", "max"],
        [_f(nb_a.get(k)) for k in ("mean", "median", "p90", "p95", "max")],
        f"Near-ball bubble area (m²) — {label}",
        "Area (m²)",
        colors=["#1d4ed8"] * 5,
    )
    out_map["nearBallArea"] = "cmp_near_ball_area.png"

    return out_map
