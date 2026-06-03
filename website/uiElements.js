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
    $("#error_div_possessions").hide();
    $("#error_div_events").hide();

    function onPlay() {
        if (gameData == null || maxFrame <= 0) return;
        isPlaying = true;
        setFrameNr(frameNr);
        $("#button_pause").show();
        $("#button_play").hide();
    }

    function onPause() {
        isPlaying = false;
        $("#button_pause").hide();
        $("#button_play").show();
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
        isPlaying = false;
        $("#button_pause").hide();
        $("#button_play").show();
        setFrameNr(+$(this).val());
    });
}
