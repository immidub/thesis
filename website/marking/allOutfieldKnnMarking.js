var allOutfieldKnnK = 1;
var allOutfieldKnnOpponentsOnly = false;

function getAllOutfieldKnnEdges(frame, k) {
    if (!isBallLive(frame)) return [];

    var built = buildAllOutfieldPlayers(frame);
    if (!built) return [];

    var players = built.players;
    var edges = [];

    for (var i = 0; i < players.length; i++) {
        var player = players[i];
        var distances = [];

        for (var j = 0; j < players.length; j++) {
            if (i === j) continue;
            var other = players[j];
            distances.push({
                other: other,
                distSq: getMarkingPairDistanceSquared(player, other, useProjectedPositions),
            });
        }

        distances.sort(function (a, b) {
            return a.distSq - b.distSq;
        });

        var count = Math.min(k, distances.length);
        for (var n = 0; n < count; n++) {
            var neighbor = distances[n].other;
            if (allOutfieldKnnOpponentsOnly && player.team === neighbor.team) continue;
            if (!passesGraphEdgePairFilter(frame, player, neighbor)) continue;
            edges.push({
                x1: player.x,
                y1: player.y,
                x2: neighbor.x,
                y2: neighbor.y,
            });
        }
    }

    return edges;
}

function setAllOutfieldKnnK(value) {
    allOutfieldKnnK = value;
    var label = document.getElementById("all_outfield_knn_k_label");
    if (label) {
        label.textContent = "" + value;
    }
}

function setupAllOutfieldKnnMarking() {
    var select = document.getElementById("all_outfield_knn_k_select");
    if (!select) return;

    setAllOutfieldKnnK(+select.value);

    select.addEventListener("change", function () {
        setAllOutfieldKnnK(+select.value);
    });

    var opponentsOnlyCheckbox = document.getElementById("all_outfield_knn_opponents_only");
    if (opponentsOnlyCheckbox) {
        allOutfieldKnnOpponentsOnly = opponentsOnlyCheckbox.checked;
        opponentsOnlyCheckbox.addEventListener("change", function () {
            allOutfieldKnnOpponentsOnly = opponentsOnlyCheckbox.checked;
        });
    }
}
