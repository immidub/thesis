function buildBehaviorContext(frame, input) {
    var ball = getBallPitchPos(frame);
    var carrier = input.ballPressure != null ? input.ballPressure.carrier : null;
    var goalH = getDefendingGoalH(frame);
    var defenders = getOutfieldDefenders(frame);
    var attackers = getOutfieldAttackers(frame);

    return {
        frame: frame,
        ball: ball,
        carrier: carrier,
        goalH: goalH,
        defenders: defenders,
        attackers: attackers,
        defenderLookup: buildPlayerLookup(defenders),
        attackerLookup: buildPlayerLookup(attackers),
        presserIds: input.presserIds || {},
        offBallPools: input.offBallPools || [],
    };
}

function classifyDefenderCandidates(frame, defender, poolTargets, context) {
    var attackers = [];

    for (var i = 0; i < poolTargets.length; i++) {
        attackers.push(enrichPoolTarget(poolTargets[i], context.attackerLookup));
    }

    var spaceCover = computeDefenderSpaceCoverContext(defender, attackers, context.goalH);
    var candidateResults = [];

    for (var j = 0; j < attackers.length; j++) {
        var attacker = attackers[j];
        var features = computePairFeatures(frame, defender, attacker, context);
        var helpDefense = computeHelpDefenseContext(
            defender,
            attacker,
            context.defenders,
            context.presserIds
        );
        var pressing = {
            isPresser: context.presserIds[defender.id] === true,
        };
        var contexts = {
            spaceCover: spaceCover,
            helpDefense: helpDefense,
            pressing: pressing,
        };
        var scores = scoreAllBehaviors(features, contexts);
        var bestCandidate = pickBestBehavior(scores);

        candidateResults.push({
            attackerId: attacker.id,
            attackerShirt: getShirtNumberLabel(attacker.id),
            features: features,
            scores: scores,
            bestBehavior: bestCandidate.behavior,
            explanation: buildCandidateExplanation(bestCandidate.behavior, features, contexts),
        });
    }

    return candidateResults;
}

function classifyPressingDefender(defender, context) {
    if (context.carrier == null) return null;

    var carrier = context.attackerLookup[context.carrier.id] || context.carrier;
    var features = computePairFeatures(context.frame, defender, carrier, context);
    var scores = scoreAllBehaviors(features, {
        spaceCover: { targetSpreadScore: 0, attackerCount: 1 },
        helpDefense: { teammateEngaged: false, teammateEngagementScore: 0 },
        pressing: { isPresser: true },
    });

    return {
        attackerId: carrier.id,
        attackerShirt: getShirtNumberLabel(carrier.id),
        features: features,
        scores: scores,
        bestBehavior: BEHAVIOR_TYPES.PRESSING,
        explanation: buildCandidateExplanation(BEHAVIOR_TYPES.PRESSING, features, {
            spaceCover: { attackerCount: 1 },
            helpDefense: {},
            pressing: { isPresser: true },
        }),
    };
}

function classifyDefenderFromPool(frame, pool, context) {
    var defender = context.defenderLookup[pool.defenderId];
    if (defender == null) {
        defender = getPlayerStateAtFrame(frame, pool.defenderId);
    }
    if (defender == null) return null;

    var candidateResults = classifyDefenderCandidates(
        frame,
        defender,
        pool.targets,
        context
    );
    if (candidateResults.length === 0) return null;

    var aggregatedScores = aggregateBehaviorScores(candidateResults);
    var decision = pickBestBehavior(aggregatedScores);
    var primaryTarget = findPrimaryTargetForBehavior(candidateResults, decision.behavior);

    return {
        defenderId: defender.id,
        defenderShirt: getShirtNumberLabel(defender.id),
        x: defender.x,
        y: defender.y,
        behavior: decision.behavior,
        behaviorLabel: BEHAVIOR_LABELS[decision.behavior],
        primaryTargetId: primaryTarget != null ? primaryTarget.attackerId : null,
        primaryTargetShirt: primaryTarget != null ? primaryTarget.attackerShirt : null,
        candidates: candidateResults,
        aggregatedScores: aggregatedScores,
        explanation: buildFinalExplanation(
            decision.behavior,
            primaryTarget,
            candidateResults,
            aggregatedScores
        ),
    };
}

function classifyPressingDefenderResult(frame, defenderId, context) {
    var defender = context.defenderLookup[defenderId];
    if (defender == null) return null;

    var candidateResults = [];
    var pressingCandidate = classifyPressingDefender(defender, context);
    if (pressingCandidate != null) {
        candidateResults.push(pressingCandidate);
    }

    if (candidateResults.length === 0) return null;

    var aggregatedScores = aggregateBehaviorScores(candidateResults);
    aggregatedScores.PRESSING = Math.max(aggregatedScores.PRESSING, 0.75);

    var decision = pickBestBehavior(aggregatedScores);
    decision.behavior = BEHAVIOR_TYPES.PRESSING;

    var primaryTarget = findPrimaryTargetForBehavior(candidateResults, BEHAVIOR_TYPES.PRESSING);

    return {
        defenderId: defender.id,
        defenderShirt: getShirtNumberLabel(defender.id),
        x: defender.x,
        y: defender.y,
        behavior: BEHAVIOR_TYPES.PRESSING,
        behaviorLabel: BEHAVIOR_LABELS.PRESSING,
        primaryTargetId: primaryTarget != null ? primaryTarget.attackerId : null,
        primaryTargetShirt: primaryTarget != null ? primaryTarget.attackerShirt : null,
        candidates: candidateResults,
        aggregatedScores: aggregatedScores,
        explanation: buildFinalExplanation(
            BEHAVIOR_TYPES.PRESSING,
            primaryTarget,
            candidateResults,
            aggregatedScores
        ),
    };
}

function classifyDefensiveBehaviors(frame, input) {
    if (input == null) input = {};

    if (!isBallLive(frame)) {
        return { active: false, reason: "Ball not live", defenders: [] };
    }

    if (getDefendingTeam(frame) == null) {
        return { active: false, reason: "No defending team", defenders: [] };
    }

    var context = buildBehaviorContext(frame, input);
    if (context.goalH == null) {
        return { active: false, reason: "Defending goal unknown", defenders: [] };
    }

    var results = [];
    var classifiedIds = {};
    var pools = context.offBallPools;
    var i;

    for (i = 0; i < pools.length; i++) {
        var poolResult = classifyDefenderFromPool(frame, pools[i], context);
        if (poolResult == null) continue;

        results.push(poolResult);
        classifiedIds[poolResult.defenderId] = true;
    }

    for (var presserId in context.presserIds) {
        if (classifiedIds[presserId]) continue;

        var presserResult = classifyPressingDefenderResult(frame, presserId, context);
        if (presserResult == null) continue;

        results.push(presserResult);
        classifiedIds[presserId] = true;
    }

    return {
        active: true,
        defenders: results,
    };
}
