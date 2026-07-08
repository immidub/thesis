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
        var period = gameData.periods[i];
        var start = period.startFrame != null ? period.startFrame : 0;
        var end = period.endFrame;
        if (frame >= start && frame <= end) {
            return i;
        }
    }
    if (frame < gameData.periods[0].startFrame) return 0;
    return gameData.periods.length - 1;
}

function getPeriodRegulationSeconds(periodIndex) {
    return periodIndex > 2 ? 15 * 60 : 45 * 60;
}

function getPeriodMatchClockOffset(periodIndex) {
    var offset = 0;
    if (periodIndex >= 1) offset += 45 * 60;
    if (periodIndex >= 2) offset += 45 * 60;
    if (periodIndex >= 3) offset += 15 * 60;
    return offset;
}

function getPeriodFrameRange(periodIndex) {
    if (!gameData.periods || gameData.periods.length === 0) {
        return { start: 0, end: maxFrame };
    }
    if (periodIndex < 0 || periodIndex >= gameData.periods.length) {
        return null;
    }
    var period = gameData.periods[periodIndex];
    return {
        start: period.startFrame != null ? period.startFrame : 0,
        end: Math.min(maxFrame, period.endFrame),
    };
}

function periodIndexFromStoppageBaseMinutes(baseMin) {
    if (baseMin === 45) return 0;
    if (baseMin === 90) return 1;
    if (baseMin === 105) return 2;
    if (baseMin === 120) return 3;
    if (baseMin < 90) return 0;
    if (baseMin < 105) return 1;
    if (baseMin < 120) return 2;
    return Math.min(3, gameData.periods ? gameData.periods.length - 1 : 3);
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
    return getPeriodMatchClockOffset(getPeriod(frame)) + ts;
}

// Parses playback-style game times. Stoppage uses "45+2:15" / "90+1:00".
// Returns { seconds, periodIndex } so first-half stoppage is not confused with early second half.
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
        return {
            seconds: baseMin * 60 + stoppageMin * 60 + sec,
            periodIndex: periodIndexFromStoppageBaseMinutes(baseMin),
            isStoppage: true,
        };
    }

    var colon = str.indexOf(":");
    if (colon < 0) return null;
    var min = parseInt(str.slice(0, colon), 10);
    var sec = parseInt(str.slice(colon + 1), 10);
    if (isNaN(min) || isNaN(sec)) return null;
    return {
        seconds: min * 60 + sec,
        periodIndex: null,
        isStoppage: false,
    };
}

function timeToFrameInRange(seconds, startFrame, endFrame) {
    var lo = startFrame;
    var hi = endFrame;
    while (lo < hi) {
        var mid = Math.floor((lo + hi) / 2);
        if (getMatchClockSeconds(mid) < seconds) lo = mid + 1;
        else hi = mid;
    }
    return lo;
}

// Broadcast wall-clock anchors in the MP4 (halftime break excluded between halves).
var VIDEO_FIRST_HALF_START_SEC = 23 * 60 + 39; // 23:39
var VIDEO_FIRST_HALF_END_SEC = 1 * 3600 + 14 * 60 + 45; // 1:14:45
var VIDEO_SECOND_HALF_START_SEC = 91 * 60; // 1:31:00
var VIDEO_SECOND_HALF_END_SEC = 2 * 3600 + 23 * 60 + 18; // 2:23:18

var periodEndGameClockCache = null;

function getPeriodEndGameClockSec(period) {
    if (!gameData || !gameData.periods || period >= gameData.periods.length) {
        return 45 * 60;
    }
    if (periodEndGameClockCache == null || periodEndGameClockCache.source !== gameData) {
        var values = [];
        for (var i = 0; i < gameData.periods.length; i++) {
            var endFrame = gameData.periods[i].endFrame;
            values[i] = (+gameData.tracking[endFrame].timestamp || 0) / 1000;
        }
        periodEndGameClockCache = { source: gameData, values: values };
    }
    return periodEndGameClockCache.values[period] || 45 * 60;
}

function getVideoWallRangeForPeriod(period) {
    if (period === 0) {
        return {
            start: VIDEO_FIRST_HALF_START_SEC,
            end: VIDEO_FIRST_HALF_END_SEC,
        };
    }
    if (period === 1) {
        return {
            start: VIDEO_SECOND_HALF_START_SEC,
            end: VIDEO_SECOND_HALF_END_SEC,
        };
    }
    var extraWallSpan = 15 * 60;
    var start = VIDEO_SECOND_HALF_END_SEC + (period - 2) * extraWallSpan;
    return { start: start, end: start + extraWallSpan };
}

function mapGameClockToVideoSeconds(period, gameClockSec) {
    var range = getVideoWallRangeForPeriod(period);
    var periodEnd = getPeriodEndGameClockSec(period);
    if (periodEnd <= 0) periodEnd = 1;
    var fraction = Math.min(1, Math.max(0, gameClockSec / periodEnd));
    return range.start + fraction * (range.end - range.start);
}

function frameToVideoSeconds(frame) {
    var ts = (+gameData.tracking[frame].timestamp || 0) / 1000;
    var videoSec;
    if (!gameData.periods || gameData.periods.length === 0) {
        return Math.max(0, mapGameClockToVideoSeconds(0, ts));
    }
    return Math.max(0, mapGameClockToVideoSeconds(getPeriod(frame), ts));
}

function formatVideoWallTime(seconds) {
    seconds = Math.max(0, Math.floor(seconds));
    var h = Math.floor(seconds / 3600);
    var m = Math.floor((seconds % 3600) / 60);
    var s = seconds % 60;
    var mStr = m < 10 ? "0" + m : "" + m;
    var sStr = s < 10 ? "0" + s : "" + s;
    if (h > 0) {
        return h + ":" + mStr + ":" + sStr;
    }
    return mStr + ":" + sStr;
}

function frameToVideoTime(frame) {
    if (gameData == null) return "--:--";
    return formatVideoWallTime(frameToVideoSeconds(frame));
}

function updateTimeLabels(frame) {
    var gameEl = document.getElementById("time_label_text");
    var videoEl = document.getElementById("video_time_label_text");
    if (!gameEl) return;

    gameEl.textContent = frameToTime(frame);
    gameEl.title = "Game clock";

    if (videoEl) {
        videoEl.textContent = frameToVideoTime(frame);
        videoEl.title = "MP4 time";
    }

    var wrap = document.getElementById("time_label_wrap");
    if (wrap && gameData != null) {
        wrap.title = "frame: " + gameData.tracking[frame].frame;
    }
}
