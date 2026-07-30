// Distance model: momentum-adjusted ranking/matching cost
// (mirrors analysis/assignments/momentum.py).
// d' = d - λ * v_towards, with v_towards = (v_def - v_att) · u_def→att.
// Drawn edge geometry stays Euclidean; only ranking / threshold / matching use d'.
// Pitch velocities use h = -speed·cos(direction) to match getCoordinates mirroring.

var momentumDistanceEnabled = false;
var momentumLambda = 1.0;
var showVelocityArrows = false;

const MOMENTUM_LAMBDA_MIN = 0;
const MOMENTUM_LAMBDA_MAX = 2;
const MOMENTUM_LAMBDA_DEFAULT = 1.0;
const MOMENTUM_EPS = 1e-12;
const VELOCITY_ARROW_MAX_M = 10;
const VELOCITY_ARROW_SPEED_SCALE = 1.2;
const VELOCITY_ARROW_MIN_M = 2.5;

function getEffectiveMomentumLambda() {
    return momentumDistanceEnabled ? momentumLambda : 0;
}

function playerVelocityPitch(player) {
    // Pitch-space velocity matching getCoordinates mirroring: h = -raw_x.
    if (player.speed == null || player.direction == null || player.speed <= 0) {
        return { h: 0, v: 0 };
    }
    var rad = (player.direction * Math.PI) / 180;
    return {
        h: -player.speed * Math.cos(rad),
        v: player.speed * Math.sin(rad),
    };
}

function getEuclideanPairDistance(playerA, playerB) {
    return Math.sqrt(getMarkingPairDistanceSquared(playerA, playerB));
}

function getMomentumPairCost(defender, attacker) {
    // Ranking / matching cost d' for a defender→attacker pair.
    var dh = attacker.h - defender.h;
    var dv = attacker.v - defender.v;
    var dist = Math.sqrt(dh * dh + dv * dv);
    var lam = getEffectiveMomentumLambda();
    if (lam === 0 || dist < MOMENTUM_EPS) return dist;

    var inv = 1 / dist;
    var uh = dh * inv;
    var uv = dv * inv;
    var vDef = playerVelocityPitch(defender);
    var vAtt = playerVelocityPitch(attacker);
    var vTowards = (vDef.h - vAtt.h) * uh + (vDef.v - vAtt.v) * uv;
    return dist - lam * vTowards;
}

function getDirectedRankingCost(source, target, sourceIsDefender) {
    // kNN may run attacker→defender; cost is always defined on defender→attacker.
    var defender = sourceIsDefender ? source : target;
    var attacker = sourceIsDefender ? target : source;
    return getMomentumPairCost(defender, attacker);
}

function updateMomentumLambdaControls() {
    var enabled = momentumDistanceEnabled;
    var controls = document.getElementById("momentum_lambda_controls");
    var slider = document.getElementById("momentum_lambda_slider");

    if (controls) {
        controls.classList.toggle("distance-model-controls--passive", !enabled);
    }
    if (slider) {
        slider.disabled = !enabled;
    }
}

function setMomentumLambda(value) {
    if (!Number.isFinite(value)) return;
    momentumLambda = Math.min(
        MOMENTUM_LAMBDA_MAX,
        Math.max(MOMENTUM_LAMBDA_MIN, value)
    );
    var label = document.getElementById("momentum_lambda_label");
    if (label) {
        label.textContent = momentumLambda.toFixed(1);
    }
    var slider = document.getElementById("momentum_lambda_slider");
    if (slider && +slider.value !== momentumLambda) {
        slider.value = String(momentumLambda);
    }
}

function setMomentumDistanceEnabled(enabled) {
    momentumDistanceEnabled = enabled;
    updateMomentumLambdaControls();
    if (typeof updateOrientedKnnControls === "function") {
        updateOrientedKnnControls();
    }
    if (typeof updateDensityMomentumNote === "function") {
        updateDensityMomentumNote();
    }
}

function setShowVelocityArrows(enabled) {
    showVelocityArrows = enabled;
}

function drawVelocityArrows(frame) {
    if (!showVelocityArrows || !isBallLive(frame)) return;

    var players = getTeamPlayerPositions(frame, 1).concat(
        getTeamPlayerPositions(frame, 2)
    );
    if (players.length === 0) return;

    var ctx = gameCanvas.ctx;
    var prevStroke = ctx.strokeStyle;
    var prevFill = ctx.fillStyle;
    var prevWidth = ctx.lineWidth;
    var prevDash = ctx.getLineDash();

    ctx.strokeStyle = "#374151";
    ctx.fillStyle = "#374151";
    ctx.lineWidth = 2.5;
    ctx.setLineDash([]);

    for (var i = 0; i < players.length; i++) {
        var player = players[i];
        var vel = playerVelocityPitch(player);
        var speed = Math.sqrt(vel.h * vel.h + vel.v * vel.v);
        if (speed < MOMENTUM_EPS) continue;

        var arrowM = Math.min(
            VELOCITY_ARROW_MAX_M,
            Math.max(VELOCITY_ARROW_MIN_M, speed * VELOCITY_ARROW_SPEED_SCALE)
        );
        var scale = arrowM / speed;
        // Canvas axes flip both pitch axes via pt().
        var dx = -vel.h * scale * scaling;
        var dy = -vel.v * scale * scaling;
        var len = Math.sqrt(dx * dx + dy * dy);
        if (len < 4) continue;

        var x1 = player.x;
        var y1 = player.y;
        var x2 = x1 + dx;
        var y2 = y1 + dy;

        ctx.beginPath();
        ctx.moveTo(x1, y1);
        ctx.lineTo(x2, y2);
        ctx.stroke();

        var ah = Math.min(14, Math.max(9, len * 0.4));
        var ux = dx / len;
        var uy = dy / len;
        var px = -uy;
        var py = ux;
        ctx.beginPath();
        ctx.moveTo(x2, y2);
        ctx.lineTo(x2 - ux * ah + px * ah * 0.5, y2 - uy * ah + py * ah * 0.5);
        ctx.lineTo(x2 - ux * ah - px * ah * 0.5, y2 - uy * ah - py * ah * 0.5);
        ctx.closePath();
        ctx.fill();
    }

    ctx.setLineDash(prevDash);
    ctx.strokeStyle = prevStroke;
    ctx.fillStyle = prevFill;
    ctx.lineWidth = prevWidth;
}

function setupDistanceModel() {
    var momentumCheckbox = document.getElementById("momentum_distance_enabled");
    if (momentumCheckbox) {
        setMomentumDistanceEnabled(momentumCheckbox.checked);
        momentumCheckbox.addEventListener("change", function () {
            setMomentumDistanceEnabled(momentumCheckbox.checked);
            if (momentumCheckbox.checked && momentumLambda === 0) {
                setMomentumLambda(MOMENTUM_LAMBDA_DEFAULT);
            }
        });
    }

    var lambdaSlider = document.getElementById("momentum_lambda_slider");
    if (lambdaSlider) {
        setMomentumLambda(+lambdaSlider.value);
        lambdaSlider.addEventListener("input", function () {
            if (!momentumDistanceEnabled) return;
            setMomentumLambda(+lambdaSlider.value);
        });
    }

    updateMomentumLambdaControls();
}
