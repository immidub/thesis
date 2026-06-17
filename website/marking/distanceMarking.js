var distanceThresholdMeters = 10;

function getDistanceMarkingEdges(frame, thresholdMeters) {
    if (!isBallLive(frame)) return [];

    var team1 = getTeamPlayerPositions(frame, 1);
    var team2 = getTeamPlayerPositions(frame, 2);
    var edges = [];
    var thresholdSq = thresholdMeters * thresholdMeters;

    for (var i = 0; i < team1.length; i++) {
        var p1 = team1[i];
        for (var j = 0; j < team2.length; j++) {
            var p2 = team2[j];
            if (getPitchDistanceSquared(p1.h, p1.v, p2.h, p2.v) <= thresholdSq) {
                edges.push({
                    x1: p1.x,
                    y1: p1.y,
                    x2: p2.x,
                    y2: p2.y,
                });
            }
        }
    }

    return edges;
}

function setDistanceThresholdMeters(value) {
    distanceThresholdMeters = value;
    var label = document.getElementById("distance_threshold_label");
    if (label) {
        label.textContent = value.toFixed(1);
    }
}

function setupDistanceMarking() {
    var slider = document.getElementById("distance_threshold_slider");
    if (!slider) return;

    setDistanceThresholdMeters(+slider.value);

    slider.addEventListener("input", function () {
        setDistanceThresholdMeters(+slider.value);
    });
}
