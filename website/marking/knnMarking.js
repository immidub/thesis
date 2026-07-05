var knnK = 1;
var knnAssignmentMode = "defender-to-attacker";

function getKnnMarkingEdges(frame, k) {
    if (!isBallLive(frame)) return [];

    var defendingTeam = getDefendingTeam(frame);
    if (defendingTeam == null) return [];

    var attackers = getTeamPlayerPositions(frame, defendingTeam === 1 ? 2 : 1);
    var defenders = getTeamPlayerPositions(frame, defendingTeam);

    if (knnAssignmentMode === "both") {
        return getKnnBothMarkingEdges(defenders, attackers, k, frame);
    }

    var attackerToDefender = knnAssignmentMode === "attacker-to-defender";
    var sources = attackerToDefender ? attackers : defenders;
    var targets = attackerToDefender ? defenders : attackers;
    var edges = [];

    addKnnEdgesForDefenders(sources, targets, k, edges, frame, !attackerToDefender);

    return edges;
}

function getKnnPairKey(defenderId, attackerId) {
    return defenderId + ":" + attackerId;
}

function getKnnBothMarkingEdges(defenders, attackers, k, frame) {
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

function addKnnEdgesForDefenders(sources, targets, k, edges, frame, sourceIsDefender) {
    for (var i = 0; i < sources.length; i++) {
        var player = sources[i];
        var distances = [];

        for (var j = 0; j < targets.length; j++) {
            var opp = targets[j];
            distances.push({
                opponent: opp,
                distSq: getMarkingPairDistanceSquared(player, opp, useProjectedPositions),
            });
        }

        distances.sort(function (a, b) {
            return a.distSq - b.distSq;
        });

        var count = Math.min(k, distances.length);
        for (var n = 0; n < count; n++) {
            var opp = distances[n].opponent;
            var defender = sourceIsDefender ? player : opp;
            var attacker = sourceIsDefender ? opp : player;
            if (!passesMarkingEdgeFilters(frame, defender, attacker)) {
                continue;
            }

            edges.push({
                x1: player.x,
                y1: player.y,
                x2: opp.x,
                y2: opp.y,
                sourceId: player.id,
                targetId: opp.id,
            });
        }
    }
}

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
}
