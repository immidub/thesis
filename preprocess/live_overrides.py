"""Apply durable live-flag corrections after convert (survives Mode A rebuilds).

Reads data/live_overrides.json (next to tracking.jsonl):

{
  "forceNotLive": [
    {
      "period": 1,
      "gameClockStart": 780.0,
      "gameClockEnd": 812.0,
      "note": "optional"
    }
  ]
}

Ranges are inclusive on both ends (period + gameClock seconds).
"""

from __future__ import annotations

import json
from pathlib import Path


def apply_live_overrides(tracking_path: Path, overrides_path: Path | None = None) -> dict:
    """Force live=false for configured ranges. Returns a small stats dict."""
    tracking_path = Path(tracking_path)
    overrides_path = Path(overrides_path) if overrides_path else tracking_path.parent / "live_overrides.json"
    stats = {
        "overridesPath": str(overrides_path),
        "ranges": 0,
        "framesMatched": 0,
        "framesForcedNotLive": 0,
        "applied": False,
    }
    if not overrides_path.is_file():
        return stats
    if not tracking_path.is_file():
        raise FileNotFoundError(tracking_path)

    payload = json.loads(overrides_path.read_text(encoding="utf-8"))
    ranges = payload.get("forceNotLive") or []
    if not ranges:
        return stats

    parsed: list[tuple[int, float, float]] = []
    for r in ranges:
        period = int(r["period"])
        start = float(r["gameClockStart"])
        end = float(r["gameClockEnd"])
        if end < start:
            raise ValueError(f"Invalid live override range (end < start): {r}")
        parsed.append((period, start, end))
    stats["ranges"] = len(parsed)

    tmp_path = tracking_path.with_suffix(tracking_path.suffix + ".tmp")
    matched = forced = 0
    with tracking_path.open("r", encoding="utf-8") as src, tmp_path.open(
        "w", encoding="utf-8"
    ) as dst:
        for line in src:
            raw = line.strip()
            if not raw:
                continue
            frame = json.loads(raw)
            period = int(frame.get("period") or 0)
            clock = float(frame.get("gameClock") or 0.0)
            hit = any(p == period and start <= clock <= end for p, start, end in parsed)
            if hit:
                matched += 1
                if frame.get("live") is not False:
                    frame["live"] = False
                    forced += 1
            dst.write(json.dumps(frame, separators=(",", ":")))
            dst.write("\n")

    tmp_path.replace(tracking_path)
    stats["framesMatched"] = matched
    stats["framesForcedNotLive"] = forced
    stats["applied"] = True
    return stats


def print_override_stats(stats: dict) -> None:
    if not stats.get("applied"):
        print(f"  No live overrides at {stats.get('overridesPath')} (skipped)")
        return
    print(
        f"  Live overrides: {stats['ranges']} range(s), "
        f"{stats['framesMatched']} frames matched, "
        f"{stats['framesForcedNotLive']} set live=false"
    )
