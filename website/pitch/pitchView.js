//pitchView.js handles the several drawing functions for the pitch view

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

function getCoordinates(object1, object2) { //interpolates the coordinates of the object between two frames
    if (object2 == null) object2 = object1;

    var h = +object1.h + (+object2.h - +object1.h) * frameDelta;
    var v = +object1.v + (+object2.v - +object1.v) * frameDelta;

    return [-h, v];
    //-h because the pitch is mirrored for display specifically for this game to match the camera angle
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

function getGoalkeeperH(frame, team) {
    //gets the horizontal coordinate of the goalkeeper for the given team and frame
    //used to determine the direction of the pitch (bades on where each goalie is positioned)
    var dataLine = gameData.tracking[frame];
    if (!dataLine) return null;

    var teamPlayers = team === 1 ? gameData.homeTeam.players : gameData.awayTeam.players;
    if (!teamPlayers) return null;

    var playerId = null;
    for (var i = 0; i < teamPlayers.length; i++) {
        var player = teamPlayers[i];
        if (!player.isGoalie) continue;
        var id = String(player.id);
        if (!dataLine.objects[id]) continue;
        playerId = id;
        break;
    }
    if (!playerId) return null;

    var object1 = dataLine.objects[playerId];
    var object2 = (gameData.tracking[frame + 1] ?? dataLine).objects[playerId] ?? object1;
    return getCoordinates(object1, object2)[0];
}

function getGamePoints(frame, team, options) {
    options = options || {};
    var goalkeepersOnly = options.goalkeepersOnly === true;
    var points = [];
    var dataLine = gameData.tracking[frame];
    if (!dataLine) return goalkeepersOnly ? points : [points];
    var dataLine2 = gameData.tracking[frame + 1] ?? dataLine;
    var teamIds = team === 1 ? gameData.players.team1 : gameData.players.team2;

    for (var playerId in dataLine.objects) {
        if (!teamIds.includes(String(playerId))) continue;
        var isGk = isGoalkeeperPlayer(playerId);
        if (goalkeepersOnly ? !isGk : isGk) continue;

        var object1 = dataLine.objects[playerId];
        var object2 = dataLine2.objects[playerId] ?? object1;
        var [h, v] = getCoordinates(object1, object2);
        var [x, y] = pt(h, v);
        if (goalkeepersOnly) {
            points.push([x, y, team]);
        } else {
            points.push(x, y);
        }
    }

    return goalkeepersOnly ? points : [points];
}

function drawGameSetup() {
    scaling = Math.min(
        (gameCanvas.width - 30) / gameData.pitch.length,
        (gameCanvas.height - 30) / gameData.pitch.width
    );
    pitchOffsetX = (gameCanvas.width - convertDist(gameData.pitch.length)) / 2;
    pitchOffsetY = (gameCanvas.height - convertDist(gameData.pitch.width)) / 2;
}

//-------------------------------- drawing functions --------------------------------//

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
    gameCanvas.ctx.fillStyle = ballLive === false ? "#B0B0B0" : "#575757";
    gameCanvas.drawDot(x, y, 4);
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

function getHomeAttacksRight(frame) {
    //determines if the home team is attacking from the right side of the pitch
    //based on the position of the goalkeepers at the start of the period
    var periodIndex = gameData.tracking[frame].period - 1;
    var startFrame =
        gameData.periods && gameData.periods.length > 0
            ? gameData.periods[periodIndex].startFrame
            : 0;

    var savedDelta = frameDelta;
    frameDelta = 0;
    var homeH = getGoalkeeperH(startFrame, 1);
    var awayH = getGoalkeeperH(startFrame, 2);
    frameDelta = savedDelta;

    if (homeH != null && awayH != null && homeH !== awayH) {
        return awayH < homeH;
    }
    return true;
}

function getPitchDirectionHtml(frame) {
    var periodIndex = gameData.tracking[frame].period - 1;
    if (pitchDirectionCache[periodIndex] != null) {
        return pitchDirectionCache[periodIndex];
    }

    var savedDelta = frameDelta;
    frameDelta = 0;
    var homeAttacksRight = getHomeAttacksRight(frame);
    frameDelta = savedDelta;

    var homeColor = gameData.homeTeam.colorShirt || "#B73B92";
    var awayColor = gameData.awayTeam.colorShirt || "#3395AB";
    var homeName = gameData.homeTeam.name || "Home";
    var awayName = gameData.awayTeam.name || "Away";

    var leftLabel = homeAttacksRight
        ? dirLabel(homeName, homeColor, true)
        : dirLabel(awayName, awayColor, true);
    var rightLabel = homeAttacksRight
        ? dirLabel(awayName, awayColor, false)
        : dirLabel(homeName, homeColor, false);

    pitchDirectionCache[periodIndex] =
        '<div class="pitch-direction-inner">' +
        '<span class="pitch-dir-side pitch-dir-side--left">' + leftLabel + "</span>" +
        '<span class="pitch-dir-side pitch-dir-side--right">' + rightLabel + "</span>" +
        "</div>";

    return pitchDirectionCache[periodIndex];
}

function updatePitchDirectionBars(frame) {
    if (gameData == null) return;

    var html = getPitchDirectionHtml(frame);
    if (html === lastPitchDirectionHtml) return;

    lastPitchDirectionHtml = html;
    var pitchCount = canvasLayout.pitchCount;
    for (var i = 1; i <= pitchCount; i++) {
        var element = document.getElementById("pitch_direction_" + i);
        if (element) element.innerHTML = html;
    }
}
