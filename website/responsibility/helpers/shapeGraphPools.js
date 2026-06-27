function getNearestPoolTargets(source, targets, count) {
    var distances = [];

    for (var j = 0; j < targets.length; j++) {
        var target = targets[j];
        distances.push({
            target: target,
            distSq: getPitchDistanceSquared(source.h, source.v, target.h, target.v),
        });
    }

    distances.sort(function (a, b) {
        return a.distSq - b.distSq;
    });

    var limit = Math.min(count, distances.length);
    var result = [];

    for (var n = 0; n < limit; n++) {
        var entry = distances[n];
        result.push(formatPoolTarget(entry.target, entry.distSq, false));
    }

    return result;
}

function formatPoolTarget(player, distSq, inShapeGraph) {
    var target = {
        id: player.id,
        h: player.h,
        v: player.v,
        x: player.x,
        y: player.y,
        dist: Math.sqrt(distSq),
        shirtNumber: getShirtNumberLabel(player.id),
        inShapeGraph: inShapeGraph,
    };

    if (player.speed != null) target.speed = player.speed;
    if (player.direction != null) target.direction = player.direction;

    return target;
}

function getShapeGraphPoolTargets(defenderIndex, graph, players) {
    var defender = players[defenderIndex];
    var neighbors = graph[defenderIndex] || [];
    var targets = [];

    for (var i = 0; i < neighbors.length; i++) {
        var neighbor = players[neighbors[i]];
        if (neighbor.team === defender.team) continue;

        var distSq = getPitchDistanceSquared(defender.h, defender.v, neighbor.h, neighbor.v);
        targets.push(formatPoolTarget(neighbor, distSq, true));
    }

    targets.sort(function (a, b) {
        return a.dist - b.dist;
    });

    return targets;
}

function getOffBallShapeGraphPools(frame, excludedDefenderIds) {
    if (!isBallLive(frame)) return [];

    var defendingTeam = getDefendingTeam(frame);
    if (defendingTeam == null) return [];

    var built = buildAllOutfieldShapeGraph(frame);
    if (!built) return [];

    var outfieldAttackers = getOutfieldAttackers(frame);
    var pools = [];

    for (var d = 0; d < built.players.length; d++) {
        var defender = built.players[d];
        if (defender.team !== defendingTeam) continue;
        if (isGoalkeeperPlayer(defender.id)) continue;
        if (excludedDefenderIds[defender.id]) continue;

        var targets = getShapeGraphPoolTargets(d, built.graph, built.players);
        if (targets.length === 0) {
            targets = getNearestPoolTargets(defender, outfieldAttackers, 1);
        }

        if (targets.length === 0) continue;

        pools.push({
            defenderId: defender.id,
            defenderShirt: getShirtNumberLabel(defender.id),
            x: defender.x,
            y: defender.y,
            targets: targets,
        });
    }

    return pools;
}
