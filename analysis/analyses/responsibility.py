"""Hybrid responsibility analysis.

Categories: contestant | near_ball | space | collective
Plus: overlap vs oriented mutual 2-NN, residual zone load, near-ball size,
collective defender workload (degree + man/space/mixed).

Only complete frames: possession, contestants, near-ball set, exact-frame zones.
Attacker metrics use category pools; defender workload is collective-only.

CLI: --assignment responsibility --analyses responsibility
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
MAX_GAP = max(2, int(ZONES_STRIDE))
LEN_BINS = (0, 3, 6, 9, 12, 15, 18, 21, 24, 27, 30, float("inf"))
LEN_THRESH = (5, 10, 15, 20, 25)
ORIENTED = OrientedKnnAssignment(k=MARKING_K, alpha=MARKING_ALPHA, behind_mode="neutral")


class ResponsibilityAnalysis:
    name = "responsibility"

    def run(self, frames, edges_by_frame, ctx: AnalysisContext) -> dict:
        asg = ctx.assignment
        if not isinstance(asg, ResponsibilityAssignment):
            raise TypeError("requires --assignment responsibility")

        gk = home_goalkeeper_on_positive_x_by_period(frames)
        track = {c: _Cat(c) for c in CATS}
        def_load = _DefenderLoad()
        n_coll = n_ori = n_inter = assigned = skipped = 0
        zone_loads: list[int] = []
        near_n: list[int] = []
        near_def: list[int] = []
        near_att: list[int] = []
        near_a: list[float] = []
        prev_clock = prev_idx = prev_period = prev_def = None

        def flush(t, idx):
            for tr in track.values():
                tr.flush(t, idx)
                tr.prev.clear()

        for frame, _ in zip(frames, edges_by_frame):
            defending = frame.defending_team
            complete = defending is not None and asg.is_complete_frame(frame)

            if not complete:
                if defending is not None:
                    skipped += 1
                if defending is None or (
                    prev_idx is not None and frame.frame_idx - prev_idx > MAX_GAP
                ):
                    flush(
                        prev_clock if prev_clock is not None else frame.game_clock,
                        prev_idx if prev_idx is not None else frame.frame_idx,
                    )
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
                flush(
                    prev_clock if prev_clock is not None else frame.game_clock,
                    prev_idx if prev_idx is not None else frame.frame_idx,
                )

            assigned += 1
            cats = asg.categories_for_frame(frame)
            elig = _eligible(asg, frame)
            defs = _defenders_by_category(asg, frame)
            goal = defended_goal_center(frame, home_goalkeeper_on_positive_x_flag=gk[frame.period])
            dt = max(0.0, float(frame.game_clock) - float(prev_clock)) if cont and prev_clock else 0.0
            end_c = prev_clock if prev_clock is not None else frame.game_clock

            for c in CATS:
                track[c].add(frame, cats[c], elig[c], defs[c], goal, cont, dt, end_c)
            def_load.add(defs["collective"], cats["near_ball"], cats["space"])

            coll = {(e.defender_id, e.attacker_id) for e in cats["collective"]}
            ori = {(e.defender_id, e.attacker_id) for e in ORIENTED.edges_for_frame(frame)}
            n_coll += len(coll)
            n_ori += len(ori)
            n_inter += len(coll & ori)

            zs = asg.zone_stats(frame, space_edges=cats["space"])
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
            flush(frames[-1].game_clock, frames[-1].frame_idx)

        rows = [track[c].finish(assigned) for c in CATS]
        denom = n_coll + n_ori - n_inter
        overlap = {
            "baseline": ORIENTED.slug(),
            "nCollectiveEdges": n_coll,
            "nOrientedEdges": n_ori,
            "nIntersection": n_inter,
            "shareOrientedInCollective": (n_inter / n_ori) if n_ori else None,
            "shareCollectiveInOriented": (n_inter / n_coll) if n_coll else None,
            "jaccard": (n_inter / denom) if denom else None,
        }
        occupied = [x for x in zone_loads if x > 0]
        zone_load = {
            "n": len(zone_loads),
            "nOccupied": len(occupied),
            **_dist(zone_loads),
            **_load_shares(zone_loads),
            "meanOccupied": (sum(occupied) / len(occupied)) if occupied else None,
        }
        pitch = PITCH_LENGTH_M * PITCH_WIDTH_M
        area_d = _dist(near_a)
        near_ball = {
            "players": _dist(near_n),
            "defenders": _dist(near_def),
            "attackers": _dist(near_att),
            "area_m2": area_d,
            "meanAreaShareOfPitch": (area_d["mean"] / pitch) if area_d["mean"] is not None else None,
            "p95AreaShareOfPitch": (area_d["p95"] / pitch) if area_d["p95"] is not None else None,
        }
        defender_workload = def_load.finish()

        for r in rows:
            if r["category"] == "collective":
                r["overlapJaccard"] = overlap["jaccard"]
                r["overlapOrientedInCollective"] = overlap["shareOrientedInCollective"]
            else:
                r["overlapJaccard"] = None
                r["overlapOrientedInCollective"] = None

        out = ctx.out_dir
        out.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(rows).to_csv(out / "summary.csv", index=False)

        summary = {
            "analysis": self.name,
            **assignment_summary_fields(asg),
            **asg.summary_fields(),
            "assignedFrames": assigned,
            "skippedIncompleteFrames": skipped,
            "completeFrameRule": (
                "possession known; non-empty contestantIds; non-empty nearBallIds; "
                "residual space zones present for the exact frame"
            ),
            "categories": rows,
            "overlapWithOrientedMutual2nn": overlap,
            "spaceZoneAttackerLoad": zone_load,
            "nearBallRegion": near_ball,
            "defenderWorkload": defender_workload,
            "outputs": {"summaryCsv": "summary.csv", "summaryJson": "summary.json"},
        }
        summary["outputs"].update(
            _plots(rows, summary, out, overlap, zone_load, near_ball, defender_workload)
        )
        (out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
        return summary


@dataclass
class _DefenderLoad:
    n_obs: int = 0
    deg_sum: int = 0
    deg: Counter = field(default_factory=Counter)
    mix: Counter = field(default_factory=Counter)

    def add(self, defenders, near_edges, space_edges) -> None:
        near_by: dict[str, set[str]] = defaultdict(set)
        space_by: dict[str, set[str]] = defaultdict(set)
        for e in near_edges:
            near_by[e.defender_id].add(e.attacker_id)
        for e in space_edges:
            space_by[e.defender_id].add(e.attacker_id)
        for p in defenders:
            near_set = near_by.get(p.player_id, set())
            space_set = space_by.get(p.player_id, set())
            deg = len(near_set | space_set)
            self.n_obs += 1
            self.deg_sum += deg
            self.deg[0 if deg == 0 else 1 if deg == 1 else 2 if deg == 2 else 3] += 1
            if not near_set and not space_set:
                self.mix["none"] += 1
            elif near_set and not space_set:
                self.mix["man"] += 1
            elif space_set and not near_set:
                self.mix["space"] += 1
            else:
                self.mix["mixed"] += 1

    def finish(self) -> dict:
        n = self.n_obs
        pct = lambda k, ctr: (100.0 * ctr[k] / n) if n else None
        return {
            "nDefenderObservations": n,
            "meanDefenderDegree": (self.deg_sum / n) if n else None,
            "pctDegree0": pct(0, self.deg),
            "pctDegree1": pct(1, self.deg),
            "pctDegree2": pct(2, self.deg),
            "pctDegree3Plus": pct(3, self.deg),
            "pctNoEdges": pct("none", self.mix),
            "pctManMarkingOnly": pct("man", self.mix),
            "pctSpaceOnly": pct("space", self.mix),
            "pctMixed": pct("mixed", self.mix),
        }


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
        for key in list(self.open):
            sp = self.open.pop(key)
            dur = max(0.0, float(t) - float(sp[0]))
            if dur <= 0 and idx == sp[1]:
                dur = 1.0 / FPS
            self.durs.append(dur)

    def add(self, frame, edges, attackers, defenders, goal, cont, dt, end_c) -> None:
        self.counts.append(len(edges))
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
                sp = self.open.pop(key)
                dur = max(0.0, float(end_c) - float(sp[0]))
                if dur <= 0 and frame.frame_idx == sp[1]:
                    dur = 1.0 / FPS
                self.durs.append(dur)
        for key in pairs:
            if key not in self.open:
                self.open[key] = (frame.game_clock, frame.frame_idx)

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
                del self.prev[did]

    def finish(self, assigned: int) -> dict:
        c, L = self.counts, self.lengths
        arr = np.asarray(L, dtype=float) if L else None
        darr = np.asarray(self.durs, dtype=float) if self.durs else None
        n_e = int(sum(c)) if c else 0
        rates = [self.switches[pid] / (sec / 60.0) for pid, sec in self.active.items() if sec > 0]
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
    """Defender pools for switches/active time (not for degree — that is collective-only)."""
    all_defs = list(frame.outfield_players(frame.defending_team))
    row = asg.result_row(frame.frame_idx) or {}
    near = {str(x) for x in (row.get("nearBallIds") or [])}
    near_defs = [p for p in all_defs if p.player_id in near]
    owners = set(asg.residual_zone_owner_ids(frame))
    return {
        "contestant": near_defs,
        "near_ball": near_defs,
        "space": [p for p in all_defs if p.player_id in owners],
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
    if not vals:
        return [
            {"binStart": edges[i], "binEnd": None if edges[i + 1] == float("inf") else edges[i + 1], "share": 0.0}
            for i in range(len(edges) - 1)
        ]
    arr = np.asarray(vals, dtype=float)
    finite = list(edges[:-1]) + [max(float(arr.max()) + 1.0, edges[-2] + 1.0)]
    hist, _ = np.histogram(arr, bins=finite)
    total = max(int(hist.sum()), 1)
    return [
        {
            "binStart": edges[i],
            "binEnd": None if edges[i + 1] == float("inf") else edges[i + 1],
            "share": float(hist[i] / total),
        }
        for i in range(len(hist))
    ]


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


def _dist_bars(path: Path, dist: dict, title: str, ylabel: str, color: str) -> None:
    keys = ("mean", "median", "p90", "p95", "max")
    _bars(path, list(keys), [_f(dist.get(k)) for k in keys], title, ylabel, colors=[color] * 5)


def _grouped(ax, bin_labels, series, ylabel, title) -> None:
    x = np.arange(len(bin_labels))
    n = len(series)
    w = min(0.8 / max(n, 1), 0.22)
    for i, (cat, vals) in enumerate(series.items()):
        ax.bar(x + (i - (n - 1) / 2) * w, vals, w, label=LABELS[cat], color=COLORS[CATS.index(cat)])
    ax.set_xticks(x)
    ax.set_xticklabels(
        bin_labels, rotation=45 if len(bin_labels) > 6 else 0,
        ha="right" if len(bin_labels) > 6 else "center",
    )
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    ax.legend(frameon=False, fontsize=8)
    style_ax(ax)


def _plots(rows, summary, out: Path, overlap, zone_load, near_ball, defender_workload) -> dict[str, str]:
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

    dw = defender_workload or {}
    _bars(
        out / "cmp_def_degree_shares.png",
        ["deg 0", "deg 1", "deg 2", "deg ≥3"],
        [_f(dw.get(k)) for k in ("pctDegree0", "pctDegree1", "pctDegree2", "pctDegree3Plus")],
        f"Collective defender degree — {label} (mean={_f(dw.get('meanDefenderDegree')):.2f})",
        "Share of defender observations (%)",
        colors=["#94a3b8", "#047857", "#1d4ed8", "#b45309"],
    )
    out_map["defenderDegreeShares"] = "cmp_def_degree_shares.png"
    _bars(
        out / "cmp_def_edge_mix.png",
        ["none", "man only", "space only", "mixed"],
        [_f(dw.get(k)) for k in ("pctNoEdges", "pctManMarkingOnly", "pctSpaceOnly", "pctMixed")],
        f"Defender edge mix (collective) — {label}",
        "Share of defender observations (%)",
        colors=["#94a3b8", "#1d4ed8", "#047857", "#b45309"],
    )
    out_map["defenderEdgeMix"] = "cmp_def_edge_mix.png"

    by = {r["category"]: r for r in rows}
    ref = by["collective"]["lengthBinShares"]
    bin_labs = [
        f"{b['binStart']:.0f}+" if b["binEnd"] is None else f"{b['binStart']:.0f}–{b['binEnd']:.0f}"
        for b in ref
    ]
    series = {c: [100 * _f(by[c]["lengthBinShares"][i]["share"]) for i in range(len(ref))] for c in CATS}
    fig, ax = plt.subplots(figsize=(11, 4.5))
    _grouped(ax, bin_labs, series, "Share of edges (%)", f"Edge length distribution — {label}")
    fig.tight_layout()
    fig.savefig(out / "cmp_length_bins.png", dpi=150)
    plt.close(fig)
    out_map["lengthBins"] = "cmp_length_bins.png"

    series = {c: [100 * _f(by[c]["lengthThresholdShares"].get(str(t))) for t in LEN_THRESH] for c in CATS}
    fig, ax = plt.subplots(figsize=(8, 4.2))
    _grouped(ax, [f">{t}" for t in LEN_THRESH], series, "Share longer than T (%)", f"Long edges — {label}")
    fig.tight_layout()
    fig.savefig(out / "cmp_length_thresholds.png", dpi=150)
    plt.close(fig)
    out_map["lengthThresholds"] = "cmp_length_thresholds.png"

    starts = sorted({b["binStart"] for r in rows for b in r.get("edgeCountHistShares") or []})
    if starts:
        series = {
            c: [100 * _f({b["binStart"]: b["share"] for b in by[c].get("edgeCountHistShares") or []}.get(s)) for s in starts]
            for c in CATS
        }
        fig, ax = plt.subplots(figsize=(10, 4.5))
        _grouped(ax, [f"{s}–{s + 5}" for s in starts], series, "Share of frames (%)", f"Edges per frame — {label}")
        fig.tight_layout()
        fig.savefig(out / "cmp_edge_counts.png", dpi=150)
        plt.close(fig)
        out_map["edgeCounts"] = "cmp_edge_counts.png"

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

    _dist_bars(
        out / "cmp_zone_load.png", zone_load,
        f"Attackers per residual defender zone — {label}", "Attackers", "#047857",
    )
    out_map["zoneLoad"] = "cmp_zone_load.png"
    _bars(
        out / "cmp_zone_load_shares.png",
        ["load 0", "load 1", "load ≥2", "load ≥3"],
        [100 * _f(zone_load.get(k)) for k in ("share0", "share1", "share2Plus", "share3Plus")],
        f"Residual zone load shares — {label}",
        "Share of zones (%)",
        colors=["#94a3b8", "#047857", "#b45309", "#7f1d1d"],
    )
    out_map["zoneLoadShares"] = "cmp_zone_load_shares.png"

    for key, fname, title, color in (
        ("players", "cmp_near_ball_players.png", "Players in near-ball region", "#1d4ed8"),
        ("defenders", "cmp_near_ball_defenders.png", "Defenders in near-ball region", "#1d4ed8"),
        ("attackers", "cmp_near_ball_attackers.png", "Attackers in near-ball region", "#b45309"),
        ("area_m2", "cmp_near_ball_area.png", "Near-ball bubble area (m²)", "#1d4ed8"),
    ):
        ylab = "Area (m²)" if key == "area_m2" else title.split()[0]
        _dist_bars(out / fname, near_ball.get(key) or {}, f"{title} — {label}", ylab, color)
        out_map[{
            "players": "nearBallPlayers",
            "defenders": "nearBallDefenders",
            "attackers": "nearBallAttackers",
            "area_m2": "nearBallArea",
        }[key]] = fname

    return out_map
