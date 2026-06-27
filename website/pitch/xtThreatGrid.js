const XT_GRID_PATH = "../xtGrid.json";
const XT_GRID_FILL_ALPHA = 0.42;
const XT_GRID_LINE_COLOR = "rgba(255, 255, 255, 0.25)";
const XT_GRID_LINE_WIDTH = 0.5;

var showXtThreatGrid = true;
var xtGridMeta = null;
var xtLookup = null;
var xtMaxValue = 0;
var xtGridLoadPromise = null;

function loadXtGrid() {
    if (xtGridLoadPromise != null) return xtGridLoadPromise;

    xtGridLoadPromise = fetch(XT_GRID_PATH)
        .then(function (response) {
            if (!response.ok) {
                throw new Error("Failed to load xT grid (" + response.status + ")");
            }
            return response.json();
        })
        .then(function (data) {
            buildXtLookup(data);
            return data;
        })
        .catch(function (err) {
            console.warn("xT grid load failed:", err.message);
            xtGridLoadPromise = null;
            return null;
        });

    return xtGridLoadPromise;
}

function buildXtLookup(data) {
    xtGridMeta = {
        pitchLength: data.pitchLength,
        pitchWidth: data.pitchWidth,
        gridX: data.gridX,
        gridY: data.gridY,
    };

    xtLookup = [];
    xtMaxValue = 0;

    for (var x = 0; x < data.gridX; x++) {
        xtLookup[x] = [];
    }

    for (var i = 0; i < data.cells.length; i++) {
        var cell = data.cells[i];
        if (cell.xt == null) continue;

        xtLookup[cell.zoneX][cell.zoneY] = cell.xt;
        if (cell.xt > xtMaxValue) {
            xtMaxValue = cell.xt;
        }
    }
}

function getHomeAttacksRight(frame) {
    var period = getPeriod(frame);
    var startFrame =
        gameData.periods && gameData.periods.length > 0
            ? gameData.periods[period].startFrame
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

function attackingTeamAttacksTowardNegativeH(frame) {
    var team = getAttackingTeam(frame);
    if (team == null) return true;

    var homeAttacksRight = getHomeAttacksRight(frame);
    return team === 1 ? homeAttacksRight : !homeAttacksRight;
}

function pitchHToZoneX(h, frame) {
    var hl = gameData.pitch.length / 2;
    var cellLen = gameData.pitch.length / xtGridMeta.gridX;
    var attacksTowardNegativeH = attackingTeamAttacksTowardNegativeH(frame);

    var zoneX = attacksTowardNegativeH
        ? Math.floor((hl - h) / cellLen)
        : Math.floor((h + hl) / cellLen);

    if (zoneX < 0) zoneX = 0;
    if (zoneX >= xtGridMeta.gridX) zoneX = xtGridMeta.gridX - 1;

    return zoneX;
}

function pitchVToZoneY(v) {
    var hw = gameData.pitch.width / 2;
    var cellW = gameData.pitch.width / xtGridMeta.gridY;

    var zoneY = Math.floor((v + hw) / cellW);

    if (zoneY < 0) zoneY = 0;
    if (zoneY >= xtGridMeta.gridY) zoneY = xtGridMeta.gridY - 1;

    return zoneY;
}

function getXtAtPitchPos(h, v, frame) {
    if (xtLookup == null || xtGridMeta == null) return null;

    var zoneX = pitchHToZoneX(h, frame);
    var zoneY = pitchVToZoneY(v);
    var value = xtLookup[zoneX][zoneY];

    return value != null ? value : 0;
}

function getZonePitchBounds(zoneX, zoneY, frame) {
    var hl = gameData.pitch.length / 2;
    var hw = gameData.pitch.width / 2;
    var cellLen = gameData.pitch.length / xtGridMeta.gridX;
    var cellW = gameData.pitch.width / xtGridMeta.gridY;
    var attacksTowardNegativeH = attackingTeamAttacksTowardNegativeH(frame);

    var hLow;
    var hHigh;

    if (attacksTowardNegativeH) {
        hHigh = hl - zoneX * cellLen;
        hLow = hl - (zoneX + 1) * cellLen;
    } else {
        hLow = -hl + zoneX * cellLen;
        hHigh = -hl + (zoneX + 1) * cellLen;
    }

    var vLow = -hw + zoneY * cellW;
    var vHigh = -hw + (zoneY + 1) * cellW;

    return { hLow: hLow, hHigh: hHigh, vLow: vLow, vHigh: vHigh };
}

function xtToFillColor(xt) {
    if (xtMaxValue <= 0) return "rgba(240, 249, 232, " + XT_GRID_FILL_ALPHA + ")";

    var t = xt / xtMaxValue;
    if (t < 0) t = 0;
    if (t > 1) t = 1;

    var r = Math.round(254 * t + 240 * (1 - t));
    var g = Math.round(226 * (1 - t) + 59 * t);
    var b = Math.round(226 * (1 - t) + 48 * t);

    return "rgba(" + r + ", " + g + ", " + b + ", " + XT_GRID_FILL_ALPHA + ")";
}

function drawXtThreatGrid(frame) {
    if (!showXtThreatGrid || xtLookup == null || xtGridMeta == null) return;
    if (!isBallLive(frame)) return;

    var attackingTeam = getAttackingTeam(frame);
    if (attackingTeam == null) return;

    var ctx = gameCanvas.ctx;

    ctx.save();

    for (var zoneX = 0; zoneX < xtGridMeta.gridX; zoneX++) {
        for (var zoneY = 0; zoneY < xtGridMeta.gridY; zoneY++) {
            var xt = xtLookup[zoneX][zoneY];
            if (xt == null) continue;

            var bounds = getZonePitchBounds(zoneX, zoneY, frame);
            var topLeft = pt(bounds.hHigh, bounds.vLow);
            var bottomRight = pt(bounds.hLow, bounds.vHigh);

            var x = Math.min(topLeft[0], bottomRight[0]);
            var y = Math.min(topLeft[1], bottomRight[1]);
            var w = Math.abs(bottomRight[0] - topLeft[0]);
            var h = Math.abs(bottomRight[1] - topLeft[1]);

            ctx.fillStyle = xtToFillColor(xt);
            ctx.fillRect(x, y, w, h);
        }
    }

    ctx.strokeStyle = XT_GRID_LINE_COLOR;
    ctx.lineWidth = XT_GRID_LINE_WIDTH;

    var hl = gameData.pitch.length / 2;
    var hw = gameData.pitch.width / 2;
    var cellLen = gameData.pitch.length / xtGridMeta.gridX;
    var cellW = gameData.pitch.width / xtGridMeta.gridY;
    var attacksTowardNegativeH = attackingTeamAttacksTowardNegativeH(frame);

    for (var gx = 0; gx <= xtGridMeta.gridX; gx++) {
        var hLine = attacksTowardNegativeH
            ? hl - gx * cellLen
            : -hl + gx * cellLen;
        pitchLine(hLine, -hw, hLine, hw);
    }

    for (var gy = 0; gy <= xtGridMeta.gridY; gy++) {
        var vLine = -hw + gy * cellW;
        pitchLine(-hl, vLine, hl, vLine);
    }

    ctx.restore();
}

function setupXtThreatGrid() {
    loadXtGrid();

    var checkbox = document.getElementById("xt_threat_grid_toggle");
    if (!checkbox) return;

    showXtThreatGrid = checkbox.checked;

    checkbox.addEventListener("change", function () {
        showXtThreatGrid = checkbox.checked;
    });
}
