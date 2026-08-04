// Space-control zone overlay for the Responsibility Viewer (option A).
// Sidecar: header + {frame, collective:[cellIdx...] marking bubble,
//          defenders:{id:[cellIdx...]} defender pitch-control outside bubble}.

var responsibilityZonesEnabled = true;
var responsibilityZonesHeader = null;
var responsibilityZonesByFrame = {};
var responsibilityZonesFrameList = [];
// Sticky color index per defender id (stable across frames; only changes on neighbor conflict).
var responsibilityZoneColorByPlayer = {};
var selectedSpaceZonePlayerId = null;

const SPACE_ZONE_COLLECTIVE_FILL = "rgba(37, 99, 235, 0.22)";
const SPACE_ZONE_SELECTED_OUTLINE = "#111827";
const SPACE_ZONE_SELECTED_PLAYER_BORDER = "#111827";
const SPACE_ZONE_SELECTED_PLAYER_BORDER_WIDTH = 4;
// Distinct categorical colors (not near-identical greens).
const SPACE_ZONE_DEFENDER_PALETTE = [
    { fill: "rgba(220, 38, 38, 0.38)", stroke: "#991B1B" },   // red
    { fill: "rgba(234, 88, 12, 0.38)", stroke: "#9A3412" },   // orange
    { fill: "rgba(202, 138, 4, 0.40)", stroke: "#854D0E" },   // yellow
    { fill: "rgba(22, 163, 74, 0.38)", stroke: "#166534" },   // green
    { fill: "rgba(13, 148, 136, 0.38)", stroke: "#115E59" },  // teal
    { fill: "rgba(2, 132, 199, 0.38)", stroke: "#075985" },   // sky
    { fill: "rgba(79, 70, 229, 0.38)", stroke: "#3730A3" },   // indigo
    { fill: "rgba(147, 51, 234, 0.38)", stroke: "#6B21A8" },  // purple
    { fill: "rgba(219, 39, 119, 0.38)", stroke: "#9D174D" },  // pink
    { fill: "rgba(100, 116, 139, 0.40)", stroke: "#334155" }, // slate
    { fill: "rgba(180, 83, 9, 0.38)", stroke: "#78350F" },    // amber-brown
];

function setResponsibilityZonesEnabled(on) {
    responsibilityZonesEnabled = on !== false;
    if (!responsibilityZonesEnabled) selectedSpaceZonePlayerId = null;
}

function clearResponsibilityZones() {
    responsibilityZonesHeader = null;
    responsibilityZonesByFrame = {};
    responsibilityZonesFrameList = [];
    responsibilityZoneColorByPlayer = {};
    selectedSpaceZonePlayerId = null;
}

function ingestResponsibilityZonesLine(line) {
    if (!line) return;
    var obj = JSON.parse(line);
    if (obj.type === "header" || obj.type === "mesh") {
        if (!responsibilityZonesHeader) responsibilityZonesHeader = obj;
        else {
            for (var k in obj) {
                if (obj.hasOwnProperty(k)) responsibilityZonesHeader[k] = obj[k];
            }
        }
        return;
    }
    if (obj.frame == null) return;
    responsibilityZonesByFrame[obj.frame] = obj;
    responsibilityZonesFrameList.push(obj.frame);
}

async function tryLoadLocalResponsibilityZones() {
    try {
        if (typeof setResponsibilityLoadingSubtitle === "function") {
            setResponsibilityLoadingSubtitle("Loading responsibility_zones.jsonl...");
        }
        var response = await fetch(getLocalDataDir() + "/responsibility_zones.jsonl");
        if (!response.ok) {
            console.warn("responsibility_zones.jsonl not found (" + response.status + ")");
            return false;
        }
        clearResponsibilityZones();
        await streamJsonlResponse(response, ingestResponsibilityZonesLine, function (n) {
            if (typeof setResponsibilityLoadingSubtitle === "function") {
                setResponsibilityLoadingSubtitle("Loading responsibility_zones.jsonl... " + n + " frames");
            }
        });
        responsibilityZonesFrameList.sort(function (a, b) { return a - b; });
        var ok = responsibilityZonesFrameList.length > 0 && !!responsibilityZonesHeader;
        console.info(
            "Loaded responsibility zones:",
            responsibilityZonesFrameList.length,
            "frames",
            "header.shape=",
            responsibilityZonesHeader && responsibilityZonesHeader.shape
        );
        if (!ok) {
            console.warn("Zones file loaded but contained no usable frames/header.");
        }
        return ok;
    } catch (err) {
        console.error("Failed to load responsibility_zones.jsonl:", err);
        clearResponsibilityZones();
        return false;
    }
}

function getHeldResponsibilityZoneFrame(frame) {
    if (responsibilityZonesByFrame[frame]) return frame;
    var list = responsibilityZonesFrameList;
    if (!list || list.length === 0) return null;
    var best = null;
    for (var i = 0; i < list.length; i++) {
        if (list[i] <= frame) best = list[i];
        else break;
    }
    return best;
}

function meshCellBounds(header, cellIndex) {
    var shape = header.shape;
    if (!shape || shape.length !== 2) return null;
    var rows = shape[0];
    var cols = shape[1];
    var row = Math.floor(cellIndex / cols);
    var col = cellIndex % cols;
    if (row < 0 || row >= rows || col < 0 || col >= cols) return null;

    var dx = header.dx != null ? header.dx : ((header.xlim[1] - header.xlim[0]) / cols);
    var dy = header.dy != null ? header.dy : ((header.ylim[1] - header.ylim[0]) / rows);
    var xCenter = header.x0 != null ? header.x0 + col * dx : (header.xlim[0] + (col + 0.5) * dx);
    var yCenter = header.y0 != null ? header.y0 + row * dy : (header.ylim[0] + (row + 0.5) * dy);
    return {
        row: row,
        col: col,
        x0: xCenter - dx / 2,
        x1: xCenter + dx / 2,
        y0: yCenter - dy / 2,
        y1: yCenter + dy / 2,
    };
}

function fillPitchCell(bounds) {
    // Tracking (x,y) → viewer getCoordinates space (-x, y) → canvas via pt.
    var a = pt(-bounds.x0, bounds.y0);
    var b = pt(-bounds.x1, bounds.y0);
    var c = pt(-bounds.x1, bounds.y1);
    var d = pt(-bounds.x0, bounds.y1);
    var ctx = gameCanvas.ctx;
    ctx.beginPath();
    ctx.moveTo(a[0], a[1]);
    ctx.lineTo(b[0], b[1]);
    ctx.lineTo(c[0], c[1]);
    ctx.lineTo(d[0], d[1]);
    ctx.closePath();
    ctx.fill();
}

function strokePitchSegment(x0, y0, x1, y1) {
    var p0 = pt(-x0, y0);
    var p1 = pt(-x1, y1);
    gameCanvas.drawLine(p0[0], p0[1], p1[0], p1[1]);
}

function cellKey(row, col) {
    return row + ":" + col;
}

function buildCellSet(cells, header) {
    var set = {};
    var boundsByKey = {};
    for (var i = 0; i < cells.length; i++) {
        var b = meshCellBounds(header, cells[i]);
        if (!b) continue;
        var key = cellKey(b.row, b.col);
        set[key] = true;
        boundsByKey[key] = b;
    }
    return { set: set, boundsByKey: boundsByKey };
}

function edgeKey(x0, y0, x1, y1) {
    var ax = Math.round(x0 * 1000);
    var ay = Math.round(y0 * 1000);
    var bx = Math.round(x1 * 1000);
    var by = Math.round(y1 * 1000);
    if (ax < bx || (ax === bx && ay <= by)) {
        return ax + "," + ay + "," + bx + "," + by;
    }
    return bx + "," + by + "," + ax + "," + ay;
}

function drawSelectedZoneOutline(cells, header, strokeColor) {
    if (!cells || !cells.length) return;
    var cellInfo = buildCellSet(cells, header);
    var ctx = gameCanvas.ctx;
    var prevStroke = ctx.strokeStyle;
    var prevWidth = ctx.lineWidth;
    ctx.strokeStyle = strokeColor || "#111827";
    ctx.lineWidth = 2.75;

    var set = cellInfo.set;
    var boundsByKey = cellInfo.boundsByKey;
    var drawn = {};

    function maybeStroke(x0, y0, x1, y1) {
        var key = edgeKey(x0, y0, x1, y1);
        if (drawn[key]) return;
        drawn[key] = true;
        strokePitchSegment(x0, y0, x1, y1);
    }

    // y0 toward row-1, y1 toward row+1; x0 toward col-1, x1 toward col+1.
    for (var key in boundsByKey) {
        if (!boundsByKey.hasOwnProperty(key)) continue;
        var b = boundsByKey[key];
        if (!set[cellKey(b.row - 1, b.col)]) maybeStroke(b.x0, b.y0, b.x1, b.y0);
        if (!set[cellKey(b.row + 1, b.col)]) maybeStroke(b.x0, b.y1, b.x1, b.y1);
        if (!set[cellKey(b.row, b.col - 1)]) maybeStroke(b.x0, b.y0, b.x0, b.y1);
        if (!set[cellKey(b.row, b.col + 1)]) maybeStroke(b.x1, b.y0, b.x1, b.y1);
    }

    ctx.strokeStyle = prevStroke;
    ctx.lineWidth = prevWidth;
}

function buildDefenderZoneAdjacency(defenders, header) {
    var shape = header.shape;
    var rows = shape[0];
    var cols = shape[1];
    var owner = {};
    var playerIds = [];

    for (var playerId in defenders) {
        if (!defenders.hasOwnProperty(playerId)) continue;
        var cells = defenders[playerId];
        if (!cells || !cells.length) continue;
        playerIds.push(String(playerId));
        for (var i = 0; i < cells.length; i++) {
            owner[cells[i]] = String(playerId);
        }
    }

    var adj = {};
    for (var p = 0; p < playerIds.length; p++) {
        adj[playerIds[p]] = {};
    }

    function link(a, b) {
        if (!a || !b || a === b) return;
        adj[a][b] = true;
        adj[b][a] = true;
    }

    for (var cellIdx in owner) {
        if (!owner.hasOwnProperty(cellIdx)) continue;
        var idx = +cellIdx;
        var row = Math.floor(idx / cols);
        var col = idx % cols;
        var id = owner[idx];
        if (col + 1 < cols) link(id, owner[idx + 1]);
        if (row + 1 < rows) link(id, owner[idx + cols]);
    }

    return { playerIds: playerIds, adj: adj };
}

function preferredDefenderColorIndex(playerId) {
    var id = String(playerId);
    var hash = 0;
    for (var i = 0; i < id.length; i++) {
        hash = ((hash << 5) - hash) + id.charCodeAt(i);
        hash |= 0;
    }
    return Math.abs(hash) % SPACE_ZONE_DEFENDER_PALETTE.length;
}

function colorDefenderZones(defenders, header) {
    var graph = buildDefenderZoneAdjacency(defenders, header);
    var playerIds = graph.playerIds.slice();
    var adj = graph.adj;
    var paletteSize = SPACE_ZONE_DEFENDER_PALETTE.length;

    // Stable order so the same conflict resolves the same way each frame.
    playerIds.sort();

    var colorIndex = {};
    for (var i = 0; i < playerIds.length; i++) {
        var pid = playerIds[i];
        var used = {};
        var neighbors = Object.keys(adj[pid] || {});
        for (var n = 0; n < neighbors.length; n++) {
            var nid = neighbors[n];
            if (colorIndex[nid] != null) used[colorIndex[nid]] = true;
        }

        var prefer = responsibilityZoneColorByPlayer[pid];
        if (prefer == null) prefer = preferredDefenderColorIndex(pid);

        var choice = prefer;
        if (used[choice]) {
            choice = 0;
            while (choice < paletteSize && used[choice]) choice++;
            if (choice >= paletteSize) choice = prefer % paletteSize;
        }

        colorIndex[pid] = choice;
        responsibilityZoneColorByPlayer[pid] = choice;
    }
    return colorIndex;
}

function drawResponsibilitySpaceZones(frame) {
    if (!responsibilityZonesEnabled) return;
    if (!responsibilityZonesHeader || !responsibilityZonesHeader.shape) return;
    if (typeof isBallLive === "function" && !isBallLive(frame)) return;

    var held = getHeldResponsibilityZoneFrame(frame);
    if (held == null) return;
    var data = responsibilityZonesByFrame[held];
    if (!data) return;

    var ctx = gameCanvas.ctx;
    var prevFill = ctx.fillStyle;
    var header = responsibilityZonesHeader;
    var styles = data.defenders
        ? colorDefenderZones(data.defenders, header)
        : {};
    var selectedCells = null;
    var selectedStroke = SPACE_ZONE_SELECTED_OUTLINE;

    if (data.defenders) {
        for (var playerId in data.defenders) {
            if (!data.defenders.hasOwnProperty(playerId)) continue;
            var cells = data.defenders[playerId];
            if (!cells || !cells.length) continue;
            var colorIdx = styles[String(playerId)];
            if (colorIdx == null) colorIdx = 0;
            var style = SPACE_ZONE_DEFENDER_PALETTE[colorIdx % SPACE_ZONE_DEFENDER_PALETTE.length];
            ctx.fillStyle = style.fill;
            for (var i = 0; i < cells.length; i++) {
                var b = meshCellBounds(header, cells[i]);
                if (b) fillPitchCell(b);
            }
            if (selectedSpaceZonePlayerId != null && String(playerId) === String(selectedSpaceZonePlayerId)) {
                selectedCells = cells;
                selectedStroke = style.stroke || SPACE_ZONE_SELECTED_OUTLINE;
            }
        }
    }

    if (data.collective && data.collective.length) {
        ctx.fillStyle = SPACE_ZONE_COLLECTIVE_FILL;
        for (var j = 0; j < data.collective.length; j++) {
            var bc = meshCellBounds(header, data.collective[j]);
            if (bc) fillPitchCell(bc);
        }
    }

    if (selectedCells) {
        drawSelectedZoneOutline(selectedCells, header, selectedStroke);
    }

    ctx.fillStyle = prevFill;
}

function drawSelectedSpaceZoneDefenderHighlight(frame) {
    if (!responsibilityZonesEnabled || selectedSpaceZonePlayerId == null) return;
    var pos = getPlayerScreenPosition(frame, selectedSpaceZonePlayerId);
    if (!pos) return;
    var r = typeof PLAYER_DOT_RADIUS === "number" ? PLAYER_DOT_RADIUS : 8;
    gameCanvas.drawDotWithStroke(
        pos.x,
        pos.y,
        r,
        SPACE_ZONE_SELECTED_PLAYER_BORDER,
        SPACE_ZONE_SELECTED_PLAYER_BORDER_WIDTH
    );
}

function screenToTrackingPitch(sx, sy) {
    var halfLength = gameData.pitch.length / 2;
    var halfWidth = gameData.pitch.width / 2;
    var h = halfLength - (sx - pitchOffsetX) / scaling;
    var v = halfWidth - (sy - pitchOffsetY) / scaling;
    // Inverse of getCoordinates / pt: display uses (-trackingX, trackingY).
    return { x: -h, y: v };
}

function trackingPitchToCellIndex(x, y, header) {
    if (!header || !header.shape) return null;
    var rows = header.shape[0];
    var cols = header.shape[1];
    var dx = header.dx != null ? header.dx : ((header.xlim[1] - header.xlim[0]) / cols);
    var dy = header.dy != null ? header.dy : ((header.ylim[1] - header.ylim[0]) / rows);
    if (!dx || !dy) return null;
    var col = Math.round((x - header.x0) / dx);
    var row = Math.round((y - header.y0) / dy);
    if (row < 0 || row >= rows || col < 0 || col >= cols) return null;
    return row * cols + col;
}

function buildZoneOwnerByCell(defenders) {
    var owner = {};
    for (var playerId in defenders) {
        if (!defenders.hasOwnProperty(playerId)) continue;
        var cells = defenders[playerId];
        if (!cells) continue;
        for (var i = 0; i < cells.length; i++) {
            owner[cells[i]] = String(playerId);
        }
    }
    return owner;
}

function findClickedZoneDefenderId(canvasX, canvasY, frame) {
    var held = getHeldResponsibilityZoneFrame(frame);
    if (held == null) return null;
    var data = responsibilityZonesByFrame[held];
    if (!data || !data.defenders) return null;

    var hitR = (typeof PLAYER_DOT_RADIUS === "number" ? PLAYER_DOT_RADIUS : 8) + 2;
    var bestId = null;
    var bestDist = hitR;
    for (var playerId in data.defenders) {
        if (!data.defenders.hasOwnProperty(playerId)) continue;
        if (!data.defenders[playerId] || !data.defenders[playerId].length) continue;
        var pos = getPlayerScreenPosition(frame, playerId);
        if (!pos) continue;
        var dx = pos.x - canvasX;
        var dy = pos.y - canvasY;
        var dist = Math.sqrt(dx * dx + dy * dy);
        if (dist <= bestDist) {
            bestDist = dist;
            bestId = String(playerId);
        }
    }
    if (bestId != null) return bestId;

    // Fall back: click anywhere inside a defender's zone cells.
    var pitch = screenToTrackingPitch(canvasX, canvasY);
    var cellIdx = trackingPitchToCellIndex(pitch.x, pitch.y, responsibilityZonesHeader);
    if (cellIdx == null) return null;
    var owner = buildZoneOwnerByCell(data.defenders);
    return owner[cellIdx] || null;
}

function onResponsibilityPitchClick(event) {
    if (!responsibilityZonesEnabled || !gameData || !gameCanvas) return;
    var canvas = document.getElementById("canvas1");
    if (!canvas || event.target !== canvas) return;

    var rect = canvas.getBoundingClientRect();
    if (rect.width <= 0 || rect.height <= 0) return;
    // CanvasHelper draws in logical CSS pixels (ctx scaled 2x); map using logical size.
    var x = (event.clientX - rect.left) * (gameCanvas.width / rect.width);
    var y = (event.clientY - rect.top) * (gameCanvas.height / rect.height);

    var clickedId = findClickedZoneDefenderId(x, y, frameNr);
    if (clickedId == null) {
        selectedSpaceZonePlayerId = null;
    } else if (selectedSpaceZonePlayerId === clickedId) {
        selectedSpaceZonePlayerId = null;
    } else {
        selectedSpaceZonePlayerId = clickedId;
    }
}

function setupResponsibilitySpaceZonesUi() {
    var arrowsCheckbox = document.getElementById("show_velocity_arrows");
    if (arrowsCheckbox && typeof setShowVelocityArrows === "function") {
        setShowVelocityArrows(arrowsCheckbox.checked);
        arrowsCheckbox.addEventListener("change", function () {
            setShowVelocityArrows(arrowsCheckbox.checked);
        });
    }

    document.addEventListener("click", onResponsibilityPitchClick);
    responsibilityZonesEnabled = true;
}
