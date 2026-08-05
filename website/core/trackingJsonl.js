const BALL_TRACKING_ID = "__ball__";
const TRACKING_FRAME_RATE = 50;


//builds tracking data from a jsonl file
async function parseTrackingJsonl(source, options) {
    options = options || {};
    var totalBytes = options.totalBytes || 0;
    var receivedBytes = 0;
    var tracking = [];
    var homePlayerMeta = {};
    var awayPlayerMeta = {};
    var periods = [];
    var periodStartIndex = 0;
    var currentPeriod = null;

    function reportProgress() {
        if (typeof setDataLoadingProgress !== "function") return;
        if (totalBytes > 0) {
            setDataLoadingProgress((100 * receivedBytes) / totalBytes);
        } else if (typeof setDataLoadingIndeterminate === "function") {
            setDataLoadingIndeterminate();
        }
    }

    function addLine(trimmed) {
        if (!trimmed) return;

        var frame = JSON.parse(trimmed);
        var frameIdx = frame.frameIdx != null ? frame.frameIdx : tracking.length;
        var period = frame.period != null ? frame.period : 1;
        var gameClock = frame.gameClock != null ? frame.gameClock : 0;

        if (currentPeriod == null) {
            currentPeriod = period;
            periodStartIndex = tracking.length;
        } else if (period !== currentPeriod) {
            periods.push({ startFrame: periodStartIndex, endFrame: tracking.length - 1 });
            currentPeriod = period;
            periodStartIndex = tracking.length;
        }

        var objects = {};
        addTeam(frame.homePlayers, objects, homePlayerMeta);
        addTeam(frame.awayPlayers, objects, awayPlayerMeta);
        if (frame.ball && frame.ball.xyz) {
            objects[BALL_TRACKING_ID] = buildObject(frame.ball);
        }

        tracking.push({
            frame: frameIdx,
            period: period,
            timestamp: Math.round(gameClock * 1000),
            possession: frame.attacking || null,
            live: frame.live != null ? frame.live : null,
            objects: objects,
        });
    }

    var decoder = new TextDecoder();
    var buffer = "";
    var reader = source.body && source.body.getReader
        ? source.body.getReader()
        : source.getReader
            ? source.getReader()
            : source.stream().getReader();

    reportProgress();
    while (true) {
        var chunk = await reader.read();
        if (chunk.done) break;
        if (chunk.value) receivedBytes += chunk.value.byteLength;
        reportProgress();

        buffer += decoder.decode(chunk.value, { stream: true });
        var nl;
        while ((nl = buffer.indexOf("\n")) >= 0) {
            addLine(buffer.slice(0, nl).trim());
            buffer = buffer.slice(nl + 1);
        }
    }

    buffer += decoder.decode();
    addLine(buffer.trim());
    if (typeof setDataLoadingProgress === "function") setDataLoadingProgress(100);

    if (tracking.length === 0) {
        throw new Error("No tracking frames found");
    }

    periods.push({ startFrame: periodStartIndex, endFrame: tracking.length - 1 });

    return {
        version: "1.0",
        frameRate: TRACKING_FRAME_RATE,
        periods: periods,
        pitch: { width: 68, length: 105 },
        homeTeam: { name: "Home", players: Object.values(homePlayerMeta) },
        awayTeam: { name: "Away", players: Object.values(awayPlayerMeta) },
        ballId: BALL_TRACKING_ID,
        tracking: tracking,
    };
}

function buildObject(entry) {
    var obj = {
        h: +entry.xyz[0],
        v: +entry.xyz[1],
        z: +entry.xyz[2] || 0,
    };
    if (entry.speed != null) obj.speed = +entry.speed;
    if (entry.direction != null) obj.direction = +entry.direction;
    return obj;
}

function addTeam(players, objects, metaMap) {
    if (!players) return;
    for (var i = 0; i < players.length; i++) {
        var p = players[i];
        if (!p.playerId) continue;
        objects[p.playerId] = buildObject(p);
        if (!metaMap[p.playerId]) {
            metaMap[p.playerId] = { id: String(p.playerId), shirtNumber: p.number, isGoalie: false };
        }
    }
}
