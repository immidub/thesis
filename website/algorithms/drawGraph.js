const GRAPH_EDGE_COLOR = "#9333EA";

function buildDelaunayFromPlayers(players) {
    if (players.length < 2) return null;

    var points = [];
    for (var i = 0; i < players.length; i++) {
        points.push([players[i].v, players[i].h]);
    }

    return {
        delaunay: d3.Delaunay.from(points),
        players: players,
    };
}

function buildAttackingDelaunay(frame) {
    if (!isBallLive(frame)) return null;

    var attackingTeam = getAttackingTeam(frame);
    if (attackingTeam == null) return null;

    return buildDelaunayFromPlayers(getTeamPlayerPositions(frame, attackingTeam));
}

function getAttackingDelaunayEdges(frame) {
    var built = buildAttackingDelaunay(frame);
    if (!built) return [];

    var graph = computeBaseGraph(built.delaunay);
    return graphToCanvasEdges(graph, built.players);
}

function getAttackingShapeGraphEdges(frame) {
    var built = buildAttackingDelaunay(frame);
    if (!built) return [];

    var graph = computeBaseGraph(built.delaunay);
    if (built.players.length >= 4) {
        computeShapeGraph(built.delaunay, graph);
    }

    return graphToCanvasEdges(graph, built.players);
}

function getAllOutfieldShapeGraphEdges(frame) {
    if (!isBallLive(frame)) return [];

    var team1Players = getTeamPlayerPositions(frame, 1);
    var team2Players = getTeamPlayerPositions(frame, 2);

    for (var i = 0; i < team1Players.length; i++) {
        team1Players[i].team = 1;
    }
    for (var j = 0; j < team2Players.length; j++) {
        team2Players[j].team = 2;
    }

    var players = team1Players.concat(team2Players);
    var built = buildDelaunayFromPlayers(players);
    if (!built) return [];

    var graph = computeBaseGraph(built.delaunay);
    if (built.players.length >= 4) {
        computeShapeGraph(built.delaunay, graph);
    }

    return graphToCanvasEdges(graph, built.players, shapeGraphOpponentsOnly);
}

function graphToCanvasEdges(graph, players, opponentsOnly) {
    var edges = [];
    for (var i = 0; i < graph.length; i++) {
        for (var j = 0; j < graph[i].length; j++) {
            var k = graph[i][j];
            if (k <= i) continue;
            if (opponentsOnly && players[i].team === players[k].team) continue;
            edges.push({
                x1: players[i].x,
                y1: players[i].y,
                x2: players[k].x,
                y2: players[k].y,
            });
        }
    }
    return edges;
}

function drawGraphEdges(edges, color) {
    if (!edges || edges.length === 0) return;

    gameCanvas.ctx.strokeStyle = color != null ? color : GRAPH_EDGE_COLOR;
    gameCanvas.ctx.lineWidth = 2;

    for (var i = 0; i < edges.length; i++) {
        var edge = edges[i];
        gameCanvas.drawLine(edge.x1, edge.y1, edge.x2, edge.y2);
    }

    gameCanvas.ctx.lineWidth = 1;
}

var shapeGraphOpponentsOnly = false;

function setupAllOutfieldShapeGraph() {
    var checkbox = document.getElementById("shape_graph_opponents_only");
    if (!checkbox) return;

    shapeGraphOpponentsOnly = checkbox.checked;

    checkbox.addEventListener("change", function () {
        shapeGraphOpponentsOnly = checkbox.checked;
    });
}
