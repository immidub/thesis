const BALL_AIR_Z = 1.0;
const BALL_GRAVITY = 9.81;
const BALL_Z_VELOCITY_LOOKBACK_FRAMES = 15;

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

function getBallVerticalVelocity(frame) {
    var frameRate = getTrackingFrameRate();
    var startFrame = Math.max(0, frame - BALL_Z_VELOCITY_LOOKBACK_FRAMES);
    var samples = [];

    for (var f = startFrame; f <= frame; f++) {
        var dataLine = gameData.tracking[f];
        var dataLine2 = gameData.tracking[f + 1];
        if (!dataLine || !dataLine.objects || !dataLine2 || !dataLine2.objects) continue;

        var object1 = dataLine.objects[gameData.ballId];
        var object2 = dataLine2.objects[gameData.ballId];
        if (object1 == null || object2 == null) continue;
        if (object1.z == null || object2.z == null) continue;

        samples.push((object2.z - object1.z) * frameRate);
    }

    if (samples.length === 0) return null;

    var sum = 0;
    for (var i = 0; i < samples.length; i++) {
        sum += samples[i];
    }
    return sum / samples.length;
}

function getBallTimeToLand(z, vz) {
    if (z == null || z <= 0) return 0;

    var verticalSpeed = vz != null ? vz : 0;
    var discriminant = verticalSpeed * verticalSpeed + 2 * BALL_GRAVITY * z;
    if (discriminant < 0) return null;

    return (verticalSpeed + Math.sqrt(discriminant)) / BALL_GRAVITY;
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
    var frameRate = getTrackingFrameRate();
    var dataLine = gameData.tracking[frame];
    var ballObject = dataLine && dataLine.objects ? dataLine.objects[gameData.ballId] : null;
    var z = ballObject != null ? ballObject.z : null;
    var vz = getBallVerticalVelocity(frame);
    var lookaheadSeconds = getBallTimeToLand(z, vz);
    if (lookaheadSeconds == null || lookaheadSeconds <= 0) return null;

    if (distSq <= 0) {
        return { h: pitchH, v: pitchV, timeToLand: lookaheadSeconds };
    }

    var dist = Math.sqrt(distSq);
    var unitH = delta.dh / dist;
    var unitV = delta.dv / dist;

    if (speed == null || speed <= 0) {
        if (ballObject != null && ballObject.speed != null && ballObject.speed > 0) {
            speed = ballObject.speed;
        }
    }

    speed = resolveBallHorizontalSpeed(speed, dist, frameRate);
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
