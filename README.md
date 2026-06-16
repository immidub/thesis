# Defensive Responsibility in Football

Browser-based tracking playback with three pitch views for defensive marking experiments (distance threshold and k-nearest neighbors).

There are two ways to prepare data, depending on what you have:

| Source | What you need | Steps |
|---|---|---|
| **UEFA / pre-formatted tracking** | `tracking-produced.jsonl` already in the correct format | Copy files into `data/` → start server |
| **FIFA enriched tracking** | Raw `.enriched` folder + unified metadata JSON | Put in `input/` → run `convert_fwc_match.py` → start server |

Both paths end with the same two files in `data/`. See [Local development](#local-development) for how to open the viewer.

---

## Using UEFA / pre-formatted tracking

Many UEFA (and similar) feeds already provide `tracking-produced.jsonl` in the format this viewer expects. **No conversion step is required.**

### 1. Copy tracking into `data/`

Place the tracking file in `data/` at the repo root:

```
data/
  tracking-produced.jsonl
```

### 2. Prepare `metaData.json`

The JSONL does not include team names, kit colors, or goalkeeper flags. Create `data/metaData.json` separately (see the [metaData.json example](#example-metadatajson) below). Player rows are joined using `playerExternalIds.fspId` in the JSONL and `players[].id` in the metadata — those id strings must match.

If you omit `metaData.json`, playback still works with generic defaults (teams “Home” / “Away”, default colors, goalkeepers inferred from positions).

### 3. Open the viewer

Start a local server from the repo root and open the website — see [Local development](#local-development). The app auto-loads both files from `data/`.

**Alternative:** you can upload a `.jsonl` file from the entry screen instead of relying on auto-load, but `metaData.json` must still be present in `data/` (it is loaded via HTTP, not through the upload button).

---

## Using FIFA data

If you have FIFA World Cup enriched tracking, convert it before opening the viewer. Raw FIFA files are **not** loaded directly by the website.

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

Conversion takes a few minutes for a full match (~300k frames). Team names and player rosters come from the FIFA metadata file; kit colors use the same defaults as the website (`#3395AB` home, `#B73B92` away).

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

The viewer loads tracking from the JSONL file and merges metadata when `metaData.json` is present. Player rows are joined using `playerExternalIds.fspId` in the JSONL and `players[].id` in the metadata (same id string). Half-time boundaries for the clock come from the `period` field in the JSONL; the pitch view uses a fixed orientation in both periods.

---

### Example: `tracking-produced.jsonl`

One JSON object per line (JSON Lines). Each line is one frame.

```jsonl
{"period":1,"frameIdx":0,"gameClock":0.0,"homePlayers":[{"playerId":"a1b2c3d4-0001-4000-8000-000000000001","number":9,"xyz":[12.5,-8.0,0.0],"playerExternalIds":{"fspId":"10001"}},{"playerId":"a1b2c3d4-0001-4000-8000-000000000002","number":1,"xyz":[-40.0,0.0,0.0],"playerExternalIds":{"fspId":"10002"}}],"awayPlayers":[{"playerId":"b2c3d4e5-0002-4000-8000-000000000010","number":7,"xyz":[-10.2,15.3,0.0],"playerExternalIds":{"fspId":"20001"}}],"ball":{"xyz":[0.5,0.0,0.0]}}
{"period":1,"frameIdx":1,"gameClock":0.04,"homePlayers":[{"playerId":"a1b2c3d4-0001-4000-8000-000000000001","number":9,"xyz":[12.6,-7.9,0.0],"playerExternalIds":{"fspId":"10001"}}],"awayPlayers":[{"playerId":"b2c3d4e5-0002-4000-8000-000000000010","number":7,"xyz":[-10.0,15.5,0.0],"playerExternalIds":{"fspId":"20001"}}],"ball":{"xyz":[0.6,0.1,0.0]}}
```

Expanded view of a single frame (pretty-printed for readability; the file itself is one line per frame):

```json
{
  "period": 1,
  "frameIdx": 0,
  "gameClock": 0.0,
  "homePlayers": [
    {
      "playerId": "a1b2c3d4-0001-4000-8000-000000000001",
      "number": 9,
      "xyz": [12.5, -8.0, 0.0],
      "playerExternalIds": { "fspId": "10001" }
    },
    {
      "playerId": "a1b2c3d4-0001-4000-8000-000000000002",
      "number": 1,
      "xyz": [-40.0, 0.0, 0.0],
      "playerExternalIds": { "fspId": "10002" }
    }
  ],
  "awayPlayers": [
    {
      "playerId": "b2c3d4e5-0002-4000-8000-000000000010",
      "number": 7,
      "xyz": [-10.2, 15.3, 0.0],
      "playerExternalIds": { "fspId": "20001" }
    }
  ],
  "ball": { "xyz": [0.5, 0.0, 0.0] }
}
```

---

### Example: `metaData.json`

Single JSON file. Supplies what the JSONL does not: display names, kit colors, and which players are goalkeepers.

```json
{
  "homeTeam": {
    "name": "Red FC",
    "colorShirt": "#3395AB",
    "colorNumber": "#fff",
    "players": [
      { "id": "10001", "shirtNumber": 9, "isGoalie": false },
      { "id": "10002", "shirtNumber": 1, "isGoalie": true },
      { "id": "10003", "shirtNumber": 4, "isGoalie": false }
    ]
  },
  "awayTeam": {
    "name": "Blue United",
    "colorShirt": "#B73B92",
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

1. Ensure `data/tracking-produced.jsonl` exists, and add `data/metaData.json` if you have it:
   - **UEFA / pre-formatted:** copy both files into `data/` (see [Using UEFA / pre-formatted tracking](#using-uefa--pre-formatted-tracking)).
   - **FIFA enriched:** run `convert_fwc_match.py` to generate both files in `data/` (see [Using FIFA data](#using-fifa-data)).

2. From the **repo root**, start a static server. Do **not** open `index.html` directly from Finder — the app uses `fetch()` to load data files:

   ```bash
   python3 -m http.server 8000
   ```

3. Open [http://localhost:8000/website/index.html](http://localhost:8000/website/index.html).

   The app auto-loads `data/tracking-produced.jsonl` and `data/metaData.json`. Large JSONL files can take a minute to parse.

4. **Optional:** upload a `.jsonl` file from the entry screen instead of using auto-load. Metadata still loads from `data/metaData.json` when served over HTTP.
