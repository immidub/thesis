//classifies defensive behaviors for each defender in the frame

function buildBehaviorContext(frame, input) {
    var ball = getBallPitchPos(frame);
    var carrier = input.ballPressure != null ? input.ballPressure.carrier : null;
    var defenders = getOutfieldDefenders(frame);
    var attackers = getOutfieldAttackers(frame);

    return {
        frame: frame,
        ball: ball,
        carrier: carrier,
        defenders: defenders,
        attackers: attackers,
        defenderLookup: buildPlayerLookup(defenders),
        attackerLookup: buildPlayerLookup(attackers),
        presserIds: input.presserIds || {},
        offBallPools: input.offBallPools || [],
        ballPressure: input.ballPressure || null,
        passingOptions: input.passingOptions || null,
    };
}

function buildPoolByDefenderId(pools) {
    var map = {};
    for (var i = 0; i < pools.length; i++) {
        map[pools[i].defenderId] = pools[i];
    }
    return map;
}

function decisionToDefenderResult(defender, decision) {
    var primaryTarget = decision.primaryTarget;
    var primaryTargetId = primaryTarget != null ? primaryTarget.id : null;
    var primaryTargetShirt =
        primaryTarget != null
            ? primaryTarget.shirtNumber || getShirtNumberLabel(primaryTarget.id)
            : null;

    return {
        defenderId: defender.id,
        defenderShirt: getShirtNumberLabel(defender.id),
        x: defender.x,
        y: defender.y,
        behavior: decision.behavior,
        behaviorLabel: BEHAVIOR_LABELS[decision.behavior],
        pipelineStep: decision.step,
        pipelineStepName: PIPELINE_STEP_NAMES[decision.step],
        primaryTargetId: primaryTargetId,
        primaryTargetShirt: primaryTargetShirt,
        explanation: buildBehaviorExplanation(decision),
        evidence: decision.evidence,
    };
}

function classifyDefender(frame, defender, context, poolByDefenderId) {
    if (defender == null) return null;

    var pool = poolByDefenderId[defender.id];
    var targets = pool != null ? pool.targets : [];

    var decision = runDefenderPipeline(defender, targets, context);
    return decisionToDefenderResult(defender, decision);
}

function classifyDefensiveBehaviors(frame, input) {
    if (input == null) input = {};

    if (!isBallLive(frame)) {
        return { active: false, reason: "Ball not live", defenders: [] };
    }

    if (getDefendingTeam(frame) == null) {
        return { active: false, reason: "No defending team", defenders: [] };
    }

    if (!isXtGridReady()) {
        return { active: false, reason: "xT grid not loaded", defenders: [] };
    }

    var context = buildBehaviorContext(frame, input);
    var poolByDefenderId = buildPoolByDefenderId(context.offBallPools);
    var results = [];

    for (var i = 0; i < context.defenders.length; i++) {
        var result = classifyDefender(
            frame,
            context.defenders[i],
            context,
            poolByDefenderId
        );
        if (result == null) continue;
        results.push(result);
    }

    return {
        active: true,
        defenders: results,
    };
}
