// Visual overlays — separate from the distance model.
// Colours / highlights do not change which edges exist; they only style drawing.

var overlayLongEdgesEnabled = false;
var overlayLongEdgeThresholdM = 15;
var overlayGoalSideEnabled = false;
var overlayHighDegreeEnabled = false;
var overlayUnmarkedAttackersEnabled = false;
var overlayBallZonesEnabled = false;
var overlayPitchGridEnabled = false;

const OVERLAY_LONG_EDGE_MIN_M = 5;
const OVERLAY_LONG_EDGE_MAX_M = 40;
const OVERLAY_HIGH_DEGREE_MIN = 3;
const OVERLAY_BALL_ZONE_NEAR_M = 5;
const OVERLAY_BALL_ZONE_COOP_M = 20;
const OVERLAY_PITCH_ZONE_COLS = 12;
const OVERLAY_PITCH_ZONE_ROWS = 8;

const OVERLAY_EDGE_DEFAULT = "#2563EB";
const OVERLAY_EDGE_LONG = "#DC2626";
const OVERLAY_EDGE_GOAL_SIDE = "#16A34A";
const OVERLAY_EDGE_LONG_AND_GOAL = "#7C3AED";
const OVERLAY_DEGREE_HALO = "#F59E0B";
const OVERLAY_UNMARKED_RING = "#9CA3AF";
const OVERLAY_BALL_ZONE_STROKE = "rgba(55, 65, 81, 0.55)";
const OVERLAY_PITCH_GRID_STROKE = "rgba(148, 163, 184, 0.55)";

function playerTeamNumber(playerId) {
    var id = String(playerId);
    if (gameData.players.team1.includes(id)) return 1;
    if (gameData.players.team2.includes(id)) return 2;
    return null;
}

function buildOverlayPlayerIndex(frame) {
    var index = {};
    var home = getTeamPlayerPositions(frame, 1);
    var away = getTeamPlayerPositions(frame, 2);
    for (var i = 0; i < home.length; i++) index[String(home[i].id)] = home[i];
    for (var j = 0; j < away.length; j++) index[String(away[j].id)] = away[j];
    return index;
}

function edgeEndpointIds(edge) {
    var a = edge.defenderId != null ? edge.defenderId
        : edge.sourceId != null ? edge.sourceId
        : edge.playerIdA;
    var b = edge.attackerId != null ? edge.attackerId
        : edge.targetId != null ? edge.targetId
        : edge.playerIdB;
    if (a == null || b == null) return null;
    return { a: String(a), b: String(b) };
}

function edgeLengthMeters(edge, playerIndex) {
    if (edge.lengthM != null && Number.isFinite(edge.lengthM)) return edge.lengthM;
    var ids = edgeEndpointIds(edge);
    if (ids && playerIndex[ids.a] && playerIndex[ids.b]) {
        return Math.sqrt(getMarkingPairDistanceSquared(playerIndex[ids.a], playerIndex[ids.b]));
    }
    var dx = edge.x2 - edge.x1;
    var dy = edge.y2 - edge.y1;
    return Math.sqrt(dx * dx + dy * dy) / scaling;
}

function resolveDefenderAttacker(edge, playerIndex, defendingTeam) {
    var ids = edgeEndpointIds(edge);
    if (!ids) return null;
    var pa = playerIndex[ids.a];
    var pb = playerIndex[ids.b];
    if (!pa || !pb || defendingTeam == null) return null;

    var teamA = playerTeamNumber(ids.a);
    var teamB = playerTeamNumber(ids.b);
    if (teamA === defendingTeam && teamB !== defendingTeam) {
        return { defender: pa, attacker: pb };
    }
    if (teamB === defendingTeam && teamA !== defendingTeam) {
        return { defender: pb, attacker: pa };
    }
    return null;
}

function isGoalSidePair(goal, attacker, defender) {
    // Port of analysis.pitch.is_defender_goal_side in pitch (h, v) space.
    if (!goal || !attacker || !defender) return false;
    var gah = attacker.h - goal.h;
    var gav = attacker.v - goal.v;
    var gaLenSq = gah * gah + gav * gav;
    if (gaLenSq < 1e-9) return false;

    var dah = defender.h - goal.h;
    var dav = defender.v - goal.v;
    var t = (dah * gah + dav * gav) / gaLenSq;
    if (t < 0 || t > 1) return false;

    var projH = goal.h + t * gah;
    var projV = goal.v + t * gav;
    var latH = defender.h - projH;
    var latV = defender.v - projV;
    var lateral = Math.sqrt(latH * latH + latV * latV);
    var toAttH = attacker.h - projH;
    var toAttV = attacker.v - projV;
    var toAttacker = Math.sqrt(toAttH * toAttH + toAttV * toAttV);
    return lateral < toAttacker;
}

function overlayEdgeColor(edge, playerIndex, defendingTeam, goal) {
    var lengthM = edgeLengthMeters(edge, playerIndex);
    var isLong = overlayLongEdgesEnabled && lengthM > overlayLongEdgeThresholdM;
    var isGoal = false;
    if (overlayGoalSideEnabled) {
        var roles = resolveDefenderAttacker(edge, playerIndex, defendingTeam);
        if (roles) {
            isGoal = isGoalSidePair(goal, roles.attacker, roles.defender);
        }
    }

    if (isLong && isGoal) return OVERLAY_EDGE_LONG_AND_GOAL;
    if (isLong) return OVERLAY_EDGE_LONG;
    if (isGoal) return OVERLAY_EDGE_GOAL_SIDE;
    return OVERLAY_EDGE_DEFAULT;
}

function countPlayerDegrees(edges) {
    var degrees = {};
    for (var i = 0; i < edges.length; i++) {
        var ids = edgeEndpointIds(edges[i]);
        if (!ids) continue;
        degrees[ids.a] = (degrees[ids.a] || 0) + 1;
        degrees[ids.b] = (degrees[ids.b] || 0) + 1;
    }
    return degrees;
}

function drawOverlayPitchGrid() {
    if (!overlayPitchGridEnabled || !gameData) return;

    var halfL = gameData.pitch.length / 2;
    var halfW = gameData.pitch.width / 2;
    var cellL = gameData.pitch.length / OVERLAY_PITCH_ZONE_COLS;
    var cellW = gameData.pitch.width / OVERLAY_PITCH_ZONE_ROWS;

    var ctx = gameCanvas.ctx;
    var prevStroke = ctx.strokeStyle;
    var prevWidth = ctx.lineWidth;
    var prevDash = ctx.getLineDash();

    ctx.strokeStyle = OVERLAY_PITCH_GRID_STROKE;
    ctx.lineWidth = 1;
    ctx.setLineDash([3, 3]);

    for (var c = 0; c <= OVERLAY_PITCH_ZONE_COLS; c++) {
        var h = -halfL + c * cellL;
        var a = pt(h, -halfW);
        var b = pt(h, halfW);
        gameCanvas.drawLine(a[0], a[1], b[0], b[1]);
    }
    for (var r = 0; r <= OVERLAY_PITCH_ZONE_ROWS; r++) {
        var v = -halfW + r * cellW;
        var c0 = pt(-halfL, v);
        var c1 = pt(halfL, v);
        gameCanvas.drawLine(c0[0], c0[1], c1[0], c1[1]);
    }

    ctx.setLineDash(prevDash);
    ctx.strokeStyle = prevStroke;
    ctx.lineWidth = prevWidth;
}

function drawOverlayBallZones(frame) {
    if (!overlayBallZonesEnabled || !isBallLive(frame)) return;

    var dataLine = gameData.tracking[frame];
    if (!dataLine || !dataLine.objects[gameData.ballId]) return;

    var object1 = dataLine.objects[gameData.ballId];
    var object2 = (gameData.tracking[frame + 1] ?? dataLine).objects[gameData.ballId] ?? object1;
    var hv = getCoordinates(object1, object2);
    var xy = pt(hv[0], hv[1]);

    var ctx = gameCanvas.ctx;
    var prevStroke = ctx.strokeStyle;
    var prevWidth = ctx.lineWidth;
    var prevDash = ctx.getLineDash();

    ctx.strokeStyle = OVERLAY_BALL_ZONE_STROKE;
    ctx.lineWidth = 1.5;
    ctx.setLineDash([5, 4]);
    gameCanvas.drawCircle(xy[0], xy[1], convertDist(OVERLAY_BALL_ZONE_NEAR_M));
    gameCanvas.drawCircle(xy[0], xy[1], convertDist(OVERLAY_BALL_ZONE_COOP_M));

    ctx.setLineDash(prevDash);
    ctx.strokeStyle = prevStroke;
    ctx.lineWidth = prevWidth;
}

function drawOverlayEdges(edges, frame) {
    if (!edges || edges.length === 0) return;

    var anyEdgeOverlay = overlayLongEdgesEnabled || overlayGoalSideEnabled;
    if (!anyEdgeOverlay) {
        drawMarkingEdges(edges, OVERLAY_EDGE_DEFAULT);
        return;
    }

    var playerIndex = buildOverlayPlayerIndex(frame);
    var defendingTeam = getDefendingTeam(frame);
    var goal = null;
    if (overlayGoalSideEnabled && typeof getDefendedGoalPitch === "function") {
        goal = getDefendedGoalPitch(frame);
    }

    var byColor = {};
    for (var i = 0; i < edges.length; i++) {
        var edge = edges[i];
        var color = overlayEdgeColor(edge, playerIndex, defendingTeam, goal);
        if (!byColor[color]) byColor[color] = [];
        byColor[color].push(edge);
    }

    var colorOrder = [
        OVERLAY_EDGE_DEFAULT,
        OVERLAY_EDGE_GOAL_SIDE,
        OVERLAY_EDGE_LONG,
        OVERLAY_EDGE_LONG_AND_GOAL,
    ];
    for (var c = 0; c < colorOrder.length; c++) {
        var col = colorOrder[c];
        if (byColor[col] && byColor[col].length) {
            drawMarkingEdges(byColor[col], col);
        }
    }
}

function drawOverlayHighDegreeHalos(edges) {
    if (!overlayHighDegreeEnabled || !edges || edges.length === 0) return;

    var degrees = countPlayerDegrees(edges);
    var ctx = gameCanvas.ctx;
    var prevStroke = ctx.strokeStyle;
    var prevWidth = ctx.lineWidth;
    var prevDash = ctx.getLineDash();

    ctx.strokeStyle = OVERLAY_DEGREE_HALO;
    ctx.lineWidth = 3;
    ctx.setLineDash([]);

    for (var playerId in degrees) {
        if (degrees[playerId] < OVERLAY_HIGH_DEGREE_MIN) continue;
        var pos = getPlayerScreenPosition(frameNr, playerId);
        if (!pos) continue;
        gameCanvas.drawCircle(pos.x, pos.y, PLAYER_DOT_RADIUS + 5);
    }

    ctx.setLineDash(prevDash);
    ctx.strokeStyle = prevStroke;
    ctx.lineWidth = prevWidth;
}

function drawOverlayUnmarkedAttackers(edges, frame) {
    if (!overlayUnmarkedAttackersEnabled || !isBallLive(frame)) return;

    var defendingTeam = getDefendingTeam(frame);
    if (defendingTeam == null) return;

    var attackingTeam = defendingTeam === 1 ? 2 : 1;
    var attackers = getTeamPlayerPositions(frame, attackingTeam);
    if (attackers.length === 0) return;

    var degrees = countPlayerDegrees(edges || []);
    var ctx = gameCanvas.ctx;
    var prevStroke = ctx.strokeStyle;
    var prevWidth = ctx.lineWidth;
    var prevDash = ctx.getLineDash();

    ctx.strokeStyle = OVERLAY_UNMARKED_RING;
    ctx.lineWidth = 2.5;
    ctx.setLineDash([4, 3]);

    for (var i = 0; i < attackers.length; i++) {
        var attacker = attackers[i];
        var id = String(attacker.id);
        if ((degrees[id] || 0) > 0) continue;
        gameCanvas.drawCircle(attacker.x, attacker.y, PLAYER_DOT_RADIUS + 5);
    }

    ctx.setLineDash(prevDash);
    ctx.strokeStyle = prevStroke;
    ctx.lineWidth = prevWidth;
}

function drawOverlayBackground(frame) {
    drawOverlayPitchGrid();
    drawOverlayBallZones(frame);
}

function drawOverlayForeground(edges, frame) {
    drawOverlayHighDegreeHalos(edges);
    drawOverlayUnmarkedAttackers(edges, frame != null ? frame : frameNr);
}

function updateLongEdgeThresholdControls() {
    var enabled = overlayLongEdgesEnabled;
    var controls = document.getElementById("overlay_long_edge_controls");
    var input = document.getElementById("overlay_long_edge_threshold_m");
    if (controls) {
        controls.classList.toggle("pitch-control-subsection--passive", !enabled);
    }
    if (input) input.disabled = !enabled;
}

function setOverlayLongEdgeThresholdM(value) {
    if (!Number.isFinite(value)) return;
    overlayLongEdgeThresholdM = Math.min(
        OVERLAY_LONG_EDGE_MAX_M,
        Math.max(OVERLAY_LONG_EDGE_MIN_M, Math.round(value))
    );
    var label = document.getElementById("overlay_long_edge_label");
    if (label) label.textContent = String(overlayLongEdgeThresholdM);
    var input = document.getElementById("overlay_long_edge_threshold_m");
    if (input && +input.value !== overlayLongEdgeThresholdM) {
        input.value = String(overlayLongEdgeThresholdM);
    }
}

function setupOverlays() {
    var longCheckbox = document.getElementById("overlay_long_edges");
    if (longCheckbox) {
        overlayLongEdgesEnabled = longCheckbox.checked;
        longCheckbox.addEventListener("change", function () {
            overlayLongEdgesEnabled = longCheckbox.checked;
            updateLongEdgeThresholdControls();
        });
    }

    var longInput = document.getElementById("overlay_long_edge_threshold_m");
    if (longInput) {
        setOverlayLongEdgeThresholdM(+longInput.value);
        longInput.addEventListener("input", function () {
            if (!overlayLongEdgesEnabled) return;
            setOverlayLongEdgeThresholdM(+longInput.value);
        });
        longInput.addEventListener("change", function () {
            setOverlayLongEdgeThresholdM(+longInput.value);
        });
    }

    var goalCheckbox = document.getElementById("overlay_goal_side");
    if (goalCheckbox) {
        overlayGoalSideEnabled = goalCheckbox.checked;
        goalCheckbox.addEventListener("change", function () {
            overlayGoalSideEnabled = goalCheckbox.checked;
        });
    }

    var degreeCheckbox = document.getElementById("overlay_high_degree");
    if (degreeCheckbox) {
        overlayHighDegreeEnabled = degreeCheckbox.checked;
        degreeCheckbox.addEventListener("change", function () {
            overlayHighDegreeEnabled = degreeCheckbox.checked;
        });
    }

    var unmarkedCheckbox = document.getElementById("overlay_unmarked_attackers");
    if (unmarkedCheckbox) {
        overlayUnmarkedAttackersEnabled = unmarkedCheckbox.checked;
        unmarkedCheckbox.addEventListener("change", function () {
            overlayUnmarkedAttackersEnabled = unmarkedCheckbox.checked;
        });
    }

    var ballCheckbox = document.getElementById("overlay_ball_zones");
    if (ballCheckbox) {
        overlayBallZonesEnabled = ballCheckbox.checked;
        ballCheckbox.addEventListener("change", function () {
            overlayBallZonesEnabled = ballCheckbox.checked;
        });
    }

    var gridCheckbox = document.getElementById("overlay_pitch_grid");
    if (gridCheckbox) {
        overlayPitchGridEnabled = gridCheckbox.checked;
        gridCheckbox.addEventListener("change", function () {
            overlayPitchGridEnabled = gridCheckbox.checked;
        });
    }

    var arrowsCheckbox = document.getElementById("show_velocity_arrows");
    if (arrowsCheckbox && typeof setShowVelocityArrows === "function") {
        setShowVelocityArrows(arrowsCheckbox.checked);
        arrowsCheckbox.addEventListener("change", function () {
            setShowVelocityArrows(arrowsCheckbox.checked);
        });
    }

    updateLongEdgeThresholdControls();
}
