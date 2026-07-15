"""Coordinate full-match marking analysis.

Example:
  python -m analysis.run \\
    --data data/tracking.parquet \\
    --assignment distance_threshold \\
    --threshold 10 \\
    --analyses edge_counts \\
    --out analysis/output
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from analysis.analyses import create_analysis
from analysis.analyses.base import AnalysisContext
from analysis.assignments import create_assignment
from analysis.assignments.knn import KNN_MODES
from analysis.data import Frame, iter_frames, load_tracking


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    parquet_path = args.data.resolve()
    out_dir = args.out.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    assignment_kwargs = _assignment_kwargs(args)
    assignment = create_assignment(args.assignment, **assignment_kwargs)
    analysis_names = args.analyses

    print(f"Loading {parquet_path}...", flush=True)
    df = load_tracking(parquet_path)
    print(f"  {len(df)} entity rows", flush=True)

    print("Building frames...", flush=True)
    frames: list[Frame] = list(iter_frames(df, live_only=args.live_only))
    print(f"  {len(frames)} frames", flush=True)

    print(f"Computing edges ({assignment.name})...", flush=True)
    edges_by_frame = [assignment.edges_for_frame(frame) for frame in frames]
    total_edges = sum(len(edges) for edges in edges_by_frame)
    print(f"  {total_edges} edges across all frames", flush=True)

    run_summaries: dict[str, dict] = {}
    for name in analysis_names:
        analysis = create_analysis(name)
        analysis_out = out_dir / name
        ctx = AnalysisContext(assignment=assignment, out_dir=analysis_out)
        print(f"Running analysis: {name} → {analysis_out}", flush=True)
        run_summaries[name] = analysis.run(frames, edges_by_frame, ctx)

    manifest = {
        "data": str(parquet_path),
        "assignment": assignment.name,
        "assignmentParams": assignment_kwargs,
        "frameCount": len(frames),
        "liveOnly": args.live_only,
        "analyses": run_summaries,
    }
    manifest_path = out_dir / "run_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {manifest_path}", flush=True)

    if "edge_counts" in run_summaries:
        s = run_summaries["edge_counts"]
        print(
            "edge_counts: "
            f"assignedFrames={s['assignedFrames']} "
            f"meanEdges={s['meanEdgesPerAssignedFrame']:.2f} "
            f"maxEdges={s['maxEdgesPerAssignedFrame']}",
            flush=True,
        )

    return 0


def _assignment_kwargs(args: argparse.Namespace) -> dict:
    if args.assignment == "distance_threshold":
        return {"threshold_m": args.threshold}
    if args.assignment == "knn":
        return {"k": args.k, "mode": args.knn_mode}
    return {}


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    repo_root = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(
        description="Run full-match marking analyses on tracking.parquet",
    )
    parser.add_argument(
        "--data",
        type=Path,
        default=repo_root / "data" / "tracking.parquet",
        help="Path to tracking.parquet (default: data/tracking.parquet)",
    )
    parser.add_argument(
        "--assignment",
        default="distance_threshold",
        choices=["distance_threshold", "perfect_match", "knn"],
        help=(
            "Marking assignment: distance_threshold, perfect_match "
            "(all-outfield min-cost matching), or knn"
        ),
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=10.0,
        help="Distance threshold in metres (distance_threshold only)",
    )
    parser.add_argument(
        "--k",
        type=int,
        default=1,
        help="Number of nearest neighbours (knn only)",
    )
    parser.add_argument(
        "--knn-mode",
        default="defender-to-attacker",
        choices=list(KNN_MODES),
        help=(
            "knn direction mode: defender-to-attacker, attacker-to-defender, "
            "both-mutual (intersection), both-all (union)"
        ),
    )
    parser.add_argument(
        "--analyses",
        nargs="+",
        default=["edge_counts"],
        choices=["edge_counts"],
        help="Analyses to run",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=repo_root / "analysis" / "output",
        help="Output directory (default: analysis/output)",
    )
    parser.add_argument(
        "--live-only",
        action="store_true",
        help="Skip non-live frames when iterating (assignment already returns [] when not live)",
    )
    return parser.parse_args(argv)


if __name__ == "__main__":
    sys.exit(main())
