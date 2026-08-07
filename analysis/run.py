"""Coordinate full-match marking analysis.

Example:
  python -m analysis.run \\
    --data data/tracking.parquet \\
    --assignment distance_threshold \\
    --threshold 10 \\
    --analyses edge_counts edge_lengths

Non-live frames are skipped by default; pass --no-live-only to include them.

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
from analysis.assignments.oriented_knn import BEHIND_MODES
from analysis.assignments.perfect_match import PERFECT_MATCH_RESTRICT_MODES
from analysis.assignments.meta import assignment_slug, assignment_summary_fields
from analysis.data import Frame, iter_frames, load_tracking


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    parquet_path = args.data.resolve()
    out_dir = args.out.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    assignment_kwargs = _assignment_kwargs(args) # get the assignment parameters from the arguments
    assignment = create_assignment(args.assignment, **assignment_kwargs) # create the assignment objects
    slug = assignment_slug(assignment)
    analysis_names = args.analyses

# load the tracking data from the parquet file
    print(f"Loading {parquet_path}...", flush=True)
    df = load_tracking(parquet_path)
    print(f"  {len(df)} entity rows", flush=True)

# build the frames from the tracking data
    print("Building frames...", flush=True)
    frames: list[Frame] = list(iter_frames(df, live_only=args.live_only))
    print(f"  {len(frames)} frames", flush=True)

    align = getattr(assignment, "align_frames", None)
    if align is not None:
        print("Aligning frames to responsibility possession...", flush=True)
        frames = align(frames)

# compute the edges for the assignment for each frame
    print(f"Computing edges ({assignment.name})...", flush=True)
    edges_by_frame = [assignment.edges_for_frame(frame) for frame in frames]
    total_edges = sum(len(edges) for edges in edges_by_frame)
    print(f"  {total_edges} edges across all frames", flush=True)

# assignment variations (e.g. dynamic_threshold) write their extra outputs
# to {out}/variations/ via this optional hook
    variation_outputs = getattr(assignment, "write_variation_outputs", None)
    if variation_outputs is not None:
        variation_outputs(out_dir)

# run the analyses
    run_summaries: dict[str, dict] = {}
    for name in analysis_names:
        analysis = create_analysis(name) # main call to the analysis module
        # Responsibility writes a single flat output folder.
        if analysis.name == "responsibility":
            analysis_out = out_dir / "responsibility"
        else:
            analysis_out = out_dir / name / slug
        ctx = AnalysisContext(assignment=assignment, out_dir=analysis_out)
        print(f"Running analysis: {name} → {analysis_out}", flush=True)
        run_summaries[name] = analysis.run(frames, edges_by_frame, ctx) # run the analysis

# write the manifest file
        assignment_fields = assignment_summary_fields(assignment)
        manifest = {
            "data": str(parquet_path),
            "assignment": assignment.name,
            "assignmentSlug": slug,
            "assignmentParams": {
                "threshold_m": assignment_fields["threshold_m"],
                "k": assignment_fields["k"],
                "mode": assignment_fields["knnMode"],
                "dynScale": assignment_fields["dynScale"],
                "dynMinThreshold_m": assignment_fields["dynMinThreshold_m"],
                "dynMaxThreshold_m": assignment_fields["dynMaxThreshold_m"],
                "orientedAlpha": assignment_fields["orientedAlpha"],
                "orientedBehindMode": assignment_fields["orientedBehindMode"],
                "pmMaxLength_m": assignment_fields["pmMaxLength_m"],
                "pmRestrict": assignment_fields["pmRestrict"],
                "momentum_lambda": assignment_fields.get("momentum_lambda", 0.0),
            },
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
            max_deg = s.get("maxDegreeAcrossFrames")
            max_def = s.get("maxDefenderDegreeAcrossFrames")
            max_att = s.get("maxAttackerDegreeAcrossFrames")
            extra = ""
            if max_deg is not None:
                extra = f" maxDegree={max_deg}"
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
            median_dur = s.get("medianDurationSec")
            mean_sw = s.get("meanSwitchesPerPlayer")
            mean_sw_rate = s.get("meanSwitchesPerActiveMinutePerPlayer")
            mean_spell_rate = s.get("meanSpellsPerActiveMinutePerPlayer")
            print(
                "temporal_stability: "
                f"spells={s.get('nSpells', 0)} "
                + (
                    f"meanDuration={mean_dur:.2f}s "
                    if mean_dur is not None
                    else ""
                )
                + (
                    f"medianDuration={median_dur:.2f}s "
                    if median_dur is not None
                    else ""
                )
                + (
                    f"meanSpells/activeMin={mean_spell_rate:.2f} "
                    if mean_spell_rate is not None
                    else ""
                )
                + (
                    f"meanSwitches/player={mean_sw:.1f} "
                    if mean_sw is not None
                    else ""
                )
                + (
                    f"meanSwitches/activeMin={mean_sw_rate:.2f}"
                    if mean_sw_rate is not None
                    else ""
                ),
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
                f"{z['zone']}:deg={z.get('meanDegree')}"
                + (
                    f",gs={z['goalSidePercent']:.1f}%"
                    if z.get("goalSidePercent") is not None
                    else ""
                )
                for z in zones
            )
            print(f"ball_zones: {brief}", flush=True)
        elif name == "responsibility":
            cats = run_summaries[name].get("categories") or []
            parts = [
                f"{c.get('category')}:edges/f={c.get('meanEdgesPerFrame', 0):.2f}"
                for c in cats
            ]
            print(f"responsibility: {', '.join(parts)}", flush=True)
            ov = run_summaries[name].get("overlapWithOrientedMutual2nn") or {}
            if ov.get("jaccard") is not None:
                print(
                    "  overlap: "
                    f"jaccard={100 * ov['jaccard']:.1f}%",
                    flush=True,
                )
            zl = run_summaries[name].get("spaceZoneAttackerLoad") or {}
            if zl.get("mean") is not None:
                print(
                    f"  zone load: mean={zl['mean']:.2f} p95={zl.get('p95'):.2f} max={zl.get('max')}",
                    flush=True,
                )
            nb = run_summaries[name].get("nearBallRegion") or {}
            players = nb.get("players") or {}
            defs = nb.get("defenders") or {}
            atts = nb.get("attackers") or {}
            area = nb.get("area_m2") or {}
            if players.get("mean") is not None:
                print(
                    f"  near-ball: players mean={players['mean']:.2f} "
                    f"(def={defs.get('mean', 0):.2f} att={atts.get('mean', 0):.2f}) "
                    f"p95={players.get('p95'):.2f}"
                    + (
                        f", area mean={area['mean']:.1f}m² p95={area.get('p95'):.1f}m²"
                        if area.get("mean") is not None
                        else ""
                    ),
                    flush=True,
                )
        elif name == "overlap":
            comps = run_summaries[name].get("comparisons") or []
            print(
                f"overlap: target={run_summaries[name].get('targetSlug')} "
                f"sources={len(comps)}",
                flush=True,
            )

    return 0


def _assignment_kwargs(args: argparse.Namespace) -> dict:
    lam = getattr(args, "momentum_lambda", 0.0)
    if args.assignment == "distance_threshold":
        return {"threshold_m": args.threshold, "momentum_lambda": lam}
    if args.assignment == "dynamic_threshold":
        return {
            "scale": args.dyn_scale,
            "min_threshold_m": args.dyn_min,
            "max_threshold_m": args.dyn_max,
        }
    if args.assignment == "knn":
        return {"k": args.k, "mode": args.knn_mode, "momentum_lambda": lam}
    if args.assignment == "oriented_knn":
        return {"k": args.k, "alpha": args.alpha, "behind_mode": args.behind_mode}
    if args.assignment == "perfect_match":
        kwargs = {
            "max_length_m": args.pm_max_length,
            "restrict": args.pm_restrict,
            "momentum_lambda": lam,
        }
        if args.pm_restrict == "knn":
            kwargs["k"] = args.pm_k
            kwargs["knn_mode"] = args.pm_knn_mode
        return kwargs
    if args.assignment == "responsibility":
        kwargs = {}
        if args.responsibility_results is not None:
            kwargs["results_path"] = args.responsibility_results
        if args.responsibility_zones is not None:
            kwargs["zones_path"] = args.responsibility_zones
        if args.responsibility_results is None and args.responsibility_zones is None:
            kwargs["data_dir"] = args.data.resolve().parent
        return kwargs
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
        choices=[
            "distance_threshold",
            "dynamic_threshold",
            "perfect_match",
            "knn",
            "oriented_knn",
            "delaunay",
            "shape_graph",
            "responsibility",
        ],
        help=(
            "Marking assignment: distance_threshold, dynamic_threshold "
            "(compactness-scaled radius), perfect_match "
            "(all-outfield min-cost matching; optional --pm-max-length / "
            "--pm-restrict), knn, oriented_knn "
            "(mutual knn with goal-side oriented cost), delaunay "
            "(bipartite all-outfield Delaunay), shape_graph "
            "(bipartite all-outfield shape graph), or responsibility "
            "(precomputed near-ball 2-NN + space-derived edges)"
        ),
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=10.0,
        help="Distance threshold in metres (distance_threshold only)",
    )
    parser.add_argument(
        "--pm-max-length",
        type=float,
        default=None,
        help=(
            "perfect_match only: forbid defender–attacker pairs longer than "
            "this distance in metres (e.g. 20)"
        ),
    )
    parser.add_argument(
        "--pm-restrict",
        default="none",
        choices=list(PERFECT_MATCH_RESTRICT_MODES),
        help=(
            "perfect_match only: extra allow-list on candidate pairs "
            "(none, knn, or delaunay)"
        ),
    )
    parser.add_argument(
        "--pm-k",
        type=int,
        default=2,
        help="perfect_match --pm-restrict knn: neighbour count (default: 2)",
    )
    parser.add_argument(
        "--pm-knn-mode",
        default="both-all",
        choices=list(KNN_MODES),
        help=(
            "perfect_match --pm-restrict knn: kNN mode "
            "(default: both-all)"
        ),
    )
    parser.add_argument(
        "--dyn-scale",
        type=float,
        default=1.5,
        help=(
            "dynamic_threshold only: multiplier applied to the frame "
            "compactness (mean nearest-attacker distance of defenders)"
        ),
    )
    parser.add_argument(
        "--dyn-min",
        type=float,
        default=5.0,
        help="dynamic_threshold only: lower clip for the frame threshold (m)",
    )
    parser.add_argument(
        "--dyn-max",
        type=float,
        default=15.0,
        help="dynamic_threshold only: upper clip for the frame threshold (m)",
    )
    parser.add_argument(
        "--k",
        type=int,
        default=1,
        help="Number of nearest neighbours (knn / oriented_knn)",
    )
    parser.add_argument(
        "--alpha",
        type=float,
        default=2.0,
        help=(
            "oriented_knn only: goal-side stretch factor (>= 1) of the "
            "anisotropic ranking cost"
        ),
    )
    parser.add_argument(
        "--behind-mode",
        default="neutral",
        choices=list(BEHIND_MODES),
        help=(
            "oriented_knn only: along-axis scale behind the attacker "
            "(neutral = 1, penalize = 1/alpha)"
        ),
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
        "--momentum-lambda",
        type=float,
        default=0.0,
        help=(
            "distance_threshold / knn / perfect_match: strength of the "
            "momentum adjustment d' = d - λ·v_towards (0 = Euclidean)"
        ),
    )
    parser.add_argument(
        "--responsibility-results",
        type=Path,
        default=None,
        help="responsibility only: path to responsibility.jsonl",
    )
    parser.add_argument(
        "--responsibility-zones",
        type=Path,
        default=None,
        help="responsibility only: path to responsibility_zones.jsonl",
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
            "overlap",
            "responsibility",
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
        action=argparse.BooleanOptionalAction,
        default=True,
        help=(
            "Skip non-live frames when building the frame list (default: on). "
            "Use --no-live-only to include dead-ball frames."
        ),
    )
    return parser.parse_args(argv)


if __name__ == "__main__":
    sys.exit(main())
