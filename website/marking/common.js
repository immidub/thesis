function getTeamPlayerPositions(frame, team, includeGoalkeepers) {
    var players = [];
    var dataLine = gameData.tracking[frame];

    for (var playerId in dataLine.objects) {
        if (team == 1 && !gameData.players.team1.includes(String(playerId))) continue;
        if (team == 2 && !gameData.players.team2.includes(String(playerId))) continue;
        if (!includeGoalkeepers && isGoalkeeperPlayer(playerId)) continue;

        var object = dataLine.objects[playerId];
        var hv = getCoordinates(object, object);
        var xy = pt(hv[0], hv[1]);

        var player = {
            id: playerId,
            h: hv[0],
            v: hv[1],
            x: xy[0],
            y: xy[1],
        };
        if (object.speed != null) player.speed = object.speed;
        if (object.direction != null) player.direction = object.direction;
        players.push(player);
    }

    return players;
}

function getMarkingSides(frame) {
    // Live-ball defending / attacking outfield sides, or null if unavailable.
    if (!isBallLive(frame)) return null;

    var defendingTeam = getDefendingTeam(frame);
    if (defendingTeam == null) return null;

    var defenders = getTeamPlayerPositions(frame, defendingTeam);
    var attackers = getTeamPlayerPositions(frame, defendingTeam === 1 ? 2 : 1);
    if (defenders.length === 0 || attackers.length === 0) return null;

    return {
        defendingTeam: defendingTeam,
        defenders: defenders,
        attackers: attackers,
    };
}

const MARKING_EDGE_COLOR = "#2563EB";

function getMarkingPairDistanceSquared(playerA, playerB) {
    return getPitchDistanceSquared(playerA.h, playerA.v, playerB.h, playerB.v);
}

function getPitchDistanceSquared(h1, v1, h2, v2) {
    var dh = h1 - h2;
    var dv = v1 - v2;
    return dh * dh + dv * dv;
}

function drawCanvasEdges(edges, options) {
    if (!edges || edges.length === 0) return;
    options = options || {};

    var ctx = gameCanvas.ctx;
    var prevWidth = ctx.lineWidth;
    var prevStroke = ctx.strokeStyle;
    var prevDash = ctx.getLineDash();

    ctx.strokeStyle = options.color != null ? options.color : MARKING_EDGE_COLOR;
    ctx.lineWidth = options.lineWidth != null ? options.lineWidth : 2;

    var dashedSupport = options.dashedSupport !== false;
    for (var i = 0; i < edges.length; i++) {
        var edge = edges[i];
        if (dashedSupport) {
            ctx.setLineDash(edge.dashed ? [6, 4] : []);
        }
        gameCanvas.drawLine(edge.x1, edge.y1, edge.x2, edge.y2);
    }

    ctx.setLineDash(prevDash);
    ctx.strokeStyle = prevStroke;
    ctx.lineWidth = prevWidth;
}

function drawMarkingEdges(edges, color) {
    drawCanvasEdges(edges, { color: color, dashedSupport: true });
}

function collectKnnOpponentEdges(sources, targets, k, processMatch, sourceIsDefender, frame, options) {
    // Ranks by oriented cost (k-NN) or momentum / Euclidean (mirrors analysis).
    // options.ignoreOriented: force momentum/Euclidean (perfect-match knn allow-list).
    options = options || {};
    var sourceIsDef = sourceIsDefender !== false;
    var ignoreOriented = options.ignoreOriented === true;
    for (var i = 0; i < sources.length; i++) {
        var player = sources[i];
        var distances = [];

        for (var j = 0; j < targets.length; j++) {
            var opp = targets[j];
            var cost;
            if (!ignoreOriented && frame != null) {
                cost = getKnnPairRankingCost(player, opp, sourceIsDef, frame);
            } else {
                cost = getDirectedRankingCost(player, opp, sourceIsDef);
            }
            distances.push({
                opponent: opp,
                cost: cost,
            });
        }

        distances.sort(function (a, b) {
            return a.cost - b.cost;
        });

        var count = Math.min(k, distances.length);
        for (var n = 0; n < count; n++) {
            processMatch(player, distances[n].opponent);
        }
    }
}
