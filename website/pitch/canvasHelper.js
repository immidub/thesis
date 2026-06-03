var gameCanvas;

//helper class for canvas setup and drawing

class CanvasHelper {
    constructor(id, width, height, mouseClick, mouseDown, draw, limitedRefresh = false) {
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

        window.requestAnimationFrame(() => {
            this.drawHandler();
        });

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

function setupCanvases() {
    var windowSize = Math.min($(window).width(), $(window).height() * 1.35);

    if (windowSize == null) {
        windowSize = 1200;
    }
    if (windowSize > 1200) {
        windowSize = 1200;
    }
    if (windowSize < 400) {
        windowSize = 400;
    }

    var w1 = Math.floor(windowSize * 0.85);
    var h1 = Math.floor(w1 * 1.35);

    gameCanvas = new CanvasHelper("canvas1", w1, h1, empty, empty, draw);
    gameCanvas.clearCanvas();
}