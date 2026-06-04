var scaling = 6;
var pitchOffsetX = -1;
var pitchOffsetY = -1;

/*
 * Coordinate Representation
 * 
 * h,v (horizontal, vertical): coordinate system used in the data json
 * x,y : coordinate system used internally for the pitch
 */

//if true, flips the whole coordinate system (used to change the direction the game is displayed)
var flipPitch = false; 

//converts between coordinate systems
function convertX(x) {
    return pitchOffsetX+((flipPitch*-2+1)*(+x)+gameData.pitch.width/2)*scaling
}

function convertY(y) {
    return pitchOffsetY+((flipPitch*-2+1)*(+y)+gameData.pitch.length/2)*scaling
}

function convertDist(d) {
    return d*scaling;
}

function getIsSecondHalf(frame) {
    if (!gameData.periods || gameData.periods.length < 2) {
        return false;
    }
    if(gameData.periods.length >= 2) {
        if(gameData.periods[1].startFrame < frame && frame <= gameData.periods[1].endFrame) {
            return true;
        }
    }

    if(gameData.periods.length >= 4) {
        if(gameData.periods[3].startFrame < frame && frame <= gameData.periods[3].endFrame) {
            return true;
        }
    }

    return false;
}

function getGoalKeepers(frame) {
    var points = [];

    var dataLine = gameData.tracking[frame];
    var dataLine2 = gameData.tracking[frame + 1];

    for(var playerId in dataLine.objects) {

        var object1 = dataLine.objects[playerId];
        var object2 = dataLine2.objects[playerId] ?? object1;
        var [h,v] = getCoordinates(object1, object2);

        var isInTeam1 = gameData.players.team1.includes(playerId);
        var isInTeam2 = gameData.players.team2.includes(playerId);

        if(gameData.players.goalKeepers.includes(playerId)) {
            if(isInTeam1) {
                points.push([convertX(v),convertY(h),1])
            }
            else {
                points.push([convertX(v),convertY(h),2])
            }
        }
    }

    return points;
}

function getCoordinates(object1, object2) {
    if (object2 == null) {
        return [+object1.h, +object1.v];
    }

    var h1 = +object1.h;
    var v1 = +object1.v;
    var h2 = +object2.h;
    var v2 = +object2.v;

    var h = h1 + (h2 - h1) * frameDelta;
    var v = v1 + (v2 - v1) * frameDelta;

    return [h, v];
}

function getGamePoints(frame, team) {
    var points = [];

    var dataLine = gameData.tracking[frame];
    var dataLine2 = gameData.tracking[frame + 1];

    for(var playerId in dataLine.objects) {

        var object1 = dataLine.objects[playerId];
        var object2 = dataLine2.objects[playerId] ?? object1;

        if(gameData.players.goalKeepers.includes(playerId)) continue;

        var [h,v] = getCoordinates(object1, object2);

        if(team == 1 && gameData.players.team1.includes(playerId)) {
            points.push(convertX(v), convertY(h));
        }
        if(team == 2 && gameData.players.team2.includes(playerId)) {
            points.push(convertX(v), convertY(h));
        }
    }

    return [points];
}

function drawGameSetup() {
    console.log("draw game setup");    

    var scalingA = (gameCanvas.height-30)/gameData.pitch.length
    var scalingB = (gameCanvas.width-30)/gameData.pitch.width
    scaling = Math.min(scalingA,scalingB);

    pitchOffsetX = (gameCanvas.width-convertDist(gameData.pitch.width))/2;
    pitchOffsetY = (gameCanvas.height-convertDist(gameData.pitch.length))/2;

}

function drawPlayerLabels(frame) {
    var dataLine = gameData.tracking[frame];
    var dataLine2 = gameData.tracking[frame+1];

    for(var playerId in dataLine.objects) {

        var object1 = dataLine.objects[playerId];
        var object2 = dataLine2.objects[playerId] ?? object1;

        if(playerId == gameData.ballId) continue;

        var isInTeam1 = gameData.players.team1.includes(playerId);
        var isInTeam2 = gameData.players.team2.includes(playerId);
        if(!isInTeam1 && !isInTeam2) continue;

        var [h,v] = getCoordinates(object1, object2);

        if(!gameData.players.goalKeepers.includes(playerId)) {
            if(isInTeam1) {
                gameCanvas.ctx.fillStyle = gameData.homeTeam.colorNumber;
            }
            else {
                gameCanvas.ctx.fillStyle = gameData.awayTeam.colorNumber;
            }
        }
        else {
            gameCanvas.ctx.fillStyle = "#FFF";
        }

        gameCanvas.fillTextCenter(getShirtNumberLabel(playerId), convertX(v), convertY(h)+3)
    }
}

function drawBall(frame) {
    var dataLine = gameData.tracking[frame];
    var dataLine2 = gameData.tracking[frame+1];

    gameCanvas.ctx.fillStyle = "#575757";

    for(var playerId in dataLine.objects) {

        var object1 = dataLine.objects[playerId];
        var object2 = dataLine2.objects[playerId] ?? object1;
        
        if(playerId != gameData.ballId) continue;

        var [h,v] = getCoordinates(object1, object2);

        gameCanvas.drawDot(convertX(v),convertY(h),4);

    }
}

function drawPitch() {
    //source: https://upload.wikimedia.org/wikipedia/commons/b/b3/Soccer_pitch_dimensions.png

    gameCanvas.ctx.fillStyle = "#8C8C8C"
    gameCanvas.ctx.strokeStyle = "#8C8C8C"

    var height = gameData.pitch.width;
    var width = gameData.pitch.length;

    gameCanvas.drawLine(convertX(-height/2),convertY(0),convertX(height/2),convertY(0));

    //Touch line (outside line)
    gameCanvas.drawLine(convertX(-height/2),convertY(-width/2),convertX(height/2),convertY(-width/2));
    gameCanvas.drawLine(convertX(-height/2),convertY(width/2),convertX(height/2),convertY(width/2));
    gameCanvas.drawLine(convertX(-height/2),convertY(-width/2),convertX(-height/2),convertY(width/2));
    gameCanvas.drawLine(convertX(height/2),convertY(-width/2),convertX(height/2),convertY(width/2));


    var h0 = -height/2;
    var h1 = height/2;
    var w0 = -width/2;
    var w1 = width/2;

    //Goal Posts
    gameCanvas.drawLine(convertX(-3.66),convertY(w0)-3,convertX(-3.66),convertY(w0)+3);
    gameCanvas.drawLine(convertX(+3.66),convertY(w0)-3,convertX(+3.66),convertY(w0)+3);
    gameCanvas.drawLine(convertX(-3.66),convertY(w1)-3,convertX(-3.66),convertY(w1)+3);
    gameCanvas.drawLine(convertX(+3.66),convertY(w1)-3,convertX(+3.66),convertY(w1)+3);

    //Goal Area
    gameCanvas.drawLine(convertX(9.16),convertY(w0+5.5),convertX(-9.16),convertY(w0+5.5));
    gameCanvas.drawLine(convertX(9.16),convertY(w0),convertX(9.16),convertY(w0+5.5));
    gameCanvas.drawLine(convertX(-9.16),convertY(w0),convertX(-9.16),convertY(w0+5.5));

    gameCanvas.drawLine(convertX(9.16),convertY(w1-5.5),convertX(-9.16),convertY(w1-5.5));
    gameCanvas.drawLine(convertX(9.16),convertY(w1),convertX(9.16),convertY(w1-5.5));
    gameCanvas.drawLine(convertX(-9.16),convertY(w1),convertX(-9.16),convertY(w1-5.5));

    //Penalty Area
    gameCanvas.drawLine(convertX(20.16),convertY(w0+16.5),convertX(-20.16),convertY(w0+16.5));
    gameCanvas.drawLine(convertX(20.16),convertY(w0),convertX(20.16),convertY(w0+16.5));
    gameCanvas.drawLine(convertX(-20.16),convertY(w0),convertX(-20.16),convertY(w0+16.5));

    gameCanvas.drawLine(convertX(20.16),convertY(w1-16.5),convertX(-20.16),convertY(w1-16.5));
    gameCanvas.drawLine(convertX(20.16),convertY(w1),convertX(20.16),convertY(w1-16.5));
    gameCanvas.drawLine(convertX(-20.16),convertY(w1),convertX(-20.16),convertY(w1-16.5));

    //center circle
    gameCanvas.drawCircle(convertX(0),convertY(0),convertDist(9.15))

    const radius = convertDist(9.15);

    gameCanvas.ctx.beginPath();
    gameCanvas.ctx.arc(convertX(0),convertY(w0+(flipPitch*-2+1)*11), radius, Math.PI/2-0.92592839678, Math.PI/2+0.92592839678);
    gameCanvas.ctx.stroke();

    gameCanvas.ctx.beginPath();
    gameCanvas.ctx.arc(convertX(0),convertY(w1-(flipPitch*-2+1)*11), radius, -Math.PI/2-0.92592839678, -Math.PI/2+0.92592839678);
    gameCanvas.ctx.stroke();

    gameCanvas.drawDot(convertX(0),convertY(0),2)
    gameCanvas.drawDot(convertX(0),convertY(w0+11),2)
    gameCanvas.drawDot(convertX(0),convertY(w1-11),2)
}