"""Coordinate full-match marking analysis.

Example:
  python -m analysis.run \\
    --data data/tracking.parquet \\
    --assignment distance_threshold \\
    --threshold 10 \\
    --analyses edge_counts edge_lengths \\
    --live-only

Outputs:
  analysis/output/{analysis}/{assignment_slug}/
  e.g. analysis/output/edge_lengths/distance_threshold__t10m/
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


def _assignment_slug(assignment_name: str, params: dict) -> str:
    """Filesystem-safe folder name for one assignment configuration."""
    if assignment_name == "distance_threshold":
        threshold = params.get("threshold_m")
        if threshold is None:
            return "distance_threshold"
        threshold_str = f"{float(threshold):g}".replace(".", "p")
        return f"distance_threshold__t{threshold_str}m"
    if assignment_name == "knn":
        k = params.get("k", 1)
        mode = str(params.get("mode", "defender-to-attacker")).replace("-", "_")
        return f"knn__k{k}__{mode}"
    return assignment_name


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    parquet_path = args.data.resolve()
    out_dir = args.out.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    assignment_kwargs = _assignment_kwargs(args)
    assignment = create_assignment(args.assignment, **assignment_kwargs)
    assignment_slug = _assignment_slug(assignment.name, assignment_kwargs)
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
        analysis_out = out_dir / name / assignment_slug
        ctx = AnalysisContext(assignment=assignment, out_dir=analysis_out)
        print(f"Running analysis: {name} → {analysis_out}", flush=True)
        run_summaries[name] = analysis.run(frames, edges_by_frame, ctx)

        manifest = {
            "data": str(parquet_path),
            "assignment": assignment.name,
            "assignmentSlug": assignment_slug,
            "assignmentParams": assignment_kwargs,
            "analysis": name,
            "frameCount": len(frames),
            "liveOnly": args.live_only,
            "summary": run_summaries[name],
        }
        manifest_path = analysis_out / "run_manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        print(f"Wrote {manifest_path}", flush=True)

        if name == "edge_counts":
            s = run_summaries[name]
            mean_deg = s.get("meanDegree")
            max_deg = s.get("maxDegreeAcrossFrames")
            max_def = s.get("maxDefenderDegreeAcrossFrames")
            max_att = s.get("maxAttackerDegreeAcrossFrames")
            extra = ""
            if mean_deg is not None:
                extra = f" meanDegree={mean_deg:.2f}"
            if max_deg is not None:
                extra += f" maxDegree={max_deg}"
            if max_def is not None and max_att is not None:
                extra += f" maxDef/Att={max_def}/{max_att}"
            print(
                "edge_counts: "
                f"assignedFrames={s['assignedFrames']} "
                f"meanEdges={s['meanEdgesPerAssignedFrame']:.2f} "
                f"maxEdges={s['maxEdgesPerAssignedFrame']}"
                + extra,
                flush=True,
            )
        elif name == "edge_lengths":
            s = run_summaries[name]
            mean_d = s.get("meanDistance")
            if mean_d is None:
                print(f"edge_lengths: nEdges={s['nEdges']}", flush=True)
            else:
                print(
                    "edge_lengths: "
                    f"nEdges={s['nEdges']} "
                    f"mean={mean_d:.2f}m "
                    f"median={s['medianDistance']:.2f}m "
                    f"p95={s['p95Distance']:.2f}m "
                    f"max={s['maxDistance']:.2f}m",
                    flush=True,
                )
        elif name == "goal_side":
            s = run_summaries[name]
            if s.get("nEdges", 0) == 0:
                print("goal_side: nEdges=0", flush=True)
            else:
                print(
                    "goal_side: "
                    f"nEdges={s['nEdges']} "
                    f"goalSide={s['goalSidePercent']:.1f}% "
                    f"notGoalSide={s['notGoalSidePercent']:.1f}%",
                    flush=True,
                )
        elif name == "temporal_stability":
            s = run_summaries[name]
            mean_dur = s.get("meanDurationSec")
            mean_sw = s.get("meanSwitchesPerMinutePerPlayer")
            print(
                "temporal_stability: "
                f"spells={s.get('nSpells', 0)} "
                + (
                    f"meanDuration={mean_dur:.2f}s "
                    if mean_dur is not None
                    else ""
                )
                + (
                    f"meanSwitchRate={mean_sw:.2f}/min "
                    if mean_sw is not None
                    else ""
                )
                + f"totalSwitches={s.get('totalSwitches', 0)}",
                flush=True,
            )
        elif name == "pitch_zones":
            print(
                f"pitch_zones: assignedFrames={run_summaries[name].get('assignedFrames', 0)} "
                f"cells={len(run_summaries[name].get('zones', []))}",
                flush=True,
            )
        elif name == "ball_zones":
            zones = run_summaries[name].get("zones") or []
            brief = ", ".join(
                f"{z['zone']}={z.get('meanAttackerDegree')}" for z in zones
            )
            print(f"ball_zones: {brief}", flush=True)

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
        choices=[
            "edge_counts",
            "edge_lengths",
            "goal_side",
            "temporal_stability",
            "pitch_zones",
            "ball_zones",
        ],
        help="Analyses to run",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=repo_root / "analysis" / "output",
        help=(
            "Base output directory (default: analysis/output). "
            "Each run writes to {out}/{analysis}/{assignment_slug}/"
        ),
    )
    parser.add_argument(
        "--live-only",
        action="store_true",
        help="Skip non-live frames when iterating (assignment already returns [] when not live)",
    )
    return parser.parse_args(argv)


if __name__ == "__main__":
    sys.exit(main())
