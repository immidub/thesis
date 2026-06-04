const BALL_TRACKING_ID = "__ball__";

async function parseTrackingJsonl(source) {
    var tracking = [];
    var homePlayerMeta = {};
    var awayPlayerMeta = {};
    var periods = [];
    var periodStartIndex = 0;
    var currentPeriod = null;
    var frameRateEstimate = null;
    var prevGameClock = null;

    function addLine(trimmed) {
        if (!trimmed) return;

        var frame = JSON.parse(trimmed);
        var frameIdx = frame.frameIdx != null ? frame.frameIdx : tracking.length;
        var period = frame.period != null ? frame.period : 1;
        var gameClock = frame.gameClock != null ? frame.gameClock : 0;

        if (prevGameClock != null && frameRateEstimate == null) {
            var dt = gameClock - prevGameClock;
            if (dt > 0) frameRateEstimate = Math.round(1 / dt);
        }
        prevGameClock = gameClock;

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
            objects[BALL_TRACKING_ID] = { h: +frame.ball.xyz[0], v: +frame.ball.xyz[1], z: +frame.ball.xyz[2] || 0 };
        }

        tracking.push({
            frame: frameIdx,
            timestamp: Math.round(gameClock * 1000),
            possession: frame.lastTouch || null,
            objects: objects,
        });

        if (tracking.length % 5000 === 0) {
            var subtitle = document.getElementById("dataLoadingSubtitle");
            if (subtitle) subtitle.innerHTML = "Parsing… " + tracking.length + " frames";
        }
    }

    var decoder = new TextDecoder();
    var buffer = "";
    var reader = source.body && source.body.getReader
        ? source.body.getReader()
        : source.getReader
            ? source.getReader()
            : source.stream().getReader();

    while (true) {
        var chunk = await reader.read();
        if (chunk.done) break;

        buffer += decoder.decode(chunk.value, { stream: true });
        var nl;
        while ((nl = buffer.indexOf("\n")) >= 0) {
            addLine(buffer.slice(0, nl).trim());
            buffer = buffer.slice(nl + 1);
        }
    }

    buffer += decoder.decode();
    addLine(buffer.trim());

    if (tracking.length === 0) {
        throw new Error("No tracking frames found");
    }

    periods.push({ startFrame: periodStartIndex, endFrame: tracking.length - 1 });

    return {
        version: "1.0",
        frameRate: frameRateEstimate || 25,
        periods: periods,
        pitch: { width: 68, length: 105 },
        homeTeam: { name: "Home", players: Object.values(homePlayerMeta) },
        awayTeam: { name: "Away", players: Object.values(awayPlayerMeta) },
        ballId: BALL_TRACKING_ID,
        tracking: tracking,
    };
}

function addTeam(players, objects, metaMap) {
    if (!players) return;
    for (var i = 0; i < players.length; i++) {
        var p = players[i];
        if (!p.playerId) continue;
        objects[p.playerId] = { h: +p.xyz[0], v: +p.xyz[1], z: +p.xyz[2] || 0 };
        if (!metaMap[p.playerId]) {
            var fspId = p.playerExternalIds && p.playerExternalIds.fspId ? p.playerExternalIds.fspId : null;
            metaMap[p.playerId] = { id: p.playerId, fspId: fspId, shirtNumber: p.number, isGoalie: false };
        }
    }
}
