//helper functions for other behaviors

function getPlayerStateAtFrame(frame, playerId) {
    var dataLine = gameData.tracking[frame];
    if (!dataLine || !dataLine.objects || !dataLine.objects[playerId]) return null;

    var object1 = dataLine.objects[playerId];
    var object2 = (gameData.tracking[frame + 1] ?? dataLine).objects[playerId] ?? object1;
    var coords = getCoordinates(object1, object2);
    var canvas = pt(coords[0], coords[1]);

    var player = {
        id: String(playerId),
        h: coords[0],
        v: coords[1],
        x: canvas[0],
        y: canvas[1],
    };

    if (object1.speed != null) player.speed = object1.speed;
    if (object1.direction != null) player.direction = object1.direction;
    if (object1.distToBall != null) player.distToBall = object1.distToBall;

    return player;
}

function buildPlayerLookup(players) {
    var lookup = {};
    for (var i = 0; i < players.length; i++) {
        lookup[players[i].id] = players[i];
    }
    return lookup;
}

//helper functions for tracking run behavior
function isAttackerOnForwardRun(attacker, frame) {
    var speed = attacker.speed || 0;
    if (speed < BEHAVIOR_THRESHOLDS.trackingMinRunSpeed) return false;

    var xtGain = getXtGainAlongMovement(
        attacker,
        frame,
        BEHAVIOR_THRESHOLDS.trackingLookaheadSeconds
    );
    return xtGain >= BEHAVIOR_THRESHOLDS.trackingMinXtGain;
}

function getAttackerRunMetrics(attacker, frame) {
    var lookahead = BEHAVIOR_THRESHOLDS.trackingLookaheadSeconds;
    var projected = getProjectedPitchPos(attacker, lookahead);

    return {
        xtNow: getXtAtPitchPos(attacker.h, attacker.v, frame),
        xtGain: getXtGainAlongMovement(attacker, frame, lookahead),
        xtProjected: getXtAtPitchPos(projected.h, projected.v, frame),
    };
}

function isDefenderTrackingRun(defender, attacker) {
    var dist = getPitchDistance(defender.h, defender.v, attacker.h, attacker.v);

    var alignment = velocityAlignment(defender, attacker);
    var sameSpace = dist <= BEHAVIOR_THRESHOLDS.trackingSameAreaMaxDistance;

    //check if defender is in the same space as attacker and moving with them
    if (sameSpace && alignment >= BEHAVIOR_THRESHOLDS.trackingMinVelocityAlignment) {
        return true;
    }

    //check if defender is moving toward attacker
    var towardAttacker = isMovingTowardPoint(defender, attacker.h, attacker.v);
    if (alignment >= BEHAVIOR_THRESHOLDS.trackingMinVelocityAlignment && towardAttacker) return true;

    var closing = geometricClosingSpeed(defender, attacker);
    //check if defender is closing on attacker and moving toward them
    return (
        towardAttacker &&
        closing >= BEHAVIOR_THRESHOLDS.trackingDestinationAlignment &&
        alignment >= BEHAVIOR_THRESHOLDS.trackingMinVelocityAlignment * 0.8
    );
}

function getMovementVector(player) {
    if (player == null || player.speed == null || player.direction == null) {
        return { h: 0, v: 0, magnitude: 0 };
    }

    var unit = directionToUnitVector(player.direction);
    return {
        h: unit.h * player.speed,
        v: unit.v * player.speed,
        magnitude: player.speed,
    };
}

function velocityAlignment(playerA, playerB) {
    var moveA = getMovementVector(playerA);
    var moveB = getMovementVector(playerB);
    var magA = moveA.magnitude;
    var magB = moveB.magnitude;
    if (magA < BEHAVIOR_THRESHOLDS.movementMinSpeed || magB < BEHAVIOR_THRESHOLDS.movementMinSpeed) {
        return 0;
    }

    var dot = moveA.h * moveB.h + moveA.v * moveB.v;
    return clamp01((dot / (magA * magB) + 1) / 2);
}

function isMovingTowardPoint(player, targetH, targetV) {
    var move = getMovementVector(player);
    if (move.magnitude < BEHAVIOR_THRESHOLDS.movementMinSpeed) return false;

    var dh = targetH - player.h;
    var dv = targetV - player.v;
    var dist = Math.sqrt(dh * dh + dv * dv);
    if (dist < 0.01) return true;

    var toward = { h: dh / dist, v: dv / dist };
    var alignment = move.h * toward.h + move.v * toward.v;
    return alignment / move.magnitude > BEHAVIOR_THRESHOLDS.towardPointAlignment;
}

//helper functions for passing lane cover behavior

function projectPointOntoSegment(px, py, x1, y1, x2, y2) {
    var dx = x2 - x1;
    var dy = y2 - y1;
    var lenSq = dx * dx + dy * dy;
    if (lenSq < 0.0001) {
        var dist = Math.sqrt((px - x1) * (px - x1) + (py - y1) * (py - y1));
        return { distance: dist, t: 0, onSegment: true };
    }

    var t = ((px - x1) * dx + (py - y1) * dy) / lenSq;
    var onSegment = t >= 0 && t <= 1;
    var tClamped = t;
    if (tClamped < 0) tClamped = 0;
    if (tClamped > 1) tClamped = 1;

    var projX = x1 + tClamped * dx;
    var projY = y1 + tClamped * dy;
    var distance = Math.sqrt(
        (px - projX) * (px - projX) + (py - projY) * (py - projY)
    );

    return { distance: distance, t: t, onSegment: onSegment };
}

function distancePointToSegment(px, py, x1, y1, x2, y2) {
    return projectPointOntoSegment(px, py, x1, y1, x2, y2).distance;
}

function getPassingLaneMaxLineDist(passLengthMeters) {
    var minDist = BEHAVIOR_THRESHOLDS.passingLaneMinLineDist;
    var maxDist = BEHAVIOR_THRESHOLDS.passingLaneMaxLineDist;
    var maxPassLen = BEHAVIOR_THRESHOLDS.passingOptionMaxDistance;

    if (maxPassLen <= 0) return minDist;

    var scale = passLengthMeters / maxPassLen;
    if (scale < 0) scale = 0;
    if (scale > 1) scale = 1;

    return minDist + scale * (maxDist - minDist);
}

function computeThreatShieldScore(defender, attacker, frame) {
    var defenderXt = getXtAtPitchPos(defender.h, defender.v, frame);
    var attackerXt = getXtAtPitchPos(attacker.h, attacker.v, frame);
    if (defenderXt == null || attackerXt == null) return 0;
    if (attackerXt <= defenderXt) return 0;

    return clamp01((attackerXt - defenderXt) / Math.max(attackerXt, 0.001));
}
