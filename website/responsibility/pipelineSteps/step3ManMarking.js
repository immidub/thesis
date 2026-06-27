function stepManMarking(defender, targets, context) {
    for (var i = 0; i < targets.length; i++) {
        var attacker = targets[i];
        if (attacker.dist > BEHAVIOR_THRESHOLDS.manMarkMaxDistance) continue;

        var velSim = velocityAlignment(defender, attacker);
        if (velSim < BEHAVIOR_THRESHOLDS.manMarkMinVelocitySimilarity) continue;

        return {
            behavior: BEHAVIOR_TYPES.MAN_MARKING,
            step: PIPELINE_STEPS.MAN_MARKING,
            primaryTarget: attacker,
            evidence: {
                distance: attacker.dist,
                velocitySimilarity: velSim,
                defenderSpeed: defender.speed || 0,
                attackerSpeed: attacker.speed || 0,
            },
        };
    }

    return null;
}
