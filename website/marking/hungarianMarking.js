var hungarianAttackerCount = 10;
var hungarianAttackerSelectionMode = "nearest";
var hungarianBallRadiusMeters = 15;
var hungarianExcludeClosestAttackerToBall = false;
var hungarianEdgeRestriction = "none";

const HUNGARIAN_INFEASIBLE_COST = 1e15; //used to mark infeasible pairs in the cost matrix

function getHungarianAllowedPairSet(frame) { //gets the allowed pair set for the given frame
    if (hungarianEdgeRestriction === "knn") {
        return {
            type: "knn",
            pairs: getKnnBidirectionalPairSet(frame, knnK),
        };
    }
    if (hungarianEdgeRestriction === "delaunay") {
        return {
            type: "delaunay",
            pairs: getDelaunayOpponentPairSet(frame),
        };
    }
    return null;
}

function markingPairAllowed(allowed, defender, attacker) { //used to check if the pair is allowed for the given allowed pair set
    if (!allowed || !allowed.pairs) return true;
    if (allowed.type === "knn") {
        return markingPairInKnnSet(allowed.pairs, defender, attacker);
    }
    if (allowed.type === "delaunay") {
        return markingPairInDelaunaySet(allowed.pairs, defender, attacker);
    }
    return true;
}

function getHungarianMarkingEdges(frame, attackerCount) { //main function for hungarian marking
    if (!isBallLive(frame)) return [];

    var defendingTeam = getDefendingTeam(frame);
    if (defendingTeam == null) return [];

    var defenders = getTeamPlayerPositions(frame, defendingTeam);
    var opponents = getTeamPlayerPositions(frame, defendingTeam === 1 ? 2 : 1);

    if (defenders.length === 0 || opponents.length === 0) return [];

    var selectedAttackers;
    if (hungarianAttackerSelectionMode === "ball-radius") { //gets the attackers within the ball radius
        selectedAttackers = getAttackersWithinBallRadius(opponents, frame, hungarianBallRadiusMeters);
    } else {
        var count = attackerCount != null ? attackerCount : hungarianAttackerCount; //gets the closest attackers
        selectedAttackers = getClosestAttackers(opponents, frame, count);
    }

    if (selectedAttackers.length === 0) return [];

    if (hungarianExcludeClosestAttackerToBall) { //excludes the closest attacker to the ball
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

    var allowedPairSet = getHungarianAllowedPairSet(frame); //gets the allowed pair set
    var costMatrix = buildDefenderOpponentCostMatrix( //builds the cost matrix
        defenders,
        selectedAttackers,
        useProjectedPositions,
        allowedPairSet
    );
    var munkresOptions = allowedPairSet ? { padValue: HUNGARIAN_INFEASIBLE_COST } : undefined; //sets the padding value for the cost matrix
    var indices = computeMunkres(costMatrix, munkresOptions); //computes the munkres algorithm
    return indicesToMarkingEdges( //converts the indices to marking edges
        indices,
        defenders,
        selectedAttackers,
        frame,
        allowedPairSet,
        costMatrix
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

function buildDefenderOpponentCostMatrix(defenders, opponents, useProjected, allowedPairSet) {
    var costMatrix = [];
    for (var i = 0; i < defenders.length; i++) {
        costMatrix[i] = [];
        for (var j = 0; j < opponents.length; j++) {
            if (allowedPairSet && !markingPairAllowed(allowedPairSet, defenders[i], opponents[j])) {
                costMatrix[i][j] = HUNGARIAN_INFEASIBLE_COST;
                continue;
            }
            costMatrix[i][j] = getMarkingPairDistanceSquared(
                defenders[i],
                opponents[j],
                useProjected
            );
        }
    }
    return costMatrix;
}

function indicesToMarkingEdges(indices, defenders, opponents, frame, allowedPairSet, costMatrix) {
    var edges = [];
    for (var k = 0; k < indices.length; k++) {
        var defIdx = indices[k][0];
        var oppIdx = indices[k][1];
        if (defIdx >= defenders.length || oppIdx >= opponents.length) continue;

        var defender = defenders[defIdx];
        var attacker = opponents[oppIdx];
        if (costMatrix[defIdx][oppIdx] >= HUNGARIAN_INFEASIBLE_COST) continue;
        if (allowedPairSet && !markingPairAllowed(allowedPairSet, defender, attacker)) continue;
        if (!passesMarkingEdgeFilters(frame, defender, attacker)) continue;

        edges.push({
            x1: defender.x,
            y1: defender.y,
            x2: attacker.x,
            y2: attacker.y,
        });
    }
    return edges;
}

//-------------------------------- setup functions --------------------------------//

function setHungarianAttackerCount(value) {
    hungarianAttackerCount = value;
    var label = document.getElementById("hungarian_attacker_count_label");
    if (label) {
        label.textContent = "" + value;
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

    var edgeRestrictionRadios = document.querySelectorAll('input[name="hungarian_edge_restriction"]');
    edgeRestrictionRadios.forEach(function (radio) {
        if (radio.checked) hungarianEdgeRestriction = radio.value;
        radio.addEventListener("change", function () {
            if (radio.checked) hungarianEdgeRestriction = radio.value;
        });
    });

    updateHungarianAttackerSelectionControls();
}
