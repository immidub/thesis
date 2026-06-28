function stepPressing(defender, context) {
    if (context.presserIds[defender.id] !== true) return null;
    if (context.carrier == null) return null;

    var carrier = context.attackerLookup[context.carrier.id] || context.carrier;
    var dist = getPitchDistance(defender.h, defender.v, carrier.h, carrier.v);
    var closing = geometricClosingSpeed(defender, carrier);

    return {
        behavior: BEHAVIOR_TYPES.PRESSING,
        step: PIPELINE_STEPS.PRESSING,
        primaryTarget: carrier,
        evidence: {
            distance: dist,
            closingSpeed: closing,
            carrierSpeed: carrier.speed || 0,
            engaged: dist <= PRESS_ENGAGED_DIST,
        },
    };
}
