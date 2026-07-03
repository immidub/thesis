var hungarianAttackerCount = 10;
var hungarianThresholdMeters = 15;
var hungarianAttackerSelectionMode = "nearest";
var hungarianBallRadiusMeters = 15;
var hungarianExcludeClosestAttackerToBall = false;
var hungarianProjectedPositions = false;

function getHungarianMarkingEdges(frame, attackerCount) {
    if (!isBallLive(frame)) return [];

    var defendingTeam = getDefendingTeam(frame);
    if (defendingTeam == null) return [];

    var defenders = getTeamPlayerPositions(frame, defendingTeam);
    var opponents = getTeamPlayerPositions(frame, defendingTeam === 1 ? 2 : 1);

    if (defenders.length === 0 || opponents.length === 0) return [];

    var selectedAttackers;
    if (hungarianAttackerSelectionMode === "ball-radius") {
        selectedAttackers = getAttackersWithinBallRadius(opponents, frame, hungarianBallRadiusMeters);
    } else {
        var count = attackerCount != null ? attackerCount : hungarianAttackerCount;
        selectedAttackers = getClosestAttackers(opponents, frame, count);
    }

    if (selectedAttackers.length === 0) return [];

    if (hungarianExcludeClosestAttackerToBall) {
        var closestAttacker = getClosestAttackerToBall(opponents, frame);
        if (closestAttacker != null) {
            var closestId = String(closestAttacker.id);
            var filteredAttackers = [];
            for (var a = 0; a < selectedAttackers.length; a++) {
                if (String(selectedAttackers[a].id) !== closestId) {
                    filteredAttackers.push(selectedAttackers[a]);
                }
            }
            selectedAttackers = filteredAttackers;
        }
    }

    if (selectedAttackers.length === 0) return [];

    var costMatrix = buildDefenderOpponentCostMatrix(defenders, selectedAttackers, hungarianProjectedPositions);
    var indices = computeMunkres(costMatrix);
    return indicesToMarkingEdges(
        indices,
        defenders,
        selectedAttackers,
        hungarianThresholdMeters,
        hungarianProjectedPositions
    );
}

function getClosestAttackers(attackers, frame, count) {
    var ranked = [];
    for (var i = 0; i < attackers.length; i++) {
        var attacker = attackers[i];
        ranked.push({
            player: attacker,
            distSq: attackerDistToBallSquared(attacker, frame),
        });
    }

    ranked.sort(function (a, b) {
        return a.distSq - b.distSq;
    });

    var n = Math.min(count, ranked.length);
    var selected = [];
    for (var j = 0; j < n; j++) {
        selected.push(ranked[j].player);
    }
    return selected;
}

function getAttackersWithinBallRadius(attackers, frame, radiusMeters) {
    var radiusSq = radiusMeters * radiusMeters;
    var selected = [];
    for (var i = 0; i < attackers.length; i++) {
        var attacker = attackers[i];
        if (attackerDistToBallSquared(attacker, frame) <= radiusSq) {
            selected.push(attacker);
        }
    }
    return selected;
}

function getClosestAttackerToBall(attackers, frame) {
    var closest = null;
    var bestDistSq = Infinity;

    for (var i = 0; i < attackers.length; i++) {
        var attacker = attackers[i];
        var distSq = attackerDistToBallSquared(attacker, frame);
        if (distSq < bestDistSq) {
            bestDistSq = distSq;
            closest = attacker;
        }
    }

    return closest;
}

function attackerDistToBallSquared(attacker, frame) {
    if (attacker.distToBall != null) {
        return attacker.distToBall * attacker.distToBall;
    }

    var ball = getBallPitchPosition(frame);
    if (!ball) return Infinity;
    return getPitchDistanceSquared(ball.h, ball.v, attacker.h, attacker.v);
}

function buildDefenderOpponentCostMatrix(defenders, opponents, useProjected) {
    var costMatrix = [];
    for (var i = 0; i < defenders.length; i++) {
        costMatrix[i] = [];
        for (var j = 0; j < opponents.length; j++) {
            costMatrix[i][j] = getMarkingPairDistanceSquared(
                defenders[i],
                opponents[j],
                useProjected
            );
        }
    }
    return costMatrix;
}

function indicesToMarkingEdges(indices, defenders, opponents, thresholdMeters, useProjected) {
    var thresholdSq = thresholdMeters * thresholdMeters;
    var edges = [];
    for (var k = 0; k < indices.length; k++) {
        var defIdx = indices[k][0];
        var oppIdx = indices[k][1];
        if (defIdx >= defenders.length || oppIdx >= opponents.length) continue;

        var distSq = getMarkingPairDistanceSquared(
            defenders[defIdx],
            opponents[oppIdx],
            useProjected
        );
        if (distSq > thresholdSq) continue;

        edges.push({
            x1: defenders[defIdx].x,
            y1: defenders[defIdx].y,
            x2: opponents[oppIdx].x,
            y2: opponents[oppIdx].y,
        });
    }
    return edges;
}

function setHungarianAttackerCount(value) {
    hungarianAttackerCount = value;
    var label = document.getElementById("hungarian_attacker_count_label");
    if (label) {
        label.textContent = "" + value;
    }
}

function setHungarianThresholdMeters(value) {
    hungarianThresholdMeters = value;
    var label = document.getElementById("hungarian_threshold_label");
    if (label) {
        label.textContent = value.toFixed(1);
    }
}

function setHungarianBallRadiusMeters(value) {
    hungarianBallRadiusMeters = value;
    var label = document.getElementById("hungarian_ball_radius_label");
    if (label) {
        label.textContent = value.toFixed(1);
    }
}

function updateHungarianAttackerSelectionControls() {
    var nearestControls = document.getElementById("hungarian_nearest_controls");
    var ballRadiusControls = document.getElementById("hungarian_ball_radius_controls");
    var isBallRadius = hungarianAttackerSelectionMode === "ball-radius";

    if (nearestControls) nearestControls.hidden = isBallRadius;
    if (ballRadiusControls) ballRadiusControls.hidden = !isBallRadius;
}

function setupHungarianMarking() {
    var select = document.getElementById("hungarian_attacker_count_select");
    if (!select) return;

    setHungarianAttackerCount(+select.value);

    select.addEventListener("change", function () {
        setHungarianAttackerCount(+select.value);
    });

    var slider = document.getElementById("hungarian_threshold_slider");
    if (slider) {
        setHungarianThresholdMeters(+slider.value);
        slider.addEventListener("input", function () {
            setHungarianThresholdMeters(+slider.value);
        });
    }

    var ballRadiusSlider = document.getElementById("hungarian_ball_radius_slider");
    if (ballRadiusSlider) {
        setHungarianBallRadiusMeters(+ballRadiusSlider.value);
        ballRadiusSlider.addEventListener("input", function () {
            setHungarianBallRadiusMeters(+ballRadiusSlider.value);
        });
    }

    var selectionRadios = document.querySelectorAll('input[name="hungarian_attacker_selection"]');
    selectionRadios.forEach(function (radio) {
        if (radio.checked) hungarianAttackerSelectionMode = radio.value;
        radio.addEventListener("change", function () {
            if (radio.checked) {
                hungarianAttackerSelectionMode = radio.value;
                updateHungarianAttackerSelectionControls();
            }
        });
    });

    var excludeClosestCheckbox = document.getElementById("hungarian_exclude_closest_attacker");
    if (excludeClosestCheckbox) {
        hungarianExcludeClosestAttackerToBall = excludeClosestCheckbox.checked;
        excludeClosestCheckbox.addEventListener("change", function () {
            hungarianExcludeClosestAttackerToBall = excludeClosestCheckbox.checked;
        });
    }

    var projectedCheckbox = document.getElementById("hungarian_projected_positions");
    if (projectedCheckbox) {
        hungarianProjectedPositions = projectedCheckbox.checked;
        projectedCheckbox.addEventListener("change", function () {
            hungarianProjectedPositions = projectedCheckbox.checked;
        });
    }

    updateHungarianAttackerSelectionControls();
}
