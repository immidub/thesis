// Shape-graph pruning on a Delaunay neighbour graph (Eppler-style angle filter).

function computeShapeGraph(delaunay, graph) {
    var queue = new PriorityQueue();
    var points = delaunay.points;
    var halfedges = delaunay.halfedges;
    var triangles = delaunay.triangles;
    var hull = delaunay.hull;

    if (points.length / 2 < 4) return;

    for (var i = 0, n = halfedges.length; i < n; ++i) {
        var j = halfedges[i];
        if (j < i) continue;
        var ti = triangles[i];
        var tj = triangles[j];

        var neighborsA = Array.from(delaunay.neighbors(ti));
        var neighborsB = Array.from(delaunay.neighbors(tj));

        var a = getNextEdge(neighborsA, tj);
        var b = getNextEdge(neighborsB, ti);

        var angleA = getAngle(ti, a, tj, points);
        var angleB = getAngle(tj, b, ti, points);
        var angle = Math.abs(angleA + angleB);

        queue.enqueueFunction({ a: ti, b: tj }, -angle);
    }

    for (var h = 0; h < hull.length; h++) {
        var hullTi = h === 0 ? hull[hull.length - 1] : hull[h - 1];
        var hullTj = hull[h];
        var hullNeighbors = Array.from(delaunay.neighbors(hullTi));
        var hullPrev = getPrevEdge(hullNeighbors, hullTj);
        var hullAngle = Math.abs(getAngle(hullTi, hullPrev, hullTj, points));
        queue.enqueueFunction({ a: hullTi, b: hullTj }, -hullAngle);
    }

    while (!queue.isPriorityQueueEmpty()) {
        var queueElement = queue.dequeueFunction();
        var edge = queueElement.element;
        var edgeAngle = -queueElement.priority;

        if (edgeAngle > 135 / 180 * Math.PI) {
            var prevNode = edge.a;
            var node = getNextEdge(graph[edge.a], edge.b);
            removeEdge(graph, edge.a, edge.b);

            var cnt = 0;
            while (node != edge.a && cnt < 100) {
                if (!isHullEdge(prevNode, node, hull)) {
                    var updateA = getStabilityAngle(prevNode, node, graph, points);
                    var updateB = getStabilityAngle(node, prevNode, graph, points);
                    queue.updateElement({ a: prevNode, b: node }, -(updateA + updateB));
                }

                cnt++;
                var nextNode = getNextEdge(graph[node], prevNode);
                prevNode = node;
                node = nextNode;
            }
        }
    }
}

function getStabilityAngle(a, b, graph, points) {
    var minAngle = Math.PI;
    var prevNode = a;
    var node = getNextEdge(graph[a], b);
    var cnt = 0;

    while (node != a && cnt < 100) {
        cnt++;
        var nextNode = getNextEdge(graph[node], prevNode);
        var alpha = getAngle(a, node, b, points);
        if (alpha < minAngle) minAngle = alpha;
        prevNode = node;
        node = nextNode;
    }

    return Math.abs(minAngle);
}

function removeEdge(graph, a, b) {
    graph[a] = graph[a].filter(function (item) { return item != b; });
    graph[b] = graph[b].filter(function (item) { return item != a; });
}

function getPrevEdge(neighbors, k) {
    for (var i = 0; i < neighbors.length; i++) {
        if (neighbors[i] == k) {
            return i === 0 ? neighbors[neighbors.length - 1] : neighbors[i - 1];
        }
    }
}

function getNextEdge(neighbors, k) {
    for (var i = 0; i < neighbors.length; i++) {
        if (neighbors[i] == k) {
            return i < neighbors.length - 1 ? neighbors[i + 1] : neighbors[0];
        }
    }
}

function isHullEdge(a, b, hull) {
    return isHullEdgeOneWay(a, b, hull) || isHullEdgeOneWay(b, a, hull);
}

function isHullEdgeOneWay(a, b, hull) {
    for (var i = 0; i < hull.length; i++) {
        if (hull[i] == a) {
            return i === hull.length - 1 ? hull[0] == b : hull[i + 1] == b;
        }
    }
}

function getAngle(neighborA, center, neighborB, points) {
    var ax = points[2 * neighborA] - points[2 * center];
    var ay = points[2 * neighborA + 1] - points[2 * center + 1];
    var bx = points[2 * neighborB] - points[2 * center];
    var by = points[2 * neighborB + 1] - points[2 * center + 1];
    var magA = Math.sqrt(ax * ax + ay * ay);
    var magB = Math.sqrt(bx * bx + by * by);
    if (magA === 0 || magB === 0) return 0;
    var cos = (ax * bx + ay * by) / (magA * magB);
    cos = Math.max(-1, Math.min(1, cos));
    return Math.acos(cos);
}
