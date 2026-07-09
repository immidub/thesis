var isExporting = false;

function draw() {
    if (gameCanvases.length === 0) return;
    if (gameData == null) return;

    handleFrameNr();
    updateTimeLabels(frameNr);

    gameCanvas = gameCanvases[0];
    if (pitchOffsetX == -1) {
        drawGameSetup();
    }

    updatePitchDirectionBars(frameNr);

    gameCanvas.clearCanvasWhite();
    drawPitch();

    var ballLive = isBallLive(frameNr);

    gameCanvas.ctx.save();
    if (!ballLive) {
        gameCanvas.ctx.globalAlpha = 0.45;
    }

    drawTeam(1, null);
    drawTeam(2, null);
    drawGoalKeepers(getGoalKeepers(frameNr), null);
    drawPlayerLabels(frameNr);
    drawBall(frameNr, ballLive);

    // Debug: highlight controller / contestants (reachability-to-ball).
    if (ballLive) {
        drawBallContestOverlay(frameNr);
    }
    gameCanvas.ctx.restore();
}

const DEFENDING_PLAYER_BORDER_COLOR = "#1a1a1a";
const DEFENDING_PLAYER_BORDER_WIDTH = 2.5;
const PLAYER_DOT_RADIUS = 8;

const CONTEST_CONTROLLER_RING_COLOR = "#16A34A"; // green
const CONTEST_CONTESTANT_RING_COLOR = "#F59E0B"; // amber
const CONTEST_RING_WIDTH = 3.0;
const CONTEST_RING_EXTRA_RADIUS = 3.5;

function getPlayerScreenPosition(frame, playerId) {
    var dataLine = gameData.tracking[frame];
    if (!dataLine || !dataLine.objects) return null;
    var obj = dataLine.objects[String(playerId)];
    if (!obj) return null;
    var [h, v] = getCoordinates(obj, obj);
    var [x, y] = pt(h, v);
    return { x: x, y: y };
}

function drawRingAt(x, y, radius, color) {
    var ctx = gameCanvas.ctx;
    var prevWidth = ctx.lineWidth;
    var prevStroke = ctx.strokeStyle;
    ctx.lineWidth = CONTEST_RING_WIDTH;
    ctx.strokeStyle = color;
    ctx.beginPath();
    ctx.arc(x, y, radius, 0, 2 * Math.PI);
    ctx.stroke();
    ctx.strokeStyle = prevStroke;
    ctx.lineWidth = prevWidth;
}

function drawBallContestOverlay(frame) {
    if (typeof inferBallContest !== "function") return;
    var res = inferBallContest(frame);
    if (!res || !res.ball) return;
    if (res.state !== "controlled" && res.state !== "contested") return;

    if (!res.contestants || res.contestants.length === 0) return;

    var ringColor = res.contestants.length === 1
        ? CONTEST_CONTROLLER_RING_COLOR
        : CONTEST_CONTESTANT_RING_COLOR;

    for (var i = 0; i < res.contestants.length; i++) {
        var c = res.contestants[i];
        if (!c || c.id == null) continue;
        var pos = getPlayerScreenPosition(frame, c.id);
        if (!pos) continue;
        drawRingAt(
            pos.x,
            pos.y,
            PLAYER_DOT_RADIUS + CONTEST_RING_EXTRA_RADIUS,
            ringColor
        );
    }
}

function drawTeam(team, defendingTeam) {
    const [points] = getGamePoints(frameNr, team);
    if (points == null || points.length === 0) return;

    const fill = team == 1 ? gameData.homeTeam.colorShirt : gameData.awayTeam.colorShirt;
    const isDefending = team === defendingTeam;

    gameCanvas.ctx.fillStyle = fill;

    for (var i = 0; i < points.length; i += 2) {
        var x = points[i];
        var y = points[i + 1];
        gameCanvas.drawDot(x, y, PLAYER_DOT_RADIUS);
        if (isDefending) {
            gameCanvas.drawDotWithStroke(x, y, PLAYER_DOT_RADIUS, DEFENDING_PLAYER_BORDER_COLOR, DEFENDING_PLAYER_BORDER_WIDTH);
        }
    }
}

function drawGoalKeepers(points, defendingTeam) {
    if (points == null) return;

    gameCanvas.ctx.fillStyle = "#575757";

    for (const point of points) {
        gameCanvas.drawDot(point[0], point[1], PLAYER_DOT_RADIUS);
        if (point[2] === defendingTeam) {
            gameCanvas.drawDotWithStroke(point[0], point[1], PLAYER_DOT_RADIUS, DEFENDING_PLAYER_BORDER_COLOR, DEFENDING_PLAYER_BORDER_WIDTH);
        }
    }
}
