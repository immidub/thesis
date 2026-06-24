# Defensive Responsibility in Football

Browser-based tracking playback with multiple pitch views for defensive marking experiments.

Raw FIFA enriched tracking is converted into the viewer format before playback. Put match files in `input/`, run the converter, then open the website with the generated files in `data/`.

---

## Prepare match data

Raw FIFA files are **not** loaded directly by the website.

### 1. Add files to `input/`

Place exactly one enriched tracking folder and one unified metadata JSON file in `input/` at the repo root (gitignored except `.gitkeep`):

```
input/
  20260613_FWC_08_QAT-SUI_HEI_Scrubbed_Data_Enriched/   # *.football.fifa.samples.enriched files
  20260613_FWC_08_QAT-SUI_FIFA_Unified_Event_Data_Metadata.json
```

Requirements:

- The enriched folder name must end with `_Enriched` and contain the `.enriched` sample files for the match.
- The metadata file name must end with `Metadata.json` (for example `*_FIFA_Unified_Event_Data_Metadata.json`).
- Only **one** enriched folder and **one** metadata file should be in `input/` at a time.

To use a different match, replace both the enriched folder and the metadata JSON with that match’s files.

### 2. Run the converter

From the **repo root**:

```bash
python3 convert_fwc_match.py
```

This reads from `input/` by default and writes two files into `data/`:

```
data/
  tracking-produced.jsonl
  metaData.json
```

Optional paths:

```bash
python3 convert_fwc_match.py --input-dir input --output-dir data
```

Conversion takes a few minutes for a full match (~300k frames). Team names and player rosters come from the FIFA metadata file; kit colors use the same defaults as the website (`#B73B92` home, `#3395AB` away).

### 3. Open the viewer

See [Local development](#local-development) below. The app auto-loads `data/tracking-produced.jsonl` and `data/metaData.json`.

---

## Preparing data for the `data/` folder

The viewer expects two files in `data/` (gitignored except `.gitkeep`):

```
data/
  tracking-produced.jsonl   # required — frame-by-frame positions
  metaData.json             # optional — team names, colors, goalkeepers
```

The viewer loads tracking from the JSONL file and merges metadata when `metaData.json` is present. Player rows are joined using `playerId` in the JSONL and `players[].id` in the metadata (same id string). Each frame includes `period`, `gameClock`, `live`, and optionally `lastTouch` (`"home"` or `"away"`). Half-time boundaries for the clock come from the `period` field; the pitch view uses a fixed orientation in both periods.

---

### Example: `tracking-produced.jsonl`

One JSON object per line (JSON Lines). Each line is one frame.

```jsonl
{"period":1,"frameIdx":0,"gameClock":0.0,"live":true,"lastTouch":"home","homePlayers":[{"playerId":"10001","number":9,"xyz":[12.5,-8.0,0.0],"speed":2.5,"direction":62.8,"distToBall":18.51},{"playerId":"10002","number":1,"xyz":[-40.0,0.0,0.0],"speed":0.6,"direction":15.22,"distToBall":42.97}],"awayPlayers":[{"playerId":"20001","number":7,"xyz":[-10.2,15.3,0.0],"speed":1.9,"direction":33.27,"distToBall":29.55}],"ball":{"xyz":[0.5,0.0,0.0],"speed":9.3,"direction":20.21}}
{"period":1,"frameIdx":1,"gameClock":0.02,"live":true,"lastTouch":"home","homePlayers":[{"playerId":"10001","number":9,"xyz":[12.6,-7.9,0.0],"speed":2.5,"direction":63.1,"distToBall":18.4}],"awayPlayers":[{"playerId":"20001","number":7,"xyz":[-10.0,15.5,0.0],"speed":1.9,"direction":33.5,"distToBall":29.3}],"ball":{"xyz":[0.6,0.1,0.0],"speed":9.3,"direction":20.21}}
```

Expanded view of a single frame (pretty-printed for readability; the file itself is one line per frame):

```json
{
  "period": 1,
  "frameIdx": 0,
  "gameClock": 0.0,
  "live": true,
  "lastTouch": "home",
  "homePlayers": [
    {
      "playerId": "10001",
      "number": 9,
      "xyz": [12.5, -8.0, 0.0],
      "speed": 2.5,
      "direction": 62.8,
      "distToBall": 18.51
    },
    {
      "playerId": "10002",
      "number": 1,
      "xyz": [-40.0, 0.0, 0.0],
      "speed": 0.6,
      "direction": 15.22,
      "distToBall": 42.97
    }
  ],
  "awayPlayers": [
    {
      "playerId": "20001",
      "number": 7,
      "xyz": [-10.2, 15.3, 0.0],
      "speed": 1.9,
      "direction": 33.27,
      "distToBall": 29.55
    }
  ],
  "ball": {
    "xyz": [0.5, 0.0, 0.0],
    "speed": 9.3,
    "direction": 20.21
  }
}
```

---

### Example: `metaData.json`

Single JSON file. Supplies what the JSONL does not: display names, kit colors, and which players are goalkeepers.

```json
{
  "homeTeam": {
    "name": "Red FC",
    "colorShirt": "#B73B92",
    "colorNumber": "#fff",
    "players": [
      { "id": "10001", "shirtNumber": 9, "isGoalie": false },
      { "id": "10002", "shirtNumber": 1, "isGoalie": true },
      { "id": "10003", "shirtNumber": 4, "isGoalie": false }
    ]
  },
  "awayTeam": {
    "name": "Blue United",
    "colorShirt": "#3395AB",
    "colorNumber": "#fff",
    "players": [
      { "id": "20001", "shirtNumber": 7, "isGoalie": false },
      { "id": "20002", "shirtNumber": 12, "isGoalie": true }
    ]
  }
}
```

If `metaData.json` is omitted, playback still works with defaults: teams “Home” / “Away”, generic colors, and one goalkeeper per team chosen from the first frame as the player closest to the nearer goal line.

---

## Local development

1. Run `convert_fwc_match.py` to generate `data/tracking-produced.jsonl` and `data/metaData.json` (see [Prepare match data](#prepare-match-data)).

2. From the **repo root**, start the dev server. Do **not** open `index.html` directly from Finder — the app uses `fetch()` to load data files:

   ```bash
   python3 serve.py
   ```

   This also enables **Export WebM** in the viewer (clips are saved to `clips/`).

3. Open [http://localhost:8000/website/index.html](http://localhost:8000/website/index.html).

   The app auto-loads `data/tracking-produced.jsonl` and `data/metaData.json`. Large JSONL files can take a minute to parse.

4. **Optional:** upload a `.jsonl` file from the entry screen instead of using auto-load. Metadata still loads from `data/metaData.json` when served over HTTP.
