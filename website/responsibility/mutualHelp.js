// Zone of mutual help: teammates linked by Delaunay edges around each ball contestant.

function getMutualHelpEdges(frame, contestants) {
    if (!contestants || contestants.length === 0) return [];

    // Build one Delaunay graph per team (cached so we don't rebuild for every contestant).
    var teamBuilt = {};
    var teamGraph = {};
    var teamIndexById = {};

    for (var t = 0; t < contestants.length; t++) {
        var team = contestants[t].team;
        if (teamBuilt[team]) continue;

        var built = buildDelaunayFromPlayers(getTeamPlayerPositions(frame, team));
        teamBuilt[team] = built;
        if (!built) continue;

        teamGraph[team] = computeDelaunayNeighborGraph(built.delaunay); // computes the delaunay neighbor graph for the given team

        var byId = {};
        for (var i = 0; i < built.players.length; i++) {
            byId[String(built.players[i].id)] = i;
        }
        teamIndexById[team] = byId;
    }

    var seen = {};
    var edges = [];

    // For each contestant, draw edges to their same-team Delaunay neighbors.
    for (var c = 0; c < contestants.length; c++) {
        var contestant = contestants[c];
        if (!contestant || contestant.id == null || contestant.team == null) continue;

        var builtTeam = teamBuilt[contestant.team];
        var graph = teamGraph[contestant.team];
        var indexById = teamIndexById[contestant.team];
        if (!builtTeam || !graph || !indexById) continue;

        var idx = indexById[String(contestant.id)];
        if (idx == null) continue;

        var neighbors = graph[idx];
        for (var n = 0; n < neighbors.length; n++) {
            var neighbor = builtTeam.players[neighbors[n]];
            if (!neighbor) continue;

            var pairKey = getUndirectedPairKey(contestant.id, neighbor.id);
            if (seen[pairKey]) continue; // avoid duplicate edges when two contestants share a neighbor
            seen[pairKey] = true;

            edges.push({
                x1: builtTeam.players[idx].x,
                y1: builtTeam.players[idx].y,
                x2: neighbor.x,
                y2: neighbor.y,
            });
        }
    }

    return edges;
}

// Returns the set of player IDs in the mutual-help zone: contestants plus their Delaunay neighbors.
function getMutualHelpZonePlayerIds(frame, contestants) {
    var ids = {};
    if (!contestants || contestants.length === 0) return ids;

    for (var c = 0; c < contestants.length; c++) {
        var contestant = contestants[c];
        if (!contestant || contestant.id == null || contestant.team == null) continue;

        ids[String(contestant.id)] = true;

        // Neighbors on the same team's Delaunay triangulation are in the help zone.
        var built = buildDelaunayFromPlayers(getTeamPlayerPositions(frame, contestant.team));
        if (!built) continue;

        var graph = computeDelaunayNeighborGraph(built.delaunay);
        var indexById = {};
        for (var i = 0; i < built.players.length; i++) { // builds the index by id for the given built
            indexById[String(built.players[i].id)] = i;
        }

        var idx = indexById[String(contestant.id)];
        if (idx == null) continue;

        var neighbors = graph[idx];
        for (var n = 0; n < neighbors.length; n++) { // adds the neighbors to the ids
            var neighbor = built.players[neighbors[n]];
            if (neighbor) {
                ids[String(neighbor.id)] = true;
            }
        }
    }

    return ids;
}
