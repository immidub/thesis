// Step through time: first t with any player in circle, then check only [t, t + epsilon].

const DEFAULT_BALL_CONTEST_PARAMS = {
    reach: DEFAULT_BALL_REACH_PARAMS,
    epsilonSeconds: 0.30,
    majorityWindow: 5,
    majorityVotes: 3,
};

var contestantHistory = [];

function resetContestantHistoryIfNeeded(frame) {
    if (contestantHistory.length === 0) return;
    if (frame < contestantHistory[contestantHistory.length - 1].frame) {
        contestantHistory = [];
    }
}

function applyContestantMajorityVote(frame, rawContestants, allPlayers, params) {
    var p = params || DEFAULT_BALL_CONTEST_PARAMS;
    var windowSize = p.majorityWindow != null ? p.majorityWindow : 3;
    var minVotes = p.majorityVotes != null ? p.majorityVotes : 2;

    resetContestantHistoryIfNeeded(frame);

    if (
        contestantHistory.length > 0 &&
        contestantHistory[contestantHistory.length - 1].frame === frame
    ) {
        contestantHistory.pop();
    }

    var ids = rawContestants.map(function (c) {
        return c.id;
    });
    contestantHistory.push({ frame: frame, ids: ids });
    if (contestantHistory.length > windowSize) {
        contestantHistory.shift();
    }

    var votesNeeded = contestantHistory.length >= windowSize ? minVotes : 1;
    var counts = {};
    for (var i = 0; i < contestantHistory.length; i++) {
        for (var j = 0; j < contestantHistory[i].ids.length; j++) {
            var id = contestantHistory[i].ids[j];
            counts[id] = (counts[id] || 0) + 1;
        }
    }

    var votedIds = Object.keys(counts).filter(function (id) {
        return counts[id] >= votesNeeded;
    });
    votedIds.sort(function (a, b) {
        return counts[b] - counts[a];
    });

    var byId = {};
    for (var k = 0; k < allPlayers.length; k++) {
        byId[allPlayers[k].id] = allPlayers[k];
    }

    var result = [];
    for (var n = 0; n < votedIds.length; n++) {
        var entry = byId[votedIds[n]];
        if (entry) {
            result.push({ id: entry.id, team: entry.team, player: entry.player });
        }
    }
    return result;
}

function findPlayersInCircleAtTime(players, ball, t, kinematics) {
    var found = [];
    for (var i = 0; i < players.length; i++) {
        var entry = players[i];
        if (isBallInReachCircle(entry.player, ball, t, kinematics)) {
            found.push(entry);
        }
    }
    return found;
}

function inferBallContest(frame, params) {
    var p = params || DEFAULT_BALL_CONTEST_PARAMS;
    var kinematics = p.reach.kinematics || DEFAULT_KINEMATICS_PARAMS;
    var tMax = clampNumber(kinematics.tMax, 0.1, 30);
    var dt = clampNumber(kinematics.dt, 0.005, 1.0);
    var eps = p.epsilonSeconds != null ? p.epsilonSeconds : 0.3;

    if (gameData == null) return { state: "no-data" };
    if (!isBallLive(frame)) return { state: "dead" };

    var ball = getBallState(frame);
    if (!ball) return { state: "no-ball" };

    var players = getAllPlayersForFrame(frame);
    if (players.length === 0) {
        return { state: "none", ball: ball, controller: null, best: null, contestants: [], tStar: null };
    }

    // 1) Find first time any player has the ball in their reachability circle.
    var tStar = null;
    for (var t = 0; t <= tMax + 1e-9; t += dt) {
        if (findPlayersInCircleAtTime(players, ball, t, kinematics).length > 0) {
            tStar = t;
            break;
        }
    }

    if (tStar == null) {
        var rawEmpty = [];
        var smoothedEmpty = applyContestantMajorityVote(frame, rawEmpty, players, p);
        var bestEmpty = smoothedEmpty.length > 0 ? smoothedEmpty[0] : null;
        var stateEmpty = smoothedEmpty.length === 1 ? "controlled" : smoothedEmpty.length > 1 ? "contested" : "none";
        return {
            state: stateEmpty,
            ball: ball,
            controller: stateEmpty === "controlled" ? bestEmpty : null,
            best: bestEmpty,
            contestants: smoothedEmpty,
            rawContestants: rawEmpty,
            tStar: null,
            epsilonSeconds: eps,
        };
    }

    // 2) First player at tStar is the possessor; only opponents can contest in [tStar, tStar + eps].
    var atStar = findPlayersInCircleAtTime(players, ball, tStar, kinematics);
    if (atStar.length === 0) {
        var rawEmpty = [];
        var smoothedEmpty = applyContestantMajorityVote(frame, rawEmpty, players, p);
        var bestEmpty = smoothedEmpty.length > 0 ? smoothedEmpty[0] : null;
        var stateEmpty = smoothedEmpty.length === 1 ? "controlled" : smoothedEmpty.length > 1 ? "contested" : "none";
        return {
            state: stateEmpty,
            ball: ball,
            controller: stateEmpty === "controlled" ? bestEmpty : null,
            best: bestEmpty,
            contestants: smoothedEmpty,
            rawContestants: rawEmpty,
            tStar: tStar,
            epsilonSeconds: eps,
        };
    }

    var possessor = atStar[0];
    var possessorTeam = possessor.team;
    var tEnd = tStar + eps;
    var seen = {};
    var contestants = [];
    var best = { id: possessor.id, team: possessor.team, player: possessor.player, t: tStar };
    seen[possessor.id] = true;
    contestants.push(best);

    for (var t2 = tStar; t2 <= tEnd + 1e-9; t2 += dt) {
        var atTime = findPlayersInCircleAtTime(players, ball, t2, kinematics);
        for (var i = 0; i < atTime.length; i++) {
            var entry = atTime[i];
            if (entry.team === possessorTeam) continue;
            if (seen[entry.id]) continue;
            seen[entry.id] = true;
            contestants.push({ id: entry.id, team: entry.team, player: entry.player, t: t2 });
        }
    }

    var rawContestants = contestants;
    contestants = applyContestantMajorityVote(frame, rawContestants, players, p);
    if (contestants.length > 0) {
        var possessorEntry = null;
        for (var j = 0; j < contestants.length; j++) {
            if (contestants[j].id === possessor.id) {
                possessorEntry = contestants[j];
                break;
            }
        }
        best = possessorEntry || contestants[0];
    } else {
        best = null;
    }

    var state = contestants.length === 1 ? "controlled" : contestants.length > 1 ? "contested" : "none";

    return {
        state: state,
        ball: ball,
        controller: state === "controlled" ? best : null,
        best: best,
        contestants: contestants,
        rawContestants: rawContestants,
        tStar: tStar,
        epsilonSeconds: eps,
    };
}
