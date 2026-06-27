const XT_GRID_PATH = "../xtGrid.json";

var xtGridMeta = null;
var xtLookup = null;
var xtMaxValue = 0;
var xtGridLoadPromise = null;

function isXtGridReady() {
    return xtLookup != null && xtGridMeta != null;
}

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

function getPeriodStartFrame(frame) {
    var period = getPeriod(frame);
    if (gameData.periods && gameData.periods.length > 0) {
        return gameData.periods[period].startFrame;
    }
    return 0;
}

function getGoalkeeperHAtPeriodStart(frame, team) {
    var savedDelta = frameDelta;
    frameDelta = 0;
    var goalH = getGoalkeeperH(getPeriodStartFrame(frame), team);
    frameDelta = savedDelta;
    return goalH;
}

function getAttackingTeamOwnGoalH(frame) {
    var attackingTeam = getAttackingTeam(frame);
    if (attackingTeam == null) return null;
    return getGoalkeeperHAtPeriodStart(frame, attackingTeam);
}

function getAttackingTeamOpponentGoalH(frame) {
    var defendingTeam = getDefendingTeam(frame);
    if (defendingTeam == null) return null;
    return getGoalkeeperHAtPeriodStart(frame, defendingTeam);
}

function getGridCellLength() {
    return gameData.pitch.length / xtGridMeta.gridX;
}

function getGridCellWidth() {
    return gameData.pitch.width / xtGridMeta.gridY;
}

// zoneX 0 = attacking team's own goal end, zoneX (gridX-1) = opponent goal end.
function pitchHToZoneX(h, frame) {
    var ownGoalH = getAttackingTeamOwnGoalH(frame);
    var oppGoalH = getAttackingTeamOpponentGoalH(frame);
    if (ownGoalH == null || oppGoalH == null) return 0;

    var cellLen = getGridCellLength();
    var distFromOwnGoal =
        ownGoalH > oppGoalH ? ownGoalH - h : h - ownGoalH;

    var zoneX = Math.floor(distFromOwnGoal / cellLen);
    if (zoneX < 0) zoneX = 0;
    if (zoneX >= xtGridMeta.gridX) zoneX = xtGridMeta.gridX - 1;

    return zoneX;
}

function pitchVToZoneY(v) {
    var hw = gameData.pitch.width / 2;
    var cellW = getGridCellWidth();
    var zoneY = Math.floor((v + hw) / cellW);

    if (zoneY < 0) zoneY = 0;
    if (zoneY >= xtGridMeta.gridY) zoneY = xtGridMeta.gridY - 1;

    return zoneY;
}

function getXtAtPitchPos(h, v, frame) {
    if (!isXtGridReady()) return null;
    if (getAttackingTeam(frame) == null) return null;

    var zoneX = pitchHToZoneX(h, frame);
    var zoneY = pitchVToZoneY(v);
    var value = xtLookup[zoneX][zoneY];

    return value != null ? value : 0;
}

function getProjectedPitchPos(player, seconds) {
    var move = getMovementVector(player);
    return {
        h: player.h + move.h * seconds,
        v: player.v + move.v * seconds,
    };
}

function getXtGainAlongMovement(player, frame, seconds) {
    if (!isXtGridReady()) return 0;
    if (getAttackingTeam(frame) == null) return 0;

    var xtNow = getXtAtPitchPos(player.h, player.v, frame);
    if (xtNow == null) return 0;

    var projected = getProjectedPitchPos(player, seconds);
    var xtAhead = getXtAtPitchPos(projected.h, projected.v, frame);
    if (xtAhead == null) return 0;

    return xtAhead - xtNow;
}

function isHighThreatXt(xt) {
    if (xt == null) return false;
    return xt >= BEHAVIOR_THRESHOLDS.minThreatXt;
}

function isHighThreatPitchPos(h, v, frame) {
    return isHighThreatXt(getXtAtPitchPos(h, v, frame));
}
