function draw() {
    if (gameCanvases.length === 0) return;
    if (gameData == null) return;
    if (isExporting) return;

    handleFrameNr();

    document.getElementById("time_label_text").innerHTML = frameToTime(frameNr);
    document.getElementById("time_label_text").setAttribute("title", "frame: " + gameData.tracking[frameNr].frame);

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
        var hungarianEdges = getHungarianMarkingEdges(frameNr, hungarianAttackerCount);
        drawMarkingEdges(hungarianEdges, MARKING_EDGE_COLOR);
    }

    if (pitchIndex === 3) {
        var delaunayEdges = getAttackingDelaunayEdges(frameNr);
        drawGraphEdges(delaunayEdges, GRAPH_EDGE_COLOR);
    }

    if (pitchIndex === 4) {
        var shapeGraphEdges = getAttackingShapeGraphEdges(frameNr);
        drawGraphEdges(shapeGraphEdges, GRAPH_EDGE_COLOR);
    }

    if (pitchIndex === 5) {
        var allOutfieldShapeGraphEdges = getAllOutfieldShapeGraphEdges(frameNr);
        drawGraphEdges(allOutfieldShapeGraphEdges, GRAPH_EDGE_COLOR);
    }

    var responsibilityAnalysis = null;
    if (pitchIndex === 6) {
        responsibilityAnalysis = analyzeResponsibility(frameNr);
    }

    var defendingTeam = (pitchIndex < 3 || pitchIndex === 5) ? getDefendingTeam(frameNr) : null;
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

    if (pitchIndex === 6 && responsibilityAnalysis != null) {
        drawResponsibilityOverlay(responsibilityAnalysis);
        updateResponsibilityInfo(responsibilityAnalysis);
    }
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

