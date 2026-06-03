function getTeamPlayerPositions(frame, team) {
    var players = [];
    var dataLine = gameData.tracking[frame];

    for (var playerId in dataLine.objects) {
        if (team == 1 && !gameData.players.team1.includes(playerId)) continue;
        if (team == 2 && !gameData.players.team2.includes(playerId)) continue;
        if (gameData.players.goalKeepers.includes(playerId)) continue;

        var object = dataLine.objects[playerId];
        var [h, v] = getCoordinates(object);

        players.push({
            id: playerId,
            h: h,
            v: v,
            x: convertX(v),
            y: convertY(h),
        });
    }

    return players;
}

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
