const BEHAVIOR_TYPES = {
    MAN_MARKING: "MAN_MARKING",
    TRACKING_RUN: "TRACKING_RUN",
    SPACE_COVERING: "SPACE_COVERING",
    PASSING_LANE_COVER: "PASSING_LANE_COVER",
    HELP_DEFENSE: "HELP_DEFENSE",
    PRESSING: "PRESSING",
};

const BEHAVIOR_LABELS = {
    MAN_MARKING: "Man marking",
    TRACKING_RUN: "Tracking run",
    SPACE_COVERING: "Space covering",
    PASSING_LANE_COVER: "Passing lane cover",
    HELP_DEFENSE: "Help defense",
    PRESSING: "Pressing",
};

const BEHAVIOR_SCORE_WEIGHTS = {
    MAN_MARKING: {
        distance: 0.35,
        velocitySimilarity: 0.35,
        goalSide: 0.2,
        lowThreatZone: 0.1,
    },
    TRACKING_RUN: {
        attackerGoalward: 0.35,
        velocitySimilarity: 0.25,
        defenderClosing: 0.25,
        distance: 0.15,
    },
    SPACE_COVERING: {
        multiTargetSpread: 0.4,
        goalSide: 0.25,
        lowCoupling: 0.2,
        centralZone: 0.15,
    },
    PASSING_LANE_COVER: {
        laneProximity: 0.5,
        goalSide: 0.2,
        distance: 0.15,
        notCarrier: 0.15,
    },
    HELP_DEFENSE: {
        teammateEngaged: 0.55,
        secondaryDistance: 0.25,
        goalSide: 0.2,
    },
    PRESSING: {
        towardCarrier: 0.35,
        closingSpeed: 0.3,
        highThreatZone: 0.2,
        engagedDistance: 0.15,
    },
};

const BEHAVIOR_THRESHOLDS = {
    manMarkMaxDistance: 8,
    trackingMaxDistance: 12,
    passingLaneMaxDistance: 10,
    passingLaneMaxLineDist: 3,
    helpDefenseMaxDistance: 6,
    helpDefenseTeammateMaxDistance: 5,
    pressingMaxDistance: 15,
    pressingEngagedDistance: 3,
    nearBallDistance: 6,
    centralChannelHalfWidth: 11,
    dangerZoneGoalDistance: 35,
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
