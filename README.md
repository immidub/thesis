# Defensive Responsibility in Football

Thesis software for studying **defensive marking** from football tracking data.

The repository provides:

1. A **preprocess pipeline** that turns FIFA World Cup enriched tracking (or custom tracking) into viewer- and analysis-ready files.
2. Two **browser viewers** for interactive inspection of marking methods.
3. Offline **Python analyses** that score assignments over a full match and write summaries and plots.

The working example match is **Qatar–Switzerland** (FIFA World Cup delivery under `input/`, broadcast file under `clips/`). Other matches in the **same FIFA format** can be used after updating the match-specific paths and constants listed below — start from the [Suggested checklist for a new FIFA match](#suggested-checklist-for-a-new-fifa-match).

---



## End-to-end workflow

```text
FIFA enriched (+ metadata) in input/     OR     tracking.jsonl in data/
                    │                                    │
                    └──────────────┬─────────────────────┘
                                   ▼
                    python preprocess/run.py
                                   │
     ┌─────────────────────────────┼─────────────────────────────┐
     ▼                             ▼                             ▼
data/tracking.jsonl      data/tracking.parquet     data/responsibility.jsonl
data/metaData.json                │                data/responsibility_zones.jsonl
     │                            ▼                             │
     │                   python -m analysis.run                 │
     ▼                                                          ▼
Standard / Responsibility viewers  (python serve.py)   Responsibility Viewer
```

**Minimal path for a new FIFA match**

```bash
cd /path/to/defense
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# 1. Put exactly one *_Enriched/ folder and one *Metadata.json in input/
# 2. (Optional) Place broadcast MP4 under clips/ and update serve.py if the name differs

.venv/bin/python preprocess/run.py
python3 serve.py
# → http://localhost:8000/website/index.html
# → http://localhost:8000/website/responsibility/index.html

.venv/bin/python -m analysis.run \
  --assignment distance_threshold --threshold 10 \
  --analyses edge_counts edge_lengths goal_side
```

---



## Repository layout


| Path               | Role                                                                                |
| ------------------ | ----------------------------------------------------------------------------------- |
| `input/`           | FIFA enriched folder + metadata JSON (Mode A input; gitignored)                     |
| `preprocess/`      | Convert → fix → validate → parquet → responsibility                                 |
| `data/`            | Pipeline outputs used by viewers and analysis                                       |
| `website/`         | Browser UIs (`index.html` = standard methods; `responsibility/` = thesis algorithm) |
| `serve.py`         | Local HTTP server + clip-export API (`localhost:8000`)                              |
| `analysis/`        | Full-match assignments and analyses → `analysis/output/`                            |
| `clips/`           | Broadcast MP4 and exported clips/images                                             |
| `requirements.txt` | Python dependencies                                                                 |
| `index.html`       | Redirects to `website/index.html`                                                   |


---



## Setup

**Requirements**

- Python **3.10+** (3.13 works in development)
- Dependencies in `requirements.txt`: `pyarrow`, `pandas`, `scipy`, `matplotlib`, `floodlight` (needed for responsibility space zones)
- A modern browser
- `ffmpeg` / `ffprobe` **only** if you export pitch + broadcast clips

```bash
cd /path/to/defense
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

Always run preprocess and analysis commands from the **repository root**, using the venv interpreter (or an activated venv).

---



## 1. Prepare input data



### Mode A — FIFA World Cup enriched delivery

Place **exactly one** enriched directory and **exactly one** metadata JSON in `input/`:

```text
input/
├── 20260613_FWC_XX_ABC-XYZ_HEI_Scrubbed_Data_Enriched/
│   └── *.enriched
└── 20260613_FWC_XX_ABC-XYZ_FIFA_Unified_Event_Data_Metadata.json
```

Discovery is by pattern (not by fixed match name):

- Metadata: exactly one `input/*Metadata.json`
- Enriched: exactly one directory whose name ends with `_Enriched`, containing `*.enriched` files named like `*_N_N_N.football...` (parsed by `preprocess/convert_fwc.py`)

**Metadata fields used by the converter**


| Field                                     | Use                                                |
| ----------------------------------------- | -------------------------------------------------- |
| `home_team_id` / `away_team_id`           | Map enriched `teamId` → home/away                  |
| `home_team_name` / `away_team_name`       | Display names in `metaData.json`                   |
| `home_team_players` / `away_team_players` | Roster; `player_id` must match enriched `playerId` |
| `video_kickoff_time`, `phases`            | Broadcast sync → `metaData.json` → `videoSync`     |


Coordinates in enriched samples are centimetres with a corner-style origin; the converter maps them to **metres with origin at pitch centre** on a **105 × 68 m** pitch.

### Mode B — custom / already-converted tracking

Place files directly under `data/` (no FIFA folder required):

```text
data/
  tracking.jsonl    # required
  metaData.json     # optional
```

Then run the **same** preprocess command (see §2). Conversion is skipped; fix → validate → parquet → responsibility still run.

### Optional broadcast video (clip export)

```text
clips/281-M08-QAT-SUI-camera1-720p.mp4
```

This filename is hardcoded in `serve.py` → `find_source_video()`. For another match, rename the file to match or edit that path.

---



## 2. Preprocess

```bash
.venv/bin/python preprocess/run.py
.venv/bin/python preprocess/run.py --no-zones
.venv/bin/python preprocess/run.py --input-dir input --output-dir data
.venv/bin/python preprocess/run.py --skip-responsibility   # stop after parquet
```


| Flag                     | Default  | Meaning                                                     |
| ------------------------ | -------- | ----------------------------------------------------------- |
| `--input-dir`            | `input/` | Delivery root                                               |
| `--output-dir`           | `data/`  | All outputs                                                 |
| `--skip-responsibility`  | off      | Skip `responsibility.jsonl` / zones                         |
| `--responsibility-limit` | none     | Cap live frames (debug / smoke tests)                       |
| `--no-zones`             | off      | Skip `responsibility_zones.jsonl` (zones **on** by default) |
| `--zones-stride`         | `2`      | Subsample responsibility frames for zones                   |
| `--zones-xpoints`        | `50`     | Voronoi mesh resolution                                     |


**Mode selection:** if `input/` looks like FIFA enriched data (any `*Metadata.json` or `*_Enriched` directory), Mode A runs and **rebuilds** `data/` from enriched. Otherwise, if `data/tracking.jsonl` exists, Mode B runs. If both exist, **Mode A wins**.

### What the pipeline does

**Mode A only**

1. Scan `.enriched` files.
2. Write `data/tracking.jsonl` (one JSON object per frame).
3. Write `data/metaData.json` (teams, players, kit colours, optional `videoSync`).

**Both modes**

1. **Jump fix** (`fix_tracking.py`) in place on `tracking.jsonl`:
  - interpolate clean single-frame position spikes;
  - mark severe / systemic teleports as `live: false`;
  - replace player `speed` when it disagrees with position deltas by more than **5 m/s**;
  - recompute ball `speed` / `direction` from forward position deltas (enriched ball kinematics are treated as unreliable).
2. **Validate** (`validate_tracking.py`) and print a report. The orchestrator **does not abort** on warnings.
3. Write `data/tracking.parquet` (one row per entity per frame, including non-live frames).
4. Unless `--skip-responsibility`: write `responsibility.jsonl`, and by default `responsibility_zones.jsonl` (needs `floodlight`; skip with `--no-zones`).

Standalone re-fix / re-validate (normally unnecessary after a full preprocess):

```bash
.venv/bin/python preprocess/fix_tracking.py data/tracking.jsonl
.venv/bin/python preprocess/validate_tracking.py data/tracking.jsonl
```

After a standalone fix, re-run `preprocess/run.py` in Mode B so parquet and responsibility stay aligned.

### Outputs


| File                              | Used by                                                            |
| --------------------------------- | ------------------------------------------------------------------ |
| `data/tracking.jsonl`             | Both viewers                                                       |
| `data/metaData.json`              | Both viewers (optional but recommended)                            |
| `data/tracking.parquet`           | `python -m analysis.run`                                           |
| `data/responsibility.jsonl`       | Responsibility viewer; `--assignment responsibility`               |
| `data/responsibility_zones.jsonl` | Responsibility viewer / analysis (space zones; default)            |




### When to rerun preprocess


| Change                                              | Action                                                                                                                               |
| --------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------ |
| New / replaced FIFA files in `input/`               | Full `preprocess/run.py` (Mode A)                                                                                                    |
| Edited `data/tracking.jsonl` by hand                | `preprocess/run.py` (Mode B; clear `input/` of enriched files if you must avoid Mode A)                                              |
| Only responsibility algorithm / zone params changed | Re-run preprocess, or temporarily use `--skip-responsibility` then a dedicated responsibility rebuild via full run without that flag |
| Only video sync values in `metaData.json`           | Edit `videoSync` and reload the viewer (no re-convert)                                                                               |


---



## 3. Match-specific and hardcoded settings

These are **not** read from FIFA as authoritative FPS / pitch size. Update every listed site if your data differ.


| What                                | Where                                                                                              | Notes                                                                      |
| ----------------------------------- | -------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------- |
| Frame rate **50 Hz**                | `preprocess/config.py`, `website/core/trackingJsonl.js`, `analysis/analyses/temporal_stability.py` | Assumed everywhere                                                         |
| Pitch **105 × 68 m**, centre origin | `preprocess/config.py`, viewer JS (`canvasHelper.js` / tracking load), `analysis/pitch.py`         | Duplicated across Python and JS                                            |
| Default kit colours                 | `preprocess/config.py`, viewer fallbacks                                                           | Home `#B73B92`, away `#3395AB`                                             |
| Broadcast MP4                       | `serve.py` → `find_source_video()`                                                                 | Default `clips/281-M08-QAT-SUI-camera1-720p.mp4`                           |
| Video sync fallback                 | `website/core/timeline.js` → `VIDEO_*_SEC`                                                         | Used only if `metaData.json` has no `videoSync` (Qatar–Switzerland values) |
| Responsibility algorithm params     | `preprocess/config.py`                                                                             | e.g. `V_MAX`, `MARKING_K=2`, `MARKING_ALPHA`, hull margin, majority window |
| Zone mesh defaults                  | `preprocess/config.py` / CLI                                                                       | `ZONES_STRIDE=2`, `ZONES_XPOINTS=50`                                       |
| Analysis pitch grid                 | `analysis/pitch.py`                                                                                | 12 × 8 cells                                                               |
| Analysis ball-distance bands        | `analysis/` zone helpers                                                                           | ≤5 m / 5–20 m / >20 m                                                      |
| Serve bind                          | `serve.py`                                                                                         | `localhost:8000`                                                           |


Team names and rosters come from FIFA metadata on convert (Mode A), not from hardcoded strings.

---



## 4. Video sync

On Mode A convert, `metaData.json` → `videoSync` is built from FIFA `video_kickoff_time` + `phases` (MP4 wall-clock seconds for half starts/ends). The viewer prefers that object via `matchMeta.js`. If it is missing, it falls back to the Qatar–Switzerland `VIDEO_*_SEC` constants in `timeline.js`.

**Always verify sync against your MP4.** For Qatar–Switzerland, FIFA’s `video_kickoff_time` did not match the broadcast file used in this project.

If sync is wrong:

1. Fix `video_kickoff_time` / `phases` in the input `*Metadata.json` and re-run preprocess (Mode A), **or**
2. Edit `data/metaData.json` → `videoSync` and reload (no re-convert), **or**
3. If there is no `videoSync`, edit `VIDEO_*_SEC` in `website/core/timeline.js`.

Clip export needs correct sync, `ffmpeg` on `PATH`, and the MP4 from `find_source_video()`. Exports land in `clips/clip/` and `clips/image/`.

---



## 5. Viewers

```bash
python3 serve.py
```


| URL                                                                                                                | Purpose                                              |
| ------------------------------------------------------------------------------------------------------------------ | ---------------------------------------------------- |
| [http://localhost:8000/website/index.html](http://localhost:8000/website/index.html)                               | Compare **standard marking algorithms** side by side |
| [http://localhost:8000/website/responsibility/index.html](http://localhost:8000/website/responsibility/index.html) | **Responsibility** thesis algorithm + space zones    |


Open via `serve.py`, not as a `file://` page — the UIs fetch `data/*` over HTTP.

### Standard marking viewer

Requires `data/tracking.jsonl` (+ optional `metaData.json`).

Four panels share the same frame, distance model, and overlays:

1. **Delaunay / shape graph** — spatial neighbourhood over outfield players (not a marking assignment)
2. **Distance threshold** — pairs within a cutoff (optional density-based threshold)
3. **k-nearest neighbours** — optional goal-side oriented ranking
4. **Perfect matching** — Hungarian one-to-one assignment, optional max length / graph restriction

Tune shared momentum and overlays above the pitches; each panel has its own controls. Clip export can record any panel.

### Responsibility viewer

Additionally requires:

- `data/responsibility.jsonl` (edges / carrier / contestants / near-ball set)
- `data/responsibility_zones.jsonl` (recommended; UI warns if missing)

High-level algorithm (precomputed in `preprocess/responsibility.py`):

1. Who can reach the ball first, and who can contest shortly after.
2. Near-ball region from those players and Delaunay teammates, then expanded.
3. Marking edges inside that region (oriented mutual 2-NN).
4. Outside the bubble, defender pitch-control zones.

Click a defender or their zone to highlight that space and their marking edge(s).

**Important:** most analysis assignments use each frame’s `attacking` field for defending/attacking sides. The responsibility viewer and `--assignment responsibility` use reachability-based possession (`possessionTeam` / `carrierId`, majority-smoothed). Those two sources can diverge on some frames.

---



## 6. Full-match analysis

Requires `data/tracking.parquet` (written by preprocess).

```bash
.venv/bin/python -m analysis.run \
  --assignment <name> [assignment options] \
  --analyses <analysis> [<analysis> ...] \
  [--data data/tracking.parquet] \
  [--out analysis/output] \
  [--live-only | --no-live-only]
```

Defaults: `--data data/tracking.parquet`, `--assignment distance_threshold`, `--threshold 10`, `--analyses edge_counts`, `--live-only` **on**, `--out analysis/output`.

```bash
.venv/bin/python -m analysis.run \
  --assignment distance_threshold --threshold 10 \
  --analyses edge_counts edge_lengths goal_side

.venv/bin/python -m analysis.run --assignment perfect_match --analyses edge_counts
.venv/bin/python -m analysis.run --assignment knn --k 1 --knn-mode defender-to-attacker --analyses edge_counts
.venv/bin/python -m analysis.run --assignment oriented_knn --k 2 --alpha 2 --behind-mode neutral --analyses edge_counts
.venv/bin/python -m analysis.run --assignment delaunay --analyses overlap edge_counts
.venv/bin/python -m analysis.run --assignment dynamic_threshold --dyn-scale 1.5 --dyn-min 5 --dyn-max 15 --analyses edge_counts
.venv/bin/python -m analysis.run --assignment responsibility --analyses responsibility
```

See `python -m analysis.run --help` for the full flag list (including `--momentum-lambda`, perfect-match `--pm-max-length` / `--pm-restrict`, optional `--responsibility-results` / `--responsibility-zones`, etc.).

### Assignments (`--assignment`)


| Name                 | Main options                                                                                                         |
| -------------------- | -------------------------------------------------------------------------------------------------------------------- |
| `distance_threshold` | `--threshold` (m); `--momentum-lambda`                                                                               |
| `dynamic_threshold`  | `--dyn-scale`, `--dyn-min`, `--dyn-max` (Euclidean; ignores momentum)                                                |
| `perfect_match`      | `--pm-max-length`, `--pm-restrict` (`none` / `knn` / `delaunay`), `--pm-k`, `--pm-knn-mode`; `--momentum-lambda`     |
| `knn`                | `--k`, `--knn-mode` (`defender-to-attacker`, `attacker-to-defender`, `both-mutual`, `both-all`); `--momentum-lambda` |
| `oriented_knn`       | `--k`, `--alpha`, `--behind-mode` (`neutral` / `penalize`); no momentum                                              |
| `delaunay`           | —                                                                                                                    |
| `shape_graph`        | —                                                                                                                    |
| `responsibility`     | Loads `data/responsibility.jsonl` (+ zones); optional `--responsibility-results` / `--responsibility-zones`          |


Note: CLI default for `--k` is **1**. The oriented kNN **sweep** and many thesis figures use `k=2` — set `--k 2` explicitly when reproducing those settings.

### Analyses (`--analyses`)

Run one or more names in a single `analysis.run` call (or use a sweep under `analysis/sweep_compare/` for parameter grids).

| Name | Role |
| ---- | ---- |
| `edge_counts` | Edges per frame; defender/attacker degree shares |
| `edge_lengths` | Distance distribution of edges |
| `goal_side` | Share of edges with defender goal-side of attacker |
| `temporal_stability` | Assignment spells and defender switches |
| `pitch_zones` | Metrics on a 12×8 attack-oriented pitch grid |
| `ball_zones` | Metrics by attacker–ball distance bands |
| `overlap` | Share of other assignments’ edges contained in the current one |
| `responsibility` | Edge categories, oriented-2NN overlap, near-ball / residual-zone summaries |

### Outputs

```text
analysis/output/{analysis}/{assignment_slug}/
  run_manifest.json
  *_summary.json
  *_per_frame.csv          # when applicable
  *.png                    # when the analysis plots
```

Example slugs: `distance_threshold__t10m`, `knn__k1__defender_to_attacker`.

### Parameter sweeps (optional)

Sweeps repeatedly call `analysis.run` and aggregate comparison plots. They can take a long time on a full match.

```bash
.venv/bin/python -m analysis.sweep_compare.threshold_sweep --k-min 5 --k-max 15
.venv/bin/python -m analysis.sweep_compare.knn_sweep
.venv/bin/python -m analysis.sweep_compare.oriented_knn_sweep
.venv/bin/python -m analysis.sweep_compare.momentum_overlap
```

- `threshold_sweep`’s `--k-min` / `--k-max` are **distance thresholds in metres**, not neighbour counts.
- Oriented sweep: mutual `k=2`, α grid × behind modes; comparison plots under `analysis/output/comparison/oriented_knn_sweep/`.
- Use `--compare-only` on threshold / knn / oriented sweeps to rebuild comparison plots from existing run folders.

---



## 7. Custom `tracking.jsonl` schema (Mode B)

One JSON object per line. Coordinates: metres on a **105 × 68 m** pitch, **origin at centre**. Assumed frame rate: **50 Hz**.

```json
{"period":1,"frameIdx":0,"gameClock":0.0,"live":true,"attacking":"home","homePlayers":[{"playerId":"10001","number":9,"xyz":[12.5,-8.0,0.0],"speed":2.5,"direction":62.8}],"awayPlayers":[{"playerId":"20001","number":7,"xyz":[-10.2,15.3,0.0],"speed":1.9,"direction":33.27}],"ball":{"xyz":[0.5,0.0,0.0],"speed":9.3,"direction":20.21}}
```


| Field                         | Meaning                                                                                                                        |
| ----------------------------- | ------------------------------------------------------------------------------------------------------------------------------ |
| `period`                      | Half index (1, 2, …)                                                                                                           |
| `gameClock`                   | Seconds from kickoff in that period                                                                                            |
| `live`                        | Ball in play (`--live-only` filters on this)                                                                                   |
| `attacking`                   | `"home"` or `"away"` — team in possession (used by analysis assignments)                                                       |
| `homePlayers` / `awayPlayers` | `playerId`, `number`, `xyz` required; `speed` / `direction` optional for plain playback but needed for momentum / reachability |
| `ball`                        | `xyz` required                                                                                                                 |




### `tracking.parquet`

Columns: `period`, `frameIdx`, `gameClock`, `live`, `attacking`, `team` (`home` / `away` / `ball`), `playerId`, `number`, `isGoalie`, `x`, `y`, `z`, `speed`, `direction`.

### `metaData.json` (optional)

`players[].id` must match JSONL `playerId`.

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

Without metadata: teams default to Home / Away; goalkeepers may be inferred from positions. Without `videoSync`: see §4.

---



## Assumptions and limitations

- **FIFA WC 2026 enriched format** is the supported official delivery. Other providers need a custom converter into the `tracking.jsonl` schema.
- **50 Hz** and **105 × 68 m** are assumed.
- Pitch size and FPS are **duplicated** in preprocess config, analysis, and website JS — changing one copy is not enough.
- Enrichment **ball kinematics** are discarded; ball speed/direction are recomputed from positions during fix.
- Validation in `preprocess/run.py` is **informational**; standalone `validate_tracking.py` may exit non-zero on the same data.
- Responsibility zones require `floodlight` and are slower than edge-only responsibility; use `--no-zones` for a faster preprocess if you only need the standard viewer or analysis.
- Goalkeepers are excluded from outfield marking graphs in analysis and viewers.
- The project does not ship match data; `input/`, `data/`, `clips/`, and `analysis/output/` are gitignored.

---



## Troubleshooting


| Problem                                              | What to check                                                                                    |
| ---------------------------------------------------- | ------------------------------------------------------------------------------------------------ |
| `Expected exactly one *Metadata.json` / `*_Enriched` | Only one of each under `input/`; names must match those patterns                                 |
| `No .enriched files`                                 | Files end in `.enriched` and match the `*_N_N_N.football…` naming the converter parses           |
| `Could not determine the start frame for period 2`   | Enriched samples must include `halfId: 2`                                                        |
| Missing players after convert                        | Enriched `playerId` must appear in metadata rosters                                              |
| Mode B unexpectedly overwritten                      | Clear enriched files from `input/` or Mode A will rebuild `data/`                                |
| `ImportError` / floodlight during zones              | Install `requirements.txt`, or pass `--no-zones`                                                 |
| Viewer shows no match                                | Use `serve.py`; confirm `data/tracking.jsonl`; check browser network failures                    |
| Responsibility viewer incomplete                     | Re-run preprocess without `--skip-responsibility`; ensure zones file if you want space colouring |
| Video / clip out of sync                             | See §4                                                                                           |
| Clip export fails                                    | `ffmpeg` on `PATH`; MP4 path in `find_source_video()`                                            |
| Analysis `FileNotFoundError` for parquet             | Run `preprocess/run.py` (or pass `--data`)                                                       |
| Wrong frame rate / pitch size                        | Update every site in the hardcoded table (§3)                                                    |


---



## Suggested checklist for a new FIFA match

1. Replace `input/` with exactly one `*_Enriched/` folder and one `*Metadata.json`.
2. Confirm 50 Hz and 105 × 68 m, or update all hardcoded sites (§3).
3. Place/rename the broadcast MP4 and update `serve.py` if needed; verify video sync (§4).
4. Install deps: `.venv/bin/pip install -r requirements.txt`.
5. Run `.venv/bin/python preprocess/run.py`.
6. Start `python3 serve.py` and check both viewers.
7. Run analyses: `.venv/bin/python -m analysis.run --assignment … --analyses …`.
8. Inspect `analysis/output/.../run_manifest.json` and summaries.

