function stepPassingLaneCover(defender, targets, context) {
    if (targets.length === 0) return null;

    var passingOptions = context.passingOptions;
    if (passingOptions == null || !passingOptions.active) return null;

    var carrier = context.carrier || passingOptions.carrier;
    if (carrier == null) return null;

    var recipientLookup = buildPassRecipientLookup(passingOptions.recipients);

    for (var i = 0; i < targets.length; i++) {
        var attacker = targets[i];
        var recipient = recipientLookup[String(attacker.id)];
        if (recipient == null) continue;

        var projection = projectPointOntoSegment(
            defender.h,
            defender.v,
            carrier.h,
            carrier.v,
            attacker.h,
            attacker.v
        );

        if (!projection.onSegment) continue;

        var maxLineDist = getPassingLaneMaxLineDist(recipient.distFromCarrier);
        if (projection.distance > maxLineDist) continue;

        if (isPassingLaneCoverMovementDisqualified(defender, carrier.h, carrier.v, attacker.h, attacker.v)) {
            continue;
        }

        return {
            behavior: BEHAVIOR_TYPES.PASSING_LANE_COVER,
            step: PIPELINE_STEPS.PASSING_LANE_COVER,
            primaryTarget: attacker,
            evidence: {
                laneType: "carrier_to_attacker",
                lineDistance: projection.distance,
                maxLineDistance: maxLineDist,
                segmentProjection: projection.t,
                passDistanceFromCarrier: recipient.distFromCarrier,
                primaryTargetShirt:
                    attacker.shirtNumber || recipient.shirtNumber,
                threatShieldScore: computeThreatShieldScore(
                    defender,
                    attacker,
                    context.frame
                ),
            },
        };
    }

    return null;
}
