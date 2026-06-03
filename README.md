# Defensive Responsibility in Football

Open `website/index.html` and upload the JSON tracking file (or a ZIP archive).

For local development, create `website/data/local.json` with your uncompressed tracking data (the `website/data/` folder is gitignored). When the site is served over HTTP, it auto-loads on every open/reload. From the `website` folder run `python3 -m http.server 8000` and open `http://localhost:8000/index.html`. Opening the HTML file directly (`file://`) does not support auto-load; use the upload button instead.

The webpage accepts the file as a zip as well, but decompressing in the browser is slow and it is recommended to decompress the file before uploading.

# Preparing the JSON file

See `/data.json.zip` for an example

The JSON file that is uploaded to the webpage must have the following format:

```

{
    "version" : "1.0",
    "frameRate": Number,
    "periods": [
        {
            "startFrame": Number
            "endFrame": Number
        }
    ]
    "pitch": {
        "width": Number (in meters),
        "length": Number (in meters)
    },
    "homeTeam": {
        "name": String (optional),
        "colorNumber": Color (optional),
        "ColorShirt": Color (optional)
    players: [
              {
                id: String
                shirtNumber: Number / Short String
                isGoalie: Boolean
                row: Number (optional)
            },
        ]
    },
    "awayTeam": {
        ...
    },
    "ballId": String
    "colorPalette: {
      (optional)
      ...
    }
    "events" : [
       (optional)
          {
                type: String
                team: Number ("home" or "away")
                frame: Number
         }
    ],
    "tracking": [
        {
                frame: Number
                timestamp: Number (in milliseconds of current period)
                possession: Number (null, "home" or "away") (optional)
                objects: {
                    id (String) : {
                        h: Number
                        v: Number
                        z: Number
                    }
                }
            }
        ]
    }
