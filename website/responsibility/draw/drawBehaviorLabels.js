const BEHAVIOR_BADGE_COLORS = {
    MAN_MARKING: "#2563EB",
    TRACKING_RUN: "#7C3AED",
    SPACE_COVER: "#059669",
    PASSING_LANE_COVER: "#0891B2",
    PRESSING: "#DC2626",
    CHALLENGING_HIGH_PASS: "#EA580C",
    HELP_DEFENDER: "#CA8A04",
};

const BEHAVIOR_BADGE_SHORT = {
    MAN_MARKING: "MAN",
    TRACKING_RUN: "RUN",
    SPACE_COVER: "SPACE",
    PASSING_LANE_COVER: "LANE",
    PRESSING: "PRESS",
    CHALLENGING_HIGH_PASS: "HIGH",
    HELP_DEFENDER: "HELP",
};

function drawBehaviorClassificationOverlay(behaviorAnalysis) {
    if (behaviorAnalysis == null || !behaviorAnalysis.active) return;
    if (!behaviorAnalysis.defenders || behaviorAnalysis.defenders.length === 0) return;

    var ctx = gameCanvas.ctx;
    ctx.save();
    ctx.font = "9px sans-serif";
    ctx.textAlign = "center";
    ctx.textBaseline = "bottom";

    for (var i = 0; i < behaviorAnalysis.defenders.length; i++) {
        var entry = behaviorAnalysis.defenders[i];
        var color = BEHAVIOR_BADGE_COLORS[entry.behavior] || "#374151";
        var targetPrefix = entry.behavior === BEHAVIOR_TYPES.HELP_DEFENDER ? " D" : " A";
        var label =
            BEHAVIOR_BADGE_SHORT[entry.behavior] +
            (entry.primaryTargetShirt != null ? targetPrefix + entry.primaryTargetShirt : "");

        ctx.fillStyle = "rgba(255, 255, 255, 0.92)";
        ctx.fillRect(entry.x - 18, entry.y - 28, 36, 12);
        ctx.fillStyle = color;
        ctx.fillText(label, entry.x, entry.y - 17);
    }

    ctx.textAlign = "start";
    ctx.textBaseline = "alphabetic";
    ctx.restore();
}

function sortBehaviorDefenders(defenders) {
    return defenders.slice().sort(function (a, b) {
        var shirtA = parseInt(a.defenderShirt, 10);
        var shirtB = parseInt(b.defenderShirt, 10);
        if (!isNaN(shirtA) && !isNaN(shirtB)) return shirtA - shirtB;
        return String(a.defenderShirt).localeCompare(String(b.defenderShirt));
    });
}

function updateBehaviorExplanationsPanel(behaviorAnalysis, analysis) {
    var panel = document.getElementById("behavior_explanations_panel");
    if (!panel) return;

    if (analysis != null && !analysis.active) {
        panel.innerHTML =
            '<div class="behavior-explanations__empty">' +
            (analysis.reason || "No active defensive analysis for this frame.") +
            "</div>";
        return;
    }

    if (
        behaviorAnalysis == null ||
        !behaviorAnalysis.active ||
        !behaviorAnalysis.defenders ||
        behaviorAnalysis.defenders.length === 0
    ) {
        panel.innerHTML =
            '<div class="behavior-explanations__empty">No defender behaviors classified for this frame.</div>';
        return;
    }

    var defenders = sortBehaviorDefenders(behaviorAnalysis.defenders);
    var html = '<div class="behavior-explanations__title">Behavior explanations</div>';
    html += '<div class="behavior-explanations__list">';

    for (var i = 0; i < defenders.length; i++) {
        var entry = defenders[i];
        var color = BEHAVIOR_BADGE_COLORS[entry.behavior] || "#374151";
        var targetLabel = "";
        if (entry.primaryTargetShirt != null) {
            var prefix = entry.behavior === BEHAVIOR_TYPES.HELP_DEFENDER ? " → D" : " → A";
            targetLabel = prefix + entry.primaryTargetShirt;
        }

        html +=
            '<div class="behavior-explanation">' +
            '<div class="behavior-explanation__header">' +
            '<span class="behavior-explanation__defender">D' +
            entry.defenderShirt +
            "</span>" +
            '<span class="behavior-explanation__label" style="color:' +
            color +
            '">' +
            entry.behaviorLabel +
            targetLabel +
            "</span>" +
            "</div>" +
            '<div class="behavior-explanation__detail">' +
            entry.explanation +
            "</div>" +
            '<div class="behavior-explanation__step">Step ' +
            entry.pipelineStep +
            ": " +
            entry.pipelineStepName +
            "</div>" +
            "</div>";
    }

    html += "</div>";
    panel.innerHTML = html;
}
