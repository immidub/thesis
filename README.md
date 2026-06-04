# Defensive Responsibility in Football

Browser-based tracking playback with three pitch views for defensive marking experiments (distance threshold and k-nearest neighbors).

## Preparing data for the `data/` folder

Place two files in `data/` at the repo root (gitignored except `.gitkeep`):

```
data/
  tracking-produced.jsonl   # required — frame-by-frame positions
  metaData.json             # optional — names, colors, goalkeepers, score
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

Single JSON file. Supplies what the JSONL does not: display names, kit colors, which players are goalkeepers, and goals for the scoreline.

```json
{
  "homeTeam": {
    "name": "Red FC",
    "colorShirt": "#c0392b",
    "colorNumber": "#ffffff",
    "players": [
      { "id": "10001", "shirtNumber": 9, "isGoalie": false },
      { "id": "10002", "shirtNumber": 1, "isGoalie": true },
      { "id": "10003", "shirtNumber": 4, "isGoalie": false }
    ]
  },
  "awayTeam": {
    "name": "Blue United",
    "colorShirt": "#2980b9",
    "colorNumber": "#ffff00",
    "players": [
      { "id": "20001", "shirtNumber": 7, "isGoalie": false },
      { "id": "20002", "shirtNumber": 12, "isGoalie": true }
    ]
  },
  "events": [
    { "frame": 1200, "team": 1, "type": "GOAL" },
    { "frame": 3400, "team": 2, "type": "GOAL" },
    { "frame": 8900, "team": 1, "type": "GOAL" }
  ]
}
```

Other event types (e.g. `"CORNER"`, `"YELLOW"`) may be listed but only goals update the header score (e.g. `Red FC 2 : 1 Blue United`).

If `metaData.json` is omitted, playback still works with defaults: teams “Home” / “Away”, generic colors, and one goalkeeper per team chosen from the first frame as the player closest to the nearer goal line.

---

## Local development

1. Add your files under `data/` as above.

2. From the **repo root**, start a static server (`fetch` does not work when opening `index.html` directly from Finder):

   ```bash
   python3 -m http.server 8000
   ```

3. Open [http://localhost:8000/website/index.html](http://localhost:8000/website/index.html).

   The app auto-loads `data/tracking-produced.jsonl` and `data/metaData.json`. Large JSONL files can take a minute to parse.

4. You can also upload a `.jsonl` file from the entry screen; metadata still loads from `data/metaData.json` when served over HTTP.
