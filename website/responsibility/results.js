// Precomputed responsibility results (from preprocess/run.py → responsibility.jsonl).
// Per frame: contestantIds, possessionTeam, mutualHelpEdges, markingEdges.

var responsibilityByFrame = {};
var responsibilityFrameList = [];

function clearResponsibilityResults() {
    responsibilityByFrame = {};
    responsibilityFrameList = [];
}

function ingestResponsibilityResultsLine(line) {
    if (!line) return;
    var obj = JSON.parse(line);
    if (obj.type === "header") return;
    if (obj.frame == null) return;
    responsibilityByFrame[obj.frame] = obj;
    responsibilityFrameList.push(obj.frame);
}

/** Stream a JSONL response line-by-line (avoids loading huge files as one string). */
async function streamJsonlResponse(response, onLine, onProgress) {
    if (!response.body || !response.body.getReader) {
        var text = await response.text();
        var lines = text.split(/\n/);
        for (var i = 0; i < lines.length; i++) {
            var trimmed = lines[i].trim();
            if (trimmed) onLine(trimmed);
            if (onProgress && (i + 1) % 5000 === 0) onProgress(i + 1);
        }
        return;
    }
    var reader = response.body.getReader();
    var decoder = new TextDecoder();
    var buffer = "";
    var count = 0;
    while (true) {
        var chunk = await reader.read();
        if (chunk.done) break;
        buffer += decoder.decode(chunk.value, { stream: true });
        var nl;
        while ((nl = buffer.indexOf("\n")) >= 0) {
            var line = buffer.slice(0, nl).trim();
            buffer = buffer.slice(nl + 1);
            if (!line) continue;
            onLine(line);
            count += 1;
            if (onProgress && count % 5000 === 0) onProgress(count);
        }
    }
    buffer += decoder.decode();
    var last = buffer.trim();
    if (last) {
        onLine(last);
        count += 1;
        if (onProgress) onProgress(count);
    }
}

function setResponsibilityLoadingSubtitle(msg) {
    var el = document.getElementById("dataLoadingSubtitle");
    if (el) el.textContent = msg;
}

async function tryLoadLocalResponsibilityResults() {
    try {
        setResponsibilityLoadingSubtitle("Loading responsibility.jsonl...");
        var response = await fetch(getLocalDataDir() + "/responsibility.jsonl");
        if (!response.ok) {
            console.warn("responsibility.jsonl not found (" + response.status + ")");
            return false;
        }
        clearResponsibilityResults();
        await streamJsonlResponse(response, ingestResponsibilityResultsLine, function (n) {
            setResponsibilityLoadingSubtitle("Loading responsibility.jsonl... " + n + " frames");
        });
        responsibilityFrameList.sort(function (a, b) { return a - b; });
        console.info("Loaded responsibility results:", responsibilityFrameList.length, "frames");
        return responsibilityFrameList.length > 0;
    } catch (err) {
        console.error("Failed to load responsibility.jsonl:", err);
        clearResponsibilityResults();
        return false;
    }
}

function getResponsibilityFrame(frame) {
    return responsibilityByFrame[frame] || null;
}

function getPossessionTeam(frame) {
    var row = getResponsibilityFrame(frame);
    if (row && row.possessionTeam === "home") return 1;
    if (row && row.possessionTeam === "away") return 2;
    // Hold last known possession while scrubbing across gaps.
    var list = responsibilityFrameList;
    var best = null;
    for (var i = 0; i < list.length; i++) {
        if (list[i] <= frame) best = list[i];
        else break;
    }
    if (best != null) {
        var held = responsibilityByFrame[best];
        if (held && held.possessionTeam === "home") return 1;
        if (held && held.possessionTeam === "away") return 2;
    }
    return null;
}

function getDefendingTeam(frame) {
    var possessionTeam = getPossessionTeam(frame);
    if (possessionTeam == null) return null;
    return possessionTeam === 1 ? 2 : 1;
}

function edgesFromIdPairs(frame, pairs, asMarking) {
    var edges = [];
    if (!pairs) return edges;
    for (var i = 0; i < pairs.length; i++) {
        var pair = pairs[i];
        if (!pair || pair.length < 2) continue;
        var a = getPlayerScreenPosition(frame, pair[0]);
        var b = getPlayerScreenPosition(frame, pair[1]);
        if (!a || !b) continue;
        var edge = { x1: a.x, y1: a.y, x2: b.x, y2: b.y };
        if (asMarking) {
            edge.defenderId = String(pair[0]);
            edge.attackerId = String(pair[1]);
        }
        edges.push(edge);
    }
    return edges;
}
