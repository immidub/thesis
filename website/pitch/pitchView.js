var scaling = 6;
var pitchOffsetX = -1;
var pitchOffsetY = -1;

// Landscape pitch; h (length) left-right, v (width) top-bottom, both axes mirrored for display.
function pt(h, v) {
    var halfLength = gameData.pitch.length / 2;
    var halfWidth = gameData.pitch.width / 2;
    return [
        pitchOffsetX + (halfLength - h) * scaling,
        pitchOffsetY + (halfWidth - v) * scaling,
    ];
}

function convertDist(d) {
    return d * scaling;
}

function getCoordinates(object1, object2) {
    if (object2 == null) object2 = object1;

    var h = +object1.h + (+object2.h - +object1.h) * frameDelta;
    var v = +object1.v + (+object2.v - +object1.v) * frameDelta;

    return [-h, v];
}

function isBallTracked(frame) {
    var dataLine = gameData.tracking[frame];
    if (!dataLine || !dataLine.objects) return false;
    return gameData.ballId in dataLine.objects;
}

function isBallLive(frame) {
    if (!isBallTracked(frame)) return false;
    var live = gameData.tracking[frame].live;
    return live !== false;
}

function getPossessionTeam(frame) {
    if (!isBallLive(frame)) return null;

    var possession = gameData.tracking[frame].possession;
    if (possession === "home") return 1;
    if (possession === "away") return 2;
    return null;
}

function getDefendingTeam(frame) {
    var possessionTeam = getPossessionTeam(frame);
    if (possessionTeam == null) return null;
    return possessionTeam === 1 ? 2 : 1;
}

function getAttackingTeam(frame) {
    return getPossessionTeam(frame);
}

function getGoalkeeperId(team, frame) {
    var teamPlayers = team === 1 ? gameData.homeTeam.players : gameData.awayTeam.players;
    if (!teamPlayers) return null;

    var dataLine = frame != null && gameData.tracking[frame] ? gameData.tracking[frame] : null;
    for (var i = 0; i < teamPlayers.length; i++) {
        var player = teamPlayers[i];
        if (!player.isGoalie) continue;
        var playerId = String(player.id);
        if (dataLine != null && !dataLine.objects[playerId]) continue;
        return playerId;
    }
    return null;
}

function getGoalkeeperH(frame, team) {
    var dataLine = gameData.tracking[frame];
    if (!dataLine) return null;

    var playerId = getGoalkeeperId(team, frame);
    if (!playerId) return null;

    var object1 = dataLine.objects[playerId];
    if (!object1) return null;

    var object2 = (gameData.tracking[frame + 1] ?? dataLine).objects[playerId] ?? object1;
    return getCoordinates(object1, object2)[0];
}

function getGoalKeepers(frame) {
    var points = [];
    var dataLine = gameData.tracking[frame];
    var dataLine2 = gameData.tracking[frame + 1];

    for (var playerId in dataLine.objects) {
        if (!isGoalkeeperPlayer(playerId)) continue;

        var object1 = dataLine.objects[playerId];
        var object2 = dataLine2.objects[playerId] ?? object1;
        var [h, v] = getCoordinates(object1, object2);
        var [x, y] = pt(h, v);
        points.push([x, y, gameData.players.team1.includes(String(playerId)) ? 1 : 2]);
    }

    return points;
}

function getGamePoints(frame, team) {
    var points = [];
    var dataLine = gameData.tracking[frame];
    var dataLine2 = gameData.tracking[frame + 1];
    var teamIds = team === 1 ? gameData.players.team1 : gameData.players.team2;

    for (var playerId in dataLine.objects) {
        if (!teamIds.includes(String(playerId))) continue;
        if (isGoalkeeperPlayer(playerId)) continue;

        var object1 = dataLine.objects[playerId];
        var object2 = dataLine2.objects[playerId] ?? object1;
        var [h, v] = getCoordinates(object1, object2);
        var [x, y] = pt(h, v);
        points.push(x, y);
    }

    return [points];
}

function drawGameSetup() {
    scaling = Math.min(
        (gameCanvas.width - 30) / gameData.pitch.length,
        (gameCanvas.height - 30) / gameData.pitch.width
    );
    pitchOffsetX = (gameCanvas.width - convertDist(gameData.pitch.length)) / 2;
    pitchOffsetY = (gameCanvas.height - convertDist(gameData.pitch.width)) / 2;
}

function drawPlayerLabels(frame) {
    var dataLine = gameData.tracking[frame];
    var dataLine2 = gameData.tracking[frame + 1];

    for (var playerId in dataLine.objects) {
        if (playerId === gameData.ballId) continue;

        var isHome = gameData.players.team1.includes(String(playerId));
        var isAway = gameData.players.team2.includes(String(playerId));
        if (!isHome && !isAway) continue;

        var object1 = dataLine.objects[playerId];
        var object2 = dataLine2.objects[playerId] ?? object1;
        var [h, v] = getCoordinates(object1, object2);
        var [x, y] = pt(h, v);

        if (isGoalkeeperPlayer(playerId)) {
            gameCanvas.ctx.fillStyle = "#FFF";
        } else {
            gameCanvas.ctx.fillStyle = isHome ? gameData.homeTeam.colorNumber : gameData.awayTeam.colorNumber;
        }

        gameCanvas.fillTextCenter(getShirtNumberLabel(playerId), x, y + 3);
    }
}

function drawBall(frame, ballLive) {
    var dataLine = gameData.tracking[frame];
    var object1 = dataLine.objects[gameData.ballId];
    if (!object1) return;

    var object2 = (gameData.tracking[frame + 1] ?? dataLine).objects[gameData.ballId] ?? object1;
    var [h, v] = getCoordinates(object1, object2);
    var [x, y] = pt(h, v);
    var ballColor = ballLive === false ? "#B0B0B0" : "#575757";

    gameCanvas.ctx.fillStyle = ballColor;
    gameCanvas.drawDot(x, y, 4);
    drawBallMovementArrow(h, v, x, y, object1, ballColor);
}

const MOVEMENT_ARROW_PREVIEW_SECONDS = 0.5;

const BALL_MOVEMENT_ARROW_MIN_METERS = 3;
const BALL_MOVEMENT_ARROW_MAX_METERS = 20;

const PLAYER_MOVEMENT_ARROW_MIN_METERS = 1;
const PLAYER_MOVEMENT_ARROW_MAX_METERS = 10;
const PLAYER_MOVEMENT_ARROW_MIN_SPEED = 0.5;

function getMovementArrowLengthMeters(speed, minMeters, maxMeters) {
    if (speed == null || speed <= 0) return minMeters;

    var length = speed * MOVEMENT_ARROW_PREVIEW_SECONDS;
    if (length < minMeters) return minMeters;
    if (length > maxMeters) return maxMeters;
    return length;
}

function drawObjectMovementArrow(
    pitchH,
    pitchV,
    canvasX,
    canvasY,
    object,
    color,
    minMeters,
    maxMeters,
    headMeters,
    minSpeed
) {
    if (object.direction == null) return;
    if (minSpeed != null && object.speed != null && object.speed < minSpeed) return;

    var unit = directionToUnitVector(object.direction);
    var lengthMeters = getMovementArrowLengthMeters(object.speed, minMeters, maxMeters);
    var endPitchH = pitchH + unit.h * lengthMeters;
    var endPitchV = pitchV + unit.v * lengthMeters;
    var endCanvas = pt(endPitchH, endPitchV);

    var prevStroke = gameCanvas.ctx.strokeStyle;
    var prevWidth = gameCanvas.ctx.lineWidth;

    gameCanvas.ctx.strokeStyle = color;
    gameCanvas.ctx.lineWidth = 2;
    gameCanvas.drawArrow(canvasX, canvasY, endCanvas[0], endCanvas[1], convertDist(headMeters));
    gameCanvas.ctx.strokeStyle = prevStroke;
    gameCanvas.ctx.lineWidth = prevWidth;
}

function drawBallMovementArrow(pitchH, pitchV, canvasX, canvasY, ballObject, color) {
    drawObjectMovementArrow(
        pitchH,
        pitchV,
        canvasX,
        canvasY,
        ballObject,
        color,
        BALL_MOVEMENT_ARROW_MIN_METERS,
        BALL_MOVEMENT_ARROW_MAX_METERS,
        0.9,
        null
    );
}

function drawPlayerMovementArrows(frame) {
    var dataLine = gameData.tracking[frame];
    if (!dataLine || !dataLine.objects) return;

    var dataLine2 = gameData.tracking[frame + 1] ?? dataLine;

    for (var playerId in dataLine.objects) {
        if (playerId === gameData.ballId) continue;

        var isHome = gameData.players.team1.includes(String(playerId));
        var isAway = gameData.players.team2.includes(String(playerId));
        if (!isHome && !isAway) continue;

        var object1 = dataLine.objects[playerId];
        var object2 = dataLine2.objects[playerId] ?? object1;
        var coords = getCoordinates(object1, object2);
        var canvas = pt(coords[0], coords[1]);
        var color;

        if (isGoalkeeperPlayer(playerId)) {
            color = "#575757";
        } else if (isHome) {
            color = gameData.homeTeam.colorShirt;
        } else {
            color = gameData.awayTeam.colorShirt;
        }

        drawObjectMovementArrow(
            coords[0],
            coords[1],
            canvas[0],
            canvas[1],
            object1,
            color,
            PLAYER_MOVEMENT_ARROW_MIN_METERS,
            PLAYER_MOVEMENT_ARROW_MAX_METERS,
            0.6,
            PLAYER_MOVEMENT_ARROW_MIN_SPEED
        );
    }
}

function pitchLine(h1, v1, h2, v2) {
    var a = pt(h1, v1);
    var b = pt(h2, v2);
    gameCanvas.drawLine(a[0], a[1], b[0], b[1]);
}

const PENALTY_ARC_HALF_ANGLE = Math.acos(5.5 / 9.15);

function drawPitch() {
    gameCanvas.ctx.lineWidth = 1;
    gameCanvas.ctx.strokeStyle = "#8C8C8C";
    gameCanvas.ctx.fillStyle = "#8C8C8C";

    var hw = gameData.pitch.width / 2;
    var hl = gameData.pitch.length / 2;

    pitchLine(-hl, -hw, hl, -hw);
    pitchLine(-hl, hw, hl, hw);
    pitchLine(-hl, -hw, -hl, hw);
    pitchLine(hl, -hw, hl, hw);
    pitchLine(0, -hw, 0, hw);
    pitchLine(-hl, -3.66, -hl, 3.66);
    pitchLine(hl, -3.66, hl, 3.66);

    drawGoalArea(-hl, 1);
    drawGoalArea(hl, -1);

    var center = pt(0, 0);
    gameCanvas.drawCircle(center[0], center[1], convertDist(9.15));
    gameCanvas.drawDot(center[0], center[1], 2);

    var leftSpot = pt(-hl + 11, 0);
    var rightSpot = pt(hl - 11, 0);
    gameCanvas.drawDot(leftSpot[0], leftSpot[1], 2);
    gameCanvas.drawDot(rightSpot[0], rightSpot[1], 2);

    drawPenaltyArc(-hl + 11, -1);
    drawPenaltyArc(hl - 11, 1);
}

function drawGoalArea(goalH, dir) {
    var boxH = goalH + dir * 5.5;
    var penH = goalH + dir * 16.5;

    pitchLine(boxH, -9.16, boxH, 9.16);
    pitchLine(goalH, -9.16, boxH, -9.16);
    pitchLine(goalH, 9.16, boxH, 9.16);
    pitchLine(penH, -20.16, penH, 20.16);
    pitchLine(goalH, -20.16, penH, -20.16);
    pitchLine(goalH, 20.16, penH, 20.16);
}

function drawPenaltyArc(spotH, dir) {
    var spot = pt(spotH, 0);
    var radius = convertDist(9.15);
    var centerAngle = dir > 0 ? 0 : Math.PI;
    var start = centerAngle - PENALTY_ARC_HALF_ANGLE;
    var end = centerAngle + PENALTY_ARC_HALF_ANGLE;

    gameCanvas.ctx.beginPath();
    gameCanvas.ctx.arc(spot[0], spot[1], radius, start, end);
    gameCanvas.ctx.stroke();
}

var pitchDirectionCache = {};
var lastPitchDirectionHtml = null;

function resetPitchDirectionCache() {
    pitchDirectionCache = {};
    lastPitchDirectionHtml = null;
}

function dirLabel(name, color, attacksRight) {
    var text = attacksRight ? name + " →" : "← " + name;
    return '<span class="pitch-dir-team" style="color:' + color + '">' + text + "</span>";
}

function getPitchDirectionHtml(frame) {
    var period = getPeriod(frame);
    if (pitchDirectionCache[period] != null) {
        return pitchDirectionCache[period];
    }

    var startFrame =
        gameData.periods && gameData.periods.length > 0
            ? gameData.periods[period].startFrame
            : 0;

    var savedDelta = frameDelta;
    frameDelta = 0;
    var homeH = getGoalkeeperH(startFrame, 1);
    var awayH = getGoalkeeperH(startFrame, 2);
    frameDelta = savedDelta;

    var homeColor = gameData.homeTeam.colorShirt || "#B73B92";
    var awayColor = gameData.awayTeam.colorShirt || "#3395AB";
    var homeName = gameData.homeTeam.name || "Home";
    var awayName = gameData.awayTeam.name || "Away";
    var homeAttacksRight;
    if (homeH != null && awayH != null && homeH !== awayH) {
        homeAttacksRight = awayH < homeH;
    } else {
        homeAttacksRight = true;
    }

    var leftLabel = homeAttacksRight
        ? dirLabel(homeName, homeColor, true)
        : dirLabel(awayName, awayColor, true);
    var rightLabel = homeAttacksRight
        ? dirLabel(awayName, awayColor, false)
        : dirLabel(homeName, homeColor, false);

    pitchDirectionCache[period] =
        '<div class="pitch-direction-inner">' +
        '<span class="pitch-dir-side pitch-dir-side--left">' + leftLabel + "</span>" +
        '<span class="pitch-dir-side pitch-dir-side--right">' + rightLabel + "</span>" +
        "</div>";

    return pitchDirectionCache[period];
}

function updatePitchDirectionBars(frame) {
    if (gameData == null) return;

    var html = getPitchDirectionHtml(frame);
    if (html === lastPitchDirectionHtml) return;

    lastPitchDirectionHtml = html;
    for (var i = 1; i <= PITCH_COUNT; i++) {
        var element = document.getElementById("pitch_direction_" + i);
        if (element) element.innerHTML = html;
    }
}
