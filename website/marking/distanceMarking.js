var distanceThresholdMeters = 10;
var distanceThresholdAngleFilter = false;
var distanceThresholdAngleDegrees = 90;

function passesDistanceThresholdAngleFilter(ball, defender, attacker, maxAngleDegrees) {
    var defenderPos = getPlayerMarkingPosition(defender);
    var attackerPos = getPlayerMarkingPosition(attacker);
    var angle = getAngleAtBallDegrees(ball, attackerPos, defenderPos);
    return angle <= maxAngleDegrees;
}

function getDistanceMarkingEdges(frame, thresholdMeters) {
    if (!isBallLive(frame)) return [];

    var defendingTeam = getDefendingTeam(frame);
    if (defendingTeam == null) return [];

    var attackers = getTeamPlayerPositions(frame, defendingTeam === 1 ? 2 : 1);
    var defenders = getTeamPlayerPositions(frame, defendingTeam);
    var edges = [];
    var thresholdSq = thresholdMeters * thresholdMeters;
    var ball = distanceThresholdAngleFilter ? getBallPitchPosition(frame) : null;
    var maxAngleDegrees = distanceThresholdAngleDegrees;

    for (var i = 0; i < defenders.length; i++) {
        var defender = defenders[i];
        for (var j = 0; j < attackers.length; j++) {
            var attacker = attackers[j];
            if (getMarkingPairDistanceSquared(defender, attacker, useProjectedPositions) > thresholdSq) {
                continue; //if the distance between the defender and attacker is greater than the threshold, skip
            }

            if (ball != null &&
                !passesDistanceThresholdAngleFilter(ball, defender, attacker, maxAngleDegrees)) {
                continue; //if the angle between the defender and attacker is greater than the threshold, skip
            }

            if (!passesMarkingEdgeFilters(frame, defender, attacker)) {
                continue; //if the edges do not pass the marking edge filters, skip
            }

            edges.push({
                x1: defender.x,
                y1: defender.y,
                x2: attacker.x,
                y2: attacker.y,
            });
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

function setDistanceThresholdAngleDegrees(value) {
    if (!Number.isFinite(value)) return;
    distanceThresholdAngleDegrees = Math.min(180, Math.max(0, value));
    var label = document.getElementById("distance_threshold_angle_label");
    if (label) {
        label.textContent = String(Math.round(distanceThresholdAngleDegrees));
    }
    var input = document.getElementById("distance_threshold_angle_degrees");
    if (input && +input.value !== distanceThresholdAngleDegrees) {
        input.value = String(distanceThresholdAngleDegrees);
    }
}

function setupDistanceMarking() {
    var slider = document.getElementById("distance_threshold_slider");
    if (!slider) return;

    setDistanceThresholdMeters(+slider.value);

    slider.addEventListener("input", function () {
        setDistanceThresholdMeters(+slider.value);
    });

    var angleCheckbox = document.getElementById("distance_threshold_angle_filter");
    if (angleCheckbox) {
        distanceThresholdAngleFilter = angleCheckbox.checked;
        angleCheckbox.addEventListener("change", function () {
            distanceThresholdAngleFilter = angleCheckbox.checked;
        });
    }

    var angleInput = document.getElementById("distance_threshold_angle_degrees");
    if (angleInput) {
        setDistanceThresholdAngleDegrees(+angleInput.value);
        angleInput.addEventListener("input", function () {
            setDistanceThresholdAngleDegrees(+angleInput.value);
        });
        angleInput.addEventListener("change", function () {
            setDistanceThresholdAngleDegrees(+angleInput.value);
        });
    }
}
