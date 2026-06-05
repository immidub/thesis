var isPlaying = false;
var playBackSpeed = 1;
var frameNr = 0;
var frameDelta = 0;

var timestampOffset = 0;

function setFrameNr(frameNrLoc) {
    if (frameNrLoc != null) frameNr = frameNrLoc;
    $("#duration_slider").val(frameNr);
    timestampOffset = Date.now() - frameNr * 1000 / (gameData.frameRate * playBackSpeed);
}

function handleFrameNr() {
    var newFrameNr = +$("#duration_slider").val();
    if (Math.abs(newFrameNr - frameNr) > 2) {
        setFrameNr(newFrameNr);
    }

    if (isPlaying && maxFrame > 0 && frameNr < maxFrame) {
        var frameRate = gameData.frameRate * playBackSpeed;
        var frameDouble = ((Date.now() - timestampOffset) / 1000) * frameRate;
        frameDelta = frameDouble % 1;
        frameNr = Math.floor(frameDouble);

        if (frameNr < 0) frameNr = 0;
        if (frameNr > maxFrame) {
            frameNr = maxFrame;
            isPlaying = false;
            $("#button_pause").hide();
            $("#button_play").show();
        }

        $("#duration_slider").val(frameNr);
    }
}

function changePlaybackSpeed(val) {
    playBackSpeed = val;
    isPlaying = true;
    setFrameNr(null);
    $("#button_pause").show();
    $("#button_play").hide();
}

function togglePlayback() {
    if (gameData == null || maxFrame <= 0) return;
    if (isPlaying) {
        pausePlayback();
    } else {
        playPlayback();
    }
}

function playPlayback() {
    if (gameData == null || maxFrame <= 0) return;
    isPlaying = true;
    setFrameNr(frameNr);
    $("#button_pause").show();
    $("#button_play").hide();
}

function pausePlayback() {
    isPlaying = false;
    $("#button_pause").hide();
    $("#button_play").show();
}

function skipPlaybackSeconds(seconds) {
    if (gameData == null || maxFrame <= 0) return;

    var wasPlaying = isPlaying;
    var deltaFrames = Math.round(seconds * gameData.frameRate);
    var newFrame = Math.max(0, Math.min(maxFrame, frameNr + deltaFrames));
    frameDelta = 0;
    setFrameNr(newFrame);

    if (newFrame >= maxFrame) {
        pausePlayback();
        return;
    }

    if (wasPlaying) {
        playPlayback();
    } else {
        pausePlayback();
    }
}

function setupPlaybackKeyboard() {
    document.addEventListener("keydown", function (e) {
        if (!$("#website_view").is(":visible")) return;
        if (gameData == null || maxFrame <= 0) return;

        var tag = e.target.tagName;
        if (tag === "INPUT" || tag === "SELECT" || tag === "TEXTAREA") return;

        if (e.code === "Space") {
            e.preventDefault();
            togglePlayback();
        } else if (e.code === "ArrowLeft") {
            e.preventDefault();
            skipPlaybackSeconds(-5);
        } else if (e.code === "ArrowRight") {
            e.preventDefault();
            skipPlaybackSeconds(5);
        }
    });
}

function getPeriod(frame) {
    if (!gameData.periods || gameData.periods.length === 0) {
        return 0;
    }
    for (var i = 0; i < gameData.periods.length; i++) {
        if (frame < gameData.periods[i].endFrame) {
            return i;
        }
    }
    return gameData.periods.length - 1;
}

function frameToTime(frame) {
    if (!gameData.periods || gameData.periods.length === 0) {
        var s = Math.floor((+gameData.tracking[frame].timestamp || 0) / 1000);
        var m = Math.floor(s / 60);
        var sec = s % 60;
        return (m < 10 ? "0" : "") + m + ":" + (sec < 10 ? "0" : "") + sec;
    }

    var p = getPeriod(frame);
    var pTime = 45;
    if (p > 2) pTime = 15;

    var secondsPeriod = (+gameData.tracking[frame].timestamp) / 1000;
    var additionalSeconds = 0;
    if (secondsPeriod > pTime * 60) {
        additionalSeconds = secondsPeriod - pTime * 60;
        secondsPeriod -= additionalSeconds;
    }

    if (p >= 1) secondsPeriod += 45 * 60;
    if (p >= 2) secondsPeriod += 45 * 60;
    if (p >= 3) secondsPeriod += 15 * 60;

    if (secondsPeriod == null) {
        secondsPeriod = frame / gameData.frameRate;
    }

    var secondsText = Math.floor(secondsPeriod % 60);
    if (secondsText < 10) secondsText = "0" + secondsText;
    else secondsText = "" + secondsText;

    var minText = Math.floor(secondsPeriod / 60);
    if (minText < 10) minText = "0" + minText;
    else minText = "" + minText;

    if (additionalSeconds > 0) {
        var secondsText2 = Math.floor(additionalSeconds % 60);
        if (secondsText2 < 10) secondsText2 = "0" + secondsText2;
        else secondsText2 = "" + secondsText2;
        return minText + "+" + Math.floor(additionalSeconds / 60) + ":" + secondsText2;
    }

    return minText + ":" + secondsText;
}
