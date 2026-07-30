var distanceThresholdMeters = 10;
var distanceThresholdDensityBased = false;

const DENSITY_THRESHOLD_SCALE = 1.5;
const DENSITY_THRESHOLD_MIN_M = 5;
const DENSITY_THRESHOLD_MAX_M = 15;

function computeFrameCompactnessMeters(defenders, attackers) {
    // Mean nearest-attacker distance across defenders (matches dynamic_threshold.py).
    if (defenders.length === 0 || attackers.length === 0) return 0;

    var sum = 0;
    for (var i = 0; i < defenders.length; i++) {
        var best = Infinity;
        for (var j = 0; j < attackers.length; j++) {
            var distSq = getMarkingPairDistanceSquared(
                defenders[i],
                attackers[j]
            );
            if (distSq < best) best = distSq;
        }
        sum += Math.sqrt(best);
    }
    return sum / defenders.length;
}

function densityThresholdForCompactness(compactnessM) {
    var raw = DENSITY_THRESHOLD_SCALE * compactnessM;
    return Math.min(
        Math.max(raw, DENSITY_THRESHOLD_MIN_M),
        DENSITY_THRESHOLD_MAX_M
    );
}

function updateDistanceThresholdLabel(value) {
    var label = document.getElementById("distance_threshold_label");
    if (label) {
        label.textContent = value.toFixed(1);
    }
}

function getDistanceMarkingEdges(frame, thresholdMeters) {
    var sides = getMarkingSides(frame);
    if (!sides) return [];

    var defenders = sides.defenders;
    var attackers = sides.attackers;

    var threshold = thresholdMeters;
    if (distanceThresholdDensityBased) {
        // Matches analysis DynamicThresholdAssignment (Euclidean compactness + clip).
        var compactness = computeFrameCompactnessMeters(defenders, attackers);
        threshold = densityThresholdForCompactness(compactness);
        updateDistanceThresholdLabel(threshold);
        var slider = document.getElementById("distance_threshold_slider");
        if (slider) slider.value = String(threshold);
    }

    var edges = [];
    for (var i = 0; i < defenders.length; i++) {
        var defender = defenders[i];
        for (var j = 0; j < attackers.length; j++) {
            var attacker = attackers[j];
            // Density: Euclidean only. Fixed threshold: d' when momentum is on.
            var cost = distanceThresholdDensityBased
                ? getEuclideanPairDistance(defender, attacker)
                : getMomentumPairCost(defender, attacker);
            if (cost > threshold) continue;

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
    }

    return edges;
}

function setDistanceThresholdMeters(value) {
    distanceThresholdMeters = value;
    updateDistanceThresholdLabel(value);
}

function updateDensityMomentumNote() {
    var note = document.getElementById("distance_density_momentum_note");
    if (!note) return;
    var show =
        distanceThresholdDensityBased &&
        typeof momentumDistanceEnabled !== "undefined" &&
        momentumDistanceEnabled;
    note.hidden = !show;
}

function setDistanceThresholdDensityBased(enabled) {
    distanceThresholdDensityBased = enabled;

    var slider = document.getElementById("distance_threshold_slider");
    if (slider) {
        slider.disabled = enabled;
        if (!enabled) {
            slider.value = String(distanceThresholdMeters);
            updateDistanceThresholdLabel(distanceThresholdMeters);
        }
    }
    updateDensityMomentumNote();
}

function setupDistanceMarking() {
    var slider = document.getElementById("distance_threshold_slider");
    if (!slider) return;

    setDistanceThresholdMeters(+slider.value);

    slider.addEventListener("input", function () {
        if (distanceThresholdDensityBased) return;
        setDistanceThresholdMeters(+slider.value);
    });

    var densityCheckbox = document.getElementById("distance_threshold_density_based");
    if (densityCheckbox) {
        setDistanceThresholdDensityBased(densityCheckbox.checked);
        densityCheckbox.addEventListener("change", function () {
            setDistanceThresholdDensityBased(densityCheckbox.checked);
        });
    }

    updateDensityMomentumNote();
}
