var hungarianAttackerCount = 10;

function getHungarianMarkingEdges(frame, attackerCount) {
    if (!isBallTracked(frame)) return [];

    var defendingTeam = getDefendingTeam(frame);
    if (defendingTeam == null) return [];

    var defenders = getTeamPlayerPositions(frame, defendingTeam);
    var opponents = getTeamPlayerPositions(frame, defendingTeam === 1 ? 2 : 1);

    if (defenders.length === 0 || opponents.length === 0) return [];

    var count = attackerCount != null ? attackerCount : hungarianAttackerCount;
    var [ballH, ballV] = getBallPitchPosition(frame);
    var selectedAttackers = getClosestAttackers(opponents, ballH, ballV, count);

    if (selectedAttackers.length === 0) return [];

    var costMatrix = buildDefenderOpponentCostMatrix(defenders, selectedAttackers);
    var indices = computeMunkres(costMatrix);
    return indicesToMarkingEdges(indices, defenders, selectedAttackers);
}

function getBallPitchPosition(frame) {
    var dataLine = gameData.tracking[frame];
    var dataLine2 = gameData.tracking[frame + 1];
    var object1 = dataLine.objects[gameData.ballId];
    var object2 = dataLine2.objects[gameData.ballId] ?? object1;
    return getCoordinates(object1, object2);
}

function getClosestAttackers(attackers, h, v, count) {
    var ranked = [];
    for (var i = 0; i < attackers.length; i++) {
        var attacker = attackers[i];
        ranked.push({
            player: attacker,
            distSq: getPitchDistanceSquared(h, v, attacker.h, attacker.v),
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

function buildDefenderOpponentCostMatrix(defenders, opponents) {
    var costMatrix = [];
    for (var i = 0; i < defenders.length; i++) {
        costMatrix[i] = [];
        for (var j = 0; j < opponents.length; j++) {
            costMatrix[i][j] = getPitchDistanceSquared(
                defenders[i].h,
                defenders[i].v,
                opponents[j].h,
                opponents[j].v
            );
        }
    }
    return costMatrix;
}

function indicesToMarkingEdges(indices, defenders, opponents) {
    var edges = [];
    for (var k = 0; k < indices.length; k++) {
        var defIdx = indices[k][0];
        var oppIdx = indices[k][1];
        if (defIdx >= defenders.length || oppIdx >= opponents.length) continue;

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

function setupHungarianMarking() {
    var select = document.getElementById("hungarian_attacker_count_select");
    if (!select) return;

    setHungarianAttackerCount(+select.value);

    select.addEventListener("change", function () {
        setHungarianAttackerCount(+select.value);
    });
}
