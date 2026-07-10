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

function buildAllOutfieldPlayers(frame) { //builds the all outfield players for the given frame
    if (!isBallLive(frame)) return null;

    var team1Players = getTeamPlayerPositions(frame, 1);
    var team2Players = getTeamPlayerPositions(frame, 2);

    for (var i = 0; i < team1Players.length; i++) {
        team1Players[i].team = 1;
    }
    for (var j = 0; j < team2Players.length; j++) {
        team2Players[j].team = 2;
    }

    return buildDelaunayFromPlayers(team1Players.concat(team2Players));
}

function computeDelaunayNeighborGraph(delaunay) { //computes the delaunay neighbor graph for the given delaunay
    var graph = [];
    var n = delaunay.points.length / 2;
    for (var i = 0; i < n; i++) {
        graph.push(Array.from(delaunay.neighbors(i)));
    }
    return graph;
}

function getUndirectedPairKey(idA, idB) {
    var a = String(idA);
    var b = String(idB);
    return a < b ? a + ":" + b : b + ":" + a;
}

function getDirectedPairKey(idA, idB) {
    return String(idA) + ":" + String(idB);
}

function getAllOutfieldDelaunayOpponentPairSet(frame, options) { //gets the all outfield delaunay opponent pair set for the given frame
    options = options || {};
    var built = buildAllOutfieldPlayers(frame);
    if (!built) return options.emptyOnMiss === true ? null : {};

    var graph = computeDelaunayNeighborGraph(built.delaunay);
    var pairs = {};
    var applyGraphEdgeFilter = options.applyGraphEdgeFilter === true;

    for (var i = 0; i < graph.length; i++) {
        for (var j = 0; j < graph[i].length; j++) {
            var k = graph[i][j];
            if (k <= i) continue;
            if (built.players[i].team === built.players[k].team) continue;
            if (applyGraphEdgeFilter &&
                !passesGraphEdgePairFilter(frame, built.players[i], built.players[k])) {
                continue;
            }
            pairs[getUndirectedPairKey(built.players[i].id, built.players[k].id)] = true;
        }
    }

    return pairs;
}
