function stepTrackingRun(defender, targets, context) {
    for (var i = 0; i < targets.length; i++) {
        var attacker = targets[i];
        if (!isAttackerOnForwardRun(attacker, context.frame)) continue;
        if (!isDefenderTrackingRun(defender, attacker)) continue;

        var runMetrics = getAttackerRunMetrics(attacker, context.frame);

        return {
            behavior: BEHAVIOR_TYPES.TRACKING_RUN,
            step: PIPELINE_STEPS.TRACKING_RUN,
            primaryTarget: attacker,
            evidence: {
                distance: attacker.dist,
                attackerXt: runMetrics.xtNow,
                attackerXtGain: runMetrics.xtGain,
                attackerXtProjected: runMetrics.xtProjected,
                velocityAlignment: velocityAlignment(defender, attacker),
                defenderSpeed: defender.speed || 0,
                attackerSpeed: attacker.speed || 0,
                closingSpeed: geometricClosingSpeed(defender, attacker),
            },
        };
    }

    return null;
}
