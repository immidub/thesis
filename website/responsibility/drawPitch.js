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
    drawGoalKeepers(frameNr, null);
    drawPlayerLabels(frameNr);
    drawBall(frameNr, ballLive);

    if (ballLive) {
        drawBallContestOverlay(frameNr);
    }
    gameCanvas.ctx.restore();
}

const CONTEST_CONTROLLER_RING_COLOR = "#16A34A";
const CONTEST_CONTESTANT_RING_COLOR = "#F59E0B";
const CONTEST_RING_WIDTH = 3.0;
const CONTEST_RING_EXTRA_RADIUS = 3.5;

const MUTUAL_HELP_EDGE_COLOR = "#94A3B8";
const MUTUAL_HELP_EDGE_WIDTH = 1;
const RESPONSIBILITY_MARKING_EDGE_WIDTH = 2;

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

function drawBallContestOverlay(frame) { // draws the ball contest overlay
    if (typeof inferBallContest !== "function") return;
    var res = inferBallContest(frame);
    if (!res || !res.ball) return;
    if (res.state !== "controlled" && res.state !== "contested") return;

    if (!res.contestants || res.contestants.length === 0) return;

    if (typeof getMutualHelpEdges === "function") { // draws the mutual help edges between the contestants
        drawCanvasEdges(getMutualHelpEdges(frame, res.contestants), {
            color: MUTUAL_HELP_EDGE_COLOR,
            lineWidth: MUTUAL_HELP_EDGE_WIDTH,
            dashedSupport: false,
        });
    }

    if (typeof getResponsibilityMarkingEdges === "function") { // draws the responsibility marking edges between the contestants
        drawCanvasEdges(getResponsibilityMarkingEdges(frame, res.contestants), {
            color: MARKING_EDGE_COLOR,
            lineWidth: RESPONSIBILITY_MARKING_EDGE_WIDTH,
            dashedSupport: false,
        });
    }

    var ringColor = res.contestants.length === 1
        ? CONTEST_CONTROLLER_RING_COLOR
        : CONTEST_CONTESTANT_RING_COLOR;

    for (var i = 0; i < res.contestants.length; i++) {
        var c = res.contestants[i];
        if (!c || c.id == null) continue;
        var pos = getPlayerScreenPosition(frame, c.id);
        if (!pos) continue;
        drawRingAt( // draws the ring at the position of the contestant
            pos.x,
            pos.y,
            PLAYER_DOT_RADIUS + CONTEST_RING_EXTRA_RADIUS,
            ringColor
        );
    }
}
