function stepChallengingHighPass(defender, context) {
    if (context.highPassChallengerIds[defender.id] !== true) return null;
    if (context.intendedTarget == null) return null;

    var target = context.attackerLookup[context.intendedTarget.id] || context.intendedTarget;
    var dist = getPitchDistance(defender.h, defender.v, target.h, target.v);
    var closing = geometricClosingSpeed(defender, target);

    return {
        behavior: BEHAVIOR_TYPES.CHALLENGING_HIGH_PASS,
        step: PIPELINE_STEPS.PRESSING,
        stepName: "High pass challenge",
        primaryTarget: target,
        evidence: {
            distance: dist,
            closingSpeed: closing,
            targetSpeed: target.speed || 0,
            engaged: dist <= PRESS_ENGAGED_DIST,
        },
    };
}
