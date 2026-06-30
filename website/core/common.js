function getTeamPlayerPositions(frame, team, includeGoalkeepers) {
    if (team == null) return [];

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

function getPitchDistance(h1, v1, h2, v2) {
    return Math.sqrt(getPitchDistanceSquared(h1, v1, h2, v2));
}

const MARKING_EDGE_COLOR = "#2563EB";

const BALL_AIR_Z = 1.0;
const BALL_GRAVITY = 9.81;
const BALL_LANDING_FALLBACK_SECONDS = 0.5;
const BALL_LANDING_MAX_FLIGHT_SECONDS = 4.0;
const BALL_LANDING_MIN_FLIGHT_SECONDS = 0.05;

function getTrackingFrameRate() {
    return gameData.frameRate != null ? gameData.frameRate : 50;
}

function getBallPitchDelta(frame) {
    var dataLine = gameData.tracking[frame];
    if (!dataLine || !dataLine.objects) return null;

    var object1 = dataLine.objects[gameData.ballId];
    if (!object1) return null;

    var dataLine2 = gameData.tracking[frame + 1] ?? dataLine;
    var object2 = dataLine2.objects[gameData.ballId] ?? object1;

    var h1 = -object1.h;
    var v1 = object1.v;
    var h2 = -object2.h;
    var v2 = object2.v;

    return {
        dh: h2 - h1,
        dv: v2 - v1,
        dz: object2.z - object1.z,
        z: object1.z,
    };
}

function getBallTimeToLand(z, vz) {
    if (z == null || z <= 0) return 0;

    var verticalSpeed = vz != null ? vz : 0;
    var discriminant = verticalSpeed * verticalSpeed + 2 * BALL_GRAVITY * z;
    if (discriminant < 0) return null;

    var timeToLand = (verticalSpeed + Math.sqrt(discriminant)) / BALL_GRAVITY;
    if (timeToLand < BALL_LANDING_MIN_FLIGHT_SECONDS) {
        return BALL_LANDING_MIN_FLIGHT_SECONDS;
    }
    if (timeToLand > BALL_LANDING_MAX_FLIGHT_SECONDS) {
        return BALL_LANDING_MAX_FLIGHT_SECONDS;
    }
    return timeToLand;
}

function getBallLandingLookaheadSeconds(delta) {
    if (delta == null || delta.z == null || delta.z <= BALL_AIR_Z) {
        return BALL_LANDING_FALLBACK_SECONDS;
    }

    var vz = delta.dz != null ? delta.dz * getTrackingFrameRate() : 0;
    var timeToLand = getBallTimeToLand(delta.z, vz);
    if (timeToLand == null) return BALL_LANDING_FALLBACK_SECONDS;
    return timeToLand;
}

function resolveBallHorizontalSpeed(speed, dist, frameRate) {
    if (speed != null && speed > 0) return speed;
    if (dist > 0) return dist * frameRate;
    return 0;
}

function getBallLandingSpot(frame, pitchH, pitchV, speed) {
    var delta = getBallPitchDelta(frame);
    if (delta == null) return null;

    var distSq = delta.dh * delta.dh + delta.dv * delta.dv;
    if (distSq <= 0) {
        return { h: pitchH, v: pitchV };
    }

    var dist = Math.sqrt(distSq);
    var unitH = delta.dh / dist;
    var unitV = delta.dv / dist;
    var frameRate = getTrackingFrameRate();

    if (speed == null || speed <= 0) {
        var dataLine = gameData.tracking[frame];
        var ballObject = dataLine && dataLine.objects ? dataLine.objects[gameData.ballId] : null;
        if (ballObject != null && ballObject.speed != null && ballObject.speed > 0) {
            speed = ballObject.speed;
        }
    }

    speed = resolveBallHorizontalSpeed(speed, dist, frameRate);
    var lookaheadSeconds = getBallLandingLookaheadSeconds(delta);
    var travel = speed * lookaheadSeconds;

    return {
        h: pitchH + unitH * travel,
        v: pitchV + unitV * travel,
        timeToLand: lookaheadSeconds,
    };
}

function isBallInAir(ball) {
    return ball != null && ball.z != null && ball.z > BALL_AIR_Z;
}

function directionToUnitVector(directionDeg) {
    var rad = (directionDeg * Math.PI) / 180;
    // Match getCoordinates pitch space where h is negated.
    return { h: -Math.cos(rad), v: Math.sin(rad) };
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
