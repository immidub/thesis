var knnK = 1;
var knnAssignmentMode = "defender-to-attacker";

function getKnnMarkingEdges(frame, k) {
    var sides = getMarkingSides(frame);
    if (!sides) return [];

    var defenders = sides.defenders;
    var attackers = sides.attackers;

    if (knnAssignmentMode === "both-all" || knnAssignmentMode === "both-mutual") {
        return getKnnBothMarkingEdges(
            defenders,
            attackers,
            k,
            frame,
            knnAssignmentMode === "both-mutual"
        );
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

function buildKnnDirectionMaps(defenders, attackers, k, frame, options) {
    // Shared D→A / A→D edge lists and key maps for both drawing and allow-lists.
    options = options || {};
    var collectOpts = options.ignoreOriented ? { ignoreOriented: true } : undefined;

    var defenderToAttacker = [];
    var attackerToDefender = [];
    addKnnEdgesForDefenders(defenders, attackers, k, defenderToAttacker, frame, true, collectOpts);
    addKnnEdgesForDefenders(attackers, defenders, k, attackerToDefender, frame, false, collectOpts);

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

    return {
        inDefenderToAttacker: inDefenderToAttacker,
        inAttackerToDefender: inAttackerToDefender,
        edgeByKey: edgeByKey,
    };
}

function pairSetFromKnnDirectionMaps(maps, mode) {
    var pairs = {};
    var inDef = maps.inDefenderToAttacker;
    var inAtt = maps.inAttackerToDefender;

    if (mode === "both-mutual") {
        for (var key in inDef) {
            if (inAtt[key]) pairs[key] = true;
        }
    } else if (mode === "attacker-to-defender") {
        for (var keyA in inAtt) pairs[keyA] = true;
    } else if (mode === "defender-to-attacker") {
        for (var keyD in inDef) pairs[keyD] = true;
    } else { // both-all
        for (var keyBoth in inDef) pairs[keyBoth] = true;
        for (var keyBothA in inAtt) pairs[keyBothA] = true;
    }
    return pairs;
}

function collectKnnBidirectionalPairs(defenders, attackers, k, frame, options) {
    // options.mode overrides knnAssignmentMode; options.ignoreOriented forces momentum/Euclidean ranking.
    options = options || {};
    var mode = options.mode != null ? options.mode : knnAssignmentMode;
    var maps = buildKnnDirectionMaps(defenders, attackers, k, frame, options);
    return pairSetFromKnnDirectionMaps(maps, mode);
}

function markingPairInKnnSet(pairSet, defender, attacker) {
    return pairSet != null &&
        pairSet[getKnnPairKey(String(defender.id), String(attacker.id))] === true;
}

function getKnnBothMarkingEdges(defenders, attackers, k, frame, mutualOnly) {
    var maps = buildKnnDirectionMaps(defenders, attackers, k, frame);
    var merged = [];
    for (var key in maps.edgeByKey) {
        var isMutual =
            maps.inDefenderToAttacker[key] && maps.inAttackerToDefender[key];
        if (mutualOnly && !isMutual) continue;
        var mergedEdge = maps.edgeByKey[key];
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
    if (label) label.textContent = "" + value;
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

    setupOrientedKnn();
}
