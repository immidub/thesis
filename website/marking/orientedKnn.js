// Oriented (goal-side) ranking cost for k-NN — mirrors analysis/assignments/oriented_knn.py.
// When enabled, k-NN ranks by anisotropic cost toward the defended goal and ignores
// global momentum (oriented_knn in analysis has no momentum_lambda).

var knnOrientedEnabled = false;
var knnOrientedAlpha = 2.0;
var knnOrientedBehindMode = "neutral"; // "neutral" | "penalize"

const ORIENTED_ALPHA_MIN = 1;
const ORIENTED_ALPHA_MAX = 3;
const ORIENTED_ALPHA_DEFAULT = 2;
const ORIENTED_EPS = 1e-9;

function getDefendedGoalPitch(frame) {
    // Goal centre defended by the team without possession (matches former getTeamGoalLineH).
    var defendingTeam = getDefendingTeam(frame);
    if (defendingTeam == null) return null;

    var halfLength = gameData.pitch.length / 2;
    var homeAttacksRight = getHomeAttacksRight(frame);
    var goalH;
    if (defendingTeam === 1) {
        goalH = homeAttacksRight ? halfLength : -halfLength;
    } else {
        goalH = homeAttacksRight ? -halfLength : halfLength;
    }
    return { h: goalH, v: 0 };
}

function getOrientedPairCost(defender, attacker, goal, alpha, behindMode) {
    // Anisotropic cost in pitch (h, v); ellipse stretched toward defended goal.
    var ah = attacker.h;
    var av = attacker.v;
    var toGoalH = goal.h - ah;
    var toGoalV = goal.v - av;
    var goalDist = Math.sqrt(toGoalH * toGoalH + toGoalV * toGoalV);

    var dh = defender.h - ah;
    var dv = defender.v - av;
    var distSq = dh * dh + dv * dv;
    var dist = Math.sqrt(distSq);

    if (goalDist < ORIENTED_EPS) return dist;

    var uh = toGoalH / goalDist;
    var uv = toGoalV / goalDist;
    var rPar = dh * uh + dv * uv;
    var rPerpSq = Math.max(distSq - rPar * rPar, 0);
    var behindScale = behindMode === "penalize" ? 1 / alpha : 1;
    var scale = rPar > 0 ? alpha : behindScale;
    return Math.sqrt((rPar / scale) * (rPar / scale) + rPerpSq);
}

function getKnnPairRankingCost(source, target, sourceIsDefender, frame) {
    var defender = sourceIsDefender ? source : target;
    var attacker = sourceIsDefender ? target : source;

    if (knnOrientedEnabled) {
        var goal = getDefendedGoalPitch(frame);
        if (goal == null) {
            return Math.sqrt(getMarkingPairDistanceSquared(defender, attacker));
        }
        return getOrientedPairCost(
            defender,
            attacker,
            goal,
            knnOrientedAlpha,
            knnOrientedBehindMode
        );
    }

    if (typeof getMomentumPairCost === "function") {
        return getMomentumPairCost(defender, attacker);
    }
    return Math.sqrt(getMarkingPairDistanceSquared(defender, attacker));
}

function updateOrientedKnnControls() {
    var enabled = knnOrientedEnabled;
    var controls = document.getElementById("knn_oriented_controls");
    var alphaSlider = document.getElementById("knn_oriented_alpha_slider");
    var behindSelect = document.getElementById("knn_oriented_behind_select");
    var momentumNote = document.getElementById("knn_oriented_momentum_note");

    if (controls) {
        controls.classList.toggle("pitch-control-subsection--passive", !enabled);
    }
    if (alphaSlider) alphaSlider.disabled = !enabled;
    if (behindSelect) behindSelect.disabled = !enabled;
    if (momentumNote) {
        var showNote = enabled && typeof momentumDistanceEnabled !== "undefined" && momentumDistanceEnabled;
        momentumNote.hidden = !showNote;
    }
}

function setKnnOrientedAlpha(value) {
    if (!Number.isFinite(value)) return;
    knnOrientedAlpha = Math.min(
        ORIENTED_ALPHA_MAX,
        Math.max(ORIENTED_ALPHA_MIN, value)
    );
    var label = document.getElementById("knn_oriented_alpha_label");
    if (label) label.textContent = knnOrientedAlpha.toFixed(1);
    var slider = document.getElementById("knn_oriented_alpha_slider");
    if (slider && +slider.value !== knnOrientedAlpha) {
        slider.value = String(knnOrientedAlpha);
    }
}

function setKnnOrientedEnabled(enabled) {
    knnOrientedEnabled = enabled;
    updateOrientedKnnControls();
}

function setKnnOrientedBehindMode(mode) {
    knnOrientedBehindMode = mode === "penalize" ? "penalize" : "neutral";
}

function setupOrientedKnn() {
    var checkbox = document.getElementById("knn_oriented_enabled");
    if (checkbox) {
        setKnnOrientedEnabled(checkbox.checked);
        checkbox.addEventListener("change", function () {
            setKnnOrientedEnabled(checkbox.checked);
        });
    }

    var alphaSlider = document.getElementById("knn_oriented_alpha_slider");
    if (alphaSlider) {
        setKnnOrientedAlpha(+alphaSlider.value);
        alphaSlider.addEventListener("input", function () {
            if (!knnOrientedEnabled) return;
            setKnnOrientedAlpha(+alphaSlider.value);
        });
    }

    var behindSelect = document.getElementById("knn_oriented_behind_select");
    if (behindSelect) {
        setKnnOrientedBehindMode(behindSelect.value);
        behindSelect.addEventListener("change", function () {
            setKnnOrientedBehindMode(behindSelect.value);
        });
    }

    updateOrientedKnnControls();
}
