function draw() {
    if (gameCanvases.length === 0) return;
    if (gameData == null) return;

    handleFrameNr();

    updateTimeLabel(frameNr);

    gameCanvas = gameCanvases[0];
    if (pitchOffsetX == -1) {
        drawGameSetup();
    }

    updatePitchDirectionBars(frameNr);

    gameCanvas.clearCanvasWhite();
    drawDefensivePitchFrame();
}

function drawDefensivePitchFrame() {
    drawPitch();

    var analysis = analyzeDefensiveFrame(frameNr);
    if (analysis.active) {
        drawOffBallPoolEdges(analysis.offBallPools);
        drawPassingOptionsOverlay(analysis.passingOptions);
    }

    var defendingTeam = getDefendingTeam(frameNr);
    var ballLive = isBallLive(frameNr);

    gameCanvas.ctx.save();
    if (!ballLive) {
        gameCanvas.ctx.globalAlpha = 0.45;
    }

    drawTeam(1, defendingTeam);
    drawTeam(2, defendingTeam);
    drawGoalKeepers(getGoalKeepers(frameNr), defendingTeam);
    drawPlayerLabels(frameNr);
    drawBall(frameNr, ballLive);
    gameCanvas.ctx.restore();

    if (analysis.active && analysis.ballPressure != null) {
        drawBallPressureOverlay(analysis.ballPressure);
    }

    if (analysis.behaviors != null) {
        drawBehaviorClassificationOverlay(analysis.behaviors);
    }

    updateBehaviorExplanationsPanel(analysis.behaviors, analysis);
}

const OFF_BALL_POOL_EDGE_COLOR = "#9CA3AF";
const OFF_BALL_POOL_EDGE_WIDTH = 1.5;

function drawOffBallPoolEdges(pools) {
    if (!pools || pools.length === 0) return;

    gameCanvas.ctx.strokeStyle = OFF_BALL_POOL_EDGE_COLOR;
    gameCanvas.ctx.lineWidth = OFF_BALL_POOL_EDGE_WIDTH;

    for (var i = 0; i < pools.length; i++) {
        var pool = pools[i];
        for (var j = 0; j < pool.targets.length; j++) {
            var target = pool.targets[j];
            gameCanvas.drawLine(pool.x, pool.y, target.x, target.y);
        }
    }

    gameCanvas.ctx.lineWidth = 1;
}
