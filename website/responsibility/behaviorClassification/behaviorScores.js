function score_man_marking(features) {
    var weights = BEHAVIOR_SCORE_WEIGHTS.MAN_MARKING;
    var distanceScore = normalizeInverse(
        features.distance,
        BEHAVIOR_THRESHOLDS.manMarkMaxDistance
    );
    var zoneScore = features.inCentralZone ? 0.6 : 1;

    return clamp01(
        weights.distance * distanceScore +
            weights.velocitySimilarity * features.velocitySimilarity +
            weights.goalSide * features.goalSideScore +
            weights.lowThreatZone * zoneScore
    );
}

function score_tracking_run(features) {
    var weights = BEHAVIOR_SCORE_WEIGHTS.TRACKING_RUN;
    var distanceScore = normalizeInverse(
        features.distance,
        BEHAVIOR_THRESHOLDS.trackingMaxDistance
    );
    var closingScore = clamp01(
        Math.max(features.defenderClosingSpeed, 0) / 4
    );
    var attackerRunScore = features.attackerMovingTowardGoal ? 1 : 0;
    if (features.attackerAcceleratingTowardGoal) attackerRunScore = 1;

    return clamp01(
        weights.attackerGoalward * attackerRunScore +
            weights.velocitySimilarity * features.velocitySimilarity +
            weights.defenderClosing * closingScore +
            weights.distance * distanceScore
    );
}

function score_space_covering(features, defenderContext) {
    var weights = BEHAVIOR_SCORE_WEIGHTS.SPACE_COVERING;
    var lowCoupling = clamp01(1 - features.velocitySimilarity);
    var centralScore = features.inCentralZone ? 1 : 0.55;

    return clamp01(
        weights.multiTargetSpread * defenderContext.targetSpreadScore +
            weights.goalSide * features.goalSideScore +
            weights.lowCoupling * lowCoupling +
            weights.centralZone * centralScore
    );
}

function score_passing_lane_cover(features) {
    var weights = BEHAVIOR_SCORE_WEIGHTS.PASSING_LANE_COVER;
    var distanceScore = normalizeInverse(
        features.distance,
        BEHAVIOR_THRESHOLDS.passingLaneMaxDistance
    );
    var notCarrierScore = features.attackerIsCarrier ? 0.2 : 1;

    return clamp01(
        weights.laneProximity * features.passingLaneProximity +
            weights.goalSide * features.goalSideScore +
            weights.distance * distanceScore +
            weights.notCarrier * notCarrierScore
    );
}

function score_help_defense(features, helpContext) {
    if (!helpContext.teammateEngaged) return 0;

    var weights = BEHAVIOR_SCORE_WEIGHTS.HELP_DEFENSE;
    var secondaryDistance = normalizeInverse(
        features.distance,
        BEHAVIOR_THRESHOLDS.helpDefenseMaxDistance
    );

    return clamp01(
        weights.teammateEngaged * helpContext.teammateEngagementScore +
            weights.secondaryDistance * secondaryDistance +
            weights.goalSide * features.goalSideScore
    );
}

function score_pressing(features, pressingContext) {
    if (!pressingContext.isPresser && !features.attackerIsCarrier) {
        if (!features.attackerNearBallZone) return 0;
    }

    var weights = BEHAVIOR_SCORE_WEIGHTS.PRESSING;
    var distanceScore = normalizeInverse(
        features.distance,
        BEHAVIOR_THRESHOLDS.pressingMaxDistance
    );
    var closingScore = clamp01(
        Math.max(features.defenderClosingSpeed, 0) / 6
    );
    var towardCarrier = features.defenderMovingTowardAttacker ? 1 : 0;
    var engagedScore =
        features.distance <= BEHAVIOR_THRESHOLDS.pressingEngagedDistance ? 1 : 0;
    var zoneScore = features.attackerInDangerZone ? 1 : 0.55;

    var score =
        weights.towardCarrier * towardCarrier +
        weights.closingSpeed * closingScore +
        weights.highThreatZone * zoneScore +
        weights.engagedDistance * engagedScore;

    if (pressingContext.isPresser) {
        score = Math.max(score, 0.65);
    }

    return clamp01(score * Math.max(distanceScore, pressingContext.isPresser ? 0.75 : 0));
}

function scoreAllBehaviors(features, contexts) {
    return {
        MAN_MARKING: score_man_marking(features),
        TRACKING_RUN: score_tracking_run(features),
        SPACE_COVERING: score_space_covering(features, contexts.spaceCover),
        PASSING_LANE_COVER: score_passing_lane_cover(features),
        HELP_DEFENSE: score_help_defense(features, contexts.helpDefense),
        PRESSING: score_pressing(features, contexts.pressing),
    };
}

function aggregateBehaviorScores(candidateResults) {
    var aggregated = {
        MAN_MARKING: 0,
        TRACKING_RUN: 0,
        SPACE_COVERING: 0,
        PASSING_LANE_COVER: 0,
        HELP_DEFENSE: 0,
        PRESSING: 0,
    };

    for (var i = 0; i < candidateResults.length; i++) {
        var scores = candidateResults[i].scores;
        for (var behavior in aggregated) {
            if (scores[behavior] > aggregated[behavior]) {
                aggregated[behavior] = scores[behavior];
            }
        }
    }

    return aggregated;
}

function pickBestBehavior(aggregatedScores) {
    var bestBehavior = BEHAVIOR_TYPES.SPACE_COVERING;
    var bestScore = -1;

    for (var behavior in aggregatedScores) {
        var score = aggregatedScores[behavior];
        if (score > bestScore) {
            bestScore = score;
            bestBehavior = behavior;
        }
    }

    return {
        behavior: bestBehavior,
        bestScore: bestScore,
    };
}

function findPrimaryTargetForBehavior(candidateResults, behavior) {
    var best = null;

    for (var i = 0; i < candidateResults.length; i++) {
        var candidate = candidateResults[i];
        var score = candidate.scores[behavior];
        if (best == null || score > best.score) {
            best = {
                attackerId: candidate.attackerId,
                attackerShirt: candidate.attackerShirt,
                score: score,
            };
        }
    }

    return best;
}

function buildCandidateExplanation(behavior, features, contexts) {
    var parts = [];

    if (behavior === BEHAVIOR_TYPES.MAN_MARKING) {
        parts.push("distance " + features.distance.toFixed(1) + "m");
        if (features.velocitySimilarity > 0.55) parts.push("aligned movement");
        if (features.goalSideScore > 0.4) parts.push("goal-side position");
    } else if (behavior === BEHAVIOR_TYPES.TRACKING_RUN) {
        if (features.attackerMovingTowardGoal) parts.push("attacker running goalward");
        if (features.defenderMovingTowardAttacker) parts.push("defender follows");
        if (features.attackerAcceleratingTowardGoal) parts.push("attacker accelerating");
    } else if (behavior === BEHAVIOR_TYPES.SPACE_COVERING) {
        parts.push(contexts.spaceCover.attackerCount + " nearby threats");
        if (contexts.spaceCover.targetSpreadScore > 0.45) parts.push("between attackers");
        if (features.goalSideScore > 0.35) parts.push("protecting space");
    } else if (behavior === BEHAVIOR_TYPES.PASSING_LANE_COVER) {
        if (features.passingLaneProximity > 0.45) parts.push("on ball-to-attacker lane");
        if (features.goalSideScore > 0.35) parts.push("goal-side");
    } else if (behavior === BEHAVIOR_TYPES.HELP_DEFENSE) {
        if (contexts.helpDefense.engagedTeammateId != null) {
            parts.push(
                "teammate #" +
                    getShirtNumberLabel(contexts.helpDefense.engagedTeammateId) +
                    " engaged"
            );
        }
        parts.push("secondary cover at " + features.distance.toFixed(1) + "m");
    } else if (behavior === BEHAVIOR_TYPES.PRESSING) {
        if (features.attackerIsCarrier) parts.push("closing on ball carrier");
        if (features.defenderClosingSpeed > 0.5) {
            parts.push("closing speed " + features.defenderClosingSpeed.toFixed(1) + " m/s");
        }
        if (features.attackerInDangerZone) parts.push("high-threat zone");
    }

    if (parts.length === 0) {
        return BEHAVIOR_LABELS[behavior] + " based on spatial and movement cues";
    }

    return parts.join(", ");
}

function buildFinalExplanation(behavior, primaryTarget, candidateResults, aggregatedScores) {
    var targetLabel = primaryTarget != null ? "A" + primaryTarget.attackerShirt : "space";
    var candidate = null;

    for (var i = 0; i < candidateResults.length; i++) {
        if (
            primaryTarget != null &&
            candidateResults[i].attackerId === primaryTarget.attackerId
        ) {
            candidate = candidateResults[i];
            break;
        }
    }

    var detail =
        candidate != null
            ? candidate.explanation
            : BEHAVIOR_LABELS[behavior] + " (" + aggregatedScores[behavior].toFixed(2) + ")";

    return (
        BEHAVIOR_LABELS[behavior] +
        " on " +
        targetLabel +
        " — " +
        detail
    );
}
