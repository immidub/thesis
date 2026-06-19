function getTeamPlayerPositions(frame, team) {
    var players = [];
    var dataLine = gameData.tracking[frame];

    for (var playerId in dataLine.objects) {
        if (team == 1 && !gameData.players.team1.includes(String(playerId))) continue;
        if (team == 2 && !gameData.players.team2.includes(String(playerId))) continue;
        if (isGoalkeeperPlayer(playerId)) continue;

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

const MARKING_EDGE_COLOR = "#2563EB";

function getPitchDistanceSquared(h1, v1, h2, v2) {
    var dh = h1 - h2;
    var dv = v1 - v2;
    return dh * dh + dv * dv;
}

function getKnnEdges(source, neighbors, k) {
    var distances = [];

    for (var j = 0; j < neighbors.length; j++) {
        var neighbor = neighbors[j];
        distances.push({
            neighbor: neighbor,
            distSq: getPitchDistanceSquared(source.h, source.v, neighbor.h, neighbor.v),
        });
    }

    distances.sort(function (a, b) {
        return a.distSq - b.distSq;
    });

    var edges = [];
    var count = Math.min(k, distances.length);
    for (var n = 0; n < count; n++) {
        var match = distances[n].neighbor;
        edges.push({
            x1: source.x,
            y1: source.y,
            x2: match.x,
            y2: match.y,
        });
    }

    return edges;
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
