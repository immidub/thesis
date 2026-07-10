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

    if (pitchIndex === 0) {
        var edges = getDistanceMarkingEdges(frameNr, distanceThresholdMeters);
        drawMarkingEdges(edges, MARKING_EDGE_COLOR);
    }

    if (pitchIndex === 1) {
        var knnEdges = getKnnMarkingEdges(frameNr, knnK);
        drawMarkingEdges(knnEdges, MARKING_EDGE_COLOR);
    }

    if (pitchIndex === 2) {
        var allOutfieldKnnEdges = getAllOutfieldKnnEdges(frameNr, allOutfieldKnnK);
        drawMarkingEdges(allOutfieldKnnEdges, MARKING_EDGE_COLOR);
    }

    if (pitchIndex === 3) {
        var hungarianEdges = getHungarianMarkingEdges(frameNr, hungarianAttackerCount);
        drawMarkingEdges(hungarianEdges, MARKING_EDGE_COLOR);
    }

    if (pitchIndex === 4) {
        var attackingEdges = attackingGraphMode === "shape"
            ? getAttackingShapeGraphEdges(frameNr)
            : getAttackingDelaunayEdges(frameNr);
        drawGraphEdges(attackingEdges, GRAPH_EDGE_COLOR);
    }

    if (pitchIndex === 5) {
        var allOutfieldEdges = allOutfieldGraphMode === "shape"
            ? getAllOutfieldShapeGraphEdges(frameNr)
            : getAllOutfieldDelaunayEdges(frameNr);
        drawGraphEdges(allOutfieldEdges, GRAPH_EDGE_COLOR);
    }

    var defendingTeam = (pitchIndex < 4 || pitchIndex === 5) ? getDefendingTeam(frameNr) : null;
    var ballLive = isBallLive(frameNr);

    gameCanvas.ctx.save();
    if (!ballLive) {
        gameCanvas.ctx.globalAlpha = 0.45;
    }

    drawTeam(1, defendingTeam);
    drawTeam(2, defendingTeam);
    drawGoalKeepers(frameNr, defendingTeam);
    drawPlayerLabels(frameNr);
    drawBall(frameNr, ballLive);
    gameCanvas.ctx.restore();
}
