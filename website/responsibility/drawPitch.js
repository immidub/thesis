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
    gameCanvas.ctx.restore();
}

const DEFENDING_PLAYER_BORDER_COLOR = "#1a1a1a";
const DEFENDING_PLAYER_BORDER_WIDTH = 2.5;
const PLAYER_DOT_RADIUS = 8;

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
