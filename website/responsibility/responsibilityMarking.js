// Marking edges: oriented mutual 2-NN (goal-side ranking), Delaunay-filtered,
// mutual-help zone only. Mirrors analysis oriented_knn with k=2, alpha=1.5,
// behind mode neutral.

const RESPONSIBILITY_MARKING_K = 2;
const RESPONSIBILITY_ORIENTED_ALPHA = 1.5;
const RESPONSIBILITY_ORIENTED_BEHIND = "neutral";

function collectOrientedKnnEdges(sources, targets, k, frame, sourceIsDefender, outEdges) {
    collectKnnOpponentEdges(
        sources,
        targets,
        k,
        function (player, opp) {
            var defender = sourceIsDefender ? player : opp;
            var attacker = sourceIsDefender ? opp : player;
            outEdges.push({
                defenderId: String(defender.id),
                attackerId: String(attacker.id),
                x1: defender.x,
                y1: defender.y,
                x2: attacker.x,
                y2: attacker.y,
            });
        },
        sourceIsDefender,
        frame
    );
}

function getResponsibilityMarkingEdges(frame, contestants, k) {
    var knnK = k != null ? k : RESPONSIBILITY_MARKING_K;
    if (!isBallLive(frame) || !contestants || contestants.length === 0) return [];

    var sides = getMarkingSides(frame);
    if (!sides) return [];

    // Step 1: oriented mutual 2-NN on defending / attacking sides.
    var defenderToAttacker = [];
    var attackerToDefender = [];
    collectOrientedKnnEdges(
        sides.defenders,
        sides.attackers,
        knnK,
        frame,
        true,
        defenderToAttacker
    );
    collectOrientedKnnEdges(
        sides.attackers,
        sides.defenders,
        knnK,
        frame,
        false,
        attackerToDefender
    );

    var inDefenderToAttacker = {};
    var inAttackerToDefender = {};
    var edgeByPairKey = {};

    for (var i = 0; i < defenderToAttacker.length; i++) {
        var edgeA = defenderToAttacker[i];
        var defKey = edgeA.defenderId + ":" + edgeA.attackerId;
        inDefenderToAttacker[defKey] = true;
        edgeByPairKey[getUndirectedPairKey(edgeA.defenderId, edgeA.attackerId)] = edgeA;
    }

    for (var j = 0; j < attackerToDefender.length; j++) {
        var edgeB = attackerToDefender[j];
        var attKey = edgeB.defenderId + ":" + edgeB.attackerId;
        inAttackerToDefender[attKey] = true;
        var pairKeyB = getUndirectedPairKey(edgeB.defenderId, edgeB.attackerId);
        if (!edgeByPairKey[pairKeyB]) {
            edgeByPairKey[pairKeyB] = edgeB;
        }
    }

    // Step 2: keep edges that pass all three filters.
    var delaunayPairs = getAllOutfieldDelaunayOpponentPairSet(frame);
    var zonePlayerIds = getMutualHelpZonePlayerIds(frame, contestants);
    var edges = [];

    for (var pairKey in edgeByPairKey) {
        var edge = edgeByPairKey[pairKey];
        var mutualKey = edge.defenderId + ":" + edge.attackerId;
        if (!inDefenderToAttacker[mutualKey] || !inAttackerToDefender[mutualKey]) continue;
        if (!delaunayPairs[pairKey]) continue;
        if (!zonePlayerIds[edge.defenderId] && !zonePlayerIds[edge.attackerId]) continue;

        edges.push({
            x1: edge.x1,
            y1: edge.y1,
            x2: edge.x2,
            y2: edge.y2,
        });
    }

    return edges;
}

function setupResponsibilityOrientedMarking() {
    if (typeof setKnnOrientedEnabled !== "function") return;
    setKnnOrientedEnabled(true);
    setKnnOrientedAlpha(RESPONSIBILITY_ORIENTED_ALPHA);
    setKnnOrientedBehindMode(RESPONSIBILITY_ORIENTED_BEHIND);
}
