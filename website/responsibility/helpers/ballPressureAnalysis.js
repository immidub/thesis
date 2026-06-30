const PRESS_MAX_TARGET_DIST = 15;
const PRESS_ENGAGED_DIST = 3;
const PRESS_MIN_CLOSING_NEAR = 0.5;
const PRESS_MIN_CLOSING_FAR = 6.0;
const PRESS_CANDIDATE_COUNT = 3;

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
    };
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

function getNearestDefendersToTarget(defenders, target, count) {
    var candidates = [];

    for (var i = 0; i < defenders.length; i++) {
        if (isGoalkeeperPlayer(defenders[i].id)) continue;

        var defender = defenders[i];
        candidates.push({
            defender: defender,
            distSq: getPitchDistanceSquared(defender.h, defender.v, target.h, target.v),
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

function findPressureDefenders(defenders, target) {
    var pressers = [];
    var nearestDefenders = getNearestDefendersToTarget(
        defenders,
        target,
        PRESS_CANDIDATE_COUNT
    );

    for (var i = 0; i < nearestDefenders.length; i++) {
        var evaluated = evaluatePressCandidate(nearestDefenders[i], target);
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
    var ballLandingSpot = null;
    var carrier = null;
    var intendedTarget = null;
    var pressers = [];
    var highPassChallengers = [];

    if (inAir) {
        ballLandingSpot = getBallLandingSpot(frame, ballObj.h, ballObj.v, ballObj.speed);
        if (ballLandingSpot != null) {
            intendedTarget = pickBallCarrierAtPoint(
                attackers,
                ballLandingSpot.h,
                ballLandingSpot.v
            );
        }
        if (intendedTarget != null) {
            highPassChallengers = findPressureDefenders(defenders, intendedTarget);
        }
    } else {
        carrier = pickBallCarrier(attackers);
        if (carrier == null) {
            return { active: false, reason: "No clear ball carrier" };
        }
        pressers = findPressureDefenders(defenders, carrier);
    }

    if (inAir && intendedTarget == null) {
        return { active: false, reason: "No intended pass target" };
    }

    return {
        active: true,
        carrier: carrier,
        intendedTarget: intendedTarget,
        pressers: pressers,
        highPassChallengers: highPassChallengers,
        ballInAir: inAir,
        ballLandingSpot: ballLandingSpot,
    };
}
