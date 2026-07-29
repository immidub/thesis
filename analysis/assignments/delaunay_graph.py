"""Bipartite Delaunay and shape-graph marking.

``delaunay``: SciPy Delaunay on all outfield players → opponent edges.
``shape_graph``: same, after Eppler / website shapeGraph.js angle pruning.
"""

from __future__ import annotations

import math

import numpy as np
from scipy.spatial import ConvexHull, Delaunay, QhullError

from analysis.assignments.base import Edge
from analysis.data import Frame, Player

_ANGLE_LIMIT = 135.0 / 180.0 * math.pi


class DelaunayAssignment:
    name = "delaunay"

    def edges_for_frame(self, frame: Frame) -> list[Edge]:
        return _marking_edges(frame, prune_shape=False)


class ShapeGraphAssignment:
    name = "shape_graph"

    def edges_for_frame(self, frame: Frame) -> list[Edge]:
        return _marking_edges(frame, prune_shape=True)


def _marking_edges(frame: Frame, *, prune_shape: bool) -> list[Edge]:
    defending = frame.defending_team
    if defending is None:
        return []
    home = list(frame.outfield_players("home"))
    away = list(frame.outfield_players("away"))
    if not home or not away:
        return []

    players: list[Player] = home + away
    teams = (["home"] * len(home)) + (["away"] * len(away))
    points = np.asarray([[p.x, p.y] for p in players], dtype=np.float64)

    try:
        if prune_shape:
            graph = _neighbor_graph(points)
            if len(players) >= 4:
                _prune_shape_graph(points, graph)
            pairs = ((i, j) for i, nbrs in enumerate(graph) for j in nbrs if j > i)
        else:
            pairs = _delaunay_pairs(points)
    except QhullError:
        return []

    edges: list[Edge] = []
    for i, j in pairs:
        if teams[i] == teams[j]:
            continue
        d, a = (players[i], players[j]) if teams[i] == defending else (players[j], players[i])
        edges.append(
            Edge(defender_id=d.player_id, attacker_id=a.player_id, length_m=math.hypot(d.x - a.x, d.y - a.y))
        )
    return edges


def _delaunay_pairs(points: np.ndarray) -> list[tuple[int, int]]:
    n = len(points)
    if n < 2:
        return []
    if n == 2:
        return [(0, 1)]
    if n == 3:
        return [(0, 1), (0, 2), (1, 2)]
    pairs: set[tuple[int, int]] = set()
    for a, b, c in Delaunay(points).simplices:
        for u, v in ((int(a), int(b)), (int(b), int(c)), (int(c), int(a))):
            pairs.add((u, v) if u < v else (v, u))
    return list(pairs)


def _neighbor_graph(points: np.ndarray) -> list[list[int]]:
    n = len(points)
    adj: list[set[int]] = [set() for _ in range(n)]
    for i, j in _delaunay_pairs(points):
        adj[i].add(j)
        adj[j].add(i)
    graph: list[list[int]] = []
    for i, nbrs in enumerate(adj):
        ordered = sorted(
            nbrs,
            key=lambda j: math.atan2(points[j, 1] - points[i, 1], points[j, 0] - points[i, 0]),
        )
        graph.append(ordered)
    return graph


def _prune_shape_graph(points: np.ndarray, graph: list[list[int]]) -> None:
    """In-place Eppler prune (port of website/algorithms/shapeGraph.js)."""
    hull = list(map(int, ConvexHull(points).vertices))
    hull_edges = {
        (hull[i - 1], hull[i]) if hull[i - 1] < hull[i] else (hull[i], hull[i - 1])
        for i in range(len(hull))
    }
    # queue items: (priority, a, b) with priority = -angle (largest angle first)
    queue: list[tuple[float, int, int]] = []

    def push(a: int, b: int, angle: float) -> None:
        queue.append((-angle, a, b))

    def update(a: int, b: int, angle: float) -> None:
        for k, (_, u, v) in enumerate(queue):
            if (u == a and v == b) or (u == b and v == a):
                queue[k] = (-angle, u, v)
                break
        queue.sort()

    seen: set[tuple[int, int]] = set()
    for ti, nbrs in enumerate(graph):
        for tj in nbrs:
            key = (ti, tj) if ti < tj else (tj, ti)
            if key in seen:
                continue
            seen.add(key)
            if key in hull_edges:
                continue
            a, b = _next(nbrs, tj), _next(graph[tj], ti)
            if a is None or b is None:
                continue
            push(ti, tj, abs(_angle(points, ti, a, tj) + _angle(points, tj, b, ti)))

    for i, tj in enumerate(hull):
        ti = hull[i - 1]
        a = _prev(graph[ti], tj)
        if a is not None:
            push(ti, tj, abs(_angle(points, ti, a, tj)))

    queue.sort()
    while queue:
        neg_angle, ea, eb = queue.pop(0)
        if -neg_angle <= _ANGLE_LIMIT or eb not in graph[ea]:
            continue
        prev, node = ea, _next(graph[ea], eb)
        _drop(graph, ea, eb)
        if node is None:
            continue
        for _ in range(100):
            if node == ea:
                break
            if (min(prev, node), max(prev, node)) not in hull_edges:
                update(
                    prev,
                    node,
                    _stability(points, graph, prev, node) + _stability(points, graph, node, prev),
                )
            nxt = _next(graph[node], prev)
            if nxt is None:
                break
            prev, node = node, nxt


def _stability(points: np.ndarray, graph: list[list[int]], a: int, b: int) -> float:
    min_angle = math.pi
    prev, node = a, _next(graph[a], b)
    if node is None:
        return min_angle
    for _ in range(100):
        if node == a:
            break
        nxt = _next(graph[node], prev)
        if nxt is None:
            break
        min_angle = min(min_angle, _angle(points, a, node, b))
        prev, node = node, nxt
    return abs(min_angle)


def _drop(graph: list[list[int]], a: int, b: int) -> None:
    graph[a] = [x for x in graph[a] if x != b]
    graph[b] = [x for x in graph[b] if x != a]


def _prev(nbrs: list[int], k: int) -> int | None:
    try:
        i = nbrs.index(k)
    except ValueError:
        return None
    return nbrs[i - 1]


def _next(nbrs: list[int], k: int) -> int | None:
    try:
        i = nbrs.index(k)
    except ValueError:
        return None
    return nbrs[(i + 1) % len(nbrs)]


def _angle(points: np.ndarray, p: int, c: int, q: int) -> float:
    ax, ay = points[p] - points[c]
    bx, by = points[q] - points[c]
    mag_a, mag_b = math.hypot(ax, ay), math.hypot(bx, by)
    if mag_a == 0.0 or mag_b == 0.0:
        return 0.0
    cos = max(-1.0, min(1.0, (ax * bx + ay * by) / (mag_a * mag_b)))
    return math.acos(cos)
