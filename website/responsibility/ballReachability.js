// Ball state and player list for contest inference.

const DEFAULT_BALL_REACH_PARAMS = {
    kinematics: DEFAULT_KINEMATICS_PARAMS,
};

function getBallState(frame) { // gets the ball state for the given frame
    var dataLine = gameData && gameData.tracking ? gameData.tracking[frame] : null;
    if (!dataLine || !dataLine.objects || !dataLine.objects[gameData.ballId]) return null;

    var object1 = dataLine.objects[gameData.ballId];
    var object2 = (gameData.tracking[frame + 1] ?? dataLine).objects[gameData.ballId] ?? object1;

    var savedDelta = frameDelta;
    frameDelta = 0;
    var [h1, v1] = getCoordinates(object1, object1);
    var [h2, v2] = getCoordinates(object2, object2);
    frameDelta = savedDelta;

    var dtSec = gameData && gameData.frameRate ? 1 / gameData.frameRate : 0.02;
    var vel = { h: (h2 - h1) / dtSec, v: (v2 - v1) / dtSec };
    if (!isFinite(vel.h) || !isFinite(vel.v)) {
        vel = { h: 0, v: 0 };
    }

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
