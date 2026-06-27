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

function getDefendingGoalH(frame) {
    var defendingTeam = getDefendingTeam(frame);
    if (defendingTeam == null) return null;

    var period = getPeriod(frame);
    var startFrame =
        gameData.periods && gameData.periods.length > 0
            ? gameData.periods[period].startFrame
            : 0;

    var savedDelta = frameDelta;
    frameDelta = 0;
    var goalH = getGoalkeeperH(startFrame, defendingTeam);
    frameDelta = savedDelta;

    return goalH;
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

function cosineSimilarity(vecA, vecB) {
    var magA = Math.sqrt(vecA.h * vecA.h + vecA.v * vecA.v);
    var magB = Math.sqrt(vecB.h * vecB.h + vecB.v * vecB.v);
    if (magA < 0.01 || magB < 0.01) return 0;

    var dot = vecA.h * vecB.h + vecA.v * vecB.v;
    return clamp01((dot / (magA * magB) + 1) / 2);
}

function getGoalwardUnitVector(fromH, fromV, goalH) {
    var dh = goalH - fromH;
    var dv = 0 - fromV;
    var dist = Math.sqrt(dh * dh + dv * dv);
    if (dist < 0.01) return { h: 0, v: 0 };

    return { h: dh / dist, v: dv / dist };
}

function getGoalwardSpeed(player, goalH) {
    var move = getMovementVector(player);
    var goalward = getGoalwardUnitVector(player.h, player.v, goalH);
    return move.h * goalward.h + move.v * goalward.v;
}

function isMovingTowardPoint(player, targetH, targetV) {
    var move = getMovementVector(player);
    if (move.magnitude < 0.3) return false;

    var dh = targetH - player.h;
    var dv = targetV - player.v;
    var dist = Math.sqrt(dh * dh + dv * dv);
    if (dist < 0.01) return true;

    var toward = { h: dh / dist, v: dv / dist };
    var alignment = move.h * toward.h + move.v * toward.v;
    return alignment > 0.35;
}

function computeGoalSideScore(defenderH, attackerH, goalH) {
    var defenderDist = Math.abs(defenderH - goalH);
    var attackerDist = Math.abs(attackerH - goalH);
    if (attackerDist <= defenderDist) return 0;

    var span = Math.max(attackerDist - defenderDist, 0.01);
    return clamp01(span / 12);
}

function isCentralChannel(v) {
    return Math.abs(v) <= BEHAVIOR_THRESHOLDS.centralChannelHalfWidth;
}

function isDangerZone(h, goalH) {
    return Math.abs(h - goalH) <= BEHAVIOR_THRESHOLDS.dangerZoneGoalDistance;
}

function distancePointToSegment(px, py, x1, y1, x2, y2) {
    var dx = x2 - x1;
    var dy = y2 - y1;
    var lenSq = dx * dx + dy * dy;
    if (lenSq < 0.0001) {
        return Math.sqrt((px - x1) * (px - x1) + (py - y1) * (py - y1));
    }

    var t = ((px - x1) * dx + (py - y1) * dy) / lenSq;
    if (t < 0) t = 0;
    if (t > 1) t = 1;

    var projX = x1 + t * dx;
    var projY = y1 + t * dy;
    return Math.sqrt((px - projX) * (px - projX) + (py - projY) * (py - projY));
}

function computePassingLaneProximity(defender, ball, attacker) {
    if (ball == null) return 0;

    var lineDist = distancePointToSegment(
        defender.h,
        defender.v,
        ball.h,
        ball.v,
        attacker.h,
        attacker.v
    );

    return normalizeInverse(lineDist, BEHAVIOR_THRESHOLDS.passingLaneMaxLineDist);
}

function isAttackerAcceleratingTowardGoal(frame, attacker, goalH) {
    if (frame <= 0) return false;

    var previous = getPlayerStateAtFrame(frame - 1, attacker.id);
    if (previous == null) return false;

    var currentGoalward = getGoalwardSpeed(attacker, goalH);
    var previousGoalward = getGoalwardSpeed(previous, goalH);
    return currentGoalward - previousGoalward > 0.35;
}

function computePairFeatures(frame, defender, attacker, context) {
    var goalH = context.goalH;
    var ball = context.ball;
    var carrier = context.carrier;

    var distance = getPitchDistance(defender.h, defender.v, attacker.h, attacker.v);
    var defenderMove = getMovementVector(defender);
    var attackerMove = getMovementVector(attacker);
    var velocitySimilarity = cosineSimilarity(defenderMove, attackerMove);
    var goalSideScore = computeGoalSideScore(defender.h, attacker.h, goalH);
    var attackerIsCarrier = carrier != null && String(attacker.id) === String(carrier.id);
    var attackerDistToBall =
        attacker.distToBall != null
            ? attacker.distToBall
            : ball != null
              ? getPitchDistance(attacker.h, attacker.v, ball.h, ball.v)
              : Infinity;

    return {
        distance: distance,
        goalSideScore: goalSideScore,
        inCentralZone: isCentralChannel(defender.v),
        attackerInDangerZone: isDangerZone(attacker.h, goalH),
        defenderInDangerZone: isDangerZone(defender.h, goalH),
        relativePositionScore: goalSideScore,
        defenderSpeed: defenderMove.magnitude,
        attackerSpeed: attackerMove.magnitude,
        velocitySimilarity: velocitySimilarity,
        defenderMovingTowardAttacker: isMovingTowardPoint(
            defender,
            attacker.h,
            attacker.v
        ),
        defenderClosingSpeed: geometricClosingSpeed(defender, attacker),
        attackerMovingTowardGoal: getGoalwardSpeed(attacker, goalH) > 0.5,
        attackerGoalwardSpeed: Math.max(getGoalwardSpeed(attacker, goalH), 0),
        attackerAcceleratingTowardGoal: isAttackerAcceleratingTowardGoal(
            frame,
            attacker,
            goalH
        ),
        defenderDistToBall:
            defender.distToBall != null && ball != null
                ? defender.distToBall
                : ball != null
                  ? getPitchDistance(defender.h, defender.v, ball.h, ball.v)
                  : Infinity,
        attackerDistToBall: attackerDistToBall,
        attackerIsCarrier: attackerIsCarrier,
        attackerNearBallZone:
            attackerDistToBall <= BEHAVIOR_THRESHOLDS.nearBallDistance,
        passingLaneProximity: computePassingLaneProximity(defender, ball, attacker),
    };
}

function computeDefenderSpaceCoverContext(defender, attackers, goalH) {
    if (attackers.length < 2) {
        return {
            targetSpreadScore: 0.25,
            attackerCount: attackers.length,
        };
    }

    var centroidH = 0;
    var centroidV = 0;
    for (var i = 0; i < attackers.length; i++) {
        centroidH += attackers[i].h;
        centroidV += attackers[i].v;
    }
    centroidH /= attackers.length;
    centroidV /= attackers.length;

    var centroidDist = getPitchDistance(defender.h, defender.v, centroidH, centroidV);
    var spread = 0;
    for (var j = 0; j < attackers.length; j++) {
        spread += getPitchDistance(attackers[j].h, attackers[j].v, centroidH, centroidV);
    }
    spread /= attackers.length;

    var betweenScore = normalizeInverse(centroidDist, Math.max(spread, 4));
    var multiBonus = clamp01((attackers.length - 1) / 3);

    return {
        targetSpreadScore: clamp01(betweenScore * 0.7 + multiBonus * 0.3),
        attackerCount: attackers.length,
    };
}

function computeHelpDefenseContext(defender, attacker, defenders, presserIds) {
    var bestTeammateScore = 0;
    var engagedTeammateId = null;

    for (var i = 0; i < defenders.length; i++) {
        var teammate = defenders[i];
        if (teammate.id === defender.id) continue;
        if (presserIds[teammate.id]) continue;

        var teammateDist = getPitchDistance(teammate.h, teammate.v, attacker.h, attacker.v);
        if (teammateDist > BEHAVIOR_THRESHOLDS.helpDefenseTeammateMaxDistance) continue;

        var defenderDist = getPitchDistance(defender.h, defender.v, attacker.h, attacker.v);
        if (teammateDist >= defenderDist) continue;

        var engagement = normalizeInverse(
            teammateDist,
            BEHAVIOR_THRESHOLDS.helpDefenseTeammateMaxDistance
        );
        if (engagement > bestTeammateScore) {
            bestTeammateScore = engagement;
            engagedTeammateId = teammate.id;
        }
    }

    return {
        teammateEngaged: bestTeammateScore > 0.2,
        teammateEngagementScore: bestTeammateScore,
        engagedTeammateId: engagedTeammateId,
    };
}

function enrichPoolTarget(target, attackerLookup) {
    var attacker = attackerLookup[target.id];
    if (attacker == null) {
        return {
            id: target.id,
            h: target.h,
            v: target.v,
            x: target.x,
            y: target.y,
            dist: target.dist,
            shirtNumber: target.shirtNumber,
            inShapeGraph: target.inShapeGraph,
        };
    }

    return {
        id: attacker.id,
        h: attacker.h,
        v: attacker.v,
        x: attacker.x,
        y: attacker.y,
        speed: attacker.speed,
        direction: attacker.direction,
        distToBall: attacker.distToBall,
        dist: target.dist,
        shirtNumber: target.shirtNumber,
        inShapeGraph: target.inShapeGraph,
    };
}
