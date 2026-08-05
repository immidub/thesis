#!/usr/bin/env python3
"""Responsibility inference + writers for responsibility.jsonl / responsibility_zones.jsonl."""

from __future__ import annotations

import json
import math
import time
from pathlib import Path

import numpy as np
from scipy.spatial import ConvexHull, Delaunay, QhullError

from config import (
    ALPHA_REACH,
    DT,
    EPSILON_SECONDS,
    FRAME_RATE,
    HALF_LENGTH,
    HALF_WIDTH,
    HULL_MARGIN_M,
    HULL_RING_SAMPLES,
    MAJORITY_VOTES,
    MAJORITY_WINDOW,
    MARKING_ALPHA,
    MARKING_K,
    MIN_RADIUS,
    MUTUAL_HELP_MAX_EDGE_M2,
    PITCH_LENGTH,
    PITCH_WIDTH_M,
    T_MAX,
    V_MAX,
    ZONES_STRIDE,
    ZONES_XPOINTS,
)


def load_goalie_ids(meta_path: Path | None) -> set[str]:
    if meta_path is None or not meta_path.is_file():
        return set()
    meta = json.loads(meta_path.read_text())
    out = set()
    for side in ("homeTeam", "awayTeam"):
        for p in (meta.get(side) or {}).get("players") or []:
            if p.get("isGoalie"):
                out.add(str(p.get("id")))
    return out


def resolve_tracking_paths(path: Path) -> tuple[Path, str]:
    path = path.resolve()
    if path.suffix.lower() == ".parquet" and path.is_file():
        return path, "parquet"
    if path.suffix.lower() == ".jsonl" and path.is_file():
        pq = path.with_suffix(".parquet")
        return (pq, "parquet") if pq.is_file() else (path, "jsonl")
    pq = path if path.suffix.lower() == ".parquet" else path.with_name("tracking.parquet")
    jl = path if path.suffix.lower() == ".jsonl" else path.with_name("tracking.jsonl")
    if pq.is_file():
        return pq, "parquet"
    if jl.is_file():
        return jl, "jsonl"
    return path, path.suffix.lstrip(".") or "unknown"


def _to_f(v):
    return float(v) if v is not None and v == v else None


def _player_from_row(pid, x, y, speed=None, direction=None, is_goalie=False):
    return {"id": str(pid), "x": float(x), "y": float(y), "speed": _to_f(speed), "direction": _to_f(direction), "is_goalie": bool(is_goalie)}


def _json_players(raw: dict, key: str) -> list[dict]:
    out = []
    for p in raw.get(key) or []:
        if not p.get("playerId") or not p.get("xyz"):
            continue
        out.append(_player_from_row(p["playerId"], p["xyz"][0], p["xyz"][1], p.get("speed"), p.get("direction")))
    return out


def _json_ball(raw: dict):
    b = raw.get("ball")
    if not b or not b.get("xyz"):
        return None
    return {"x": float(b["xyz"][0]), "y": float(b["xyz"][1]), "speed": float(b.get("speed") or 0.0), "direction": float(b.get("direction") or 0.0)}


def load_tracking_jsonl(path: Path, frame_indices: set[int] | None = None) -> list[dict]:
    out = []
    with path.open() as f:
        for i, line in enumerate(f):
            line = line.strip()
            if not line:
                continue
            raw = json.loads(line)
            idx = int(raw["frameIdx"]) if raw.get("frameIdx") is not None else i
            if frame_indices is not None and idx not in frame_indices:
                continue
            out.append(
                {
                    "index": idx,
                    "period": int(raw.get("period") or 1),
                    "live": bool(raw.get("live")),
                    "home": _json_players(raw, "homePlayers"),
                    "away": _json_players(raw, "awayPlayers"),
                    "ball": _json_ball(raw),
                }
            )
    return out


def load_tracking_parquet(path: Path, *, live_only: bool = False, frame_indices: set[int] | None = None) -> list[dict]:
    import pandas as pd

    df = pd.read_parquet(path)
    missing = {"period", "frameIdx", "live", "team", "x", "y"} - set(df.columns)
    if missing:
        raise ValueError(f"Parquet missing columns: {sorted(missing)}")
    if live_only:
        df = df.loc[df["live"] == True]
    if frame_indices is not None:
        df = df.loc[df["frameIdx"].isin(frame_indices)]
    df = df.sort_values(["period", "frameIdx"], kind="mergesort")

    period = df["period"].to_numpy(dtype=np.int32, copy=False)
    frame_idx = df["frameIdx"].to_numpy(dtype=np.int32, copy=False)
    live = df["live"].to_numpy(dtype=bool, copy=False)
    team = df["team"].astype(str).to_numpy(copy=False)
    pid = df["playerId"].astype(str).to_numpy(copy=False) if "playerId" in df.columns else np.full(len(df), "", dtype=object)
    if "isGoalie" in df.columns:
        # Keep conversion explicit to avoid pandas future downcasting warning.
        gk_series = df["isGoalie"].infer_objects(copy=False)
        gk = gk_series.astype("boolean").fillna(False).to_numpy(dtype=bool, copy=False)
    else:
        gk = np.zeros(len(df), dtype=bool)
    x = df["x"].to_numpy(dtype=np.float64, copy=False)
    y = df["y"].to_numpy(dtype=np.float64, copy=False)
    speed = df["speed"].to_numpy(copy=False) if "speed" in df.columns else None
    direction = df["direction"].to_numpy(copy=False) if "direction" in df.columns else None

    out, n, i = [], len(df), 0
    while i < n:
        j, p0, f0 = i + 1, period[i], frame_idx[i]
        while j < n and period[j] == p0 and frame_idx[j] == f0:
            j += 1
        home, away, ball = [], [], None
        for k in range(i, j):
            sp = _to_f(speed[k]) if speed is not None else None
            di = _to_f(direction[k]) if direction is not None else None
            if team[k] == "ball":
                ball = {"x": float(x[k]), "y": float(y[k]), "speed": sp or 0.0, "direction": di or 0.0}
            elif team[k] == "home":
                home.append(_player_from_row(pid[k], x[k], y[k], sp, di, gk[k]))
            elif team[k] == "away":
                away.append(_player_from_row(pid[k], x[k], y[k], sp, di, gk[k]))
        out.append({"index": int(f0), "period": int(p0), "live": bool(live[i]), "home": home, "away": away, "ball": ball})
        i = j
    return out


def load_tracking(path: Path, *, live_only: bool = False, frame_indices: set[int] | None = None) -> tuple[list[dict], str]:
    resolved, kind = resolve_tracking_paths(path)
    if kind == "parquet":
        label = f"parquet:{resolved.name}" + (" (live only)" if live_only else "") + (" (subset)" if frame_indices is not None else "")
        return load_tracking_parquet(resolved, live_only=live_only, frame_indices=frame_indices), label
    if kind == "jsonl":
        frames = load_tracking_jsonl(resolved, frame_indices=frame_indices)
        if live_only:
            frames = [f for f in frames if f["live"] and f["ball"] is not None]
        label = f"jsonl:{resolved.name}" + (" (subset)" if frame_indices is not None else "")
        return frames, label
    raise FileNotFoundError(f"Tracking not found: {path}")


def attach_goalies(frames: list[dict], goalie_ids: set[str]) -> None:
    if not goalie_ids:
        return
    for f in frames:
        for p in f["home"] + f["away"]:
            p["is_goalie"] = bool(p.get("is_goalie")) or p["id"] in goalie_ids


def outfield(frame: dict, team: str) -> list[dict]:
    return [p for p in frame[team] if not p.get("is_goalie")]


def velocity(speed, direction_deg) -> tuple[float, float]:
    if speed is None or direction_deg is None or speed <= 0:
        return 0.0, 0.0
    r = math.radians(direction_deg)
    return speed * math.cos(r), speed * math.sin(r)


def reaches_ball(player: dict, ball: dict, t: float) -> bool:
    k = (1.0 - math.exp(-ALPHA_REACH * t)) / ALPHA_REACH if t > 0 else 0.0
    pvx, pvy = velocity(player.get("speed"), player.get("direction"))
    bvx, bvy = velocity(ball.get("speed"), ball.get("direction"))
    cx, cy = player["x"] + pvx * k, player["y"] + pvy * k
    bx, by = ball["x"] + bvx * t, ball["y"] + bvy * t
    r = MIN_RADIUS if t <= 0 else max(V_MAX * (t - k), MIN_RADIUS)
    return (cx - bx) ** 2 + (cy - by) ** 2 <= r * r


def raw_contestants(frame: dict) -> list[str]:
    if not frame["live"] or frame["ball"] is None:
        return []
    players = [("home", p["id"], p) for p in frame["home"]] + [("away", p["id"], p) for p in frame["away"]]
    if not players:
        return []
    ball, t, t_star = frame["ball"], 0.0, None
    while t <= T_MAX + 1e-9:
        if any(reaches_ball(p, ball, t) for _, _, p in players):
            t_star = t
            break
        t += DT
    if t_star is None:
        return []
    at_star = [(team, pid, p) for team, pid, p in players if reaches_ball(p, ball, t_star)]
    if not at_star:
        return []
    poss_team, poss_id, _ = at_star[0]
    out, seen, t2 = [poss_id], {poss_id}, t_star
    while t2 <= t_star + EPSILON_SECONDS + 1e-9:
        for team, pid, p in players:
            if team != poss_team and pid not in seen and reaches_ball(p, ball, t2):
                seen.add(pid)
                out.append(pid)
        t2 += DT
    return out


def majority_smooth(raw: dict[int, list[str]], keys: list[int]) -> dict[int, list[str]]:
    out, half, n = {}, (MAJORITY_WINDOW - 1) // 2, len(keys)
    for i, key in enumerate(keys):
        s = max(0, i - half)
        e = min(n - 1, s + MAJORITY_WINDOW - 1)
        s = max(0, e - MAJORITY_WINDOW + 1)
        sample = keys[s : e + 1]
        counts: dict[str, int] = {}
        for sk in sample:
            for pid in raw.get(sk, []):
                counts[pid] = counts.get(pid, 0) + 1
        need = max(1, round(MAJORITY_VOTES * len(sample) / MAJORITY_WINDOW))
        kept = [pid for pid, c in counts.items() if c >= need]
        kept.sort(key=lambda pid: (-counts[pid], pid))
        out[key] = kept
    return out


def delaunay_neighbors(players: list[dict]) -> dict[str, list[str]]:
    if len(players) < 2:
        return {p["id"]: [] for p in players}
    pts = np.array([[p["x"], p["y"]] for p in players], dtype=float)
    try:
        tri = Delaunay(pts)
    except QhullError:
        return {p["id"]: [] for p in players}
    adj = [set() for _ in players]
    for s in tri.simplices:
        for i in range(3):
            a, b = int(s[i]), int(s[(i + 1) % 3])
            adj[a].add(b)
            adj[b].add(a)
    return {
        players[i]["id"]: [players[j]["id"] for j in adj[i] if (players[i]["x"] - players[j]["x"]) ** 2 + (players[i]["y"] - players[j]["y"]) ** 2 <= MUTUAL_HELP_MAX_EDGE_M2]
        for i in range(len(players))
    }


def core_near_ball(frame: dict, contestant_ids: list[str]) -> tuple[list[dict], dict[str, dict[str, list[str]]]]:
    by_id = {p["id"]: p for p in frame["home"] + frame["away"]}
    team_by_id = {p["id"]: "home" for p in frame["home"]}
    team_by_id.update({p["id"]: "away" for p in frame["away"]})
    selected, contestants = {}, [(cid, team_by_id[cid]) for cid in contestant_ids if cid in by_id]
    for cid, _ in contestants:
        selected[cid] = by_id[cid]
    team_neigh: dict[str, dict[str, list[str]]] = {}
    for team in {t for _, t in contestants}:
        neigh = delaunay_neighbors(outfield(frame, team))
        team_neigh[team] = neigh
        for cid, cteam in contestants:
            if cteam != team:
                continue
            for nid in neigh.get(cid, []):
                if nid in by_id:
                    selected[nid] = by_id[nid]
    return list(selected.values()), team_neigh


def expand_ring(players: list[dict], margin: float) -> np.ndarray:
    return np.asarray(
        [[p["x"], p["y"]] for p in players]
        + [[p["x"] + margin * math.cos(2 * math.pi * k / HULL_RING_SAMPLES), p["y"] + margin * math.sin(2 * math.pi * k / HULL_RING_SAMPLES)] for p in players for k in range(HULL_RING_SAMPLES)],
        dtype=float,
    )


def make_hull_contains(core: list[dict], margin: float):
    if not core:
        return lambda _x, _y: False
    if len(core) == 1:
        p, r2 = core[0], margin * margin
        return lambda x, y: (x - p["x"]) ** 2 + (y - p["y"]) ** 2 <= r2
    if len(core) == 2:
        a, b, r2 = core[0], core[1], margin * margin
        abx, aby = b["x"] - a["x"], b["y"] - a["y"]
        ab2 = abx * abx + aby * aby
        def contains(x, y):
            t = 0.0 if ab2 <= 0 else ((x - a["x"]) * abx + (y - a["y"]) * aby) / ab2
            t = max(0.0, min(1.0, t))
            cx, cy = a["x"] + t * abx, a["y"] + t * aby
            return (x - cx) ** 2 + (y - cy) ** 2 <= r2
        return contains
    expanded = expand_ring(core, margin)
    try:
        verts = expanded[ConvexHull(expanded).vertices]
    except QhullError:
        r2 = margin * margin
        return lambda x, y: any((x - p["x"]) ** 2 + (y - p["y"]) ** 2 <= r2 for p in core)
    xs, ys, n = verts[:, 0], verts[:, 1], len(verts)
    def contains(x, y):
        inside, j = False, n - 1
        for i in range(n):
            if (ys[i] > y) != (ys[j] > y) and x < (xs[j] - xs[i]) * (y - ys[i]) / (ys[j] - ys[i] + 0.0) + xs[i]:
                inside = not inside
            j = i
        return inside
    return contains


def near_ball_ids(frame: dict, contestant_ids: list[str], core: list[dict] | None = None, team_neigh: dict[str, dict[str, list[str]]] | None = None):
    if core is None or team_neigh is None:
        core, team_neigh = core_near_ball(frame, contestant_ids)
    ids, contains = {p["id"] for p in core}, make_hull_contains(core, HULL_MARGIN_M)
    for p in outfield(frame, "home") + outfield(frame, "away"):
        if p["id"] not in ids and contains(p["x"], p["y"]):
            ids.add(p["id"])
    return ids, core, team_neigh


def mutual_help_edges(frame: dict, contestant_ids: list[str], team_neigh: dict[str, dict[str, list[str]]] | None = None) -> list[list[str]]:
    team_by_id = {p["id"]: t for t, lst in (("home", frame["home"]), ("away", frame["away"])) for p in lst}
    if team_neigh is None:
        team_neigh = {}
        for cid in contestant_ids:
            t = team_by_id.get(cid)
            if t is not None and t not in team_neigh:
                team_neigh[t] = delaunay_neighbors(outfield(frame, t))
    seen, out = set(), []
    for cid in contestant_ids:
        t = team_by_id.get(cid)
        if t is None:
            continue
        for nid in team_neigh.get(t, {}).get(cid, []):
            a, b = (cid, nid) if cid < nid else (nid, cid)
            if (a, b) not in seen:
                seen.add((a, b))
                out.append([a, b])
    return out


def home_gk_on_pos_x(frames: list[dict]) -> dict[int, bool]:
    out: dict[int, bool] = {}
    for f in frames:
        p = f["period"]
        if p in out:
            continue
        hg = next((x for x in f["home"] if x.get("is_goalie")), None)
        ag = next((x for x in f["away"] if x.get("is_goalie")), None)
        out[p] = ag["x"] < hg["x"] if hg and ag and hg["x"] != ag["x"] else True
    return out


def defended_goal(attacking: str, home_pos_x: bool) -> tuple[float, float]:
    defending = "away" if attacking == "home" else "home"
    x = (HALF_LENGTH if home_pos_x else -HALF_LENGTH) if defending == "home" else (-HALF_LENGTH if home_pos_x else HALF_LENGTH)
    return x, 0.0


def oriented_cost(def_xy, att_xy, goal, alpha: float):
    to_goal = goal[None, :] - att_xy
    goal_dist = np.linalg.norm(to_goal, axis=1)
    safe = np.where(goal_dist < 1e-9, 1.0, goal_dist)
    u = to_goal / safe[:, None]
    r = def_xy[:, None, :] - att_xy[None, :, :]
    r_par = np.einsum("ijk,jk->ij", r, u)
    dist_sq = np.einsum("ijk,ijk->ij", r, r)
    dist = np.sqrt(dist_sq)
    r_perp_sq = np.maximum(dist_sq - r_par**2, 0.0)
    cost = np.sqrt((r_par / np.where(r_par > 0.0, alpha, 1.0)) ** 2 + r_perp_sq)
    deg = goal_dist < 1e-9
    if deg.any():
        cost = np.where(deg[None, :], dist, cost)
    return cost, dist


def mutual_pairs(cost: np.ndarray, k: int) -> list[tuple[int, int]]:
    n_def, n_att = cost.shape
    def_ch = np.argpartition(cost, min(k, n_att) - 1, axis=1)[:, : min(k, n_att)]
    att_ch = np.argpartition(cost, min(k, n_def) - 1, axis=0)[: min(k, n_def), :]
    d = {(i, j) for i in range(n_def) for j in def_ch[i].tolist()}
    a = {(i, j) for j in range(n_att) for i in att_ch[:, j].tolist()}
    return sorted(d & a)


def marking_edges(frame: dict, contestant_ids: list[str], attacking: str, home_pos_x: bool, near: set[str] | None = None) -> list[list[str]]:
    if not contestant_ids or attacking not in ("home", "away"):
        return []
    defending = "away" if attacking == "home" else "home"
    if near is None:
        near, _, _ = near_ball_ids(frame, contestant_ids)
    defenders = outfield(frame, defending)
    attackers = [p for p in outfield(frame, attacking) if p["id"] in near]
    if not defenders or not attackers:
        return []
    def_xy = np.array([[p["x"], p["y"]] for p in defenders], dtype=float)
    att_xy = np.array([[p["x"], p["y"]] for p in attackers], dtype=float)
    cost, _ = oriented_cost(def_xy, att_xy, np.asarray(defended_goal(attacking, home_pos_x), dtype=float), MARKING_ALPHA)
    out = []
    for i, j in mutual_pairs(cost, MARKING_K):
        out.append([defenders[i]["id"], attackers[j]["id"]])
    return out


def infer_frame_results(frame: dict, contestant_ids: list[str], attacking: str | None, home_pos_x: bool) -> dict:
    if not contestant_ids:
        return {"coreNearBallIds": [], "nearBallIds": [], "mutualHelpEdges": [], "markingEdges": []}
    near, core, team_neigh = near_ball_ids(frame, contestant_ids)
    return {
        "coreNearBallIds": [p["id"] for p in core],
        "nearBallIds": sorted(near),
        "mutualHelpEdges": mutual_help_edges(frame, contestant_ids, team_neigh),
        "markingEdges": marking_edges(frame, contestant_ids, attacking, home_pos_x, near=near) if attacking in ("home", "away") else [],
    }


DUMMY_XY = 1_000_000.0


def _log(msg: str) -> None:
    print(msg, flush=True)


def _fmt_rate(n: int, seconds: float) -> str:
    if seconds <= 0:
        return f"{n} frames"
    return f"{n} frames in {seconds:.1f}s ({n / seconds:.0f} frames/s)"


def build_results(
    output_dir: Path,
    *,
    limit: int | None = None,
    tracking_path: Path | None = None,
    meta_path: Path | None = None,
) -> Path:
    """Write responsibility.jsonl next to tracking. Returns results path."""
    output_dir = output_dir.resolve()
    tracking_path = tracking_path or (output_dir / "tracking.parquet")
    if not tracking_path.is_file():
        tracking_path = output_dir / "tracking.jsonl"
    meta_path = meta_path or (output_dir / "metaData.json")
    results_path = output_dir / "responsibility.jsonl"

    t0 = time.perf_counter()
    frames, source = load_tracking(tracking_path, live_only=True)
    _log(f"Loading via {source}...")
    attach_goalies(frames, load_goalie_ids(meta_path if meta_path.is_file() else None))
    gk_flags = home_gk_on_pos_x(frames)
    t_load = time.perf_counter() - t0
    _log(f"  loaded {len(frames)} frames in {t_load:.1f}s")

    live = [f for f in frames if f["live"] and f["ball"] is not None]
    if limit is not None:
        live = live[: limit + MAJORITY_WINDOW + 5]
    _log(f"Live frames to process: {len(live)}")

    t1 = time.perf_counter()
    _log("Contestants (reachability)...")
    raw: dict[int, list[str]] = {}
    for i, f in enumerate(live):
        raw[f["index"]] = raw_contestants(f)
        if (i + 1) % 2000 == 0 or i + 1 == len(live):
            _log(f"  {_fmt_rate(i + 1, time.perf_counter() - t1)}")
    smoothed = majority_smooth(raw, [f["index"] for f in live])
    t_contest = time.perf_counter() - t1
    _log(f"  contestants done in {t_contest:.1f}s")

    id_to_team = {p["id"]: "home" for f in frames for p in f["home"]}
    id_to_team.update({p["id"]: "away" for f in frames for p in f["away"]})

    results: list[dict] = []
    last_attacking = None
    t2 = time.perf_counter()
    _log("Near-ball / marking edges...")
    for i, f in enumerate(live):
        idx = f["index"]
        contestants = list(smoothed.get(idx, []))
        raw_ids = raw.get(idx, [])
        if raw_ids and raw_ids[0] in contestants:
            carrier = raw_ids[0]
            contestants = [carrier] + [p for p in contestants if p != carrier]
        if len(contestants) == 1 and contestants[0] in id_to_team:
            last_attacking = id_to_team[contestants[0]]

        graph = infer_frame_results(f, contestants, last_attacking, gk_flags.get(f["period"], True))
        results.append(
            {
                "frame": idx,
                "contestantIds": contestants,
                "carrierId": contestants[0] if len(contestants) == 1 else None,
                "possessionTeam": last_attacking,
                **graph,
            }
        )
        if limit is not None and len(results) >= limit:
            _log(f"  {_fmt_rate(len(results), time.perf_counter() - t2)} (hit --limit)")
            break
        if (i + 1) % 2000 == 0 or i + 1 == len(live):
            _log(f"  {_fmt_rate(len(results), time.perf_counter() - t2)}")
    t_edges = time.perf_counter() - t2
    _log(f"  edges done in {t_edges:.1f}s")

    t3 = time.perf_counter()
    _log(f"Writing {len(results)} frames → {results_path}")
    with results_path.open("w") as out:
        out.write(
            json.dumps(
                {
                    "type": "header",
                    "nearBall": "hull_expanded",
                    "marking": "oriented_mutual_2nn",
                    "hullMargin_m": HULL_MARGIN_M,
                }
            )
            + "\n"
        )
        for row in results:
            out.write(json.dumps(row) + "\n")
    _log(f"  wrote in {time.perf_counter() - t3:.1f}s")
    _log(
        f"Done in {time.perf_counter() - t0:.1f}s "
        f"(load {t_load:.1f}s, contestants {t_contest:.1f}s, edges {t_edges:.1f}s)"
    )
    return results_path


def _load_results(path: Path) -> list[dict]:
    rows: list[dict] = []
    with path.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            if obj.get("type") != "header":
                rows.append(obj)
    return rows


def build_zones(
    output_dir: Path,
    *,
    stride: int = ZONES_STRIDE,
    xpoints: int = ZONES_XPOINTS,
    tracking_path: Path | None = None,
    meta_path: Path | None = None,
    results_path: Path | None = None,
) -> Path:
    """Write responsibility_zones.jsonl. Requires floodlight."""
    try:
        from floodlight.core.pitch import Pitch
        from floodlight.core.xy import XY
        from floodlight.models.space import DiscreteVoronoiModel
    except ImportError as exc:
        raise ImportError(
            "floodlight is required for zones. Install with: pip install floodlight\n"
            f"Import error: {exc}"
        ) from exc

    output_dir = output_dir.resolve()
    tracking_path = tracking_path or (output_dir / "tracking.parquet")
    if not tracking_path.is_file():
        tracking_path = output_dir / "tracking.jsonl"
    meta_path = meta_path or (output_dir / "metaData.json")
    results_path = results_path or (output_dir / "responsibility.jsonl")
    zones_path = output_dir / "responsibility_zones.jsonl"
    if not results_path.is_file():
        raise FileNotFoundError(f"Missing responsibility results: {results_path}")

    def make_pitch() -> Pitch:
        return Pitch(
            xlim=(-HALF_LENGTH, HALF_LENGTH),
            ylim=(-HALF_WIDTH, HALF_WIDTH),
            unit="m",
            boundaries="fixed",
            length=PITCH_LENGTH,
            width=PITCH_WIDTH_M,
            sport="football",
        )

    def players_to_xy(frames_players: list[list[dict]]) -> XY:
        if not frames_players or not frames_players[0]:
            return XY(np.full((max(len(frames_players), 2), 2), DUMMY_XY), framerate=FRAME_RATE)
        n, rows = len(frames_players[0]), []
        for plist in frames_players:
            row = []
            for i in range(n):
                p = plist[i] if i < len(plist) else None
                row.extend([np.nan, np.nan] if p is None else [p["x"], p["y"]])
            rows.append(row)
        if len(rows) == 1:
            rows.append(list(rows[0]))
        return XY(np.asarray(rows, dtype=float), framerate=FRAME_RATE)

    def fit_controls(pitch: Pitch, players: list[dict], prev: list[dict] | None, xp: int):
        prev_by_id = {p["id"]: p for p in (prev or players)}
        prev_aligned = [prev_by_id.get(p["id"], p) for p in players]
        dvm = DiscreteVoronoiModel(
            pitch,
            mesh="square",
            xpoints=xp,
            motion_model="fujimura_sugihara",
            vmax=V_MAX,
            alpha=ALPHA_REACH,
        )
        dvm.fit(
            players_to_xy([prev_aligned, players]),
            XY(np.full((2, 2), DUMMY_XY), framerate=FRAME_RATE),
        )
        return dvm._cell_controls_[1].copy(), dvm._meshx_, dvm._meshy_

    def bubble_mask(players: list[dict], mesh_x, mesh_y, margin: float):
        if not players:
            return np.zeros(mesh_x.shape, dtype=bool)
        if len(players) == 1:
            p = players[0]
            return (mesh_x - p["x"]) ** 2 + (mesh_y - p["y"]) ** 2 <= margin * margin
        try:
            expanded = expand_ring(players, margin)
            hull = ConvexHull(expanded)
            verts = expanded[hull.vertices]
            from matplotlib.path import Path as MplPath

            pts = np.column_stack([mesh_x.ravel(), mesh_y.ravel()])
            return MplPath(verts).contains_points(pts).reshape(mesh_x.shape)
        except Exception:
            mask = np.zeros(mesh_x.shape, dtype=bool)
            for p in players:
                mask |= (mesh_x - p["x"]) ** 2 + (mesh_y - p["y"]) ** 2 <= margin * margin
            return mask

    def offside_x(frame: dict, attacking: str, home_pos_x: bool) -> float | None:
        defending = "away" if attacking == "home" else "home"
        defs = frame[defending]
        if len(defs) < 2:
            return None
        gx = defended_goal(attacking, home_pos_x)[0]
        return sorted(defs, key=lambda p: abs(p["x"] - gx))[1]["x"]

    def compute_zone_frame(frame, prev, contestant_ids, core_ids, attacking, home_pos_x, pitch, xp, mesh_cache):
        if core_ids:
            by_id = {p["id"]: p for p in frame["home"] + frame["away"]}
            core = [by_id[pid] for pid in core_ids if pid in by_id]
        else:
            core, _ = core_near_ball(frame, contestant_ids)
        if not core:
            return None
        defending = "away" if attacking == "home" else "home"
        defenders = list(frame[defending])
        if not defenders:
            return None
        prev_defs = defenders
        if prev is not None:
            prev_by_id = {p["id"]: p for p in prev[defending]}
            prev_defs = [prev_by_id.get(p["id"], p) for p in defenders]
        ctrl, mesh_x, mesh_y = fit_controls(pitch, defenders, prev_defs, xp)
        mesh_cache.update(
            {
                "shape": list(mesh_x.shape),
                "dx": float(mesh_x[0, 1] - mesh_x[0, 0]) if mesh_x.shape[1] > 1 else PITCH_LENGTH,
                "dy": float(mesh_y[1, 0] - mesh_y[0, 0]) if mesh_x.shape[0] > 1 else PITCH_WIDTH_M,
                "x0": float(mesh_x[0, 0]),
                "y0": float(mesh_y[0, 0]),
            }
        )
        bubble = bubble_mask(core, mesh_x, mesh_y, HULL_MARGIN_M)
        ox = offside_x(frame, attacking, home_pos_x)
        if ox is not None:
            if defended_goal(attacking, home_pos_x)[0] > 0:
                bubble &= mesh_x < ox
            else:
                bubble &= mesh_x > ox
        def_cells = {}
        n = len(defenders)
        for i, p in enumerate(defenders):
            mask = (ctrl == i) & np.isfinite(ctrl) & (ctrl < n) & (~bubble)
            idxs = [int(j) for j in np.flatnonzero(mask.reshape(-1))]
            if idxs:
                def_cells[p["id"]] = idxs
        return {
            "frame": frame["index"],
            "collective": [int(j) for j in np.flatnonzero(bubble.reshape(-1))],
            "defenders": def_cells,
        }

    t0 = time.perf_counter()
    rows = _load_results(results_path)
    candidates = [r for r in rows if r.get("contestantIds") and r.get("possessionTeam") in ("home", "away")]
    jobs = candidates[::stride]
    needed = {int(r["frame"]) for r in jobs}
    needed.update(int(r["frame"]) - 1 for r in jobs if int(r["frame"]) > 0)

    frames, source = load_tracking(tracking_path, live_only=False, frame_indices=needed)
    _log(f"Loaded tracking via {source}: {len(frames)} subset frames")
    attach_goalies(frames, load_goalie_ids(meta_path if meta_path.is_file() else None))
    gk_flags = home_gk_on_pos_x(frames)
    by_index = {f["index"]: f for f in frames}
    pitch = make_pitch()
    mesh_cache: dict = {}
    written = 0

    _log(f"Computing zones for {len(jobs)} jobs (stride={stride}, xpoints={xpoints})...")
    with zones_path.open("w") as out:
        out.write(
            json.dumps(
                {
                    "type": "header",
                    "xlim": [-HALF_LENGTH, HALF_LENGTH],
                    "ylim": [-HALF_WIDTH, HALF_WIDTH],
                    "xpoints": xpoints,
                    "motion_model": "fujimura_sugihara",
                    "method": "marking_bubble_plus_defender_pc",
                    "bubble_margin_m": HULL_MARGIN_M,
                    "stride": stride,
                    "possession": "reachability",
                }
            )
            + "\n"
        )
        for i, row in enumerate(jobs):
            frame = by_index.get(row["frame"])
            if frame is None:
                continue
            z = compute_zone_frame(
                frame,
                by_index.get(row["frame"] - 1),
                row["contestantIds"],
                row.get("coreNearBallIds") or [],
                row["possessionTeam"],
                gk_flags.get(frame["period"], True),
                pitch,
                xpoints,
                mesh_cache,
            )
            if z is None:
                continue
            out.write(json.dumps(z) + "\n")
            written += 1
            if written % 25 == 0 or i + 1 == len(jobs):
                _log(f"  {written}/{len(jobs)} in {time.perf_counter() - t0:.1f}s")

    if mesh_cache.get("shape"):
        zone_lines = zones_path.read_text().splitlines()
        header = json.loads(zone_lines[0])
        header.update({k: mesh_cache[k] for k in ("shape", "dx", "dy", "x0", "y0")})
        zones_path.write_text(json.dumps(header) + "\n" + "\n".join(zone_lines[1:]) + "\n")

    _log(f"Done: wrote {written} zones in {time.perf_counter() - t0:.1f}s → {zones_path}")
    return zones_path
