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

const MARKING_EDGE_COLOR = "#2563EB";
const MARKING_POSITION_LOOKAHEAD_SECONDS = 2;

function directionToUnitVector(directionDeg) {
    var rad = (directionDeg * Math.PI) / 180;
    // Match getCoordinates pitch space where h is negated.
    return { h: -Math.cos(rad), v: Math.sin(rad) };
}

function projectPlayerPitchPosition(player, seconds) {
    var lookahead = seconds != null ? seconds : MARKING_POSITION_LOOKAHEAD_SECONDS;
    if (player.speed == null || player.direction == null || player.speed <= 0) {
        return { h: player.h, v: player.v };
    }

    var unit = directionToUnitVector(player.direction);
    return {
        h: player.h + unit.h * player.speed * lookahead,
        v: player.v + unit.v * player.speed * lookahead,
    };
}

function getMarkingPairDistanceSquared(playerA, playerB, useProjected) {
    var h1 = playerA.h;
    var v1 = playerA.v;
    var h2 = playerB.h;
    var v2 = playerB.v;

    if (useProjected) {
        var projectedA = projectPlayerPitchPosition(playerA);
        var projectedB = projectPlayerPitchPosition(playerB);
        h1 = projectedA.h;
        v1 = projectedA.v;
        h2 = projectedB.h;
        v2 = projectedB.v;
    }

    return getPitchDistanceSquared(h1, v1, h2, v2);
}

function getPitchDistanceSquared(h1, v1, h2, v2) {
    var dh = h1 - h2;
    var dv = v1 - v2;
    return dh * dh + dv * dv;
}

function getBallPitchPosition(frame) {
    var dataLine = gameData.tracking[frame];
    if (!dataLine || !dataLine.objects[gameData.ballId]) return null;

    var object1 = dataLine.objects[gameData.ballId];
    var object2 = (gameData.tracking[frame + 1] ?? dataLine).objects[gameData.ballId] ?? object1;
    var [h, v] = getCoordinates(object1, object2);
    return { h: h, v: v };
}

function getAngleAtBallDegrees(ball, pointA, pointB) {
    var ax = pointA.h - ball.h;
    var ay = pointA.v - ball.v;
    var bx = pointB.h - ball.h;
    var by = pointB.v - ball.v;
    var magA = Math.sqrt(ax * ax + ay * ay);
    var magB = Math.sqrt(bx * bx + by * by);
    if (magA === 0 || magB === 0) return 180;

    var dot = ax * bx + ay * by;
    var cos = Math.max(-1, Math.min(1, dot / (magA * magB)));
    return Math.acos(cos) * (180 / Math.PI);
}

function drawMarkingEdges(edges, color) {
    gameCanvas.ctx.strokeStyle = color;
    gameCanvas.ctx.lineWidth = 2;

    for (var i = 0; i < edges.length; i++) {
        var edge = edges[i];
        gameCanvas.ctx.setLineDash(edge.dashed ? [6, 4] : []);
        gameCanvas.drawLine(edge.x1, edge.y1, edge.x2, edge.y2);
    }

    gameCanvas.ctx.setLineDash([]);
    gameCanvas.ctx.lineWidth = 1;
}

const GLOBAL_MAX_EDGE_LENGTH_METERS = 15;
const GLOBAL_BACKWARD_EDGE_MARGIN_METERS = 5;

var useProjectedPositions = false;
var maxEdgeLength15mEnabled = false;
var backwardEdgeFilterEnabled = false;

function getPlayerMarkingPosition(player) {
    if (!useProjectedPositions) {
        return { h: player.h, v: player.v };
    }
    return projectPlayerPitchPosition(player);
}

function getGlobalMaxEdgeLengthMeters() {
    return maxEdgeLength15mEnabled ? GLOBAL_MAX_EDGE_LENGTH_METERS : null;
}

function passesGlobalMaxEdgeLengthFilter(playerA, playerB) {
    var maxM = getGlobalMaxEdgeLengthMeters();
    if (maxM == null) return true;
    return getMarkingPairDistanceSquared(playerA, playerB, useProjectedPositions) <= maxM * maxM;
}

function passesGlobalBackwardEdgeFilter(frame, defender, attacker) {
    if (!backwardEdgeFilterEnabled) return true;

    var defendingTeam = getDefendingTeam(frame);
    if (defendingTeam == null) return true;

    var goalLineH = getTeamGoalLineH(frame, defendingTeam);
    var attackerPos = getPlayerMarkingPosition(attacker);
    var defenderPos = getPlayerMarkingPosition(defender);
    var attackerDist = Math.abs(attackerPos.h - goalLineH);
    var defenderDist = Math.abs(defenderPos.h - goalLineH);

    if (attackerDist >= defenderDist) return true;

    return defenderDist - attackerDist <= GLOBAL_BACKWARD_EDGE_MARGIN_METERS;
}

function passesMarkingEdgeFilters(frame, defender, attacker) {
    if (!passesGlobalMaxEdgeLengthFilter(defender, attacker)) return false;
    if (!passesGlobalBackwardEdgeFilter(frame, defender, attacker)) return false;
    return true;
}

function passesGraphEdgePairFilter(frame, playerA, playerB) {
    if (!passesGlobalMaxEdgeLengthFilter(playerA, playerB)) return false;
    if (playerA.team == null || playerB.team == null || playerA.team === playerB.team) return true;

    var defendingTeam = getDefendingTeam(frame);
    if (defendingTeam == null) return true;

    var attacker = playerA.team === defendingTeam ? playerB : playerA;
    var defender = playerA.team === defendingTeam ? playerA : playerB;
    return passesGlobalBackwardEdgeFilter(frame, defender, attacker);
}

function setupGlobalEdgeFilters() {
    var maxEdgeLengthCheckbox = document.getElementById("global_max_edge_length_15m");
    if (maxEdgeLengthCheckbox) {
        maxEdgeLength15mEnabled = maxEdgeLengthCheckbox.checked;
        maxEdgeLengthCheckbox.addEventListener("change", function () {
            maxEdgeLength15mEnabled = maxEdgeLengthCheckbox.checked;
        });
    }

    var backwardEdgeCheckbox = document.getElementById("global_backward_edge_filter");
    if (backwardEdgeCheckbox) {
        backwardEdgeFilterEnabled = backwardEdgeCheckbox.checked;
        backwardEdgeCheckbox.addEventListener("change", function () {
            backwardEdgeFilterEnabled = backwardEdgeCheckbox.checked;
        });
    }

    var projectedCheckbox = document.getElementById("global_projected_positions");
    if (projectedCheckbox) {
        useProjectedPositions = projectedCheckbox.checked;
        projectedCheckbox.addEventListener("change", function () {
            useProjectedPositions = projectedCheckbox.checked;
        });
    }
}
