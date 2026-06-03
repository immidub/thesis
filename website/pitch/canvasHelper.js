var gameCanvases = [];
var gameCanvas;
var drawLoopStarted = false;

const PITCH_COUNT = 3;

//helper class for canvas setup and drawing

class CanvasHelper {
    constructor(id, width, height, mouseClick, mouseDown, draw, limitedRefresh = false, startLoop = true) {
        this.limitedRefresh = limitedRefresh;
        this.count = 0;
        this.mouseX = 0;
        this.mouseY = 0;
        this.mouseIsPressed = false;

        this.width = width;
        this.height = height;

        this.draw = draw;

        var scaleFactor = 2;

        var canvas = document.getElementById(id);

        $("#" + id).css({ width: "" + width, height: "" + height });

        this.ctx = canvas.getContext("2d");

        canvas.width = Math.ceil(width * scaleFactor);
        canvas.height = Math.ceil(height * scaleFactor);

        this.ctx.scale(scaleFactor, scaleFactor);

        if (startLoop && draw) {
            window.requestAnimationFrame(() => {
                this.drawHandler();
            });
        }

        var helper = this;

        canvas.addEventListener("mousemove", function (event) {
            helper.mouseX = event.offsetX;
            helper.mouseY = event.offsetY;
        });

        canvas.addEventListener("mouseup", function (event) {
            mouseClick();
            helper.mouseIsPressed = false;
        });

        canvas.addEventListener("mousedown", function (event) {
            helper.mouseIsPressed = true;
            mouseDown();
        });
    }

    drawHandler() {
        this.count++;
        this.draw();
        window.requestAnimationFrame(() => {
            this.drawHandler();
        });
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

function empty() {}

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
    var pitchWidth = Math.floor((availableWidth - gap * (PITCH_COUNT - 1)) / PITCH_COUNT);
    var pitchHeight = Math.floor(pitchWidth * 1.35);

    gameCanvases = [];

    for (var i = 0; i < PITCH_COUNT; i++) {
        var canvas = new CanvasHelper("canvas" + (i + 1), pitchWidth, pitchHeight, empty, empty, null, false, false);
        canvas.clearCanvas();
        gameCanvases.push(canvas);
    }

    gameCanvas = gameCanvases[0];
    startDrawLoop();
}
