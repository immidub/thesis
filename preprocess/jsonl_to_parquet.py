#!/usr/bin/env python3
"""
Build data/tracking.parquet from an existing tracking.jsonl (+ optional metaData.json).

Use this when you already have viewer JSONL (e.g. after uploading/sharing a match)
and need parquet for offline analysis — without re-running the FIFA converter.

Usage (from repo root):
    .venv/bin/python preprocess/jsonl_to_parquet.py
    .venv/bin/python preprocess/jsonl_to_parquet.py data/tracking.jsonl -o data/tracking.parquet
    .venv/bin/python preprocess/jsonl_to_parquet.py data/tracking.jsonl --meta data/metaData.json
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from convert_fwc_match import write_tracking_parquet


def main() -> int:
    repo_root = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "tracking_jsonl",
        type=Path,
        nargs="?",
        default=repo_root / "data" / "tracking.jsonl",
        help="Path to tracking.jsonl (default: data/tracking.jsonl)",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="Output parquet path (default: same directory as JSONL, tracking.parquet)",
    )
    parser.add_argument(
        "--meta",
        type=Path,
        default=None,
        help=(
            "Optional metaData.json for isGoalie flags "
            "(default: metaData.json next to the JSONL if present)"
        ),
    )
    args = parser.parse_args()

    tracking_path = args.tracking_jsonl.resolve()
    if not tracking_path.is_file():
        print(f"Error: tracking JSONL not found: {tracking_path}", file=sys.stderr)
        return 1

    parquet_path = (
        args.output.resolve()
        if args.output is not None
        else tracking_path.with_name("tracking.parquet")
    )

    if args.meta is not None:
        metadata_path = args.meta.resolve()
        if not metadata_path.is_file():
            print(f"Error: metadata not found: {metadata_path}", file=sys.stderr)
            return 1
    else:
        candidate = tracking_path.with_name("metaData.json")
        metadata_path = candidate if candidate.is_file() else None

    print(f"JSONL:    {tracking_path}")
    print(f"Metadata: {metadata_path if metadata_path else '(none — isGoalie left unset)'}")
    print(f"Parquet:  {parquet_path}")

    try:
        rows = write_tracking_parquet(tracking_path, parquet_path, metadata_path)
    except ImportError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1

    print(f"Done: {rows} entity rows → {parquet_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
