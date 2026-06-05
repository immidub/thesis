var minFrame = 0;
var maxFrame = 0;

function setupSlider() {
    $("#duration_slider").prop("min", minFrame);
    $("#duration_slider").prop("max", maxFrame);
}

function setupUIElements() {
    $("#website_view").hide();

    $("#data_error_view").hide();
    $("#data_loading_view").hide();

    function onPlay() {
        playPlayback();
    }

    function onPause() {
        pausePlayback();
    }

    $("#play_pause_btn").on("click", function () {
        if ($("#button_pause").is(":visible")) {
            onPause();
        } else {
            onPlay();
        }
    });
    
    $("#button_pause").hide();

    $("#duration_slider").on("input", function () {
        pausePlayback();
        setFrameNr(+$(this).val());
    });

    setupPlaybackKeyboard();

    tryLoadLocalData();
}
