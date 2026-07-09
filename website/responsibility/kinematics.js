// Reachability circle model from thesis (section 3.2).

const DEFAULT_KINEMATICS_PARAMS = {
    vMax: 7.5,
    alpha: 1.3,
    tMax: 5.0,
    dt: 0.05,
    minRadius: 1.0,
};

function clampNumber(x, lo, hi) {
    if (x == null || isNaN(x)) return lo;
    if (x < lo) return lo;
    if (x > hi) return hi;
    return x;
}

function getPlayerVelocityVector(player) {
    if (!player || player.speed == null || player.direction == null || player.speed <= 0) {
        return { h: 0, v: 0 };
    }
    var unit = directionToUnitVector(player.direction);
    return { h: unit.h * player.speed, v: unit.v * player.speed };
}

// r(t) = max(vmax * ( t - (1 - exp(-α t)) / α ), R0)
function reachabilityRadius(t, vMax, alpha, minRadius) {
    var r0 = minRadius != null ? minRadius : DEFAULT_KINEMATICS_PARAMS.minRadius;
    if (t <= 0) return r0;
    var k = (1 - Math.exp(-alpha * t)) / alpha;
    var r = vMax * (t - k);
    return Math.max(r, r0);
}

// c(t) = p + ( (1 - exp(-α t)) / α ) * v
function reachabilityCenter(player, t, alpha) {
    var k = (1 - Math.exp(-alpha * t)) / alpha;
    var vel = getPlayerVelocityVector(player);
    return { h: player.h + vel.h * k, v: player.v + vel.v * k };
}

function distanceSquared(a, b) {
    var dh = a.h - b.h;
    var dv = a.v - b.v;
    return dh * dh + dv * dv;
}

function ballPositionAt(ball, t) {
    var vel = ball.vel || { h: 0, v: 0 };
    return { h: ball.h + vel.h * t, v: ball.v + vel.v * t };
}

function isBallInReachCircle(player, ball, t, params) {
    if (!player || !ball || player.h == null || player.v == null) return false;

    var p = params || DEFAULT_KINEMATICS_PARAMS;
    var vMax = clampNumber(p.vMax, 0.1, 12);
    var alpha = clampNumber(p.alpha, 0, 10);

    var ballAtT = ballPositionAt(ball, t);
    var c = reachabilityCenter(player, t, alpha);
    var r = reachabilityRadius(t, vMax, alpha, p.minRadius);
    return distanceSquared(c, ballAtT) <= r * r;
}
