// ---------------- Compute Shape Graph ----------------

var doPrint = false;

function computeShapeGraph(delaunay, graph) { //computes the shape graph for the given delaunay and graph

    let queue = new PriorityQueue();

    const {points, halfedges, triangles, hull} = delaunay;
    
    if(points.length/2 < 4) return;

    if(doPrint) console.log("--------------------------------");
    


    for (let i = 0, n = halfedges.length; i < n; ++i) {
        const j = halfedges[i];
        if (j < i) continue;
        const ti = triangles[i];
        const tj = triangles[j];

        const neighborsA = Array.from(delaunay.neighbors(ti));
        const neighborsB = Array.from(delaunay.neighbors(tj));

        var a = getNextEdge(neighborsA, tj);
        var b = getNextEdge(neighborsB, ti);

        const angleA = getAngle(ti, a, tj, points);
        const angleB = getAngle(tj, b, ti, points);

        const angle = Math.abs(angleA+angleB)

        queue.enqueueFunction({a: ti, b: tj}, -(angle));
        if(doPrint) console.log("adding edge " + ti + " " + tj + " with angle " + angle/Math.PI*180);
    }

    if(doPrint) console.log("adding hull edges");
    for (var i = 0; i < hull.length; i++) {
        if(i == 0) {
            var ti = hull[hull.length-1];
            var tj = hull[i];
        }
        else {
            var ti = hull[i-1];
            var tj = hull[i];
        }
        const neighborsA = Array.from(delaunay.neighbors(ti));
        var a = getPrevEdge(neighborsA, tj);

        const angleA = getAngle(ti, a, tj, points);

        const angle = Math.abs(angleA)

        queue.enqueueFunction({a: ti, b: tj}, -(angle));

        if(doPrint) console.log("adding edge " + ti + " " + tj + " with angle " + angle/Math.PI*180);
    }

    while(!queue.isPriorityQueueEmpty()) {
        var queueElement = queue.dequeueFunction()
        var edge = queueElement.element;
        var angle = -queueElement.priority

        if(isHullEdge(edge.a, edge.b, hull)) {
            //continue;
        }

        //logString.push( "at edge " + edge.a + " " + edge.b + " with angle " + angle/Math.PI*180)


        if(angle > 135/180*Math.PI) {
            if(doPrint) console.log("removing edge " + edge.a + " " + edge.b);
            //logString.push( "removing edge " + edge.a + " " + edge.b)


            var prevNode = edge.a
            var node = getNextEdge(graph[edge.a], edge.b)

            removeEdge(graph, edge.a, edge.b);
        
            var s = "" + prevNode + " "
            var cnt = 0;

            while (node != edge.a && cnt < 100) {
                //update angle
            
                var angle = 0

                if(!isHullEdge(prevNode,node,hull)) {
                    //logString.push( "  updating " + prevNode + " " + node)

                    const angleA = getStabilityAngle(prevNode, node, graph, points)
                    const angleB = getStabilityAngle(node, prevNode, graph, points)

                    angle = angleA + angleB;




                    if(doPrint) console.log("new angle at " + prevNode + " " + node + " of " + angleA + " and " + angleB);
                

                    if(doPrint) console.log("new angle at " + prevNode + " " + node + " of " + angleA + " and " + angleB);
                
                    queue.updateElement({a: prevNode, b: node}, -angle);
                
                }

                s += node + " "
                cnt ++;
                const nextNode = getNextEdge(graph[node], prevNode)
                prevNode = node
                node = nextNode
            }
        }
    }

    if(doPrint) console.log(graph);

    //var logStringLoc = logString
}

function getStabilityAngle(a, b, graph, points) {
    var minAngle = Math.PI
    var prevNode = a
    var node = getNextEdge(graph[a], b)

    var s = "" + prevNode + " "
    var cnt = 0;

    while (node != a && cnt < 100) {
        s += node + " "
        cnt ++;

        if(graph[node] == undefined) {
            var graphLoc = graph
            //var logStringLoc = logString
            adsf = 1;
        }

        const nextNode = getNextEdge(graph[node], prevNode)


        const alpha = getAngle(a, node, b, points);
        //logString.push("    angle for " + prevNode + " " + node + " " + nextNode + " with angle" + alpha/Math.PI*180)

        if(alpha < minAngle) {
            minAngle = alpha
        }

        prevNode = node
        node = nextNode
    }

    if(doPrint) console.log("  " + s + " " + cnt);

    return Math.abs(minAngle)
}

// ---------------- Helpers ----------------

function removeEdge(graph, a, b) {
    graph[a] = graph[a].filter(item => item != b);
    graph[b] = graph[b].filter(item => item != a);
}

function getPrevEdge(neighbors, k) {
    for(var i = 0; i < neighbors.length; i++) {
        if(neighbors[i] == k) {
            if(i == 0) {
                return neighbors[neighbors.length-1];
            }
            else {
                return neighbors[i-1];
            }
        }
    }
}

function getNextEdge(neighbors, k) {
    for(var i = 0; i < neighbors.length; i++) {
        if(neighbors[i] == k) {
            if(i < neighbors.length-1) {
                return neighbors[i+1];
            }
            else {
                return neighbors[0];
            }
        }
    }
}

function isHullEdge(a, b, hull) {
    return (isHullEdgeOneWay(a,b,hull) || isHullEdgeOneWay(b,a,hull));
}

function isHullEdgeOneWay(a, b, hull) {
    for(var i = 0; i < hull.length; i++) {
        if(hull[i] == a) {
            if(i == hull.length-1) {
                return (hull[0] == b);
            }
            else {
                return (hull[i+1] == b);
            }
        }
    }
}

function getAngle(neighborA, center, neighborB, points) {
    var ax = points[2 * neighborA] - points[2 * center];
    var ay = points[2 * neighborA + 1] - points[2 * center + 1];
    var bx = points[2 * neighborB] - points[2 * center];
    var by = points[2 * neighborB + 1] - points[2 * center + 1];
    var magA = Math.sqrt(ax * ax + ay * ay);
    var magB = Math.sqrt(bx * bx + by * by);
    if (magA === 0 || magB === 0) return 0;
    var cos = (ax * bx + ay * by) / (magA * magB);
    cos = Math.max(-1, Math.min(1, cos));
    return Math.acos(cos);
}
