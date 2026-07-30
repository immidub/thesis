// Marking edges: mutual 2-NN across teams, Delaunay-filtered, mutual-help zone only.

const RESPONSIBILITY_MARKING_K = 2;

// For each source player, find their k nearest opponents and record edges with consistent team1/team2 IDs.
function collect2nnOpponentEdges(sources, targets, k, outEdges, sourceIsTeam1) {
    collectKnnOpponentEdges(sources, targets, k, function (player, opp) {
        var team1Player = sourceIsTeam1 ? player : opp;
        var team2Player = sourceIsTeam1 ? opp : player;

        outEdges.push({
            team1Id: String(team1Player.id),
            team2Id: String(team2Player.id),
            x1: team1Player.x,
            y1: team1Player.y,
            x2: team2Player.x,
            y2: team2Player.y,
        });
    });
}

function getResponsibilityMarkingEdges(frame, contestants, k) {
    var knnK = k != null ? k : RESPONSIBILITY_MARKING_K;
    if (!isBallLive(frame) || !contestants || contestants.length === 0) return [];

    var team1Players = getTeamPlayerPositions(frame, 1);
    var team2Players = getTeamPlayerPositions(frame, 2);

    // Step 1: collect directed 2-NN edges in both directions.
    var team1ToTeam2 = [];
    var team2ToTeam1 = [];
    collect2nnOpponentEdges(team1Players, team2Players, knnK, team1ToTeam2, true);
    collect2nnOpponentEdges(team2Players, team1Players, knnK, team2ToTeam1, false);

    // Index directed edges so we can require mutual nearest-neighbor pairs.
    var inTeam1ToTeam2 = {};
    var inTeam2ToTeam1 = {};
    var edgeByPairKey = {};

    for (var i = 0; i < team1ToTeam2.length; i++) {
        var edgeA = team1ToTeam2[i];
        var directedKey = String(edgeA.team1Id) + ":" + String(edgeA.team2Id);
        inTeam1ToTeam2[directedKey] = true;
        edgeByPairKey[getUndirectedPairKey(edgeA.team1Id, edgeA.team2Id)] = edgeA;
    }

    for (var j = 0; j < team2ToTeam1.length; j++) {
        var edgeB = team2ToTeam1[j];
        var reverseKey = String(edgeB.team1Id) + ":" + String(edgeB.team2Id);
        inTeam2ToTeam1[reverseKey] = true;
        var pairKey = getUndirectedPairKey(edgeB.team1Id, edgeB.team2Id);
        if (!edgeByPairKey[pairKey]) {
            edgeByPairKey[pairKey] = edgeB;
        }
    }

    // Step 2: keep edges that pass all three filters.
    var delaunayPairs = getAllOutfieldDelaunayOpponentPairSet(frame);
    var zonePlayerIds = getMutualHelpZonePlayerIds(frame, contestants);
    var edges = [];

    for (var pairKey in edgeByPairKey) {
        var edge = edgeByPairKey[pairKey];
        var team1To2Key = String(edge.team1Id) + ":" + String(edge.team2Id);
        if (!inTeam1ToTeam2[team1To2Key] || !inTeam2ToTeam1[team1To2Key]) continue; // mutual 2-NN
        if (!delaunayPairs[pairKey]) continue;                                          // Delaunay opponent link
        if (!zonePlayerIds[edge.team1Id] && !zonePlayerIds[edge.team2Id]) continue;    // at least one in help zone

        edges.push({
            x1: edge.x1,
            y1: edge.y1,
            x2: edge.x2,
            y2: edge.y2,
        });
    }

    return edges;
}
