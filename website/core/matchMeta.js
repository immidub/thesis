async function loadMatchMetadata(path) {
	try {
		var response = await fetch(path);
		if (!response.ok) return null;
		return await response.json();
	} catch (err) {
		console.log("Metadata load failed:", err.message);
		return null;
	}
}

function mergeTeamMetadata(trackingTeam, metaTeam) {
	if (!trackingTeam) trackingTeam = { players: [] };
	if (!metaTeam) return trackingTeam;

	var metaByFspId = {};
	if (metaTeam.players) {
		for (var i = 0; i < metaTeam.players.length; i++) {
			var metaPlayer = metaTeam.players[i];
			metaByFspId[metaPlayer.id] = metaPlayer;
		}
	}

	var players = [];
	for (var j = 0; j < trackingTeam.players.length; j++) {
		var player = trackingTeam.players[j];
		var matched = player.fspId ? metaByFspId[player.fspId] : null;
		players.push({
			id: player.id,
			fspId: player.fspId,
			shirtNumber: matched != null ? matched.shirtNumber : player.shirtNumber,
			isGoalie: matched != null ? matched.isGoalie : player.isGoalie,
		});
	}

	return {
		name: metaTeam.name != null ? metaTeam.name : trackingTeam.name,
		colorShirt: metaTeam.colorShirt != null ? metaTeam.colorShirt : trackingTeam.colorShirt,
		colorNumber: metaTeam.colorNumber != null ? metaTeam.colorNumber : trackingTeam.colorNumber,
		players: players,
	};
}

function applyMatchMetadata(gameData, meta) {
	if (!meta) return;

	if (meta.periods) {
		gameData.periods = meta.periods;
	}

	if (meta.events) {
		gameData.events = meta.events;
	}

	if (meta.homeTeam) {
		gameData.homeTeam = mergeTeamMetadata(gameData.homeTeam, meta.homeTeam);
	}

	if (meta.awayTeam) {
		gameData.awayTeam = mergeTeamMetadata(gameData.awayTeam, meta.awayTeam);
	}
}

function convertFrame(oldFrame) {
	if (!gameData || !gameData.tracking) return oldFrame;

	var low = 0;
	var high = maxFrame;

	while (high - low > 1) {
		var mid = Math.floor((low + high) / 2);
		var frame = +gameData.tracking[mid].frame;

		if (frame > oldFrame) {
			high = mid;
		} else {
			low = mid;
		}
	}

	return high;
}

function convertEvents() {
	if (!gameData.events) return;

	for (var i = 0; i < gameData.events.length; i++) {
		gameData.events[i].frame = convertFrame(gameData.events[i].frame);
	}
}
