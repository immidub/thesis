"""Responsibility assignment: load preprocess JSONL (do not recompute).

Collective edges = near-ball oriented mutual 2-NN ∪ space-containment edges
(attackers outside the near-ball set only). Possession = reachability
`possessionTeam` (via align_frames).
"""

from __future__ import annotations

import bisect
import json
from collections import Counter
from dataclasses import replace
from pathlib import Path

import numpy as np

from analysis.assignments.base import Edge
from analysis.data import Frame


def _load_jsonl(path: Path) -> tuple[dict | None, dict[int, dict]]:
    header, by_frame = None, {}
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            if obj.get("type") in ("header", "mesh"):
                header = {**(header or {}), **obj}
            elif obj.get("frame") is not None:
                by_frame[int(obj["frame"])] = obj
    return header, by_frame


def _held(frame_idx: int, keys: list[int]) -> int | None:
    i = bisect.bisect_right(keys, frame_idx) - 1
    return keys[i] if i >= 0 else None


def _cell_index(x: float, y: float, h: dict) -> int | None:
    shape = h.get("shape")
    if not shape or len(shape) != 2:
        return None
    rows, cols = int(shape[0]), int(shape[1])
    xlim, ylim = h.get("xlim") or [-52.5, 52.5], h.get("ylim") or [-34.0, 34.0]
    dx = h["dx"] if h.get("dx") is not None else (xlim[1] - xlim[0]) / cols
    dy = h["dy"] if h.get("dy") is not None else (ylim[1] - ylim[0]) / rows
    if not dx or not dy:
        return None
    x0 = h["x0"] if h.get("x0") is not None else xlim[0]
    y0 = h["y0"] if h.get("y0") is not None else ylim[0]
    col, row = int(round((x - x0) / dx)), int(round((y - y0) / dy))
    if 0 <= row < rows and 0 <= col < cols:
        return row * cols + col
    return None


def _ids(row: dict | None, key: str) -> set[str]:
    return {str(x) for x in ((row or {}).get(key) or [])}


class ResponsibilityAssignment:
    name = "responsibility"

    def __init__(
        self,
        results_path: Path | str | None = None,
        zones_path: Path | str | None = None,
        data_dir: Path | str | None = None,
    ) -> None:
        root = Path(data_dir) if data_dir is not None else Path("data")
        self.results_path = Path(results_path) if results_path else root / "responsibility.jsonl"
        self.zones_path = Path(zones_path) if zones_path else root / "responsibility_zones.jsonl"
        if not self.results_path.is_file():
            raise FileNotFoundError(self.results_path)
        _, self._results = _load_jsonl(self.results_path)
        self._zh, self._zones = None, {}
        self._zframes: list[int] = []
        self._owners: dict[int, dict[int, str]] = {}
        if self.zones_path.is_file():
            self._zh, self._zones = _load_jsonl(self.zones_path)
            self._zframes = sorted(self._zones)

    def slug(self) -> str:
        return "responsibility"

    def summary_fields(self) -> dict:
        return {
            "assignment": self.name,
            "resultsPath": str(self.results_path),
            "zonesPath": str(self.zones_path) if self._zones else None,
            "zoneFrameCount": len(self._zframes),
            "resultFrameCount": len(self._results),
        }

    def align_frames(self, frames: list[Frame]) -> list[Frame]:
        out = []
        for fr in frames:
            row = self._results.get(fr.frame_idx)
            poss = row.get("possessionTeam") if row else None
            out.append(replace(fr, attacking=poss if poss in ("home", "away") else None))
        return out

    def result_row(self, frame_idx: int) -> dict | None:
        return self._results.get(frame_idx)

    def residual_zone_owner_ids(self, frame: Frame) -> list[str]:
        """Outfield defenders with a non-empty residual zone on this exact frame."""
        if frame.defending_team is None:
            return []
        data = self._zones.get(frame.frame_idx)
        if not data or not data.get("defenders"):
            return []
        outfield = {p.player_id for p in frame.outfield_players(frame.defending_team)}
        return [
            str(pid)
            for pid, cells in data["defenders"].items()
            if cells and str(pid) in outfield
        ]

    def is_complete_frame(self, frame: Frame) -> bool:
        """Contestants + near-ball set + residual zones on this exact frame."""
        if frame.defending_team is None:
            return False
        row = self._results.get(frame.frame_idx)
        if not row or row.get("possessionTeam") not in ("home", "away"):
            return False
        if not row.get("contestantIds") or not row.get("nearBallIds"):
            return False
        return bool(self.residual_zone_owner_ids(frame))

    def edges_for_frame(self, frame: Frame) -> list[Edge]:
        return self.categories_for_frame(frame)["collective"]

    def categories_for_frame(self, frame: Frame) -> dict[str, list[Edge]]:
        near = self._marking_edges(frame)
        space = self._space_edges(frame)
        cont = _ids(self._results.get(frame.frame_idx), "contestantIds")
        by_pair = {(e.defender_id, e.attacker_id): e for e in space}
        for e in near:
            by_pair[(e.defender_id, e.attacker_id)] = e
        return {
            "contestant": [e for e in near if e.attacker_id in cont],
            "near_ball": near,
            "space": space,
            "collective": list(by_pair.values()),
        }

    def zone_stats(self, frame: Frame, space_edges: list[Edge] | None = None) -> dict:
        """Residual zone loads + near-ball size / composition for this exact frame."""
        zids = self.residual_zone_owner_ids(frame)
        edges = space_edges if space_edges is not None else self._space_edges(frame)
        cnt = Counter(e.defender_id for e in edges)
        loads = [int(cnt.get(z, 0)) for z in zids]

        row = self._results.get(frame.frame_idx)
        near = _ids(row, "nearBallIds")
        n_near = n_def = n_att = None
        if row is not None and frame.defending_team is not None:
            attacking = "away" if frame.defending_team == "home" else "home"
            def_ids = {p.player_id for p in frame.outfield_players(frame.defending_team)}
            att_ids = {p.player_id for p in frame.outfield_players(attacking)}
            n_near = len(near & (def_ids | att_ids))
            n_def = len(near & def_ids)
            n_att = len(near & att_ids)
        elif row is not None:
            n_near = len(near)

        area = None
        data = self._zones.get(frame.frame_idx)
        if data is not None and self._zh:
            dx = abs(float(self._zh.get("dx") or 0.0))
            dy = abs(float(self._zh.get("dy") or 0.0))
            if dx > 0 and dy > 0:
                area = float(len(data.get("collective") or []) * dx * dy)

        return {
            "loads": loads,
            "nearPlayers": n_near,
            "nearDefenders": n_def,
            "nearAttackers": n_att,
            "nearArea_m2": area,
        }

    def _marking_edges(self, frame: Frame) -> list[Edge]:
        row = self._results.get(frame.frame_idx)
        if not row or frame.defending_team is None:
            return []
        by_id = {p.player_id: p for p in frame.home_players + frame.away_players}
        out = []
        for pair in row.get("markingEdges") or []:
            if not pair or len(pair) < 2:
                continue
            d, a = by_id.get(str(pair[0])), by_id.get(str(pair[1]))
            if d and a:
                out.append(Edge(d.player_id, a.player_id, float(np.hypot(d.x - a.x, d.y - a.y))))
        return out

    def _zone_owners(self, frame_idx: int) -> dict[int, str] | None:
        """Cell→defender map; exact frame, else held prior (viewer / incomplete frames)."""
        data = self._zones.get(frame_idx)
        held = frame_idx if data is not None else _held(frame_idx, self._zframes)
        if held is None:
            return None
        data = self._zones.get(held)
        if not data or not data.get("defenders"):
            return None
        if held not in self._owners:
            own: dict[int, str] = {}
            for pid, cells in data["defenders"].items():
                for c in cells or []:
                    own[int(c)] = str(pid)
            self._owners[held] = own
        return self._owners[held]

    def _space_edges(self, frame: Frame) -> list[Edge]:
        if frame.defending_team is None or not self._zh:
            return []
        owner = self._zone_owners(frame.frame_idx)
        if not owner:
            return []
        defending = frame.defending_team
        attacking = "away" if defending == "home" else "home"
        defs = {p.player_id: p for p in frame.outfield_players(defending)}
        near = _ids(self._results.get(frame.frame_idx), "nearBallIds")
        out = []
        for att in frame.outfield_players(attacking):
            if att.player_id in near:
                continue
            cell = _cell_index(att.x, att.y, self._zh)
            if cell is None:
                continue
            did = owner.get(cell)
            if did is None or did not in defs:
                continue
            d = defs[did]
            out.append(Edge(did, att.player_id, float(np.hypot(d.x - att.x, d.y - att.y))))
        return out
