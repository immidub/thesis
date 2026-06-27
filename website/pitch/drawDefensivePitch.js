function draw() {
    if (gameCanvases.length === 0) return;
    if (gameData == null) return;

    handleFrameNr();

    document.getElementById("time_label_text").innerHTML = frameToTime(frameNr);
    document.getElementById("time_label_text").setAttribute("title", "frame: " + gameData.tracking[frameNr].frame);

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

    updateDefensiveFrameInfo(analysis);
}
