function stepHelpDefender(defender, targets, context) {
    if (context.presserIds[defender.id] === true) return null;
    if (context.highPassChallengerIds[defender.id] === true) return null;
    if (context.carrier == null) return null;

    var pressers =
        context.ballPressure != null ? context.ballPressure.pressers : null;
    if (pressers == null || pressers.length === 0) return null;

    var carrier = context.attackerLookup[context.carrier.id] || context.carrier;
    var bestPresser = null;
    var bestDist = Infinity;

    for (var i = 0; i < pressers.length; i++) {
        var presser = context.defenderLookup[String(pressers[i].defenderId)];
        if (presser == null) continue;

        var distToPresser = getPitchDistance(
            defender.h,
            defender.v,
            presser.h,
            presser.v
        );
        if (distToPresser > BEHAVIOR_THRESHOLDS.helpDefenderSupportRadius) continue;
        if (
            !isDefenderAmongNearestToTarget(
                defender,
                context.defenders,
                presser,
                BEHAVIOR_THRESHOLDS.helpDefenderNearestPresserCount
            )
        ) {
            continue;
        }
        if (isMovingAwayFromPressSituation(defender, presser, carrier)) continue;

        if (distToPresser < bestDist) {
            bestDist = distToPresser;
            bestPresser = presser;
        }
    }

    if (bestPresser == null) return null;

    return {
        behavior: BEHAVIOR_TYPES.HELP_DEFENDER,
        step: PIPELINE_STEPS.HELP_DEFENDER,
        primaryTarget: bestPresser,
        evidence: {
            distanceToPresser: bestDist,
            primaryTargetShirt: getShirtNumberLabel(bestPresser.id),
        },
    };
}
