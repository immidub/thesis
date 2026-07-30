// Perfect matching (analysis PerfectMatchAssignment). File/vars keep "hungarian"
// as the historical Munkres wrapper name used by the viewer.

var hungarianEdgeRestriction = "none"; // "none" | "knn" | "delaunay"
var hungarianMaxLengthEnabled = false;
var hungarianMaxLengthMeters = 20;
var hungarianKnnK = 2;
var hungarianKnnMode = "both-all";

const HUNGARIAN_INFEASIBLE_COST = 1e15;
const HUNGARIAN_MAX_LENGTH_MIN_M = 10;
const HUNGARIAN_MAX_LENGTH_MAX_M = 50;

function getHungarianAllowedPairSet(frame) {
    // Matches analysis: optional max_length ∩ optional graph restrict.
    var hasMax = hungarianMaxLengthEnabled;
    var hasGraph = hungarianEdgeRestriction === "knn" || hungarianEdgeRestriction === "delaunay";
    if (!hasMax && !hasGraph) return null;

    var allowed = {
        maxLengthM: hasMax ? hungarianMaxLengthMeters : null,
        graphType: hasGraph ? hungarianEdgeRestriction : "none",
        pairs: null,
    };

    if (hungarianEdgeRestriction === "knn") {
        allowed.pairs = getHungarianKnnPairSet(frame);
    } else if (hungarianEdgeRestriction === "delaunay") {
        // Always plain Delaunay (analysis restrict="delaunay"), never shape prune.
        allowed.pairs = getAllOutfieldDelaunayOpponentPairSet(frame, {
            pruneShape: false,
            emptyOnMiss: true,
        });
    }

    return allowed;
}

function getHungarianKnnPairSet(frame) {
    // Own k / mode (defaults k=2, both-all). Momentum ranking; not oriented k-NN.
    var sides = getMarkingSides(frame);
    if (!sides) return null;
    return collectKnnBidirectionalPairs(
        sides.defenders,
        sides.attackers,
        hungarianKnnK,
        frame,
        {
            mode: hungarianKnnMode,
            ignoreOriented: true,
        }
    );
}

function markingPairAllowed(allowed, defender, attacker) {
    if (!allowed) return true;

    if (allowed.maxLengthM != null) {
        var maxSq = allowed.maxLengthM * allowed.maxLengthM;
        if (getMarkingPairDistanceSquared(defender, attacker) > maxSq) {
            return false;
        }
    }

    if (allowed.graphType === "knn") {
        return markingPairInKnnSet(allowed.pairs, defender, attacker);
    }
    if (allowed.graphType === "delaunay") {
        return markingPairInDelaunaySet(allowed.pairs, defender, attacker);
    }
    return true;
}

function getHungarianMarkingEdges(frame) {
    var sides = getMarkingSides(frame);
    if (!sides) return [];

    var defenders = sides.defenders;
    var opponents = sides.attackers;

    var allowedPairSet = getHungarianAllowedPairSet(frame);
    var costMatrix = buildDefenderOpponentCostMatrix(
        defenders,
        opponents,
        allowedPairSet
    );
    var munkresOptions = allowedPairSet ? { padValue: HUNGARIAN_INFEASIBLE_COST } : undefined;
    var indices = computeMunkres(costMatrix, munkresOptions);
    return indicesToMarkingEdges(
        indices,
        defenders,
        opponents,
        allowedPairSet,
        costMatrix
    );
}

function buildDefenderOpponentCostMatrix(defenders, opponents, allowedPairSet) {
    var costMatrix = [];
    var minCost = Infinity;
    for (var i = 0; i < defenders.length; i++) {
        costMatrix[i] = [];
        for (var j = 0; j < opponents.length; j++) {
            if (allowedPairSet && !markingPairAllowed(allowedPairSet, defenders[i], opponents[j])) {
                costMatrix[i][j] = HUNGARIAN_INFEASIBLE_COST;
                continue;
            }
            var cost = getMomentumPairCost(defenders[i], opponents[j]);
            costMatrix[i][j] = cost;
            if (cost < minCost) minCost = cost;
        }
    }
    // Munkres expects non-negative costs; shift d' when momentum makes some costs negative.
    if (Number.isFinite(minCost) && minCost < 0) {
        var shift = -minCost;
        for (var r = 0; r < costMatrix.length; r++) {
            for (var c = 0; c < costMatrix[r].length; c++) {
                if (costMatrix[r][c] < HUNGARIAN_INFEASIBLE_COST) {
                    costMatrix[r][c] += shift;
                }
            }
        }
    }
    return costMatrix;
}

function indicesToMarkingEdges(indices, defenders, opponents, allowedPairSet, costMatrix) {
    var edges = [];
    for (var k = 0; k < indices.length; k++) {
        var defIdx = indices[k][0];
        var oppIdx = indices[k][1];
        if (defIdx >= defenders.length || oppIdx >= opponents.length) continue;

        var defender = defenders[defIdx];
        var attacker = opponents[oppIdx];
        if (costMatrix[defIdx][oppIdx] >= HUNGARIAN_INFEASIBLE_COST) continue;
        if (allowedPairSet && !markingPairAllowed(allowedPairSet, defender, attacker)) continue;

        edges.push({
            x1: defender.x,
            y1: defender.y,
            x2: attacker.x,
            y2: attacker.y,
            defenderId: defender.id,
            attackerId: attacker.id,
            lengthM: getEuclideanPairDistance(defender, attacker),
        });
    }
    return edges;
}

//-------------------------------- setup functions --------------------------------//

function setHungarianMaxLengthMeters(value) {
    if (!Number.isFinite(value)) return;
    hungarianMaxLengthMeters = Math.min(
        HUNGARIAN_MAX_LENGTH_MAX_M,
        Math.max(HUNGARIAN_MAX_LENGTH_MIN_M, Math.round(value))
    );
    var label = document.getElementById("hungarian_max_length_label");
    if (label) {
        label.textContent = String(hungarianMaxLengthMeters);
    }
    var input = document.getElementById("hungarian_max_length_m");
    if (input && +input.value !== hungarianMaxLengthMeters) {
        input.value = String(hungarianMaxLengthMeters);
    }
}

function setHungarianMaxLengthEnabled(enabled) {
    hungarianMaxLengthEnabled = enabled;
    updateHungarianMaxLengthControls();
}

function updateHungarianMaxLengthControls() {
    var enabled = hungarianMaxLengthEnabled;
    var controls = document.getElementById("hungarian_max_length_controls");
    var input = document.getElementById("hungarian_max_length_m");

    if (controls) {
        controls.classList.toggle("pitch-control-subsection--passive", !enabled);
    }
    if (input) {
        input.disabled = !enabled;
    }
}

function setHungarianKnnK(value) {
    var k = Math.round(+value);
    if (!Number.isFinite(k) || k < 1) return;
    hungarianKnnK = k;
    var label = document.getElementById("hungarian_knn_k_label");
    if (label) label.textContent = String(hungarianKnnK);
    var select = document.getElementById("hungarian_knn_k_select");
    if (select && +select.value !== hungarianKnnK) {
        select.value = String(hungarianKnnK);
    }
}

function setHungarianKnnMode(mode) {
    hungarianKnnMode = mode;
}

function updateHungarianKnnControls() {
    var enabled = hungarianEdgeRestriction === "knn";
    var controls = document.getElementById("hungarian_knn_controls");
    var kSelect = document.getElementById("hungarian_knn_k_select");
    var modeSelect = document.getElementById("hungarian_knn_mode_select");

    if (controls) {
        controls.classList.toggle("pitch-control-subsection--passive", !enabled);
    }
    if (kSelect) kSelect.disabled = !enabled;
    if (modeSelect) modeSelect.disabled = !enabled;
}

function setupHungarianMarking() {
    var maxLengthCheckbox = document.getElementById("hungarian_max_length_enabled");
    if (maxLengthCheckbox) {
        setHungarianMaxLengthEnabled(maxLengthCheckbox.checked);
        maxLengthCheckbox.addEventListener("change", function () {
            setHungarianMaxLengthEnabled(maxLengthCheckbox.checked);
        });
    }

    var maxLengthInput = document.getElementById("hungarian_max_length_m");
    if (maxLengthInput) {
        setHungarianMaxLengthMeters(+maxLengthInput.value);
        maxLengthInput.addEventListener("input", function () {
            if (!hungarianMaxLengthEnabled) return;
            setHungarianMaxLengthMeters(+maxLengthInput.value);
        });
        maxLengthInput.addEventListener("change", function () {
            setHungarianMaxLengthMeters(+maxLengthInput.value);
        });
    }

    var edgeRestrictionRadios = document.querySelectorAll('input[name="hungarian_edge_restriction"]');
    edgeRestrictionRadios.forEach(function (radio) {
        if (radio.checked) hungarianEdgeRestriction = radio.value;
        radio.addEventListener("change", function () {
            if (radio.checked) {
                hungarianEdgeRestriction = radio.value;
                updateHungarianKnnControls();
            }
        });
    });

    var knnKSelect = document.getElementById("hungarian_knn_k_select");
    if (knnKSelect) {
        setHungarianKnnK(+knnKSelect.value);
        knnKSelect.addEventListener("change", function () {
            setHungarianKnnK(+knnKSelect.value);
        });
    }

    var knnModeSelect = document.getElementById("hungarian_knn_mode_select");
    if (knnModeSelect) {
        setHungarianKnnMode(knnModeSelect.value);
        knnModeSelect.addEventListener("change", function () {
            setHungarianKnnMode(knnModeSelect.value);
        });
    }

    updateHungarianMaxLengthControls();
    updateHungarianKnnControls();
}
