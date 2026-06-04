var gameData = null;

var playerShirtNumbers = {};

var startTime = 0;

const LOCAL_DATA_PATH = "../data/local.json";

/**
 * Converts frame number into the frame number without dead-frames
 * @param {Number} oldFrame old Frame
 * @returns index
 */
function convertFrame(oldFrame) {
	var low = 0;
	var high = maxFrame;

	while(high-low > 1) {
		var mid = Math.floor((low+high)/2);

		var frame = +gameData.tracking[mid].frame;

		if(frame > oldFrame) {
			high = mid;
		}
		else {
			low = mid;
		}
	}

	return high;
}

function getShirtNumberLabel(playerId) {
	return playerShirtNumbers[playerId] ?? "";
}


function dataLoaded() {
	console.log("Data loaded");
	dataFinishedReading();

	if(""+gameData.version != "1.0") {
		var versionNr = gameData.version
		gameData = null
		if(versionNr == null) {
			showDataError("Incompatible Version","Expected Version 1.0");
		}
		else {
			showDataError("Incompatible Version","Expected Version 1.0, Uploaded Version " + versionNr);
		}
		return;
	}

	if(gameData.tracking == null) {
		gameData = null
		showDataError("No tracking data found", "JSON file dose not contain field 'tracking'")
		return;
	}
	if(gameData.events == null) {
		$("#error_div_events").show();
	}

	setupDefaultColors();
	getPlayers();
	setupDefaultTeamNames();
	computeFinalScore();
	maxFrame = Math.max(0, Math.floor(gameData.tracking.length) - 2); //-2 because of framedeltas
	if (!gameData.frameRate || gameData.frameRate <= 0) {
		gameData.frameRate = 25;
	}
	if (gameData.pitch == null) {
		gameData.pitch = { width: 68, length: 105 };
	}
	convertEvents();
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

function setupDefaultColors() {

	//Filling in default information if empty
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

function convertEvents() {
	if (gameData.events == null) return;
	for(var event of gameData.events) {
		event.frame = convertFrame(event.frame);
	}
}

function getPlayers() {
	gameData.players = {};
	gameData.players.team1 = [];
	gameData.players.team2 = [];
	gameData.players.goalKeepers = [];

	gameData.players.goalKeepers

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

function computeFinalScore() {
	if(gameData.events == null) {
		var text =  gameData.homeTeam.name + " vs. " + gameData.awayTeam.name;
		document.getElementById("title_text").innerHTML = text
		return;
	}

	var score1 = 0;
	var score2 = 0;
	for(const event of gameData.events) {
		if(event.type == "GOAL") {
			if(event.team == 1) {
				score1 += 1;
			}
			else {
				score2 += 1;
			}
		}
	}

	var text =  gameData.homeTeam.name + " " + score1 + " : " + score2 + " " + gameData.awayTeam.name;
	document.getElementById("title_text").innerHTML = text

}

function setupDefaultTeamNames() {
	if(gameData.homeTeam.name == null) {
		gameData.homeTeam.name = "Home";
	}
	if(gameData.awayTeam.name == null) {
		gameData.awayTeam.name = "Away";
	}
}

// ================================================================================================
// Update UI Functions while gameData is being populated 

function dataReceived(isZipped = false) {
	$("#entry_view").hide();
	$("#website_view").hide();
	$("#data_error_view").hide();

	$("#data_loading_view").show();

	if(isZipped) {
		document.getElementById("dataLoadingTitle").innerHTML = "Unarchiving File..."
		document.getElementById("dataLoadingSubtitle").innerHTML = "This may take a while"
	}
}

function dataFinishedReading() {
	$("#entry_view").hide();
	$("#data_error_view").hide();
	$("#data_loading_view").hide();

	$("#website_view").show();
	setupCanvases();
}

function showDataError(message, secondaryMessage) {
	console.log("Showing error view");
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

// ================================================================================================
// Local dev data (data/ at repo root is gitignored — see README)

async function tryLoadLocalData() {
	try {
		const response = await fetch(LOCAL_DATA_PATH);
		if (!response.ok) {
			return;
		}

		dataReceived();
		gameData = JSON.parse(await response.text());
		dataLoaded();
	} catch (err) {
		if (err instanceof SyntaxError) {
			showDataError("Failed to parse local data", err.message);
		} else {
			console.log("No local data loaded:", err.message);
		}
	}
}

// ================================================================================================
// Uploading File Functions

function dropHandler(ev) {
	console.log("File(s) dropped");
  
	// Prevent default behavior (Prevent file from being opened)
	ev.preventDefault();
  
	if (ev.dataTransfer.items) {
	  // Use DataTransferItemList interface to access the file(s)
	  [...ev.dataTransfer.items].forEach((item, i) => {
		// If dropped items aren't files, reject them
		if (item.kind === "file") {
			const file = item.getAsFile();
		  	console.log(`recived file[${i}] with name ${file.name}`);

			handleFile(file);
		}
	  });
	} else {
	  // Use DataTransfer interface to access the file(s)
	  [...ev.dataTransfer.files].forEach((file, i) => {
		console.log(`… file[${i}].name = ${file.name}`);
	  });
	}
  }

//prevents browser opening file when dropped
function dragOverHandler(ev) {
	ev.preventDefault();
}

function handleFile(file) {
	if (file.type === 'application/zip') {
		decompressFile(file);
	}
	else if(file.type === 'application/json' || file.type === 'text/plain') {
		readFile(file);
	}
	else {
		showDataError("Unsupported file type","received " + file.type + ", expected JSON");
	}
}


function decompressFile(file) {
	console.log("Decompressing file");
	const reader = new FileReader();

      reader.onload = function(e) {
        const arrayBuffer = e.target.result;
        const zip = new JSZip();

        zip.loadAsync(arrayBuffer).then(function(zip) {
          // Get the first file name in the zip
          const fileName = Object.keys(zip.files)[0];
          console.log('File in zip:', fileName);

          // Read the file contents as text
          zip.files[fileName].async('text').then(function(content) {

			gameData = JSON.parse(content);

			dataLoaded();

			});
        }).catch(function(err) {
			showDataError("Failed reading zip file", err.message);
          	console.error('Error reading zip file:', err);
        });
      };

	dataReceived(true);
    reader.readAsArrayBuffer(file);
}

function readFile(file) {
	var reader = new FileReader();
	reader.addEventListener("loadend", function(event) {
		console.log("Read content of file");
		if(gameData == null) {
			gameData = JSON.parse(event.target.result);
			dataLoaded();
		}
	});
	dataReceived();
	reader.readAsText(file);
}

function handleFileUpload(event) {
	const file = event.target.files[0];
	if (file) {
		console.log("File uploaded:", file.name);
		handleFile(file);	
	}
	else {
		showDataError("No file received");
	}
}

function uploadFileButton() {
	document.getElementById("fileupload").click();
}