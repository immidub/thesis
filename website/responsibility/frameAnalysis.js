const BALL_AIR_Z = 1.0;
const CARRIER_MAX_BALL_DIST = 6;
const PRESS_MAX_TARGET_DIST = 15;
const PRESS_ENGAGED_DIST = 3;
const PRESS_MIN_SPEED = 0.5;
const PRESS_MIN_CLOSING_NEAR = 0.5;
const PRESS_MIN_CLOSING_FAR = 6.0;
const CHASE_CARRIER_SPEED_MIN = 2.0;
const NET_CLOSING_MIN = 0.4;
const TRAP_MAX_DIST = 7;
const TRAP_DEFENDER_MAX_SPEED = 1.5;
const TRAP_MIN_INCOMING = 2.0;
const PRESS_CANDIDATE_COUNT = 3;

function directionToUnitVector(directionDeg) {
    var rad = (directionDeg * Math.PI) / 180;
    // Match getCoordinates pitch space where h is negated.
    return { h: -Math.cos(rad), v: Math.sin(rad) };
}

function pitchDistance(h1, v1, h2, v2) {
    return Math.sqrt(getPitchDistanceSquared(h1, v1, h2, v2));
}

function alignmentToward(fromH, fromV, directionDeg, toH, toV) {
    var dh = toH - fromH;
    var dv = toV - fromV;
    var dist = Math.sqrt(dh * dh + dv * dv);
    if (dist < 0.01) return 1;

    var move = directionToUnitVector(directionDeg);
    var towardH = dh / dist;
    var towardV = dv / dist;
    return move.h * towardH + move.v * towardV;
}

function minClosingSpeedRequired(distToTarget) {
    if (distToTarget <= PRESS_ENGAGED_DIST) return 0;

    var range = PRESS_MAX_TARGET_DIST - PRESS_ENGAGED_DIST;
    var t = (distToTarget - PRESS_ENGAGED_DIST) / range;
    if (t < 0) t = 0;
    if (t > 1) t = 1;

    return PRESS_MIN_CLOSING_NEAR + t * (PRESS_MIN_CLOSING_FAR - PRESS_MIN_CLOSING_NEAR);
}

function geometricClosingSpeed(defender, carrier) {
    var dh = carrier.h - defender.h;
    var dv = carrier.v - defender.v;
    var dist = Math.sqrt(dh * dh + dv * dv);
    if (dist < 0.01) return Infinity;

    var defMove = directionToUnitVector(defender.direction || 0);
    var carMove = directionToUnitVector(carrier.direction || 0);
    var defH = defMove.h * (defender.speed || 0);
    var defV = defMove.v * (defender.speed || 0);
    var carH = carMove.h * (carrier.speed || 0);
    var carV = carMove.v * (carrier.speed || 0);
    var rx = dh / dist;
    var rv = dv / dist;

    return (defH - carH) * rx + (defV - carV) * rv;
}

function closingSpeedToward(defender, carrier) {
    var alignment = alignmentToward(
        defender.h,
        defender.v,
        defender.direction,
        carrier.h,
        carrier.v
    );
    var direct = Math.max(0, alignment) * (defender.speed || 0);
    var geometric = geometricClosingSpeed(defender, carrier);
    return Math.max(direct, Math.max(0, geometric));
}

function incomingSpeedToward(from, toH, toV) {
    if (from.speed == null || from.direction == null) return 0;

    var alignment = alignmentToward(from.h, from.v, from.direction, toH, toV);
    return Math.max(0, alignment) * from.speed;
}

function isTrapPress(defender, carrier, distToTarget) {
    if (distToTarget > TRAP_MAX_DIST || distToTarget <= PRESS_ENGAGED_DIST) return false;
    if ((defender.speed || 0) > TRAP_DEFENDER_MAX_SPEED) return false;
    if ((carrier.speed || 0) < CHASE_CARRIER_SPEED_MIN) return false;

    return incomingSpeedToward(carrier, defender.h, defender.v) >= TRAP_MIN_INCOMING;
}

function isChaseNotPress(defender, carrier) {
    if ((carrier.speed || 0) < CHASE_CARRIER_SPEED_MIN) return false;

    return geometricClosingSpeed(defender, carrier) < NET_CLOSING_MIN;
}

function isApproachingCarrier(defender, carrier, distToTarget) {
    if (defender.speed == null || defender.speed < PRESS_MIN_SPEED) return false;
    if (defender.direction == null) return false;

    var closing = closingSpeedToward(defender, carrier);
    if (closing < minClosingSpeedRequired(distToTarget)) return false;

    if (isChaseNotPress(defender, carrier)) return false;

    return true;
}

function getAttackingPlayers(frame) {
    var team = getAttackingTeam(frame);
    if (team == null) return [];
    return getTeamPlayerPositions(frame, team, true);
}

function getDefendingPlayers(frame) {
    var team = getDefendingTeam(frame);
    if (team == null) return [];
    return getTeamPlayerPositions(frame, team);
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

function isBallInAir(ball) {
    return ball != null && ball.z != null && ball.z > BALL_AIR_Z;
}

function pickCarrier(attackers) {
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

    if (best.distToBall === Infinity || best.distToBall > CARRIER_MAX_BALL_DIST) {
        return null;
    }

    best.shirtNumber = getShirtNumberLabel(best.id);
    return best;
}

function evaluatePressCandidate(defender, carrier) {
    var distToTarget = pitchDistance(defender.h, defender.v, carrier.h, carrier.v);
    var engaged = distToTarget <= PRESS_ENGAGED_DIST;
    var closing = closingSpeedToward(defender, carrier);
    var trap = isTrapPress(defender, carrier, distToTarget);
    var pressing = engaged;

    if (!pressing) {
        if (distToTarget <= PRESS_MAX_TARGET_DIST) {
            pressing = isApproachingCarrier(defender, carrier, distToTarget) || trap;
        }
    }

    return {
        defenderId: defender.id,
        x: defender.x,
        y: defender.y,
        defenderShirt: getShirtNumberLabel(defender.id),
        targetShirt: carrier.shirtNumber || getShirtNumberLabel(carrier.id),
        distToTarget: Math.round(distToTarget * 10) / 10,
        closing: Math.round(closing * 10) / 10,
        engaged: engaged,
        pressing: pressing,
    };
}

function buildPresserExplanation(presser) {
    if (presser.engaged) {
        return (
            "#" + presser.defenderShirt +
            " pressing #" + presser.targetShirt +
            " (engaged): " +
            presser.distToTarget + " m to carrier"
        );
    }

    return (
        "#" + presser.defenderShirt +
        " pressing #" + presser.targetShirt +
        ": " +
        presser.closing + " m/s toward carrier, " +
        presser.distToTarget + " m away"
    );
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

function findPressers(defenders, carrier) {
    var pressers = [];
    var nearestDefenders = getNearestDefendersToCarrier(defenders, carrier, PRESS_CANDIDATE_COUNT);

    for (var i = 0; i < nearestDefenders.length; i++) {
        var evaluated = evaluatePressCandidate(nearestDefenders[i], carrier);
        if (!evaluated.pressing) continue;

        evaluated.explanation = buildPresserExplanation(evaluated);
        delete evaluated.pressing;
        pressers.push(evaluated);
    }

    return pressers;
}

function analyzeResponsibility(frame) {
    if (!isBallLive(frame)) {
        return { active: false, reason: "Ball not live" };
    }

    var ballObj = getBallPitchPos(frame);
    if (ballObj == null) {
        return { active: false, reason: "Ball not tracked" };
    }

    if (isBallInAir(ballObj)) {
        return {
            active: false,
            reason: "Ball in air (z=" + (Math.round(ballObj.z * 10) / 10) + " m)",
        };
    }

    var attackers = getAttackingPlayers(frame);
    var defenders = getDefendingPlayers(frame);
    var carrier = pickCarrier(attackers);

    if (carrier == null) {
        return { active: false, reason: "No clear ball carrier" };
    }

    var pressers = findPressers(defenders, carrier);

    return {
        active: true,
        carrier: carrier,
        pressers: pressers,
    };
}
