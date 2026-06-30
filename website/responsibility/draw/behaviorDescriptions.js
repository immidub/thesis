function formatMeters(value) {
    if (value == null || !isFinite(value)) return "?";
    return (Math.round(value * 10) / 10).toFixed(1) + " m";
}

function formatSpeed(value) {
    if (value == null || !isFinite(value)) return "?";
    return (Math.round(value * 10) / 10).toFixed(1) + " m/s";
}

function formatXt(value) {
    if (value == null || !isFinite(value)) return "?";
    if (value >= 0.1) return value.toFixed(2);
    if (value >= 0.01) return value.toFixed(3);
    return value.toFixed(4);
}

function describeChallengingHighPass(evidence) {
    var parts = [];
    if (evidence.engaged) {
        parts.push("Challenging the intended receiver on a high pass");
    } else {
        parts.push("Closing on the intended receiver of a high pass");
    }
    parts.push(formatMeters(evidence.distance) + " away");
    if (
        !evidence.engaged &&
        evidence.closingSpeed != null &&
        isFinite(evidence.closingSpeed)
    ) {
        parts.push("closing at " + formatSpeed(evidence.closingSpeed));
    }
    return parts.join(", ") + ".";
}

function describePressing(evidence) {
    var parts = [];
    if (evidence.engaged) {
        parts.push("In a duel with the ball carrier");
    } else {
        parts.push("Actively closing on the ball carrier");
    }
    parts.push(formatMeters(evidence.distance) + " away");
    if (
        !evidence.engaged &&
        evidence.closingSpeed != null &&
        isFinite(evidence.closingSpeed)
    ) {
        parts.push("closing at " + formatSpeed(evidence.closingSpeed));
    }
    return parts.join(", ") + ".";
}

function describeTrackingRun(evidence) {
    var parts = ["Following a run into higher threat space"];
    if (evidence.attackerXtGain != null) {
        parts.push("xT gain " + formatXt(evidence.attackerXtGain) + " over 1s");
    }
    if (evidence.attackerXtProjected != null) {
        parts.push("projected xT " + formatXt(evidence.attackerXtProjected));
    }
    parts.push(formatMeters(evidence.distance) + " from defender");
    if (evidence.closingSpeed != null && isFinite(evidence.closingSpeed)) {
        parts.push("closing at " + formatSpeed(evidence.closingSpeed));
    }
    if (evidence.velocityAlignment != null) {
        parts.push(
            "movement aligned (" + Math.round(evidence.velocityAlignment * 100) + "%)"
        );
    }
    return parts.join(", ") + ".";
}

function describeManMarking(evidence) {
    var parts = ["Close man-to-man on pool attacker"];
    parts.push(formatMeters(evidence.distance) + " away");
    if (evidence.velocitySimilarity != null) {
        parts.push(
            "running together (" + Math.round(evidence.velocitySimilarity * 100) + "% aligned)"
        );
    }
    return parts.join(", ") + ".";
}

function describePassingLaneCover(evidence) {
    return (
        "Screening a pass to A" +
        evidence.primaryTargetShirt +
        " (" +
        formatMeters(evidence.passDistanceFromCarrier) +
        " from carrier), " +
        formatMeters(evidence.lineDistance) +
        " off the carrier-to-target line (max " +
        formatMeters(evidence.maxLineDistance) +
        ")."
    );
}

function describeSpaceCover(evidence) {
    return "Space cover.";
}

function buildBehaviorExplanation(decision) {
    var evidence = decision.evidence || {};

    switch (decision.behavior) {
        case BEHAVIOR_TYPES.PRESSING:
            return describePressing(evidence);
        case BEHAVIOR_TYPES.CHALLENGING_HIGH_PASS:
            return describeChallengingHighPass(evidence);
        case BEHAVIOR_TYPES.TRACKING_RUN:
            return describeTrackingRun(evidence);
        case BEHAVIOR_TYPES.MAN_MARKING:
            return describeManMarking(evidence);
        case BEHAVIOR_TYPES.PASSING_LANE_COVER:
            return describePassingLaneCover(evidence);
        case BEHAVIOR_TYPES.SPACE_COVER:
            return describeSpaceCover(evidence);
        default:
            return "Defensive behavior classified.";
    }
}
