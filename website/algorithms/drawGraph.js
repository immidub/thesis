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
    return graphToCanvasEdges(graph, built.players, false, frame);
}

function getAttackingShapeGraphEdges(frame) {
    var built = buildAttackingDelaunay(frame);
    if (!built) return [];

    var graph = computeBaseGraph(built.delaunay);
    if (built.players.length >= 4) {
        computeShapeGraph(built.delaunay, graph);
    }

    return graphToCanvasEdges(graph, built.players, false, frame);
}

function buildAllOutfieldPlayers(frame) {
    if (!isBallLive(frame)) return null;

    var team1Players = getTeamPlayerPositions(frame, 1);
    var team2Players = getTeamPlayerPositions(frame, 2);

    for (var i = 0; i < team1Players.length; i++) {
        team1Players[i].team = 1;
    }
    for (var j = 0; j < team2Players.length; j++) {
        team2Players[j].team = 2;
    }

    var players = team1Players.concat(team2Players);
    return buildDelaunayFromPlayers(players);
}

function getAllOutfieldDelaunayEdges(frame) {
    var built = buildAllOutfieldPlayers(frame);
    if (!built) return [];

    var graph = computeBaseGraph(built.delaunay);
    return graphToCanvasEdges(graph, built.players, shapeGraphOpponentsOnly, frame);
}

function getAllOutfieldShapeGraphEdges(frame) {
    var built = buildAllOutfieldPlayers(frame);
    if (!built) return [];

    var graph = computeBaseGraph(built.delaunay);
    if (built.players.length >= 4) {
        computeShapeGraph(built.delaunay, graph);
    }

    return graphToCanvasEdges(graph, built.players, shapeGraphOpponentsOnly, frame);
}

function getPlayerPairKey(playerA, playerB) {
    var idA = String(playerA.id);
    var idB = String(playerB.id);
    return idA < idB ? idA + ":" + idB : idB + ":" + idA;
}

function playerPairInSet(pairSet, playerA, playerB) {
    return pairSet != null && pairSet[getPlayerPairKey(playerA, playerB)] === true;
}

function getDelaunayOpponentPairSet(frame) {
    var built = buildAllOutfieldPlayers(frame);
    if (!built) return null;

    var graph = computeBaseGraph(built.delaunay);
    var pairs = {};
    for (var i = 0; i < graph.length; i++) {
        for (var j = 0; j < graph[i].length; j++) {
            var k = graph[i][j];
            if (k <= i) continue;
            if (built.players[i].team === built.players[k].team) continue;
            if (!passesGraphEdgePairFilter(frame, built.players[i], built.players[k])) continue;
            pairs[getPlayerPairKey(built.players[i], built.players[k])] = true;
        }
    }
    return pairs;
}

function graphToCanvasEdges(graph, players, opponentsOnly, frame) {
    var edges = [];
    for (var i = 0; i < graph.length; i++) {
        for (var j = 0; j < graph[i].length; j++) {
            var k = graph[i][j];
            if (k <= i) continue;
            if (opponentsOnly && players[i].team === players[k].team) continue;
            if (!passesGraphEdgePairFilter(frame, players[i], players[k])) continue;
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

var attackingGraphMode = "delaunay";
var allOutfieldGraphMode = "delaunay";
var shapeGraphOpponentsOnly = false;

function setupAttackingGraphMode() {
    var radios = document.querySelectorAll('input[name="attacking_graph_mode"]');
    if (!radios.length) return;

    radios.forEach(function (radio) {
        if (radio.checked) attackingGraphMode = radio.value;
        radio.addEventListener("change", function () {
            if (radio.checked) attackingGraphMode = radio.value;
        });
    });
}

function setupAllOutfieldGraph() {
    var radios = document.querySelectorAll('input[name="all_outfield_graph_mode"]');
    radios.forEach(function (radio) {
        if (radio.checked) allOutfieldGraphMode = radio.value;
        radio.addEventListener("change", function () {
            if (radio.checked) allOutfieldGraphMode = radio.value;
        });
    });

    var checkbox = document.getElementById("shape_graph_opponents_only");
    if (checkbox) {
        shapeGraphOpponentsOnly = checkbox.checked;
        checkbox.addEventListener("change", function () {
            shapeGraphOpponentsOnly = checkbox.checked;
        });
    }
}
