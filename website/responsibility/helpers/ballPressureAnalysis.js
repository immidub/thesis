const BALL_AIR_Z = 1.0;
const BALL_AIR_PREDICTION_BASE_SECONDS = 0.4;
const BALL_AIR_PREDICTION_Z_SCALE = 0.25;
const BALL_AIR_PREDICTION_MAX_SECONDS = 1.5;
const PRESS_MAX_TARGET_DIST = 15;
const PRESS_ENGAGED_DIST = 3;
const PRESS_MIN_CLOSING_NEAR = 0.5;
const PRESS_MIN_CLOSING_FAR = 6.0;
const PRESS_CANDIDATE_COUNT = 3;

function getBallAirPredictionSeconds(ball) {
    var z = ball != null && ball.z != null ? ball.z : 0;
    var seconds = BALL_AIR_PREDICTION_BASE_SECONDS + z * BALL_AIR_PREDICTION_Z_SCALE;
    if (seconds > BALL_AIR_PREDICTION_MAX_SECONDS) return BALL_AIR_PREDICTION_MAX_SECONDS;
    return seconds;
}

function minClosingSpeedRequired(distToTarget) {
    if (distToTarget <= PRESS_ENGAGED_DIST) return 0;

    var range = PRESS_MAX_TARGET_DIST - PRESS_ENGAGED_DIST;
    var t = (distToTarget - PRESS_ENGAGED_DIST) / range;
    if (t < 0) t = 0;
    if (t > 1) t = 1;

    return PRESS_MIN_CLOSING_NEAR + t * (PRESS_MIN_CLOSING_FAR - PRESS_MIN_CLOSING_NEAR);
}

function isActivelyPressing(defender, carrier, distToTarget) {
    if (distToTarget <= PRESS_ENGAGED_DIST) return true;
    if (distToTarget > PRESS_MAX_TARGET_DIST) return false;

    return geometricClosingSpeed(defender, carrier) >= minClosingSpeedRequired(distToTarget);
}

function getBallPitchPos(frame) {
    var dataLine = gameData.tracking[frame];
    if (!dataLine || !dataLine.objects) return null;

    var object1 = dataLine.objects[gameData.ballId];
    if (!object1) return null;

    var object2 = (gameData.tracking[frame + 1] ?? dataLine).objects[gameData.ballId] ?? object1;
    var [h, v] = getCoordinates(object1, object2);

    return {
        h: h,
        v: v,
        z: object1.z,
        speed: object1.speed,
        direction: object1.direction,
    };
}

function isBallInAir(ball) {
    return ball != null && ball.z != null && ball.z > BALL_AIR_Z;
}

function pickBallCarrier(attackers) {
    if (attackers.length === 0) return null;

    var best = null;
    for (var i = 0; i < attackers.length; i++) {
        var player = attackers[i];
        var dist = player.distToBall;
        if (dist == null) {
            dist = Infinity;
        }
        if (best == null || dist < best.distToBall) {
            best = {
                id: player.id,
                h: player.h,
                v: player.v,
                x: player.x,
                y: player.y,
                distToBall: dist,
                speed: player.speed,
                direction: player.direction,
            };
        }
    }

    if (best.distToBall === Infinity) {
        return null;
    }

    best.shirtNumber = getShirtNumberLabel(best.id);
    return best;
}

function pickBallCarrierAtPoint(attackers, targetH, targetV) {
    if (attackers.length === 0) return null;

    var best = null;
    var bestDist = Infinity;
    for (var i = 0; i < attackers.length; i++) {
        var player = attackers[i];
        var dist = getPitchDistance(player.h, player.v, targetH, targetV);
        if (best == null || dist < bestDist) {
            bestDist = dist;
            best = {
                id: player.id,
                h: player.h,
                v: player.v,
                x: player.x,
                y: player.y,
                distToBall: dist,
                speed: player.speed,
                direction: player.direction,
            };
        }
    }

    best.shirtNumber = getShirtNumberLabel(best.id);
    return best;
}

function evaluatePressCandidate(defender, carrier) {
    var distToTarget = getPitchDistance(defender.h, defender.v, carrier.h, carrier.v);
    var engaged = distToTarget <= PRESS_ENGAGED_DIST;
    var closing = geometricClosingSpeed(defender, carrier);
    var pressing = isActivelyPressing(defender, carrier, distToTarget);

    return {
        defenderId: defender.id,
        x: defender.x,
        y: defender.y,
        pressing: pressing,
    };
}

function getNearestDefendersToCarrier(defenders, carrier, count) {
    var candidates = [];

    for (var i = 0; i < defenders.length; i++) {
        if (isGoalkeeperPlayer(defenders[i].id)) continue;

        var defender = defenders[i];
        candidates.push({
            defender: defender,
            distSq: getPitchDistanceSquared(defender.h, defender.v, carrier.h, carrier.v),
        });
    }

    candidates.sort(function (a, b) {
        return a.distSq - b.distSq;
    });

    var nearest = [];
    var limit = Math.min(count, candidates.length);
    for (var j = 0; j < limit; j++) {
        nearest.push(candidates[j].defender);
    }

    return nearest;
}

function findBallPressers(defenders, carrier) {
    var pressers = [];
    var nearestDefenders = getNearestDefendersToCarrier(defenders, carrier, PRESS_CANDIDATE_COUNT);

    for (var i = 0; i < nearestDefenders.length; i++) {
        var evaluated = evaluatePressCandidate(nearestDefenders[i], carrier);
        if (!evaluated.pressing) continue;

        delete evaluated.pressing;
        pressers.push(evaluated);
    }

    return pressers;
}

function analyzeBallPressure(frame) {
    if (!isBallLive(frame)) {
        return { active: false, reason: "Ball not live" };
    }

    var ballObj = getBallPitchPos(frame);
    if (ballObj == null) {
        return { active: false, reason: "Ball not tracked" };
    }

    var attackers = getTeamPlayerPositions(frame, getAttackingTeam(frame), true);
    var defenders = getTeamPlayerPositions(frame, getDefendingTeam(frame), false);

    var inAir = isBallInAir(ballObj);
    var ballPrediction = null;
    var carrier;

    if (inAir) {
        var predictionSeconds = getBallAirPredictionSeconds(ballObj);
        ballPrediction = predictBallPitchPos(ballObj, predictionSeconds);
        ballPrediction.seconds = predictionSeconds;
        carrier = pickBallCarrierAtPoint(attackers, ballPrediction.h, ballPrediction.v);
    } else {
        carrier = pickBallCarrier(attackers);
    }

    if (carrier == null) {
        return { active: false, reason: "No clear ball carrier" };
    }

    if (inAir) {
        carrier.fromAirPrediction = true;
    }

    var pressers = findBallPressers(defenders, carrier);

    return {
        active: true,
        carrier: carrier,
        pressers: pressers,
        ballInAir: inAir,
        ballPrediction: ballPrediction,
    };
}
