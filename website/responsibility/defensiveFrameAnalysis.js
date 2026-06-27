//entry point for defensive responsibility analysis
//initiates ball pressure analysis and behavior classification

function buildBallPressurePresserIds(ballPressure) {
    var ids = {};
    if (ballPressure == null || !ballPressure.pressers) return ids;

    for (var i = 0; i < ballPressure.pressers.length; i++) {
        ids[ballPressure.pressers[i].defenderId] = true;
    }

    return ids;
}

function analyzeDefensiveFrame(frame) {
    var ballPressure = analyzeBallPressure(frame);

    if (!ballPressure.active) {
        return {
            active: false,
            reason: ballPressure.reason,
            ballPressure: ballPressure,
        };
    }

    var presserIds = buildBallPressurePresserIds(ballPressure);
    var offBallPools = getOffBallShapeGraphPools(frame, presserIds);
    var passingOptions = getPassingOptions(frame, ballPressure.carrier);
    var behaviors = classifyDefensiveBehaviors(frame, {
        offBallPools: offBallPools,
        ballPressure: ballPressure,
        presserIds: presserIds,
        passingOptions: passingOptions,
    });

    return {
        active: true,
        ballPressure: ballPressure,
        offBallPools: offBallPools,
        passingOptions: passingOptions,
        behaviors: behaviors,
    };
}
