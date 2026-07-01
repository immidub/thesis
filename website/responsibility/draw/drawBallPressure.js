const BALL_PRESSURE_EDGE_COLOR = "#DC2626";
const BALL_CARRIER_RING_COLOR = "#F59E0B";
const BALL_INTENDED_TARGET_RING_COLOR = "#8B5CF6";
const HIGH_PASS_CHALLENGE_EDGE_COLOR = "#EA580C";
const BALL_LANDING_SPOT_COLOR = "#06B6D4";

function drawBallPressureOverlay(ballPressure) {
    if (!ballPressure.active) return;

    if (ballPressure.ballLandingSpot != null) {
        drawBallLandingSpot(ballPressure.ballLandingSpot);
    }

    if (ballPressure.intendedTarget != null) {
        drawPlayerRing(
            ballPressure.intendedTarget.x,
            ballPressure.intendedTarget.y,
            PLAYER_DOT_RADIUS + 4,
            BALL_INTENDED_TARGET_RING_COLOR,
            2.5
        );
    } else if (ballPressure.carrier != null) {
        drawPlayerRing(
            ballPressure.carrier.x,
            ballPressure.carrier.y,
            PLAYER_DOT_RADIUS + 4,
            BALL_CARRIER_RING_COLOR,
            2.5
        );
    }

    if (ballPressure.highPassChallengers != null && ballPressure.highPassChallengers.length > 0) {
        var intendedTarget = ballPressure.intendedTarget;
        if (intendedTarget != null) {
            gameCanvas.ctx.strokeStyle = HIGH_PASS_CHALLENGE_EDGE_COLOR;
            gameCanvas.ctx.lineWidth = 2.5;

            for (var j = 0; j < ballPressure.highPassChallengers.length; j++) {
                var challenger = ballPressure.highPassChallengers[j];
                gameCanvas.drawLine(
                    challenger.x,
                    challenger.y,
                    intendedTarget.x,
                    intendedTarget.y
                );
                drawPlayerRing(
                    challenger.x,
                    challenger.y,
                    PLAYER_DOT_RADIUS + 3,
                    HIGH_PASS_CHALLENGE_EDGE_COLOR,
                    2.5
                );
            }

            gameCanvas.ctx.lineWidth = 1;
        }
    }

    if (ballPressure.pressers.length === 0) return;

    gameCanvas.ctx.strokeStyle = BALL_PRESSURE_EDGE_COLOR;
    gameCanvas.ctx.lineWidth = 2.5;

    for (var i = 0; i < ballPressure.pressers.length; i++) {
        var presser = ballPressure.pressers[i];
        var carrier = ballPressure.carrier;
        if (carrier == null) continue;

        gameCanvas.drawLine(presser.x, presser.y, carrier.x, carrier.y);
        drawPlayerRing(presser.x, presser.y, PLAYER_DOT_RADIUS + 3, BALL_PRESSURE_EDGE_COLOR, 2.5);
    }

    gameCanvas.ctx.lineWidth = 1;
}

function drawPlayerRing(x, y, radius, color, lineWidth) {
    var ctx = gameCanvas.ctx;
    ctx.save();
    ctx.strokeStyle = color;
    ctx.lineWidth = lineWidth;
    ctx.beginPath();
    ctx.arc(x, y, radius, 0, 2 * Math.PI);
    ctx.stroke();
    ctx.restore();
}

function drawBallLandingSpot(landingSpot) {
    var xy = pt(landingSpot.h, landingSpot.v);
    var x = xy[0];
    var y = xy[1];
    var radius = 6;
    var arm = 10;
    var ctx = gameCanvas.ctx;

    ctx.save();
    ctx.strokeStyle = BALL_LANDING_SPOT_COLOR;
    ctx.fillStyle = BALL_LANDING_SPOT_COLOR;
    ctx.lineWidth = 2;

    ctx.beginPath();
    ctx.arc(x, y, radius, 0, 2 * Math.PI);
    ctx.stroke();

    ctx.beginPath();
    ctx.moveTo(x - arm, y);
    ctx.lineTo(x + arm, y);
    ctx.moveTo(x, y - arm);
    ctx.lineTo(x, y + arm);
    ctx.stroke();

    ctx.beginPath();
    ctx.arc(x, y, 2, 0, 2 * Math.PI);
    ctx.fill();
    ctx.restore();
}
