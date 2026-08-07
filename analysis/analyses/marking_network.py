"""Marking network (bipartite time-weighted assignment graph).

For each defender–attacker edge from the chosen assignment, accumulate time
(1 / FRAME_RATE seconds per frame). Writes two matrices under
analysis/output/matrix/{assignment_slug}/:
  home_defending.csv — home defenders × away attackers
  away_defending.csv — away defenders × home attackers
  home_defending.png / away_defending.png — heatmaps (rows=attackers, cols=defenders)

CLI:
  python -m analysis.run --assignment <name> --analyses marking_network
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from analysis.analyses.base import AnalysisContext
from analysis.assignments.base import Edge
from analysis.assignments.meta import (
    assignment_plot_label,
    assignment_slug,
    assignment_summary_fields,
)
from analysis.data import Frame
from preprocess.config import FRAME_RATE

DT = 1.0 / float(FRAME_RATE)


class MarkingNetworkAnalysis:
    name = "marking_network"

    def run(
        self,
        frames: list[Frame],
        edges_by_frame: list[list[Edge]],
        ctx: AnalysisContext,
    ) -> dict:
        if len(frames) != len(edges_by_frame):
            raise ValueError("frames and edges_by_frame length mismatch")

        meta_path = _meta_beside_data(ctx)
        labels, team_names, roster = _load_labels(meta_path, frames)
        asg_label = assignment_plot_label(ctx.assignment)

        # seconds[(defending_side, defender_id, attacker_id)]
        seconds: dict[tuple[str, str, str], float] = defaultdict(float)
        frames_used = {"home": 0, "away": 0}

        for frame, edges in zip(frames, edges_by_frame):
            defending = frame.defending_team
            if defending is None or not edges:
                continue
            frames_used[defending] += 1
            for e in edges:
                seconds[(defending, e.defender_id, e.attacker_id)] += DT

        out_dir = ctx.out_dir
        out_dir.mkdir(parents=True, exist_ok=True)

        outputs: dict[str, str] = {}
        matrices: dict[str, dict] = {}
        for side, att_side, fname in (
            ("home", "away", "home_defending.csv"),
            ("away", "home", "away_defending.csv"),
        ):
            mat = _matrix(
                seconds,
                defending=side,
                def_ids=roster[side],
                att_ids=roster[att_side],
                labels=labels,
            )
            path = out_dir / fname
            mat.to_csv(path)
            png_name = fname.replace(".csv", ".png")
            _heatmap(
                mat,
                out_dir / png_name,
                title=(
                    f"Marking network — {team_names[side]} defending vs "
                    f"{team_names[att_side]}\n{asg_label}"
                ),
                xlabel=f"Defender ({team_names[side]})",
                ylabel=f"Attacker ({team_names[att_side]})",
            )
            outputs[fname] = fname
            outputs[png_name] = png_name
            matrices[side] = {
                "defendingTeam": team_names[side],
                "attackingTeam": team_names[att_side],
                "nDefenders": len(mat.index),
                "nAttackers": len(mat.columns),
                "totalSeconds": float(mat.to_numpy().sum()),
                "maxSeconds": float(mat.to_numpy().max()) if mat.size else 0.0,
                "framesWithEdges": frames_used[side],
                "csv": fname,
                "png": png_name,
            }

        summary = {
            "analysis": self.name,
            **assignment_summary_fields(ctx.assignment),
            "assignmentSlug": assignment_slug(ctx.assignment),
            "dtSeconds": DT,
            "metaPath": str(meta_path) if meta_path and meta_path.is_file() else None,
            "teamNames": team_names,
            "matrices": matrices,
            "outputs": outputs,
        }
        (out_dir / "summary.json").write_text(
            json.dumps(summary, indent=2) + "\n", encoding="utf-8"
        )
        return summary


def _meta_beside_data(ctx: AnalysisContext) -> Path | None:
    """Prefer data/metaData.json next to responsibility paths / default data dir."""
    asg = ctx.assignment
    for attr in ("results_path", "zones_path"):
        p = getattr(asg, attr, None)
        if p is not None:
            cand = Path(p).resolve().parent / "metaData.json"
            if cand.is_file():
                return cand
    repo_data = Path(__file__).resolve().parents[2] / "data" / "metaData.json"
    return repo_data if repo_data.is_file() else None


def _load_labels(
    meta_path: Path | None, frames: list[Frame]
) -> tuple[dict[str, str], dict[str, str], dict[str, list[str]]]:
    """Return (player_id → label, side → team name, side → ordered player ids)."""
    team_names = {"home": "Home", "away": "Away"}
    by_id: dict[str, dict] = {}
    roster: dict[str, list[str]] = {"home": [], "away": []}
    seen = {"home": set(), "away": set()}

    if meta_path is not None and meta_path.is_file():
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        for side, key in (("home", "homeTeam"), ("away", "awayTeam")):
            team = meta.get(key) or {}
            if team.get("name"):
                team_names[side] = str(team["name"])
            for p in team.get("players") or []:
                pid = str(p.get("id") or "")
                if not pid or p.get("isGoalie"):
                    continue
                by_id[pid] = p
                if pid not in seen[side]:
                    roster[side].append(pid)
                    seen[side].add(pid)

    for fr in frames:
        for side, players in (("home", fr.home_players), ("away", fr.away_players)):
            for p in players:
                if p.is_goalie:
                    continue
                if p.player_id not in seen[side]:
                    roster[side].append(p.player_id)
                    seen[side].add(p.player_id)
                if p.player_id not in by_id and p.number is not None:
                    by_id[p.player_id] = {"shirtNumber": p.number}

    labels = {
        pid: _player_label(pid, by_id.get(pid), team_names[side])
        for side in ("home", "away")
        for pid in roster[side]
    }
    return labels, team_names, roster


def _player_label(pid: str, info: dict | None, team: str) -> str:
    info = info or {}
    name = (
        info.get("name")
        or info.get("player_name")
        or info.get("shortName")
        or info.get("displayName")
    )
    if name:
        return str(name).strip()
    shirt = info.get("shirtNumber")
    if shirt is not None:
        return f"{team} #{shirt}"
    return f"{team} {pid}"


def _matrix(
    seconds: dict[tuple[str, str, str], float],
    *,
    defending: str,
    def_ids: list[str],
    att_ids: list[str],
    labels: dict[str, str],
) -> pd.DataFrame:
    data = [[0.0] * len(att_ids) for _ in def_ids]
    att_index = {a: j for j, a in enumerate(att_ids)}
    def_index = {d: i for i, d in enumerate(def_ids)}
    for (side, d, a), t in seconds.items():
        if side != defending:
            continue
        i, j = def_index.get(d), att_index.get(a)
        if i is None or j is None:
            continue
        data[i][j] = t
    return pd.DataFrame(
        data,
        index=[labels.get(d, d) for d in def_ids],
        columns=[labels.get(a, a) for a in att_ids],
    ).round(2)


def _heatmap(
    mat: pd.DataFrame,
    path: Path,
    *,
    title: str,
    xlabel: str,
    ylabel: str,
) -> None:
    """Plot attackers (rows) × defenders (cols); drop all-zero players for readability."""
    # CSV layout is defenders × attackers; transpose for the requested axes.
    plot = mat.T
    plot = plot.loc[(plot.sum(axis=1) > 0), (plot.sum(axis=0) > 0)]
    if plot.empty:
        plot = mat.T

    n_att, n_def = plot.shape
    fig_w = max(8.0, 0.45 * n_def + 2.5)
    fig_h = max(6.0, 0.4 * n_att + 2.0)
    fig, ax = plt.subplots(figsize=(fig_w, fig_h))
    im = ax.imshow(
        plot.to_numpy(dtype=float),
        aspect="auto",
        cmap="YlOrRd",
        interpolation="nearest",
        vmin=0.0,
    )
    ax.set_xticks(range(n_def))
    ax.set_yticks(range(n_att))
    ax.set_xticklabels(list(plot.columns), rotation=55, ha="right", fontsize=8)
    ax.set_yticklabels(list(plot.index), fontsize=8)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    cbar = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    cbar.set_label("Marking time (s)")
    fig.tight_layout()
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
