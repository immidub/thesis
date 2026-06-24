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

function getMatchClockSeconds(frame) {
    var ts = (+gameData.tracking[frame].timestamp || 0) / 1000;
    if (!gameData.periods || gameData.periods.length === 0) {
        return ts;
    }

    var offset = 0;
    var p = getPeriod(frame);
    if (p >= 1) offset += 45 * 60;
    if (p >= 2) offset += 45 * 60;
    if (p >= 3) offset += 15 * 60;
    return offset + ts;
}

function parseGameTime(str) {
    str = (str || "").trim();
    if (!str) return null;

    var plus = str.indexOf("+");
    if (plus >= 0) {
        var baseMin = parseInt(str.slice(0, plus), 10);
        var rest = str.slice(plus + 1);
        var colon = rest.indexOf(":");
        if (colon < 0 || isNaN(baseMin)) return null;
        var stoppageMin = parseInt(rest.slice(0, colon), 10);
        var sec = parseInt(rest.slice(colon + 1), 10);
        if (isNaN(stoppageMin) || isNaN(sec)) return null;
        return baseMin * 60 + stoppageMin * 60 + sec;
    }

    var colon = str.indexOf(":");
    if (colon < 0) return null;
    var min = parseInt(str.slice(0, colon), 10);
    var sec = parseInt(str.slice(colon + 1), 10);
    if (isNaN(min) || isNaN(sec)) return null;
    return min * 60 + sec;
}

function timeToFrame(seconds) {
    var lo = 0;
    var hi = maxFrame;
    while (lo < hi) {
        var mid = Math.floor((lo + hi) / 2);
        if (getMatchClockSeconds(mid) < seconds) lo = mid + 1;
        else hi = mid;
    }
    return lo;
}

var VIDEO_FIRST_HALF_START_SEC = 23 * 60 + 39;
var VIDEO_SECOND_HALF_START_SEC = 91 * 60;
// Game clip was ~1s behind pitch viz; start MP4 1s later in the broadcast to align.
var VIDEO_SYNC_OFFSET_SEC = 1;

function frameToVideoSeconds(frame) {
    var ts = (+gameData.tracking[frame].timestamp || 0) / 1000;
    var videoSec;
    if (!gameData.periods || gameData.periods.length === 0) {
        videoSec = VIDEO_FIRST_HALF_START_SEC + ts;
    } else {
        var period = getPeriod(frame);
        if (period === 0) {
            videoSec = VIDEO_FIRST_HALF_START_SEC + ts;
        } else if (period === 1) {
            videoSec = VIDEO_SECOND_HALF_START_SEC + ts;
        } else {
            videoSec = VIDEO_SECOND_HALF_START_SEC + 45 * 60;
            for (var i = 2; i < period; i++) {
                videoSec += (i > 2 ? 15 : 45) * 60;
            }
            videoSec += ts;
        }
    }
    return Math.max(0, videoSec + VIDEO_SYNC_OFFSET_SEC);
}
