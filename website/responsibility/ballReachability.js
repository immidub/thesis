// Ball state and player list for contest inference.

const DEFAULT_BALL_REACH_PARAMS = {
    kinematics: DEFAULT_KINEMATICS_PARAMS,
};

function getBallState(frame) { // gets the ball state for the given frame
    var dataLine = gameData && gameData.tracking ? gameData.tracking[frame] : null;
    if (!dataLine || !dataLine.objects || !dataLine.objects[gameData.ballId]) return null;

    var object1 = dataLine.objects[gameData.ballId];

    var savedDelta = frameDelta;
    frameDelta = 0;
    var [h1, v1] = getCoordinates(object1, object1);
    frameDelta = savedDelta;

    // Use speed/direction from tracking (ball direction is precomputed in the converter).
    var vel = getPlayerVelocityVector(object1);
    return { h: h1, v: v1, vel: vel };
}

function getAllPlayersForFrame(frame) { // gets all the players for the given frame
    var players = [];
    for (var team = 1; team <= 2; team++) {
        var teamPlayers = getTeamPlayerPositions(frame, team, true);
        for (var i = 0; i < teamPlayers.length; i++) {
            var player = teamPlayers[i];
            if (!player || player.id == null) continue;
            players.push({
                id: String(player.id),
                team: team,
                player: player,
            });
        }
    }
    return players;
}
