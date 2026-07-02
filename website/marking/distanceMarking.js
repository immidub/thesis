var distanceThresholdMeters = 10;
var distanceThresholdOrientationFilter = false;

function isAttackerAheadOfDefender(defender, attacker, defendingGoalLineH) {
    var defenderDist = Math.abs(defender.h - defendingGoalLineH);
    var attackerDist = Math.abs(attacker.h - defendingGoalLineH);
    return attackerDist < defenderDist;
}

function getDistanceMarkingEdges(frame, thresholdMeters) {
    if (!isBallLive(frame)) return [];

    var defendingTeam = getDefendingTeam(frame);
    if (defendingTeam == null) return [];

    var attackers = getTeamPlayerPositions(frame, defendingTeam === 1 ? 2 : 1);
    var defenders = getTeamPlayerPositions(frame, defendingTeam);
    var edges = [];
    var thresholdSq = thresholdMeters * thresholdMeters;
    var defendingGoalLineH = distanceThresholdOrientationFilter
        ? getTeamGoalLineH(frame, defendingTeam)
        : null;

    for (var i = 0; i < defenders.length; i++) {
        var defender = defenders[i];
        for (var j = 0; j < attackers.length; j++) {
            var attacker = attackers[j];
            if (getPitchDistanceSquared(defender.h, defender.v, attacker.h, attacker.v) > thresholdSq) {
                continue;
            }

            if (defendingGoalLineH != null &&
                isAttackerAheadOfDefender(defender, attacker, defendingGoalLineH)) {
                continue;
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

function setupDistanceMarking() {
    var slider = document.getElementById("distance_threshold_slider");
    if (!slider) return;

    setDistanceThresholdMeters(+slider.value);

    slider.addEventListener("input", function () {
        setDistanceThresholdMeters(+slider.value);
    });

    var orientationCheckbox = document.getElementById("distance_threshold_orientation_filter");
    if (orientationCheckbox) {
        distanceThresholdOrientationFilter = orientationCheckbox.checked;
        orientationCheckbox.addEventListener("change", function () {
            distanceThresholdOrientationFilter = orientationCheckbox.checked;
        });
    }
}
