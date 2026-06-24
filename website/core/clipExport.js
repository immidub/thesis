var isExporting = false;

var PITCH_EXPORT_OPTIONS = [
    { index: 0, label: "Distance threshold" },
    { index: 1, label: "k-nearest neighbors" },
    { index: 2, label: "Hungarian matching" },
    { index: 3, label: "Delaunay triangulation" },
    { index: 4, label: "Shape graph (attacking)" },
    { index: 5, label: "Shape graph (all outfield)" },
    { index: 6, label: "Ball pressure" },
];

function getClipMimeType() {
    if (typeof MediaRecorder === "undefined") return null;
    if (MediaRecorder.isTypeSupported("video/webm;codecs=vp9")) return "video/webm;codecs=vp9";
    if (MediaRecorder.isTypeSupported("video/webm")) return "video/webm";
    return null;
}

function sanitizeClipFilenamePart(str) {
    return (str || "").trim().replace(/[^\w.\-+]/g, "_");
}

function buildClipFilename(pitchIndex, startTime, endTime) {
    var pitch = PITCH_EXPORT_OPTIONS.find(function (p) { return p.index === pitchIndex; });
    var slug = pitch ? pitch.label.toLowerCase().replace(/[^a-z0-9]+/g, "_") : "pitch_" + pitchIndex;
    return slug + "_" + sanitizeClipFilenamePart(startTime) + "_to_" + sanitizeClipFilenamePart(endTime) + ".webm";
}

function setClipExportStatus(message, isError) {
    var el = document.getElementById("clip_export_status");
    if (!el) return;
    el.textContent = message || "";
    el.className = "clip-export-status" + (isError ? " clip-export-status--error" : "");
}

function renderPitchForExport(pitchIndex, frame) {
    frameNr = frame;
    frameDelta = 0;
    gameCanvas = gameCanvases[pitchIndex];
    if (pitchOffsetX === -1) {
        drawGameSetup();
    }
    gameCanvas.clearCanvasWhite();
    drawPitchFrame(pitchIndex);
}

async function saveClipToServer(blob, filename) {
    var response = await fetch("/api/clips", {
        method: "POST",
        headers: { "X-Filename": filename },
        body: blob,
    });
    if (!response.ok) {
        throw new Error("Server returned " + response.status);
    }
    return response.json();
}

function downloadClipFallback(blob, filename) {
    var url = URL.createObjectURL(blob);
    var link = document.createElement("a");
    link.href = url;
    link.download = filename;
    link.click();
    URL.revokeObjectURL(url);
}

async function exportPitchClip(pitchIndex, startTimeStr, endTimeStr) {
    if (isExporting) return;
    if (gameData == null || maxFrame <= 0) {
        setClipExportStatus("Load match data first.", true);
        return;
    }

    var mimeType = getClipMimeType();
    if (!mimeType) {
        setClipExportStatus("WebM recording is not supported in this browser.", true);
        return;
    }

    var startSeconds = parseGameTime(startTimeStr);
    var endSeconds = parseGameTime(endTimeStr);
    if (startSeconds == null || endSeconds == null) {
        setClipExportStatus("Use game time like 23:45 or 90+2:15.", true);
        return;
    }
    if (startSeconds >= endSeconds) {
        setClipExportStatus("Start time must be before end time.", true);
        return;
    }

    var startFrame = timeToFrame(startSeconds);
    var endFrame = timeToFrame(endSeconds);
    if (startFrame > maxFrame) {
        setClipExportStatus("Start time is after the end of the match.", true);
        return;
    }
    if (endFrame > maxFrame) endFrame = maxFrame;
    if (startFrame >= endFrame) {
        setClipExportStatus("Selected range has no frames.", true);
        return;
    }

    var canvasEl = document.getElementById("canvas" + (pitchIndex + 1));
    if (!canvasEl) {
        setClipExportStatus("Pitch canvas not found.", true);
        return;
    }

    isExporting = true;
    var savedFrame = frameNr;
    var savedDelta = frameDelta;
    var wasPlaying = isPlaying;
    pausePlayback();

    var exportBtn = document.getElementById("clip_export_btn");
    if (exportBtn) exportBtn.disabled = true;
    setClipExportStatus("Exporting… (runs in real time)");

    try {
        var stream = canvasEl.captureStream(0);
        var track = stream.getVideoTracks()[0];
        var recorder = new MediaRecorder(stream, { mimeType: mimeType });
        var chunks = [];

        recorder.ondataavailable = function (e) {
            if (e.data.size > 0) chunks.push(e.data);
        };

        var stopped = new Promise(function (resolve) {
            recorder.onstop = resolve;
        });

        recorder.start();

        var frameDelayMs = 1000 / gameData.frameRate;
        for (var f = startFrame; f <= endFrame; f++) {
            renderPitchForExport(pitchIndex, f);
            track.requestFrame();
            await new Promise(function (r) { requestAnimationFrame(r); });
            await new Promise(function (r) { setTimeout(r, frameDelayMs); });
        }

        recorder.stop();
        await stopped;

        var blob = new Blob(chunks, { type: mimeType });
        var filename = buildClipFilename(pitchIndex, startTimeStr, endTimeStr);

        try {
            var result = await saveClipToServer(blob, filename);
            setClipExportStatus("Saved to " + result.path);
        } catch (err) {
            downloadClipFallback(blob, filename);
            setClipExportStatus("Saved via download (start serve.py to save into clips/).", true);
        }
    } catch (err) {
        setClipExportStatus("Export failed: " + err.message, true);
    } finally {
        frameNr = savedFrame;
        frameDelta = savedDelta;
        setFrameNr(savedFrame);
        isExporting = false;
        if (exportBtn) exportBtn.disabled = false;
        if (wasPlaying) playPlayback();
    }
}

function setupClipExport() {
    var select = document.getElementById("clip_pitch_select");
    if (!select) return;

    PITCH_EXPORT_OPTIONS.forEach(function (opt) {
        var option = document.createElement("option");
        option.value = String(opt.index);
        option.textContent = opt.label;
        select.appendChild(option);
    });

    document.getElementById("clip_set_start_btn").addEventListener("click", function () {
        document.getElementById("clip_start_time").value = frameToTime(frameNr);
    });

    document.getElementById("clip_set_end_btn").addEventListener("click", function () {
        document.getElementById("clip_end_time").value = frameToTime(frameNr);
    });

    document.getElementById("clip_export_btn").addEventListener("click", function () {
        var pitchIndex = +document.getElementById("clip_pitch_select").value;
        var startTime = document.getElementById("clip_start_time").value;
        var endTime = document.getElementById("clip_end_time").value;
        exportPitchClip(pitchIndex, startTime, endTime);
    });
}
