const RESPONSIBILITY_EDGE_COLOR = "#DC2626";
const CARRIER_RING_COLOR = "#F59E0B";

function drawResponsibilityOverlay(analysis) {
    if (!analysis.active) return;

    if (analysis.carrier != null) {
        drawPlayerRing(analysis.carrier.x, analysis.carrier.y, PLAYER_DOT_RADIUS + 4, CARRIER_RING_COLOR, 2.5);
    }

    if (analysis.pressers.length === 0) return;

    gameCanvas.ctx.strokeStyle = RESPONSIBILITY_EDGE_COLOR;
    gameCanvas.ctx.lineWidth = 2.5;

    for (var i = 0; i < analysis.pressers.length; i++) {
        var presser = analysis.pressers[i];
        var carrier = analysis.carrier;
        if (carrier == null) continue;

        gameCanvas.drawLine(presser.x, presser.y, carrier.x, carrier.y);
        drawPlayerRing(presser.x, presser.y, PLAYER_DOT_RADIUS + 3, RESPONSIBILITY_EDGE_COLOR, 2.5);
    }

    gameCanvas.ctx.lineWidth = 1;
}

function drawPlayerRing(x, y, radius, color, lineWidth) {
    var ctx = gameCanvas.ctx;
    ctx.save();
    ctx.strokeStyle = color;
    ctx.lineWidth = lineWidth;
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

    if (analysis.pressers.length === 0) {
        lines.push("Press: none detected");
    } else {
        for (var i = 0; i < analysis.pressers.length; i++) {
            lines.push("Press: " + analysis.pressers[i].explanation);
        }
    }

    element.textContent = lines.join(" · ");
}
