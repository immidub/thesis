const PASSING_OPTION_EDGE_COLOR = "#059669";
const PASSING_OPTION_EDGE_WIDTH = 2;

function drawPassingOptionsOverlay(passingOptions) {
    if (passingOptions == null || !passingOptions.active) return;

    gameCanvas.ctx.strokeStyle = PASSING_OPTION_EDGE_COLOR;
    gameCanvas.ctx.lineWidth = PASSING_OPTION_EDGE_WIDTH;

    var edges = passingOptions.edges;
    for (var i = 0; i < edges.length; i++) {
        var edge = edges[i];
        gameCanvas.drawLine(edge.x1, edge.y1, edge.x2, edge.y2);
    }

    gameCanvas.ctx.lineWidth = 1;
}
