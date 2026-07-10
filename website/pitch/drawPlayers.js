const DEFENDING_PLAYER_BORDER_COLOR = "#1a1a1a";
const DEFENDING_PLAYER_BORDER_WIDTH = 2.5;
const PLAYER_DOT_RADIUS = 8;

function getPlayerScreenPosition(frame, playerId) {
    var dataLine = gameData.tracking[frame];
    if (!dataLine || !dataLine.objects) return null;
    var obj = dataLine.objects[String(playerId)];
    if (!obj) return null;
    var [h, v] = getCoordinates(obj, obj);
    var [x, y] = pt(h, v);
    return { x: x, y: y };
}

function drawTeam(team, defendingTeam) {
    const [points] = getGamePoints(frameNr, team);
    if (points == null || points.length === 0) return;

    const fill = team == 1 ? gameData.homeTeam.colorShirt : gameData.awayTeam.colorShirt;
    const isDefending = team === defendingTeam;

    gameCanvas.ctx.fillStyle = fill;

    for (var i = 0; i < points.length; i += 2) {
        var x = points[i];
        var y = points[i + 1];
        gameCanvas.drawDot(x, y, PLAYER_DOT_RADIUS);
        if (isDefending) {
            gameCanvas.drawDotWithStroke(x, y, PLAYER_DOT_RADIUS, DEFENDING_PLAYER_BORDER_COLOR, DEFENDING_PLAYER_BORDER_WIDTH);
        }
    }
}

function drawGoalKeepers(frame, defendingTeam) {
    var points = getGamePoints(frame, 1, { goalkeepersOnly: true })
        .concat(getGamePoints(frame, 2, { goalkeepersOnly: true }));
    if (points.length === 0) return;

    gameCanvas.ctx.fillStyle = "#575757";

    for (const point of points) {
        gameCanvas.drawDot(point[0], point[1], PLAYER_DOT_RADIUS);
        if (point[2] === defendingTeam) {
            gameCanvas.drawDotWithStroke(point[0], point[1], PLAYER_DOT_RADIUS, DEFENDING_PLAYER_BORDER_COLOR, DEFENDING_PLAYER_BORDER_WIDTH);
        }
    }
}
