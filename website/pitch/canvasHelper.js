var gameCanvases = [];
var gameCanvas;
var drawLoopStarted = false;

const PITCH_COUNT = 7;
const PITCHES_PER_ROW = 2;

class CanvasHelper {
    constructor(id, width, height) {
        this.width = width;
        this.height = height;

        var scaleFactor = 2;
        var canvas = document.getElementById(id);

        $("#" + id).css({ width: "" + width, height: "" + height });

        this.ctx = canvas.getContext("2d");

        canvas.width = Math.ceil(width * scaleFactor);
        canvas.height = Math.ceil(height * scaleFactor);

        this.ctx.scale(scaleFactor, scaleFactor);
    }

    clearCanvas() {
        this.ctx.clearRect(0, 0, this.width, this.height);
    }

    clearCanvasWhite() {
        this.ctx.fillStyle = "#fff";
        this.ctx.fillRect(0, 0, this.width, this.height);
    }

    drawDot(x, y, r, startAngle = 0, endAngle = 2 * Math.PI) {
        this.ctx.beginPath();
        this.ctx.arc(x, y, r, startAngle, endAngle);
        this.ctx.fill();
    }

    drawDotWithStroke(x, y, r, strokeStyle, lineWidth) {
        var prevStroke = this.ctx.strokeStyle;
        var prevWidth = this.ctx.lineWidth;

        this.ctx.beginPath();
        this.ctx.arc(x, y, r, 0, 2 * Math.PI);
        this.ctx.strokeStyle = strokeStyle;
        this.ctx.lineWidth = lineWidth;
        this.ctx.stroke();

        this.ctx.strokeStyle = prevStroke;
        this.ctx.lineWidth = prevWidth;
    }

    drawCircle(x, y, r, startAngle = 0, endAngle = 2 * Math.PI) {
        this.ctx.beginPath();
        this.ctx.arc(x, y, r, startAngle, endAngle);
        this.ctx.stroke();
    }

    drawLine(x1, y1, x2, y2) {
        this.ctx.beginPath();
        this.ctx.moveTo(x1, y1);
        this.ctx.lineTo(x2, y2);
        this.ctx.stroke();
    }

    fillTextCenter(text, x, y) {
        this.ctx.textAlign = "center";
        this.ctx.fillText(text, x, y);
        this.ctx.textAlign = "start";
    }
}

function startDrawLoop() {
    if (drawLoopStarted) return;
    drawLoopStarted = true;

    function loop() {
        draw();
        window.requestAnimationFrame(loop);
    }

    window.requestAnimationFrame(loop);
}

function setupCanvases() {
    var availableWidth = Math.min($(window).width() - 32, 1500);
    if (availableWidth < 600) {
        availableWidth = 600;
    }

    var gap = 12;
    var pitchWidth = Math.floor((availableWidth - gap * (PITCHES_PER_ROW - 1)) / PITCHES_PER_ROW);
    // Landscape pitch: length (105 m) horizontal, width (68 m) vertical.
    var pitchHeight = Math.floor(pitchWidth * (68 / 105));

    gameCanvases = [];

    for (var i = 0; i < PITCH_COUNT; i++) {
        var canvas = new CanvasHelper("canvas" + (i + 1), pitchWidth, pitchHeight);
        canvas.clearCanvas();
        gameCanvases.push(canvas);
    }

    gameCanvas = gameCanvases[0];
    startDrawLoop();
}
