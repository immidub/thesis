function draw() {
    if (gameCanvases.length === 0) return;
    if (gameData == null) return;
    if (typeof isExporting !== "undefined" && isExporting) return;

    handleFrameNr();
    updateTimeLabels(frameNr);

    gameCanvas = gameCanvases[0];
    if (pitchOffsetX == -1) {
        drawGameSetup();
    }

    updatePitchDirectionBars(frameNr);

    gameCanvas.clearCanvasWhite();
    drawPitchFrame(0);
}

/** Single-pitch draw used by the animation loop and clip export. */
function drawPitchFrame(_pitchIndex) {
    drawPitch();

    var ballLive = isBallLive(frameNr);
    var defendingTeam = typeof getDefendingTeam === "function" ? getDefendingTeam(frameNr) : null;

    gameCanvas.ctx.save();
    if (!ballLive) {
        gameCanvas.ctx.globalAlpha = 0.45;
    }

    if (ballLive && typeof drawResponsibilitySpaceZones === "function") {
        drawResponsibilitySpaceZones(frameNr);
    }

    if (ballLive && typeof drawVelocityArrows === "function") {
        drawVelocityArrows(frameNr);
    }

    drawTeam(1, defendingTeam);
    drawTeam(2, defendingTeam);
    drawGoalKeepers(frameNr, defendingTeam);
    if (typeof drawSelectedSpaceZoneDefenderHighlight === "function") {
        drawSelectedSpaceZoneDefenderHighlight(frameNr);
    }
    drawPlayerLabels(frameNr);
    drawBall(frameNr, ballLive);

    if (ballLive) {
        drawResponsibilityResults(frameNr);
    }
    gameCanvas.ctx.restore();
}

const CONTEST_CONTROLLER_RING_COLOR = "#16A34A";
const CONTEST_CONTESTANT_RING_COLOR = "#F59E0B";
const CONTEST_RING_WIDTH = 3.0;
const CONTEST_RING_EXTRA_RADIUS = 3.5;

const MUTUAL_HELP_EDGE_COLOR = "#94A3B8";
const MUTUAL_HELP_EDGE_WIDTH = 1;
const RESPONSIBILITY_MARKING_EDGE_WIDTH = 2;
const RESPONSIBILITY_SELECTED_MARKING_COLOR = "#DC2626";
const RESPONSIBILITY_SELECTED_MARKING_WIDTH = 4;
const RESPONSIBILITY_SELECTED_ATTACKER_RING = "#DC2626";
const ZONE_ATTACKER_EDGE_COLOR = "#EA580C";
const ZONE_ATTACKER_EDGE_WIDTH = 1.5;

var showMutualHelpEdges = false;
var showZoneAttackerEdges = false;

function setShowMutualHelpEdges(enabled) {
    showMutualHelpEdges = enabled !== false;
}

function setShowZoneAttackerEdges(enabled) {
    showZoneAttackerEdges = !!enabled;
}

function drawRingAt(x, y, radius, color) {
    var ctx = gameCanvas.ctx;
    var prevWidth = ctx.lineWidth;
    var prevStroke = ctx.strokeStyle;
    ctx.lineWidth = CONTEST_RING_WIDTH;
    ctx.strokeStyle = color;
    ctx.beginPath();
    ctx.arc(x, y, radius, 0, 2 * Math.PI);
    ctx.stroke();
    ctx.strokeStyle = prevStroke;
    ctx.lineWidth = prevWidth;
}

/** Dashed defender→attacker edges when an attacker stands in that defender's PC zone. */
function edgesFromZoneAttackers(frame) {
    var edges = [];
    if (typeof getHeldResponsibilityZoneFrame !== "function") return edges;
    if (typeof buildZoneOwnerByCell !== "function") return edges;
    if (typeof trackingPitchToCellIndex !== "function") return edges;
    if (!responsibilityZonesHeader) return edges;

    var held = getHeldResponsibilityZoneFrame(frame);
    if (held == null) return edges;
    var data = responsibilityZonesByFrame[held];
    if (!data || !data.defenders) return edges;

    var sides = typeof getMarkingSides === "function" ? getMarkingSides(frame) : null;
    if (!sides) return edges;

    var owner = buildZoneOwnerByCell(data.defenders);
    var byId = {};
    for (var d = 0; d < sides.defenders.length; d++) {
        byId[String(sides.defenders[d].id)] = sides.defenders[d];
    }

    for (var a = 0; a < sides.attackers.length; a++) {
        var attacker = sides.attackers[a];
        // player.h/v are display pitch coords from getCoordinates ([-trackingX, trackingY]).
        var cellIdx = trackingPitchToCellIndex(-attacker.h, attacker.v, responsibilityZonesHeader);
        if (cellIdx == null) continue;
        var defenderId = owner[cellIdx];
        if (!defenderId) continue;
        var defender = byId[String(defenderId)];
        if (!defender) continue;
        edges.push({
            x1: defender.x,
            y1: defender.y,
            x2: attacker.x,
            y2: attacker.y,
            dashed: true,
            defenderId: String(defenderId),
            attackerId: String(attacker.id),
        });
    }
    return edges;
}

function drawResponsibilityResults(frame) {
    var row = typeof getResponsibilityFrame === "function" ? getResponsibilityFrame(frame) : null;
    if (!row) return;

    var contestantIds = row.contestantIds || [];
    if (contestantIds.length === 0) return;

    if (showMutualHelpEdges) {
        drawCanvasEdges(edgesFromIdPairs(frame, row.mutualHelpEdges, false), {
            color: MUTUAL_HELP_EDGE_COLOR,
            lineWidth: MUTUAL_HELP_EDGE_WIDTH,
            dashedSupport: false,
        });
    }

    if (showZoneAttackerEdges) {
        drawCanvasEdges(edgesFromZoneAttackers(frame), {
            color: ZONE_ATTACKER_EDGE_COLOR,
            lineWidth: ZONE_ATTACKER_EDGE_WIDTH,
            dashedSupport: true,
        });
    }

    var markingEdges = edgesFromIdPairs(frame, row.markingEdges, true);
    if (markingEdges.length) {
        drawCanvasEdges(markingEdges, {
            color: MARKING_EDGE_COLOR,
            lineWidth: RESPONSIBILITY_MARKING_EDGE_WIDTH,
            dashedSupport: false,
        });
    }

    if (typeof selectedSpaceZonePlayerId !== "undefined" && selectedSpaceZonePlayerId != null) {
        var selectedId = String(selectedSpaceZonePlayerId);
        var selectedEdges = [];
        for (var e = 0; e < markingEdges.length; e++) {
            if (String(markingEdges[e].defenderId) === selectedId) {
                selectedEdges.push(markingEdges[e]);
            }
        }
        if (selectedEdges.length) {
            drawCanvasEdges(selectedEdges, {
                color: RESPONSIBILITY_SELECTED_MARKING_COLOR,
                lineWidth: RESPONSIBILITY_SELECTED_MARKING_WIDTH,
                dashedSupport: false,
            });
            for (var s = 0; s < selectedEdges.length; s++) {
                var attPos = getPlayerScreenPosition(frame, selectedEdges[s].attackerId);
                if (!attPos) continue;
                drawRingAt(
                    attPos.x,
                    attPos.y,
                    PLAYER_DOT_RADIUS + CONTEST_RING_EXTRA_RADIUS,
                    RESPONSIBILITY_SELECTED_ATTACKER_RING
                );
            }
        }
    }

    var ringColor = contestantIds.length === 1
        ? CONTEST_CONTROLLER_RING_COLOR
        : CONTEST_CONTESTANT_RING_COLOR;

    for (var i = 0; i < contestantIds.length; i++) {
        var pos = getPlayerScreenPosition(frame, contestantIds[i]);
        if (!pos) continue;
        drawRingAt(pos.x, pos.y, PLAYER_DOT_RADIUS + CONTEST_RING_EXTRA_RADIUS, ringColor);
    }
}
