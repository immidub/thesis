var gameData = null;

var playerShirtNumbers = {};

function getLocalDataDir() {
	return window.location.pathname.indexOf("/responsibility/") !== -1
		? "../../data"
		: "../data";
}

function setDataLoadingLabel(text) {
	var el = document.getElementById("dataLoadingSubtitle");
	if (el) el.textContent = text || "";
}

function setDataLoadingProgress(percent) {
	var bar = document.getElementById("data_loading_progress_bar");
	var progress = document.getElementById("data_loading_progress");
	if (!bar) return;
	bar.classList.remove("data-loading-progress-bar--indeterminate");
	var p = Math.max(0, Math.min(100, Number(percent) || 0));
	bar.style.width = p + "%";
	if (progress) {
		progress.setAttribute("aria-valuenow", String(Math.round(p)));
		progress.removeAttribute("aria-valuetext");
	}
}

function setDataLoadingIndeterminate() {
	var bar = document.getElementById("data_loading_progress_bar");
	var progress = document.getElementById("data_loading_progress");
	if (!bar) return;
	bar.classList.add("data-loading-progress-bar--indeterminate");
	bar.style.width = "35%";
	if (progress) {
		progress.removeAttribute("aria-valuenow");
		progress.setAttribute("aria-valuetext", "Loading");
	}
}

function resetDataLoadingProgress() {
	setDataLoadingProgress(0);
}

function getResponseContentLength(response) {
	if (!response || !response.headers || typeof response.headers.get !== "function") return 0;
	return parseInt(response.headers.get("Content-Length") || "0", 10) || 0;
}

//-- Local data handling ------------------------------------------------------------------------------

//try to load local data if not available then returns
async function tryLoadLocalData() {
	try {
		var response = await fetch(getLocalDataDir() + "/tracking.jsonl");
		if (!response.ok) {
			console.warn("Local tracking.jsonl not found (" + response.status + ")");
			return;
		}
		await loadTrackingData(response);
	} catch (err) {
		console.warn("Local data load failed:", err.message);
	}
}

//loads tracking data from source; optionalMeta may be a parsed object or a File/Blob
async function loadTrackingData(source, optionalMeta) {
	dataReceived();
	setDataLoadingLabel("Loading tracking…");
	resetDataLoadingProgress();
	gameData = await parseTrackingJsonl(source, {
		totalBytes: getResponseContentLength(source) || (source && source.size) || 0,
	});
	var meta = null;
	if (optionalMeta) {
		meta = optionalMeta instanceof Blob
			? await parseMetadataFile(optionalMeta)
			: optionalMeta;
	} else {
		meta = await loadMatchMetadata(getLocalDataDir() + "/metaData.json");
	}
	if (meta) {
		applyMatchMetadata(gameData, meta);
	} else {
		inferGoalkeepersFromPositions();
	}
	dataLoaded();
}

async function parseMetadataFile(file) {
	var text = await file.text();
	return JSON.parse(text);
}

function dataReceived() {
	$("#entry_view").hide();
	$("#website_view").hide();
	$("#data_error_view").hide();
	$("#data_loading_view").show();
	resetDataLoadingProgress();
}

function dataFinishedReading() {
	$("#entry_view").hide();
	$("#data_error_view").hide();
	$("#data_loading_view").hide();
	$("#website_view").show();
	setupCanvases();
}

//sets up the data after it has been loaded
function dataLoaded() {
	setupDefaultColors();
	getPlayers();
	setupDefaultTeamNames();

	maxFrame = Math.max(0, Math.floor(gameData.tracking.length) - 2);
	updateTitle();

	dataFinishedReading();
	setupSlider();

	frameNr = 0;
	frameDelta = 0;
	isPlaying = false;
	timestampOffset = 0;
	pitchOffsetX = -1;
	pitchOffsetY = -1;
	resetPitchDirectionCache();
	$("#duration_slider").val(0);
	$("#button_pause").hide();
	$("#button_play").show();
}

//-- Game data handling ------------------------------------------------------------------------------

function getShirtNumberLabel(playerId) {
	return playerShirtNumbers[playerId] ?? "";
}

//if no meta data is available, infer goalkeepers from positions
function inferGoalkeepersFromPositions() {
	var halfLength = gameData.pitch.length / 2;
	var firstFrame = gameData.tracking[0].objects;

	function distanceToNearestGoalLine(h) {
		return Math.min(Math.abs(h + halfLength), Math.abs(h - halfLength));
	}

	function pickGoalkeeperForTeam(teamPlayers) {
		var bestId = null;
		var bestDist = Infinity;

		for (var i = 0; i < teamPlayers.length; i++) {
			var player = teamPlayers[i];
			var obj = firstFrame[player.id];
			if (!obj) continue;
			var h = +obj.h;

			var dist = distanceToNearestGoalLine(h);
			if (dist < bestDist) {
				bestDist = dist;
				bestId = player.id;
			}
		}

		for (var j = 0; j < teamPlayers.length; j++) {
			teamPlayers[j].isGoalie = teamPlayers[j].id === bestId;
		}
	}

	pickGoalkeeperForTeam(gameData.homeTeam.players);
	pickGoalkeeperForTeam(gameData.awayTeam.players);
}

function setupDefaultColors() {
	if(gameData.homeTeam == null) gameData.homeTeam = {};
	if(gameData.awayTeam == null) gameData.awayTeam = {};

	if(gameData.homeTeam.colorShirt == null) {
		gameData.homeTeam.colorShirt = "#B73B92";
	}
	if(gameData.awayTeam.colorShirt == null) {
		gameData.awayTeam.colorShirt = "#3395AB";
	}

	if(gameData.homeTeam.colorNumber == null) {
		gameData.homeTeam.colorNumber = "#fff";
	}

	if(gameData.awayTeam.colorNumber == null) {
		gameData.awayTeam.colorNumber = "#fff";
	}
}

function getPlayers() {
	gameData.players = {};
	gameData.players.team1 = [];
	gameData.players.team2 = [];
	gameData.players.goalKeepers = [];

	for(var player of gameData.homeTeam.players) {
		gameData.players.team1.push(String(player.id))
		playerShirtNumbers[String(player.id)] = player.shirtNumber;
		if(player.isGoalie == true) {
			gameData.players.goalKeepers.push(String(player.id));
		}
	}

	for(var player of gameData.awayTeam.players) {
		gameData.players.team2.push(String(player.id))
		playerShirtNumbers[String(player.id)] = player.shirtNumber;
		if(player.isGoalie == true) {
			gameData.players.goalKeepers.push(String(player.id));
		}
	}
}

function isGoalkeeperPlayer(playerId) {
	if (!gameData || !gameData.players) return false;
	var id = String(playerId);
	for (var i = 0; i < gameData.players.goalKeepers.length; i++) {
		if (String(gameData.players.goalKeepers[i]) === id) return true;
	}
	return false;
}

function updateTitle() {
	var homeName = gameData.homeTeam.name;
	var awayName = gameData.awayTeam.name;
	var homeColor = gameData.homeTeam.colorShirt || "#B73B92";
	var awayColor = gameData.awayTeam.colorShirt || "#3395AB";

	document.getElementById("title_text").innerHTML =
		'<span style="color:' + homeColor + '">' + homeName + "</span> vs. " +
		'<span style="color:' + awayColor + '">' + awayName + "</span>";
}

function setupDefaultTeamNames() {
	if(gameData.homeTeam.name == null) {
		gameData.homeTeam.name = "Home";
	}
	if(gameData.awayTeam.name == null) {
		gameData.awayTeam.name = "Away";
	}
}

//-- Error display ------------------------------------------------------------------------------

function showDataError(message, secondaryMessage) {
	$("#entry_view").hide();
	$("#website_view").hide();
	$("#data_loading_view").hide();
	$("#data_error_view").show();
	if(message) {
		document.getElementById("dataErrorMessage").innerHTML = message
	}
	if(secondaryMessage) {
		document.getElementById("dataErrorMessageSecondary").innerHTML = secondaryMessage
	}
}
