// Zone of mutual help: Delaunay neighbors on the contestant's own team.

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
    if (players.length < 2) return null;

    var points = [];
    for (var k = 0; k < players.length; k++) {
        points.push([players[k].v, players[k].h]);
    }

    return {
        delaunay: d3.Delaunay.from(points),
        players: players,
    };
}

function getAllOutfieldDelaunayOpponentPairSet(frame) {
    var built = buildAllOutfieldPlayers(frame);
    if (!built) return {};

    var graph = computeTeamDelaunayGraph(built.delaunay);
    var pairs = {};

    for (var i = 0; i < graph.length; i++) {
        for (var j = 0; j < graph[i].length; j++) {
            var k = graph[i][j];
            if (k <= i) continue;
            if (built.players[i].team === built.players[k].team) continue;
            pairs[getMutualHelpPairKey(built.players[i].id, built.players[k].id)] = true;
        }
    }

    return pairs;
}

function buildTeamDelaunay(frame, team) {
    var players = getTeamPlayerPositions(frame, team);
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

function computeTeamDelaunayGraph(delaunay) {
    var graph = [];
    var n = delaunay.points.length / 2;
    for (var i = 0; i < n; i++) {
        graph.push(Array.from(delaunay.neighbors(i)));
    }
    return graph;
}

function getMutualHelpPairKey(idA, idB) {
    var a = String(idA);
    var b = String(idB);
    return a < b ? a + ":" + b : b + ":" + a;
}

function getMutualHelpEdges(frame, contestants) {
    if (!contestants || contestants.length === 0) return [];

    var teamBuilt = {};
    var teamGraph = {};
    var teamIndexById = {};

    for (var t = 0; t < contestants.length; t++) {
        var team = contestants[t].team;
        if (teamBuilt[team]) continue;

        var built = buildTeamDelaunay(frame, team);
        teamBuilt[team] = built;
        if (!built) continue;

        teamGraph[team] = computeTeamDelaunayGraph(built.delaunay);

        var byId = {};
        for (var i = 0; i < built.players.length; i++) {
            byId[String(built.players[i].id)] = i;
        }
        teamIndexById[team] = byId;
    }

    var seen = {};
    var edges = [];

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

            var pairKey = getMutualHelpPairKey(contestant.id, neighbor.id);
            if (seen[pairKey]) continue;
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

function getMutualHelpZonePlayerIds(frame, contestants) {
    var ids = {};
    if (!contestants || contestants.length === 0) return ids;

    for (var c = 0; c < contestants.length; c++) {
        var contestant = contestants[c];
        if (!contestant || contestant.id == null || contestant.team == null) continue;

        ids[String(contestant.id)] = true;

        var built = buildTeamDelaunay(frame, contestant.team);
        if (!built) continue;

        var graph = computeTeamDelaunayGraph(built.delaunay);
        var indexById = {};
        for (var i = 0; i < built.players.length; i++) {
            indexById[String(built.players[i].id)] = i;
        }

        var idx = indexById[String(contestant.id)];
        if (idx == null) continue;

        var neighbors = graph[idx];
        for (var n = 0; n < neighbors.length; n++) {
            var neighbor = built.players[neighbors[n]];
            if (neighbor) {
                ids[String(neighbor.id)] = true;
            }
        }
    }

    return ids;
}
