function findPlayerIndexInList(players, playerId) {
    for (var i = 0; i < players.length; i++) {
        if (String(players[i].id) === String(playerId)) {
            return i;
        }
    }
    return -1;
}

function buildPassRecipientLookup(recipients) {
    var lookup = {};
    for (var i = 0; i < recipients.length; i++) {
        var recipient = recipients[i];
        lookup[String(recipient.id)] = recipient;
    }
    return lookup;
}

function getPassingOptions(frame, carrier) {
    if (carrier == null) {
        return { active: false, carrier: null, recipients: [], edges: [] };
    }

    var built = buildAttackingDelaunay(frame);
    if (!built) {
        return { active: false, carrier: carrier, recipients: [], edges: [] };
    }

    var players = built.players;
    var carrierIndex = findPlayerIndexInList(players, carrier.id);
    if (carrierIndex < 0) {
        return { active: false, carrier: carrier, recipients: [], edges: [] };
    }

    var neighbors = Array.from(built.delaunay.neighbors(carrierIndex));
    var recipients = [];
    var edges = [];
    var maxDist = BEHAVIOR_THRESHOLDS.passingOptionMaxDistance;

    for (var i = 0; i < neighbors.length; i++) {
        var neighborIndex = neighbors[i];
        var player = players[neighborIndex];
        var distFromCarrier = getPitchDistance(
            carrier.h,
            carrier.v,
            player.h,
            player.v
        );

        if (distFromCarrier > maxDist) continue;

        recipients.push({
            id: player.id,
            h: player.h,
            v: player.v,
            x: player.x,
            y: player.y,
            shirtNumber: getShirtNumberLabel(player.id),
            distFromCarrier: distFromCarrier,
        });

        edges.push({
            x1: carrier.x,
            y1: carrier.y,
            x2: player.x,
            y2: player.y,
            recipientId: player.id,
        });
    }

    recipients.sort(function (a, b) {
        return a.distFromCarrier - b.distFromCarrier;
    });

    return {
        active: recipients.length > 0,
        carrier: carrier,
        recipients: recipients,
        edges: edges,
    };
}
