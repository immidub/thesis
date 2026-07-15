# Defensive Responsibility in Football

Browser-based tracking playback for defensive marking experiments.

---

## FIFA World Cup data

1. Put **one** enriched folder and **one** metadata JSON in `input/`:

```
input/
  20260613_FWC_XX_ABC-XYZ_HEI_Scrubbed_Data_Enriched/   # *.enriched files
  20260613_FWC_XX_ABC-XYZ_FIFA_Unified_Event_Data_Metadata.json
```

2. Convert (from repo root). Parquet export needs pyarrow once:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python preprocess/convert_fwc_match.py
```

Or with system Python if pyarrow is already installed: `python3 preprocess/convert_fwc_match.py`.

Writes:

- `data/tracking.jsonl` — frame-by-frame tracking for the viewer (When converting the data the jump fixer runs automatically: small 1-frame spikes are interpolated; large/systemic teleports set `live` to false; mismatched player speeds (if difference is over 5 m/s) are replaced from position deltas)
- `data/metaData.json` — teams, goalkeepers, kit colours, and optional `videoSync`
- `data/tracking.parquet` — same post-fix data for analysis (all frames, live and not; one row per player/ball per frame)

3. Full-match analysis (optional):

```bash
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m analysis.run --assignment distance_threshold --threshold 10 --analyses edge_counts --live-only
.venv/bin/python -m analysis.run --assignment perfect_match --analyses edge_counts --live-only
.venv/bin/python -m analysis.run --assignment knn --k 1 --knn-mode defender-to-attacker --analyses edge_counts --live-only
```

Writes results under `analysis/output/{analysis}/{assignment_slug}/`, for example:

```
analysis/output/
  edge_counts/
    perfect_match/
    distance_threshold__t10m/
    knn__k1__defender_to_attacker/
  edge_lengths/
    perfect_match/
    ...
```

Assignments:

| `--assignment` | Options |
|----------------|---------|
| `distance_threshold` | `--threshold` metres (all pairs within range) |
| `perfect_match` | min-cost matching of all outfield defenders ↔ attackers |
| `knn` | `--k`; `--knn-mode` one of `defender-to-attacker`, `attacker-to-defender`, `both-mutual`, `both-all` |

4. Run the viewer:

```bash
python3 serve.py
```

Open [http://localhost:8000/website/index.html](http://localhost:8000/website/index.html).

For clip export (pitch + broadcast stacked MP4), put the match broadcast in `clips/` and have `ffmpeg` installed. See [Hardcoded values](#hardcoded-values) for the video filename.

---

## Other data

Skip the converter. Put your own files directly in `data/`:

```
data/
  tracking.jsonl    # required
  metaData.json     # optional
```

### Tracking format (`tracking.jsonl`)

One JSON object per line. Coordinates are metres on a 105×68 m pitch (origin at centre).

**Example frame** (one line in the file):

```json
{"period":1,"frameIdx":0,"gameClock":0.0,"live":true,"lastTouch":"home","homePlayers":[{"playerId":"10001","number":9,"xyz":[12.5,-8.0,0.0],"speed":2.5,"direction":62.8}],"awayPlayers":[{"playerId":"20001","number":7,"xyz":[-10.2,15.3,0.0],"speed":1.9,"direction":33.27}],"ball":{"xyz":[0.5,0.0,0.0],"speed":9.3,"direction":20.21}}
```

- `period` — half number (1, 2, …); used for the game clock and half boundaries.
- `gameClock` — seconds from kickoff in that period.
- `lastTouch` — `"home"` or `"away"` (optional).
- `homePlayers` / `awayPlayers` — `playerId`, `number`, `xyz` required for playback. `speed` and `direction` are optional in custom JSONL (viewer falls back to zero velocity) but always written by the FIFA converter and needed for projected marking / reachability.
- `ball` — `xyz` required. `speed` and `direction` are written by the fixer from the forward position delta (this frame → next). Enriched ball kinematics are not used.


### Analysis parquet (`tracking.parquet`)

Written by the converter after JSONL fix/validation. One row per entity (home player, away player, or ball) per frame — includes non-live frames. Columns: `period`, `frameIdx`, `gameClock`, `live`, `lastTouch`, `team` (`home` / `away` / `ball`), `playerId`, `number`, `isGoalie`, `x`, `y`, `z`, `speed`, `direction`. Coordinates match the JSONL (metres, pitch centre origin).

### Metadata (`metaData.json`)

Optional. Team names, kit colours, goalkeeper flags, and video sync. `players[].id` must match `playerId` in the JSONL.

```json
{
  "homeTeam": {
    "name": "Red FC",
    "colorShirt": "#B73B92",
    "colorNumber": "#fff",
    "players": [
      { "id": "10001", "shirtNumber": 9, "isGoalie": false },
      { "id": "10002", "shirtNumber": 1, "isGoalie": true }
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
  },
  "videoSync": {
    "firstHalfStartSec": 1419,
    "firstHalfEndSec": 4485,
    "secondHalfStartSec": 5460,
    "secondHalfEndSec": 8599
  }
}
```

Without metadata, teams default to “Home” / “Away” and goalkeepers are inferred from positions. Without `videoSync` in metadata, the viewer uses defaults in `website/core/timeline.js`. More on that in [Video sync](#Video-sync)

Then run `python3 serve.py` and open the URL above (or upload the JSONL from the entry screen).

---

## Video sync

Uses kickoff time and phase times from the provided metadata. If sync is wrong, check those values, update and re-convert, or write the correct seconds into `videoSync` in `data/metaData.json` (or the `VIDEO_*_SEC` defaults in `website/core/timeline.js`).

---

## Hardcoded values

Some behaviour is still match-specific. Update these when using a different match or broadcast:

| What | Where | What to change |
|------|--------|----------------|
| Broadcast MP4 for clip export | `serve.py` → `find_source_video()` | Filename in `clips/` (currently `281-M08-QAT-SUI-camera1-720p.mp4`) |
| Video time label & clip sync (fallback) | `website/core/timeline.js` | `VIDEO_*_SEC` — used only when `metaData.json` has no `videoSync` (or a key is missing) |
| Frame rate | `preprocess/convert_fwc_match.py`, `website/core/trackingJsonl.js` | Assumes 50 Hz |
| Pitch size | `preprocess/convert_fwc_match.py`, `website/core/trackingJsonl.js` | 105×68 m |
| Default kit colours | `preprocess/convert_fwc_match.py` | Home `#B73B92`, away `#3395AB` |
