const BALL_CARRIER_MAX_DISTANCE_METERS = 6;
const BALL_CARRIER_DEFENDER_K = 3;
const BALL_CARRIER_HIGHLIGHT_COLOR = "#F59E0B";
const BALL_CARRIER_HIGHLIGHT_WIDTH = 3;

function getBallPosition(frame) {
    var dataLine = gameData.tracking[frame];
    if (!dataLine || !dataLine.objects) return null;

    var object1 = dataLine.objects[gameData.ballId];
    if (!object1) return null;

    var object2 = (gameData.tracking[frame + 1] ?? dataLine).objects[gameData.ballId] ?? object1;
    var [h, v] = getCoordinates(object1, object2);
    return { h: h, v: v };
}

function getBallCarrier(frame, maxDistanceMeters) {
    if (!isBallLive(frame)) return null;

    var possessionTeam = getPossessionTeam(frame);
    if (possessionTeam == null) return null;

    var teamPlayers = getTeamPlayerPositions(frame, possessionTeam);
    var ballPos = getBallPosition(frame);
    var closest = null;
    var closestDistSq = Infinity;
    var maxDistSq = maxDistanceMeters * maxDistanceMeters;

    for (var i = 0; i < teamPlayers.length; i++) {
        var player = teamPlayers[i];
        var distSq;

        if (player.distToBall != null) {
            var d = player.distToBall;
            distSq = d * d;
        } else if (ballPos != null) {
            distSq = getPitchDistanceSquared(player.h, player.v, ballPos.h, ballPos.v);
        } else {
            continue;
        }

        if (distSq > maxDistSq) continue;

        if (distSq < closestDistSq) {
            closestDistSq = distSq;
            closest = player;
        }
    }

    return closest;
}

function getBallCarrierDefenderEdges(frame, k) {
    var carrier = getBallCarrier(frame, BALL_CARRIER_MAX_DISTANCE_METERS);
    if (carrier == null) return { carrier: null, edges: [] };

    var defendingTeam = getDefendingTeam(frame);
    if (defendingTeam == null) return { carrier: carrier, edges: [] };

    var defenders = getTeamPlayerPositions(frame, defendingTeam);
    return { carrier: carrier, edges: getKnnEdges(carrier, defenders, k) };
}

function drawBallCarrierHighlight(player) {
    if (!player) return;

    gameCanvas.drawDotWithStroke(
        player.x,
        player.y,
        PLAYER_DOT_RADIUS,
        BALL_CARRIER_HIGHLIGHT_COLOR,
        BALL_CARRIER_HIGHLIGHT_WIDTH
    );
}
