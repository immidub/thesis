function getAllOutfieldDelaunayEdges(frame) { //gets the all outfield delaunay edges for the given frame
    var built = buildAllOutfieldPlayers(frame);
    if (!built) return [];

    var graph = computeDelaunayNeighborGraph(built.delaunay);
    return graphToCanvasEdges(graph, built.players, shapeGraphOpponentsOnly);
}

function getAllOutfieldShapeGraphEdges(frame) { //gets the all outfield shape graph edges for the given frame
    var built = buildAllOutfieldPlayers(frame);
    if (!built) return [];

    var graph = computeDelaunayNeighborGraph(built.delaunay);
    if (built.players.length >= 4) {
        computeShapeGraph(built.delaunay, graph);
    }

    return graphToCanvasEdges(graph, built.players, shapeGraphOpponentsOnly);
}

function markingPairInDelaunaySet(pairSet, defender, attacker) {
    return pairSet != null && pairSet[getUndirectedPairKey(defender.id, attacker.id)] === true;
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
                playerIdA: players[i].id,
                playerIdB: players[k].id,
                lengthM: getEuclideanPairDistance(players[i], players[k]),
            });
        }
    }
    return edges;
}

function drawGraphEdges(edges, color) {
    drawCanvasEdges(edges, {
        color: color != null ? color : MARKING_EDGE_COLOR,
        dashedSupport: false,
    });
}

var allOutfieldGraphMode = "delaunay";
var shapeGraphOpponentsOnly = false;

//-------------------------------- setup functions --------------------------------//

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
