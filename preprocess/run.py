#!/usr/bin/env python3
"""
Single preprocess entry point for viewers + analysis.

Mode A — FIFA enriched (+ *Metadata.json) in input/:
  convert → fix → validate → parquet → responsibility (+ zones by default)

Mode B — tracking.jsonl (+ optional metaData.json) already in data/:
  skip convert; fix → validate → parquet → responsibility (+ zones by default)

Preprocess files:
  run.py             this orchestrator
  config.py          shared pitch / speed / responsibility constants
  convert_fwc.py     FIFA enriched → tracking.jsonl + metaData.json
  fix_tracking.py    repair jumps / bad speeds in tracking.jsonl
  validate_tracking.py  report sanity issues in tracking.jsonl
  parquet_io.py      tracking.jsonl → tracking.parquet (for analysis)
  responsibility.py  build responsibility.jsonl (+ zones)

Usage (from repo root):
    python3 preprocess/run.py
    python3 preprocess/run.py --no-zones
    python3 preprocess/run.py --input-dir input --output-dir data
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from config import ZONES_STRIDE, ZONES_XPOINTS
from convert_fwc import convert_enriched_to_jsonl, find_input_paths, has_enriched_input
from fix_tracking import fix_tracking_jsonl, print_fix_stats
from parquet_io import write_tracking_parquet
from responsibility import build_results, build_zones
from validate_tracking import print_report, validate_tracking_jsonl


def count_jsonl_frames(path: Path) -> int:
    count = 0
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                count += 1
    return count


def finalize_tracking_outputs(output_dir: Path) -> None:
    tracking_path = output_dir / "tracking.jsonl"
    metadata_path = output_dir / "metaData.json"
    parquet_path = output_dir / "tracking.parquet"

    if not tracking_path.is_file():
        raise FileNotFoundError(f"Missing tracking.jsonl: {tracking_path}")

    meta_for_parquet = metadata_path if metadata_path.is_file() else None
    if meta_for_parquet is None:
        print(f"Note: no metaData.json at {metadata_path} (goalie flags may be missing in parquet)")

    print("Fixing tracking jumps...")
    print_fix_stats(fix_tracking_jsonl(tracking_path), tracking_path)

    print("Validating tracking.jsonl...")
    print_report(validate_tracking_jsonl(tracking_path), tracking_path)

    print("Writing tracking.parquet...")
    parquet_rows = write_tracking_parquet(tracking_path, parquet_path, meta_for_parquet)

    frames = count_jsonl_frames(tracking_path)
    print("Tracking outputs ready.")
    print(f"  {tracking_path} ({frames} frames)")
    if meta_for_parquet is not None:
        print(f"  {metadata_path}")
    print(f"  {parquet_path} ({parquet_rows} rows)")


def run_preprocess(
    input_dir: Path,
    output_dir: Path,
    *,
    skip_responsibility: bool = False,
    with_zones: bool = True,
    responsibility_limit: int | None = None,
    zones_stride: int = ZONES_STRIDE,
    zones_xpoints: int = ZONES_XPOINTS,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    existing_tracking = output_dir / "tracking.jsonl"

    if has_enriched_input(input_dir):
        find_input_paths(input_dir)  # clear error if delivery incomplete
        convert_enriched_to_jsonl(input_dir, output_dir)
    elif existing_tracking.is_file():
        print("Mode: existing data/tracking.jsonl (skip enriched conversion)")
        print(f"Output dir: {output_dir}")
        print(f"Using:      {existing_tracking}")
    else:
        raise FileNotFoundError(
            "No preprocess input found.\n"
            f"  Either put FIFA World Cup enriched tracking data (+ *Metadata.json) in {input_dir}\n"
            f"  Or place tracking.jsonl (+ optional metaData.json) in {output_dir}\n"
            "  then re-run this command."
        )

    finalize_tracking_outputs(output_dir)

    if skip_responsibility:
        return

    print("Precomputing responsibility results...")
    build_results(output_dir, limit=responsibility_limit)

    if with_zones:
        print("Precomputing responsibility zones...")
        build_zones(output_dir, stride=zones_stride, xpoints=zones_xpoints)


def main(argv: list[str] | None = None) -> int:
    repo_root = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, default=repo_root / "input")
    parser.add_argument("--output-dir", type=Path, default=repo_root / "data")
    parser.add_argument("--skip-responsibility", action="store_true")
    parser.add_argument("--responsibility-limit", type=int, default=None)
    parser.add_argument(
        "--no-zones",
        action="store_true",
        help="Skip responsibility_zones.jsonl (zones are computed by default).",
    )
    parser.add_argument("--zones-stride", type=int, default=ZONES_STRIDE)
    parser.add_argument("--zones-xpoints", type=int, default=ZONES_XPOINTS)
    args = parser.parse_args(argv)

    try:
        run_preprocess(
            args.input_dir.resolve(),
            args.output_dir.resolve(),
            skip_responsibility=args.skip_responsibility,
            with_zones=not args.no_zones,
            responsibility_limit=args.responsibility_limit,
            zones_stride=args.zones_stride,
            zones_xpoints=args.zones_xpoints,
        )
    except (FileNotFoundError, ValueError, KeyError, json.JSONDecodeError, ImportError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
