const RESPONSIBILITY_EDGE_COLOR = "#DC2626";
const CARRIER_RING_COLOR = "#F59E0B";

function drawResponsibilityOverlay(frame, analysis) {
    if (!analysis.active) return;

    if (analysis.carrier != null) {
        drawPlayerRing(analysis.carrier.x, analysis.carrier.y, PLAYER_DOT_RADIUS + 4, CARRIER_RING_COLOR, 2.5);
    }

    if (analysis.pressers.length === 0) return;

    var drawCount = Math.min(analysis.pressers.length, 2);
    gameCanvas.ctx.strokeStyle = RESPONSIBILITY_EDGE_COLOR;
    gameCanvas.ctx.lineWidth = 2.5;

    for (var i = 0; i < drawCount; i++) {
        var presser = analysis.pressers[i];
        var target = analysis.carrier;
        if (target == null) continue;

        var defenderPos = findPlayerCanvasPos(frame, presser.defenderId);
        if (defenderPos == null) continue;

        gameCanvas.drawLine(defenderPos.x, defenderPos.y, target.x, target.y);

        if (i === 0) {
            gameCanvas.drawDotWithStroke(
                defenderPos.x,
                defenderPos.y,
                PLAYER_DOT_RADIUS,
                RESPONSIBILITY_EDGE_COLOR,
                3
            );
        }
    }

    gameCanvas.ctx.lineWidth = 1;
}

function findPlayerCanvasPos(frame, playerId) {
    var dataLine = gameData.tracking[frame];
    var dataLine2 = gameData.tracking[frame + 1] || dataLine;
    var object1 = dataLine.objects[playerId];
    if (!object1) return null;

    var object2 = dataLine2.objects[playerId] || object1;
    var [h, v] = getCoordinates(object1, object2);
    var [x, y] = pt(h, v);
    return { x: x, y: y };
}

function drawPlayerRing(x, y, radius, color, lineWidth, dash) {
    var ctx = gameCanvas.ctx;
    ctx.save();
    ctx.strokeStyle = color;
    ctx.lineWidth = lineWidth;
    if (dash) {
        ctx.setLineDash(dash);
    }
    ctx.beginPath();
    ctx.arc(x, y, radius, 0, 2 * Math.PI);
    ctx.stroke();
    ctx.restore();
}

function updateResponsibilityInfo(analysis) {
    var element = document.getElementById("responsibility_info");
    if (!element) return;

    if (!analysis.active) {
        element.textContent = analysis.reason || "No responsibility analysis";
        return;
    }

    var lines = [];
    lines.push(
        "Carrier: #" + analysis.carrier.shirtNumber +
        " (" + (Math.round(analysis.carrier.distToBall * 10) / 10) + " m to ball)"
    );

    if (analysis.primaryPresser != null) {
        lines.push("Press: " + analysis.primaryPresser.explanation);
    } else {
        lines.push("Press: none detected");
    }

    element.textContent = lines.join(" · ");
}
