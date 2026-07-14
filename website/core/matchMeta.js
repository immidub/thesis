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

function applyMatchMetadata(gameData, meta) {
	if (!meta) return;

	if (meta.periods) {
		gameData.periods = meta.periods;
	}

	if (meta.homeTeam) {
		gameData.homeTeam = mergeTeamMetadata(gameData.homeTeam, meta.homeTeam);
	}

	if (meta.awayTeam) {
		gameData.awayTeam = mergeTeamMetadata(gameData.awayTeam, meta.awayTeam);
	}

	applyVideoSyncFromMetadata(meta);
}

function applyVideoSyncFromMetadata(meta) {
	if (!meta || !meta.videoSync) return;

	var sync = meta.videoSync;
	if (typeof VIDEO_FIRST_HALF_START_SEC !== "undefined" &&
		Number.isFinite(sync.firstHalfStartSec)) {
		VIDEO_FIRST_HALF_START_SEC = sync.firstHalfStartSec;
	}
	if (typeof VIDEO_FIRST_HALF_END_SEC !== "undefined" &&
		Number.isFinite(sync.firstHalfEndSec)) {
		VIDEO_FIRST_HALF_END_SEC = sync.firstHalfEndSec;
	}
	if (typeof VIDEO_SECOND_HALF_START_SEC !== "undefined" &&
		Number.isFinite(sync.secondHalfStartSec)) {
		VIDEO_SECOND_HALF_START_SEC = sync.secondHalfStartSec;
	}
	if (typeof VIDEO_SECOND_HALF_END_SEC !== "undefined" &&
		Number.isFinite(sync.secondHalfEndSec)) {
		VIDEO_SECOND_HALF_END_SEC = sync.secondHalfEndSec;
	}
}

function mergeTeamMetadata(trackingTeam, metaTeam) {
	if (!metaTeam) return trackingTeam || { players: [] };

	var trackingById = {};
	if (trackingTeam && trackingTeam.players) {
		for (var i = 0; i < trackingTeam.players.length; i++) {
			var trackingPlayer = trackingTeam.players[i];
			trackingById[String(trackingPlayer.id)] = trackingPlayer;
		}
	}

	var players = [];
	if (metaTeam.players) {
		for (var j = 0; j < metaTeam.players.length; j++) {
			var metaPlayer = metaTeam.players[j];
			var fromTracking = trackingById[String(metaPlayer.id)] || null;
			players.push({
				id: String(metaPlayer.id),
				shirtNumber: metaPlayer.shirtNumber != null ? metaPlayer.shirtNumber : (fromTracking && fromTracking.shirtNumber),
				isGoalie: metaPlayer.isGoalie != null ? metaPlayer.isGoalie : (fromTracking && fromTracking.isGoalie === true),
			});
			delete trackingById[metaPlayer.id];
			delete trackingById[String(metaPlayer.id)];
		}
	}

	for (var id in trackingById) {
		var extra = trackingById[id];
		players.push({
			id: String(extra.id),
			shirtNumber: extra.shirtNumber,
			isGoalie: extra.isGoalie === true,
		});
	}

	return {
		name: metaTeam.name != null ? metaTeam.name : (trackingTeam && trackingTeam.name),
		colorShirt: metaTeam.colorShirt != null ? metaTeam.colorShirt : (trackingTeam && trackingTeam.colorShirt),
		colorNumber: metaTeam.colorNumber != null ? metaTeam.colorNumber : (trackingTeam && trackingTeam.colorNumber),
		players: players,
	};
}
