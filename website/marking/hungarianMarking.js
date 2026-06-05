function getHungarianMarkingEdges(frame) {
    if (!isBallTracked(frame)) return [];

    var defendingTeam = getDefendingTeam(frame);
    if (defendingTeam == null) return [];

    var defenders = getTeamPlayerPositions(frame, defendingTeam);
    var opponents = getTeamPlayerPositions(frame, defendingTeam === 1 ? 2 : 1);

    if (defenders.length === 0 || opponents.length === 0) return [];

    var costMatrix = buildDefenderOpponentCostMatrix(defenders, opponents);
    var indices = computeMunkres(costMatrix);
    return indicesToMarkingEdges(indices, defenders, opponents);
}

function buildDefenderOpponentCostMatrix(defenders, opponents) {
    var costMatrix = [];
    for (var i = 0; i < defenders.length; i++) {
        costMatrix[i] = [];
        for (var j = 0; j < opponents.length; j++) {
            costMatrix[i][j] = getPitchDistanceSquared(
                defenders[i].h,
                defenders[i].v,
                opponents[j].h,
                opponents[j].v
            );
        }
    }
    return costMatrix;
}

function indicesToMarkingEdges(indices, defenders, opponents) {
    var edges = [];
    for (var k = 0; k < indices.length; k++) {
        var defIdx = indices[k][0];
        var oppIdx = indices[k][1];
        if (defIdx >= defenders.length || oppIdx >= opponents.length) continue;

        edges.push({
            x1: defenders[defIdx].x,
            y1: defenders[defIdx].y,
            x2: opponents[oppIdx].x,
            y2: opponents[oppIdx].y,
        });
    }
    return edges;
}
