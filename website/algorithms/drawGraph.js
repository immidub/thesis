const GRAPH_EDGE_COLOR = "#9333EA";

function buildAttackingDelaunay(frame) { //builds the attacking delaunay
    if (!isBallLive(frame)) return null;

    var possessionTeam = getPossessionTeam(frame);
    if (possessionTeam == null) return null;

    return buildDelaunayFromPlayers(getTeamPlayerPositions(frame, possessionTeam));
}

function getAttackingDelaunayEdges(frame) { //gets the attacking delaunay edges for the given frame
    var built = buildAttackingDelaunay(frame);
    if (!built) return [];

    var graph = computeDelaunayNeighborGraph(built.delaunay);
    return graphToCanvasEdges(graph, built.players, false, frame);
}

function getAttackingShapeGraphEdges(frame) { //gets the attacking shape graph edges for the given frame
    var built = buildAttackingDelaunay(frame);
    if (!built) return [];

    var graph = computeDelaunayNeighborGraph(built.delaunay);
    if (built.players.length >= 4) {
        computeShapeGraph(built.delaunay, graph);
    }

    return graphToCanvasEdges(graph, built.players, false, frame);
}

function getAllOutfieldDelaunayEdges(frame) { //gets the all outfield delaunay edges for the given frame
    var built = buildAllOutfieldPlayers(frame);
    if (!built) return [];

    var graph = computeDelaunayNeighborGraph(built.delaunay);
    return graphToCanvasEdges(graph, built.players, shapeGraphOpponentsOnly, frame);
}

function getAllOutfieldShapeGraphEdges(frame) { //gets the all outfield shape graph edges for the given frame
    var built = buildAllOutfieldPlayers(frame);
    if (!built) return [];

    var graph = computeDelaunayNeighborGraph(built.delaunay);
    if (built.players.length >= 4) {
        computeShapeGraph(built.delaunay, graph);
    }

    return graphToCanvasEdges(graph, built.players, shapeGraphOpponentsOnly, frame);
}

function markingPairInDelaunaySet(pairSet, defender, attacker) { //used to check if the pair is in the delaunay set
    return pairSet != null && pairSet[getUndirectedPairKey(defender.id, attacker.id)] === true;
}

function getDelaunayOpponentPairSet(frame) { //gets the delaunay opponent pair set for the given frame
    return getAllOutfieldDelaunayOpponentPairSet(frame, {
        applyGraphEdgeFilter: true,
        emptyOnMiss: true,
    });
}

function graphToCanvasEdges(graph, players, opponentsOnly, frame) { //converts the graph to canvas edges
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
    drawCanvasEdges(edges, {
        color: color != null ? color : GRAPH_EDGE_COLOR,
        dashedSupport: false,
    });
}

var attackingGraphMode = "delaunay";
var allOutfieldGraphMode = "delaunay";
var shapeGraphOpponentsOnly = false;

//-------------------------------- setup functions --------------------------------//

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
