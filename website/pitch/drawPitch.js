function draw() {
    if (gameCanvases.length === 0) return;
    if (gameData == null) return;

    handleFrameNr();

    document.getElementById("time_label_text").innerHTML = frameToTime(frameNr);
    document.getElementById("time_label_text").setAttribute("title", "frame: " + gameData.tracking[frameNr].frame);

    flipPitch = !getIsSecondHalf(frameNr);

    gameCanvas = gameCanvases[0];
    if (pitchOffsetX == -1) {
        drawGameSetup();
    }

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
        drawMarkingEdges(edges, "#E67E22");
    }

    if (pitchIndex === 1) {
        var knnEdges = getKnnMarkingEdges(frameNr, knnK);
        drawMarkingEdges(knnEdges, "#3498DB");
    }

    drawTeam(1);
    drawTeam(2);
    drawArrows(getIsSecondHalf(frameNr));
    drawGoalKeepers(getGoalKeepers(frameNr));
    drawPlayerLabels(frameNr);
    drawBall(frameNr);
}

function drawTeam(team) {
    const [points] = getGamePoints(frameNr, team);
    if (points == null || points.length === 0) return;

    const fill = team == 1 ? gameData.homeTeam.colorShirt : gameData.awayTeam.colorShirt;
    gameCanvas.ctx.fillStyle = fill;
    gameCanvas.ctx.strokeStyle = fill;

    for (var i = 0; i < points.length; i += 2) {
        gameCanvas.drawDot(points[i], points[i + 1], 8);
    }
}

function drawGoalKeepers(points) {
    if (points == null) return;

    gameCanvas.ctx.fillStyle = "#575757";
    gameCanvas.ctx.strokeStyle = "#575757";

    for (const point of points) {
        gameCanvas.drawDot(point[0], point[1], 8);
    }
}

function drawArrows(isSecondHalf) {
    var arrowDirection = flipPitch ? isSecondHalf : !isSecondHalf;

    gameCanvas.ctx.strokeStyle = "#575757";
    gameCanvas.ctx.fillStyle = gameData.homeTeam.colorShirt;
    if (!arrowDirection) drawArrowUp();
    else drawArrowDown();

    gameCanvas.ctx.fillStyle = gameData.awayTeam.colorShirt;
    if (!arrowDirection) drawArrowDown();
    else drawArrowUp();
}

function drawArrowDown() {
    const h0B = gameCanvas.height / 2 - 25;
    const h = 12;
    const h1 = 8;
    const w = 3;
    const w0 = 10;

    gameCanvas.ctx.beginPath();
    gameCanvas.ctx.moveTo(w0 + w * 1.5, h0B + h + h1);
    gameCanvas.ctx.lineTo(w0 + w * 3, h0B + h);
    gameCanvas.ctx.lineTo(w0 + w * 2, h0B + h);
    gameCanvas.ctx.lineTo(w0 + w * 2, h0B - h);
    gameCanvas.ctx.lineTo(w0 + w, h0B - h);
    gameCanvas.ctx.lineTo(w0 + w, h0B + h);
    gameCanvas.ctx.lineTo(w0, h0B + h);
    gameCanvas.ctx.closePath();
    gameCanvas.ctx.fill();
}

function drawArrowUp() {
    const h0A = gameCanvas.height / 2 + 25;
    const h = 12;
    const h1 = 8;
    const w = 3;
    const w0 = 10;

    gameCanvas.ctx.beginPath();
    gameCanvas.ctx.moveTo(w0 + w * 1.5, h0A - h - h1);
    gameCanvas.ctx.lineTo(w0 + w * 3, h0A - h);
    gameCanvas.ctx.lineTo(w0 + w * 2, h0A - h);
    gameCanvas.ctx.lineTo(w0 + w * 2, h0A + h);
    gameCanvas.ctx.lineTo(w0 + w, h0A + h);
    gameCanvas.ctx.lineTo(w0 + w, h0A - h);
    gameCanvas.ctx.lineTo(w0, h0A - h);
    gameCanvas.ctx.closePath();
    gameCanvas.ctx.fill();
}
