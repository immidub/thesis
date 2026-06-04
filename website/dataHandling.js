var gameData = null;

var playerShirtNumbers = {};

const LOCAL_DATA_PATH = "../data/tracking-produced.jsonl";
const LOCAL_META_PATH = "../data/metaData.json";

//-- Local data handling ------------------------------------------------------------------------------

//try to load local data if not available then returns
async function tryLoadLocalData() {
	try {
		var response = await fetch(LOCAL_DATA_PATH);
		if (!response.ok) return;
		await loadTrackingData(response);
	} catch (err) {
		console.log("Local data load failed:", err.message);
	}
}

//loads tracking data from source
async function loadTrackingData(source) {
	dataReceived();
	document.getElementById("dataLoadingSubtitle").textContent = "Loading tracking data...";
	gameData = await parseTrackingJsonl(source);
	var meta = await loadMatchMetadata(LOCAL_META_PATH);
	if (meta) {
		applyMatchMetadata(gameData, meta);
	} else {
		inferGoalkeepersFromPositions();
	}
	dataLoaded();
}

function dataReceived() {
	$("#entry_view").hide();
	$("#website_view").hide();
	$("#data_error_view").hide();
	$("#data_loading_view").show();
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
	console.log("Data loaded");

	setupDefaultColors();
	getPlayers();
	setupDefaultTeamNames();

	maxFrame = Math.max(0, Math.floor(gameData.tracking.length) - 2);
	convertEvents();
	updateTitle();

	dataFinishedReading();
	setupSlider();

	frameNr = 0;
	frameDelta = 0;
	isPlaying = false;
	timestampOffset = 0;
	pitchOffsetX = -1;
	pitchOffsetY = -1;
	$("#duration_slider").val(0);
	$("#button_pause").hide();
	$("#button_play").show();
}

//-- Game data handling ------------------------------------------------------------------------------

function getShirtNumberLabel(playerId) {
	return playerShirtNumbers[playerId] ?? "";
}

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
		gameData.homeTeam.colorShirt = "#3395AB";
	}
	if(gameData.awayTeam.colorShirt == null) {
		gameData.awayTeam.colorShirt = "#B73B92";
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
		gameData.players.team1.push(player.id)
		playerShirtNumbers[player.id] = player.shirtNumber;
		if(player.isGoalie == true) {
			gameData.players.goalKeepers.push(player.id);
		}
	}

	for(var player of gameData.awayTeam.players) {
		gameData.players.team2.push(player.id)
		playerShirtNumbers[player.id] = player.shirtNumber;
		if(player.isGoalie == true) {
			gameData.players.goalKeepers.push(player.id);
		}
	}
}

function updateTitle() {
	if (gameData.events == null) {
		document.getElementById("title_text").innerHTML =
			gameData.homeTeam.name + " vs. " + gameData.awayTeam.name;
		return;
	}

	var score1 = 0;
	var score2 = 0;
	for (var event of gameData.events) {
		if (event.type === "GOAL") {
			if (event.team === 1) score1++;
			else score2++;
		}
	}

	document.getElementById("title_text").innerHTML =
		gameData.homeTeam.name + " " + score1 + " : " + score2 + " " + gameData.awayTeam.name;
}

function setupDefaultTeamNames() {
	if(gameData.homeTeam.name == null) {
		gameData.homeTeam.name = "Home";
	}
	if(gameData.awayTeam.name == null) {
		gameData.awayTeam.name = "Away";
	}
}

//-- File handling ------------------------------------------------------------------------------

//handles the drop event
function dropHandler(ev) {
	ev.preventDefault();
	var files = ev.dataTransfer.files;
	for (var i = 0; i < files.length; i++) {
		handleFile(files[i]);
	}
}

//handles the upload button click
function uploadFileButton() {
	document.getElementById("fileupload").click();
}

function dragOverHandler(ev) {
	ev.preventDefault();
}

function handleFileUpload(event) {
	var file = event.target.files[0];
	if (file) {
		handleFile(file);
	} else {
		showDataError("No file received");
	}
}

async function handleFile(file) {
	gameData = null;
	try {
		await loadTrackingData(file);
	} catch (err) {
		console.error("Failed to load tracking:", err);
		showDataError("Failed to load tracking data", err.message);
	}
}

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
