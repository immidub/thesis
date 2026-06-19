var knnK = 1;

function getKnnMarkingEdges(frame, k) {
    if (!isBallLive(frame)) return [];

    var defendingTeam = getDefendingTeam(frame);
    if (defendingTeam == null) return [];

    var opponents = getTeamPlayerPositions(frame, defendingTeam === 1 ? 2 : 1);
    var defenders = getTeamPlayerPositions(frame, defendingTeam);
    var edges = [];

    for (var i = 0; i < defenders.length; i++) {
        var defenderEdges = getKnnEdges(defenders[i], opponents, k);
        for (var j = 0; j < defenderEdges.length; j++) {
            edges.push(defenderEdges[j]);
        }
    }

    return edges;
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
}
