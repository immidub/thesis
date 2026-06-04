var knnK = 1;

function getKnnMarkingEdges(frame, k) {
    var team1 = getTeamPlayerPositions(frame, 1);
    var team2 = getTeamPlayerPositions(frame, 2);
    var edges = [];

    addKnnEdgesForTeam(team1, team2, k, edges);
    addKnnEdgesForTeam(team2, team1, k, edges);

    return edges;
}

function addKnnEdgesForTeam(team, opponents, k, edges) {
    for (var i = 0; i < team.length; i++) {
        var player = team[i];
        var distances = [];

        for (var j = 0; j < opponents.length; j++) {
            var opp = opponents[j];
            distances.push({
                opponent: opp,
                distSq: getPitchDistanceSquared(player.h, player.v, opp.h, opp.v),
            });
        }

        distances.sort(function (a, b) {
            return a.distSq - b.distSq;
        });

        var count = Math.min(k, distances.length);
        for (var n = 0; n < count; n++) {
            var opp = distances[n].opponent;
            edges.push({
                x1: player.x,
                y1: player.y,
                x2: opp.x,
                y2: opp.y,
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
}
