var knnK = 1;
var knnAssignmentMode = "defender-to-attacker";

function getKnnMarkingEdges(frame, k) { //gets the knn marking edges for the given frame and k
    if (!isBallLive(frame)) return [];

    var defendingTeam = getDefendingTeam(frame);
    if (defendingTeam == null) return [];

    var attackers = getTeamPlayerPositions(frame, defendingTeam === 1 ? 2 : 1);
    var defenders = getTeamPlayerPositions(frame, defendingTeam);

    if (knnAssignmentMode === "both-all" || knnAssignmentMode === "both-mutual") {
        return getKnnBothMarkingEdges(defenders, attackers, k, frame, knnAssignmentMode === "both-mutual");
    }

    var attackerToDefender = knnAssignmentMode === "attacker-to-defender";
    var sources = attackerToDefender ? attackers : defenders;
    var targets = attackerToDefender ? defenders : attackers;
    var edges = [];

    addKnnEdgesForDefenders(sources, targets, k, edges, frame, !attackerToDefender);

    return edges;
}

function getKnnPairKey(defenderId, attackerId) {
    return String(defenderId) + ":" + String(attackerId);
}

function collectKnnBidirectionalPairs(defenders, attackers, k, frame, options) {
    // options.mode overrides knnAssignmentMode; options.ignoreOriented forces momentum/Euclidean ranking.
    options = options || {};
    var mode = options.mode != null ? options.mode : knnAssignmentMode;
    var collectOpts = options.ignoreOriented ? { ignoreOriented: true } : undefined;

    var defenderToAttacker = [];
    var attackerToDefender = [];

    addKnnEdgesForDefenders(defenders, attackers, k, defenderToAttacker, frame, true, collectOpts);
    addKnnEdgesForDefenders(attackers, defenders, k, attackerToDefender, frame, false, collectOpts);

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
    if (mode === "both-mutual") {
        for (var key in inDefenderToAttacker) {
            if (inAttackerToDefender[key]) {
                pairs[key] = true;
            }
        }
    } else if (mode === "attacker-to-defender") {
        for (var key in inAttackerToDefender) {
            pairs[key] = true;
        }
    } else if (mode === "defender-to-attacker") {
        for (var key in inDefenderToAttacker) {
            pairs[key] = true;
        }
    } else { // both-all
        for (var key in inDefenderToAttacker) {
            pairs[key] = true;
        }
        for (var key in inAttackerToDefender) {
            pairs[key] = true;
        }
    }
    return pairs;
}

function getKnnBidirectionalPairSet(frame, k) {
    if (!isBallLive(frame)) return null;

    var defendingTeam = getDefendingTeam(frame);
    if (defendingTeam == null) return null;

    var attackers = getTeamPlayerPositions(frame, defendingTeam === 1 ? 2 : 1);
    var defenders = getTeamPlayerPositions(frame, defendingTeam);
    return collectKnnBidirectionalPairs(defenders, attackers, k, frame);
}

function markingPairInKnnSet(pairSet, defender, attacker) {
    return pairSet != null &&
        pairSet[getKnnPairKey(String(defender.id), String(attacker.id))] === true;
}

function getKnnBothMarkingEdges(defenders, attackers, k, frame, mutualOnly) {
    var defenderToAttacker = [];
    var attackerToDefender = [];

    addKnnEdgesForDefenders(defenders, attackers, k, defenderToAttacker, frame, true);
    addKnnEdgesForDefenders(attackers, defenders, k, attackerToDefender, frame, false);

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
        var isMutual = inDefenderToAttacker[key] && inAttackerToDefender[key];
        if (mutualOnly && !isMutual) continue;
        var mergedEdge = edgeByKey[key];
        merged.push({
            x1: mergedEdge.x1,
            y1: mergedEdge.y1,
            x2: mergedEdge.x2,
            y2: mergedEdge.y2,
            dashed: !isMutual,
            defenderId: mergedEdge.defenderId,
            attackerId: mergedEdge.attackerId,
            lengthM: mergedEdge.lengthM,
        });
    }

    return merged;
}

function addKnnEdgesForDefenders(sources, targets, k, edges, frame, sourceIsDefender, options) {
    collectKnnOpponentEdges(sources, targets, k, function (player, opp) {
        var defender = sourceIsDefender ? player : opp;
        var attacker = sourceIsDefender ? opp : player;
        edges.push({
            x1: player.x,
            y1: player.y,
            x2: opp.x,
            y2: opp.y,
            sourceId: player.id,
            targetId: opp.id,
            defenderId: defender.id,
            attackerId: attacker.id,
            lengthM: getEuclideanPairDistance(defender, attacker),
        });
    }, sourceIsDefender, frame, options);
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

    if (typeof setupOrientedKnn === "function") {
        setupOrientedKnn();
    }
}
