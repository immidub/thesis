const BEHAVIOR_TYPES = {
    PRESSING: "PRESSING",
    TRACKING_RUN: "TRACKING_RUN",
    MAN_MARKING: "MAN_MARKING",
    PASSING_LANE_COVER: "PASSING_LANE_COVER",
    SPACE_COVER: "SPACE_COVER",
};

const BEHAVIOR_LABELS = {
    PRESSING: "Pressing",
    TRACKING_RUN: "Tracking run",
    MAN_MARKING: "Man marking",
    PASSING_LANE_COVER: "Passing lane cover",
    SPACE_COVER: "Space cover",
};

const PIPELINE_STEPS = {
    PRESSING: 1,
    TRACKING_RUN: 2,
    MAN_MARKING: 3,
    PASSING_LANE_COVER: 4,
    SPACE_COVER: 5,
};

const PIPELINE_STEP_NAMES = {
    1: "Ball carrier pressure",
    2: "Dynamic run tracking",
    3: "Man marking",
    4: "Passing lane cover",
    5: "Space cover",
};

const BEHAVIOR_THRESHOLDS = {
    trackingMinRunSpeed: 4.0,
    trackingMinXtGain: 0.004,
    trackingLookaheadSeconds: 3.0,
    trackingMinVelocityAlignment: 0.35,
    trackingSameAreaMaxDistance: 6,
    trackingDestinationAlignment: 0.35,

    manMarkMaxDistance: 3,
    manMarkMaxBallDistance: 35,
    manMarkMinVelocitySimilarity: 0.35,

    passingOptionMaxDistance: 30,
    passingLaneMinLineDist: 1,
    passingLaneMaxLineDist: 5,
    passingLaneMaxDefenderSpeed: 5,
    passingLaneMaxCrossAngle: 60,

    movementMinSpeed: 1.2,
    towardPointAlignment: 0.35,
};

function clamp01(value) {
    if (value < 0) return 0;
    if (value > 1) return 1;
    return value;
}

function normalizeInverse(value, maxValue) {
    if (maxValue <= 0) return 0;
    return clamp01(1 - value / maxValue);
}
