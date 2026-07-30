//drawPitch.js handles the drawing of the pitch view
//main draw function in the loop
function draw() {
    if (gameCanvases.length === 0) return;
    if (gameData == null) return;
    if (isExporting) return;

    handleFrameNr();

    updateTimeLabels(frameNr);

    gameCanvas = gameCanvases[0];
    if (pitchOffsetX == -1) {
        drawGameSetup();
    }

    updatePitchDirectionBars(frameNr);

    for (var i = 0; i < gameCanvases.length; i++) {
        gameCanvas = gameCanvases[i];
        gameCanvas.clearCanvasWhite();
        drawPitchFrame(i);
    }
}

function drawPitchFrame(pitchIndex) {
    drawPitch();

    if (typeof drawOverlayBackground === "function") {
        drawOverlayBackground(frameNr);
    }

    var edges = [];
    if (pitchIndex === 0) {
        edges = getDistanceMarkingEdges(frameNr, distanceThresholdMeters);
    } else if (pitchIndex === 1) {
        edges = getKnnMarkingEdges(frameNr, knnK);
    } else if (pitchIndex === 2) {
        edges = getHungarianMarkingEdges(frameNr);
    } else if (pitchIndex === 3) {
        edges = allOutfieldGraphMode === "shape"
            ? getAllOutfieldShapeGraphEdges(frameNr)
            : getAllOutfieldDelaunayEdges(frameNr);
    }

    if (typeof drawOverlayEdges === "function") {
        drawOverlayEdges(edges, frameNr);
    } else if (pitchIndex === 3) {
        drawGraphEdges(edges, MARKING_EDGE_COLOR);
    } else {
        drawMarkingEdges(edges, MARKING_EDGE_COLOR);
    }

    var defendingTeam = getDefendingTeam(frameNr);
    var ballLive = isBallLive(frameNr);

    gameCanvas.ctx.save();
    if (!ballLive) {
        gameCanvas.ctx.globalAlpha = 0.45;
    }

    drawTeam(1, defendingTeam);
    drawTeam(2, defendingTeam);
    drawGoalKeepers(frameNr, defendingTeam);
    if (typeof drawOverlayForeground === "function") {
        drawOverlayForeground(edges, frameNr);
    }
    if (typeof drawVelocityArrows === "function") {
        drawVelocityArrows(frameNr);
    }
    drawPlayerLabels(frameNr);
    drawBall(frameNr, ballLive);
    gameCanvas.ctx.restore();
}
