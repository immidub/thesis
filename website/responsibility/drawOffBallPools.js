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

function formatPoolTargetSummary(target) {
    var label = "#" + target.shirtNumber + " (" + (Math.round(target.dist * 10) / 10) + " m)";
    if (target.inShapeGraph === false) {
        label += ", nearest fallback";
    }
    return label;
}

function updateDefensiveFrameInfo(analysis) {
    var element = document.getElementById("responsibility_info");
    if (!element) return;

    if (!analysis.active) {
        element.textContent = analysis.reason || "No defensive analysis";
        return;
    }

    var ballPressure = analysis.ballPressure;
    var lines = [];

    lines.push(
        "Carrier: #" + ballPressure.carrier.shirtNumber +
        " (" + (Math.round(ballPressure.carrier.distToBall * 10) / 10) + " m to ball)"
    );

    if (ballPressure.pressers.length === 0) {
        lines.push("Press: none detected");
    } else {
        for (var i = 0; i < ballPressure.pressers.length; i++) {
            lines.push("Press: " + ballPressure.pressers[i].explanation);
        }
    }

    if (analysis.offBallPools.length === 0) {
        lines.push("Off-ball pools: none");
    } else {
        for (var p = 0; p < analysis.offBallPools.length; p++) {
            var pool = analysis.offBallPools[p];
            var targetParts = [];
            for (var t = 0; t < pool.targets.length; t++) {
                targetParts.push(formatPoolTargetSummary(pool.targets[t]));
            }
            lines.push(
                "Pool #" + pool.defenderShirt + " → " + targetParts.join(", ")
            );
        }
    }

    element.textContent = lines.join(" · ");
}
