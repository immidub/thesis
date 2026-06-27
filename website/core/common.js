function getTeamPlayerPositions(frame, team, includeGoalkeepers) {
    var players = [];
    var dataLine = gameData.tracking[frame];

    for (var playerId in dataLine.objects) {
        if (team == 1 && !gameData.players.team1.includes(String(playerId))) continue;
        if (team == 2 && !gameData.players.team2.includes(String(playerId))) continue;
        if (!includeGoalkeepers && isGoalkeeperPlayer(playerId)) continue;

        var object = dataLine.objects[playerId];
        var [h, v] = getCoordinates(object, object);

        var [x, y] = pt(h, v);

        var player = {
            id: playerId,
            h: h,
            v: v,
            x: x,
            y: y,
        };
        if (object.speed != null) player.speed = object.speed;
        if (object.direction != null) player.direction = object.direction;
        if (object.distToBall != null) player.distToBall = object.distToBall;
        players.push(player);
    }

    return players;
}

function getAttackingPlayers(frame, includeGoalkeepers) {
    var team = getAttackingTeam(frame);
    if (team == null) return [];
    return getTeamPlayerPositions(frame, team, includeGoalkeepers === true);
}

function getDefendingPlayers(frame, includeGoalkeepers) {
    var team = getDefendingTeam(frame);
    if (team == null) return [];
    return getTeamPlayerPositions(frame, team, includeGoalkeepers === true);
}

function getOutfieldAttackers(frame) {
    return getAttackingPlayers(frame, false);
}

function getOutfieldDefenders(frame) {
    return getDefendingPlayers(frame, false);
}

function getPitchDistance(h1, v1, h2, v2) {
    return Math.sqrt(getPitchDistanceSquared(h1, v1, h2, v2));
}

const MARKING_EDGE_COLOR = "#2563EB";

function getPitchDistanceSquared(h1, v1, h2, v2) {
    var dh = h1 - h2;
    var dv = v1 - v2;
    return dh * dh + dv * dv;
}

function drawMarkingEdges(edges, color) {
    gameCanvas.ctx.strokeStyle = color;
    gameCanvas.ctx.lineWidth = 2;

    for (var i = 0; i < edges.length; i++) {
        var edge = edges[i];
        gameCanvas.drawLine(edge.x1, edge.y1, edge.x2, edge.y2);
    }

    gameCanvas.ctx.lineWidth = 1;
}
