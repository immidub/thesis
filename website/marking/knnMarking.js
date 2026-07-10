var knnK = 1;
var knnAssignmentMode = "defender-to-attacker";
var knnHideDashedEdges = false;
var knnDelaunayOpponentsOnly = false;

function filterKnnEdges(edges) {
    if (!knnHideDashedEdges) return edges;
    return edges.filter(function (edge) {
        return !edge.dashed;
    });
}

function getKnnMarkingEdges(frame, k) { //gets the knn marking edges for the given frame and k
    if (!isBallLive(frame)) return [];

    var defendingTeam = getDefendingTeam(frame);
    if (defendingTeam == null) return [];

    var attackers = getTeamPlayerPositions(frame, defendingTeam === 1 ? 2 : 1);
    var defenders = getTeamPlayerPositions(frame, defendingTeam);
    var delaunayPairSet = knnDelaunayOpponentsOnly ? getDelaunayOpponentPairSet(frame) : null; //gets the delaunay opponent pair set for the given frame

    if (knnAssignmentMode === "both") {
        return filterKnnEdges(getKnnBothMarkingEdges(defenders, attackers, k, frame, delaunayPairSet));
    }

    var attackerToDefender = knnAssignmentMode === "attacker-to-defender";
    var sources = attackerToDefender ? attackers : defenders;
    var targets = attackerToDefender ? defenders : attackers;
    var edges = [];

    addKnnEdgesForDefenders(sources, targets, k, edges, frame, !attackerToDefender, delaunayPairSet);

    return filterKnnEdges(edges);
}

function getKnnPairKey(defenderId, attackerId) {
    return String(defenderId) + ":" + String(attackerId);
}

function collectKnnBidirectionalPairs(defenders, attackers, k, frame) { // used to collect the bidirectional pairs for the knn algorithm
    var defenderToAttacker = [];
    var attackerToDefender = [];

    addKnnEdgesForDefenders(defenders, attackers, k, defenderToAttacker, frame, true);
    addKnnEdgesForDefenders(attackers, defenders, k, attackerToDefender, frame, false);

    var inDefenderToAttacker = {};
    var inAttackerToDefender = {};

    for (var i = 0; i < defenderToAttacker.length; i++) {
        var edge = defenderToAttacker[i];
        inDefenderToAttacker[getKnnPairKey(edge.sourceId, edge.targetId)] = true;
    }
    for (var j = 0; j < attackerToDefender.length; j++) {
        var reverseEdge = attackerToDefender[j];
        inAttackerToDefender[getKnnPairKey(reverseEdge.targetId, reverseEdge.sourceId)] = true;
    }

    var pairs = {};
    if (knnHideDashedEdges) {
        for (var key in inDefenderToAttacker) {
            if (inAttackerToDefender[key]) {
                pairs[key] = true;
            }
        }
    } else {
        for (var key in inDefenderToAttacker) {
            pairs[key] = true;
        }
        for (var key in inAttackerToDefender) {
            pairs[key] = true;
        }
    }
    return pairs;
}

function getKnnBidirectionalPairSet(frame, k) { //gets the bidirectional pair set for the given frame and k for hungarian marking
    if (!isBallLive(frame)) return null;

    var defendingTeam = getDefendingTeam(frame);
    if (defendingTeam == null) return null;

    var attackers = getTeamPlayerPositions(frame, defendingTeam === 1 ? 2 : 1);
    var defenders = getTeamPlayerPositions(frame, defendingTeam);
    return collectKnnBidirectionalPairs(defenders, attackers, k, frame);
}

function markingPairInKnnSet(pairSet, defender, attacker) { //used to check if the pair is in the knn set
    return pairSet != null &&
        pairSet[getKnnPairKey(String(defender.id), String(attacker.id))] === true;
}

function getKnnBothMarkingEdges(defenders, attackers, k, frame, delaunayPairSet) { //gets the both marking edges for the given defenders, attackers, k, frame and delaunay pair set
    var defenderToAttacker = [];
    var attackerToDefender = [];

    addKnnEdgesForDefenders(defenders, attackers, k, defenderToAttacker, frame, true, delaunayPairSet);
    addKnnEdgesForDefenders(attackers, defenders, k, attackerToDefender, frame, false, delaunayPairSet);

    var inDefenderToAttacker = {};
    var inAttackerToDefender = {};
    var edgeByKey = {};

    for (var i = 0; i < defenderToAttacker.length; i++) {
        var edge = defenderToAttacker[i];
        var key = getKnnPairKey(edge.sourceId, edge.targetId);
        inDefenderToAttacker[key] = true;
        edgeByKey[key] = edge;
    }

    for (var j = 0; j < attackerToDefender.length; j++) {
        var reverseEdge = attackerToDefender[j];
        var reverseKey = getKnnPairKey(reverseEdge.targetId, reverseEdge.sourceId);
        inAttackerToDefender[reverseKey] = true;
        if (!edgeByKey[reverseKey]) {
            edgeByKey[reverseKey] = reverseEdge;
        }
    }

    var merged = [];
    for (var key in edgeByKey) {
        var mergedEdge = edgeByKey[key];
        merged.push({
            x1: mergedEdge.x1,
            y1: mergedEdge.y1,
            x2: mergedEdge.x2,
            y2: mergedEdge.y2,
            dashed: !(inDefenderToAttacker[key] && inAttackerToDefender[key]),
        });
    }

    return merged;
}

function addKnnEdgesForDefenders(sources, targets, k, edges, frame, sourceIsDefender, delaunayPairSet) { //runs knn + filters + pushes edges to the array
    collectKnnOpponentEdges(sources, targets, k, useProjectedPositions, function (player, opp) {
        var defender = sourceIsDefender ? player : opp;
        var attacker = sourceIsDefender ? opp : player;
        if (!passesMarkingEdgeFilters(frame, defender, attacker)) {
            return;
        }
        if (delaunayPairSet && !markingPairInDelaunaySet(delaunayPairSet, defender, attacker)) {
            return;
        }

        edges.push({
            x1: player.x,
            y1: player.y,
            x2: opp.x,
            y2: opp.y,
            sourceId: player.id,
            targetId: opp.id,
        });
    });
}

//-------------------------------- setup functions --------------------------------//

function setKnnK(value) {
    knnK = value;
    var label = document.getElementById("knn_k_label");
    if (label) {
        label.textContent = "" + value;
    }
}

function setupKnnMarking() {
    var select = document.getElementById("knn_k_select");
    if (!select) return;

    setKnnK(+select.value);

    select.addEventListener("change", function () {
        setKnnK(+select.value);
    });

    var modeSelect = document.getElementById("knn_assignment_mode_select");
    if (modeSelect) {
        knnAssignmentMode = modeSelect.value;
        modeSelect.addEventListener("change", function () {
            knnAssignmentMode = modeSelect.value;
        });
    }

    var hideDashedCheckbox = document.getElementById("knn_hide_dashed_edges");
    if (hideDashedCheckbox) {
        knnHideDashedEdges = hideDashedCheckbox.checked;
        hideDashedCheckbox.addEventListener("change", function () {
            knnHideDashedEdges = hideDashedCheckbox.checked;
        });
    }

    var delaunayCheckbox = document.getElementById("knn_delaunay_opponents_only");
    if (delaunayCheckbox) {
        knnDelaunayOpponentsOnly = delaunayCheckbox.checked;
        delaunayCheckbox.addEventListener("change", function () {
            knnDelaunayOpponentsOnly = delaunayCheckbox.checked;
        });
    }
}
