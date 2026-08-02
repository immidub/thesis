# Defensive Responsibility in Football

Thesis repository for exploring **defensive marking** from football tracking data: browser viewers for playback and interactive experiments, plus offline Python analyses over full matches.

Two web UIs share the same tracking load path:

- `website/index.html` — main viewer for comparing **standard marking algorithms** (distance threshold, kNN, Hungarian / perfect match, Delaunay, etc.)
- `website/responsibility/index.html` — **responsibility marking**, the author’s own algorithm (reachability / contest-style responsibility)

The pipeline is built around **FIFA World Cup 2026 enriched tracking** (scrubbed `.enriched` samples + unified event-data metadata). The working example in this repo is **Qatar–Switzerland** (match folder names under `input/`, broadcast filename under `clips/`). Other World Cup matches in the **same FIFA delivery format** can be used after checking the hardcoded assumptions below.

---

## Repository layout


| Path               | Role                                                                                  |
| ------------------ | ------------------------------------------------------------------------------------- |
| `input/`           | FIFA enriched folder + metadata JSON (converter input; gitignored)                    |
| `preprocess/` | Convert, jump-fix, validate; `jsonl_to_parquet.py` builds analysis parquet from JSONL |
| `data/`            | Converter outputs: `tracking.jsonl`, `metaData.json`, `tracking.parquet` (gitignored) |
| `website/` | `index.html`: standard marking comparison; `responsibility/`: author’s responsibility algorithm |
| `serve.py`         | Local HTTP server + clip-export API (`localhost:8000`)                                |
| `analysis/`        | Full-match assignment + analyses; results under `analysis/output/` (gitignored)       |
| `clips/`           | Broadcast MP4 for clip export; exported clips/images (gitignored)                     |
| `requirements.txt` | Python deps for convert + analysis                                                    |


Root `index.html` redirects to `website/index.html`.

---

## Requirements

- **Python 3** (3.10+ recommended)
- Dependencies in `requirements.txt`: `pyarrow`, `pandas`, `scipy`, `matplotlib`
- **Browser** for the viewer
- `ffmpeg` **/** `ffprobe` only if you export pitch + broadcast clips

```bash
cd /path/to/defense
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

---

## 1. If working with data from the FIFA WORLD CUP 2026:

Put **exactly one** enriched directory and **exactly one** metadata JSON in `input/`:

```text
input/
├── 20260613_FWC_XX_ABC-XYZ_HEI_Scrubbed_Data_Enriched/
│   └── *.enriched
└── 20260613_FWC_XX_ABC-XYZ_FIFA_Unified_Event_Data_Metadata.json
```

The converter discovers them by pattern, not by fixed match name:

- Metadata: exactly one file matching `input/*Metadata.json`
- Enriched: exactly one directory whose name ends with `_Enriched`, containing `*.enriched` files whose names match `*_N_N_N.football...` (parsed by `preprocess/convert_fwc_match.py`)

### Metadata fields the converter uses

From the unified metadata JSON (field names as in the FIFA file):


| Field | Use |
|-------|-----|
| `home_team_id` / `away_team_id` | Map enriched `teamId` → home/away |
| `home_team_name` / `away_team_name` | Display names in `metaData.json` |
| `home_team_players` / `away_team_players` | Roster; `player_id` must match enriched `playerId` |
| `video_kickoff_time`, `phases` | Broadcast sync → `metaData.json` `videoSync` (see [§4](#4-video-sync)) |

### Optional broadcast for clip export

```text
clips/281-M08-QAT-SUI-camera1-720p.mp4
```

Filename is hardcoded in `serve.py` → `find_source_video()`. For another match, change that path or rename the file.

---

## 2. Preprocess (convert → fix → validate → parquet)

From the repo root:

```bash
.venv/bin/python preprocess/convert_fwc_match.py
# optional overrides:
.venv/bin/python preprocess/convert_fwc_match.py --input-dir input --output-dir data
```

### What the converter does (in order)

1. **Scan** all `.enriched` files: unique `frameCount`s, first `halfId == 2` → period-2 start, goalkeeper `playerId`s.
2. **Write** `data/tracking.jsonl` — one JSON object per frame (viewer format).
3. **Write** `data/metaData.json` — teams, players, goalkeepers, kit colours, optional `videoSync`.
4. **Jump fix** (`fix_tracking`) on that JSONL in place:
  - interpolate clean single-frame position spikes;
  - set `live: false` on severe / systemic teleports;
  - replace player `speed` when it disagrees with position deltas by more than **5 m/s**;
  - recompute ball `speed` / `direction` from the forward position delta (enriched ball kinematics are not used as they turned out to be unreliable).
5. **Validate** (`validate_tracking`) and print a report (does not abort the run).
6. **Write** `data/tracking.parquet` — one row per entity (home / away / ball) per frame, including non-live frames.

Standalone re-fix / re-validate (normally not needed after convert):

```bash
.venv/bin/python preprocess/fix_tracking.py data/tracking.jsonl
.venv/bin/python preprocess/validate_tracking.py data/tracking.jsonl
```

After a standalone fix, re-run convert or rewrite parquet yourself if analysis must see the new positions (`convert_fwc_match.py` is the supported path that keeps JSONL and parquet aligned).

### Outputs

- `data/tracking.jsonl` — viewer + upload format
- `data/metaData.json` — teams / GK / `videoSync`
- `data/tracking.parquet` — analysis input (default for `python -m analysis.run`)

---

## 3. Hardcoded values (update for another match)

| What | Where | Notes |
|------|--------|-------|
| Frame rate 50 Hz | `convert_fwc_match.py`, `fix_tracking.py`, `validate_tracking.py`, `trackingJsonl.js`, `temporal_stability.py` | Assumed, not read from FIFA as FPS |
| Pitch 105 × 68 m | preprocess / viewer / `analysis/pitch.py` | Centre origin after convert |
| Broadcast MP4 | `serve.py` → `find_source_video()` | Default `clips/281-M08-QAT-SUI-camera1-720p.mp4` |
| Video sync fallback | `website/core/timeline.js` → `VIDEO_*_SEC` | Used only if `metaData.json` has no `videoSync` |
| Default kit colours | Converter + viewer | Home `#B73B92`, away `#3395AB` |

---

## 4. Video sync

Converter builds `metaData.json` → `videoSync` from FIFA `video_kickoff_time` + `phases` (MP4 wall-clock seconds for half starts/ends). The viewer applies that via `matchMeta.js`; if missing, it uses the QAT–SUI `VIDEO_*_SEC` fallbacks in `timeline.js`.

**Always check against your MP4** — for Qatar–Switzerland, FIFA’s `video_kickoff_time` did not match the broadcast file used here.

If sync is wrong:

1. Fix `video_kickoff_time` / `phases` in the input `*Metadata.json` and re-convert, **or**
2. Edit `data/metaData.json` → `videoSync` and reload (no re-convert), **or**
3. If there is no `videoSync`, edit `VIDEO_*_SEC` in `timeline.js`.

---

## 5. Run the viewer

```bash
python3 serve.py
```

Open:

- [website/index.html](http://localhost:8000/website/index.html) — main viewer for comparing standard marking algorithms
- [website/responsibility/index.html](http://localhost:8000/website/responsibility/index.html) — responsibility marking (author’s own algorithm)

Both load `../data/tracking.jsonl` and `../data/metaData.json` via the local server (or you can upload a JSONL from the UI). Serving with a plain file URL will not fetch those files reliably—use `serve.py`.

Clip export needs `ffmpeg`, the MP4 from `find_source_video()`, and correct sync ([§4](#4-video-sync)). Outputs: `clips/clip/`, `clips/image/`.

---

## 6. Full-match analysis

General form:

```bash
.venv/bin/python -m analysis.run \
  --assignment <name> [assignment options] \
  --analyses <analysis> [<analysis> ...] \
  [--data data/tracking.parquet] [--live-only | --no-live-only] [--out analysis/output]
```

All statistics and plots used in the thesis were produced by running these analyses (and the optional sweeps below).

**Order:** have `data/tracking.parquet` → run assignment analyses. The viewer does not require analysis. After convert, parquet is written automatically; if you only have `tracking.jsonl`, run `preprocess/jsonl_to_parquet.py` first (see [§7](#7-custom-tracking-skip-fifa-converter)).

Default data path: `data/tracking.parquet`. Default: **live frames only** (`--live-only`; use `--no-live-only` to include dead-ball frames).

Example:

```bash
.venv/bin/python -m analysis.run \
  --assignment distance_threshold --threshold 10 \
  --analyses edge_counts edge_lengths goal_side \
  --live-only
```

Further examples:

```bash
.venv/bin/python -m analysis.run --assignment perfect_match --analyses edge_counts --live-only
.venv/bin/python -m analysis.run --assignment knn --k 1 --knn-mode defender-to-attacker --analyses edge_counts --live-only
.venv/bin/python -m analysis.run --assignment oriented_knn --k 2 --alpha 2 --behind-mode neutral --analyses edge_counts
.venv/bin/python -m analysis.run --assignment delaunay --analyses overlap edge_counts
.venv/bin/python -m analysis.run --assignment dynamic_threshold --dyn-scale 1.5 --dyn-min 5 --dyn-max 15 --analyses edge_counts
```

Useful flags: `--data`, `--out`, `--momentum-lambda` (distance_threshold / knn / perfect_match), perfect-match `--pm-max-length` / `--pm-restrict`, etc. See `python -m analysis.run --help`.

### Assignments (`--assignment`)


| Name                 | Main options                                                                                    |
| -------------------- | ----------------------------------------------------------------------------------------------- |
| `distance_threshold` | `--threshold` (metres)                                                                          |
| `dynamic_threshold`  | `--dyn-scale`, `--dyn-min`, `--dyn-max`                                                         |
| `perfect_match`      | `--pm-max-length`, `--pm-restrict` (`none` / `knn` / `delaunay`)                                |
| `knn`                | `--k`, `--knn-mode` (`defender-to-attacker`, `attacker-to-defender`, `both-mutual`, `both-all`) |
| `oriented_knn`       | `--k`, `--alpha`, `--behind-mode` (`neutral` / `penalize`)                                      |
| `delaunay`           | —                                                                                               |
| `shape_graph`        | —                                                                                               |


Defending / attacking sides come from frame `attacking` (`"home"` / `"away"`) on live frames.

### Analyses (`--analyses`)

`edge_counts`, `edge_lengths`, `goal_side`, `temporal_stability`, `pitch_zones`, `ball_zones`, `overlap`

### Outputs

Each run writes:

```text
analysis/output/{analysis}/{assignment_slug}/
  run_manifest.json
  *_summary.json
  *_per_frame.csv          # when applicable (e.g. edge_counts, edge_lengths, goal_side)
  *.png                    # plots when the analysis generates them
```

Example slug: `distance_threshold__t10m`, `knn__k1__defender_to_attacker`.

### Parameter sweeps (optional)

After parquet exists, sweeps call `analysis.run` repeatedly and aggregate plots:

```bash
.venv/bin/python -m analysis.sweep_compare.threshold_sweep --k-min 5 --k-max 15
.venv/bin/python -m analysis.sweep_compare.knn_sweep
.venv/bin/python -m analysis.sweep_compare.oriented_knn_sweep
.venv/bin/python -m analysis.sweep_compare.momentum_overlap
```

Oriented kNN sweep: mutual `k=2`, α ∈ {1, 1.25, 1.5, 1.75, 2, 2.5, 3} × behind modes `neutral`/`penalize`, analyses `goal_side`/`edge_lengths`/`edge_counts`/`temporal_stability`. Comparison plots vs α (plus plain mutual 2NN baseline) land under `analysis/output/comparison/oriented_knn_sweep/`.

Use `--compare-only` on the threshold/knn/oriented sweeps to rebuild comparison plots from existing outputs without re-running every configuration. These can take a long time on a full match.

---

## 7. Custom tracking (skip FIFA converter)

Place files directly under `data/`:

```text
data/
  tracking.jsonl    # required for the viewer
  metaData.json     # optional
  tracking.parquet  # required for analysis (build yourself or via converter)
```

### `tracking.jsonl`

One JSON object per line. Coordinates: metres on a **105×68 m** pitch, **origin at centre**. Assumed frame rate in the viewer: **50 Hz**.

```json
{"period":1,"frameIdx":0,"gameClock":0.0,"live":true,"attacking":"home","homePlayers":[{"playerId":"10001","number":9,"xyz":[12.5,-8.0,0.0],"speed":2.5,"direction":62.8}],"awayPlayers":[{"playerId":"20001","number":7,"xyz":[-10.2,15.3,0.0],"speed":1.9,"direction":33.27}],"ball":{"xyz":[0.5,0.0,0.0],"speed":9.3,"direction":20.21}}
```

- `period` — half index (1, 2, …)
- `gameClock` — seconds from kickoff in that period
- `live` — ball in play (analysis `--live-only` filters on this)
- `attacking` — `"home"` or `"away"` (optional); team in possession
- `homePlayers` / `awayPlayers` — `playerId`, `number`, `xyz` required for playback; `speed` / `direction` optional in custom files (viewer falls back to zero) but needed for projected marking / reachability
- `ball` — `xyz` required

### `tracking.parquet`

Required for `python -m analysis.run`. Columns: `period`, `frameIdx`, `gameClock`, `live`, `attacking`, `team` (`home` / `away` / `ball`), `playerId`, `number`, `isGoalie`, `x`, `y`, `z`, `speed`, `direction`.

If you only have `tracking.jsonl` (and optionally `metaData.json` for goalkeeper flags), build parquet without re-converting from FIFA:

```bash
.venv/bin/python preprocess/jsonl_to_parquet.py data/tracking.jsonl
# or explicitly:
.venv/bin/python preprocess/jsonl_to_parquet.py data/tracking.jsonl -o data/tracking.parquet --meta data/metaData.json
```

Then run analysis as usual. Needs `pyarrow` (see `requirements.txt`).

### `metaData.json`

Optional for the viewer. `players[].id` must match JSONL `playerId`.

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

Without metadata: teams default to Home / Away; goalkeepers may be inferred from positions. Without `videoSync`: see [§4](#4-video-sync).

---

## Troubleshooting


| Problem                                              | What to check                                                                                           |
| ---------------------------------------------------- | ------------------------------------------------------------------------------------------------------- |
| `Expected exactly one *Metadata.json` / `*_Enriched` | Only one of each under `input/`; names must match those patterns                                        |
| `No .enriched files`                                 | Files end in `.enriched` and match the `*_N_N_N.football` naming the converter parses                   |
| `Could not determine the start frame for period 2`   | Enriched samples must include `halfId: 2`                                                               |
| Missing players after convert                        | Enriched `playerId` must appear in metadata `home_team_players` / `away_team_players`                   |
| Viewer shows no match                                | Run `serve.py`; confirm `data/tracking.jsonl` exists; check browser network for failed fetches          |
| Video / clip out of sync | See [§4](#4-video-sync) |
| Clip export fails | `ffmpeg` on PATH; MP4 path in `find_source_video()` |
| Analysis `FileNotFoundError` for parquet | Run converter or `preprocess/jsonl_to_parquet.py` (or pass `--data`) |
| Validation warnings after convert                    | Informational; convert still finishes. Large jumps may already be `live: false`                         |
| Wrong frame rate / pitch size                        | Update every hardcoded site in the table above—do not assume FIFA files declare FPS                     |


---

## Suggested end-to-end path (new FIFA match)

1. Clear or replace contents of `input/` with **one** `*_Enriched/` folder and **one** `*Metadata.json`.
2. Confirm 50 Hz and 105×68 m (or update constants).
3. Verify video sync against the MP4 ([§4](#4-video-sync)); place/rename broadcast and update `serve.py` if exporting clips.
4. `.venv/bin/pip install -r requirements.txt`
5. `.venv/bin/python preprocess/convert_fwc_match.py`
6. `python3 serve.py` → verify playback and sync in the browser.
7. `.venv/bin/python -m analysis.run --assignment … --analyses … --live-only`
8. Inspect `analysis/output/.../run_manifest.json` and summaries.

