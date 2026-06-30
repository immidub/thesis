//defender pipeline steps for classifying defensive behaviors
function runDefenderPipeline(defender, targets, context) {
    var decision = stepChallengingHighPass(defender, context);
    if (decision != null) return decision;

    decision = stepPressing(defender, context);
    if (decision != null) return decision;

    decision = stepTrackingRun(defender, targets, context);
    if (decision != null) return decision;

    decision = stepManMarking(defender, targets, context);
    if (decision != null) return decision;

    decision = stepPassingLaneCover(defender, targets, context);
    if (decision != null) return decision;

    return {
        behavior: BEHAVIOR_TYPES.SPACE_COVER,
        step: PIPELINE_STEPS.SPACE_COVER,
        primaryTarget: targets.length > 0 ? targets[0] : null,
        evidence: {},
    };
}
