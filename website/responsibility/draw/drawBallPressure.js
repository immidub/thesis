const BALL_PRESSURE_EDGE_COLOR = "#DC2626";
const BALL_CARRIER_RING_COLOR = "#F59E0B";
const BALL_PREDICTION_COLOR = "#575757";

function drawBallPressureOverlay(ballPressure) {
    if (!ballPressure.active) return;

    if (ballPressure.ballPrediction != null) {
        var predictedCanvas = pt(ballPressure.ballPrediction.h, ballPressure.ballPrediction.v);
        var ctx = gameCanvas.ctx;
        ctx.save();
        ctx.strokeStyle = BALL_PREDICTION_COLOR;
        ctx.lineWidth = 2;
        gameCanvas.drawCircle(predictedCanvas[0], predictedCanvas[1], convertDist(0.8));
        ctx.restore();
    }

    if (ballPressure.carrier != null) {
        drawPlayerRing(
            ballPressure.carrier.x,
            ballPressure.carrier.y,
            PLAYER_DOT_RADIUS + 4,
            BALL_CARRIER_RING_COLOR,
            2.5
        );
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
