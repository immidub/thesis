"""Orchestrate distance-threshold parameter sweeps (k = threshold in metres).

Runs the existing single-configuration analysis command for each integer
threshold in a range, then aggregates results for comparison.

Example:
  python -m analysis.sweep_compare.threshold_sweep --k-min 5 --k-max 15
  python -m analysis.sweep_compare.threshold_sweep --compare-only
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from analysis.sweep_compare.threshold_compare import compare_threshold_sweep

DEFAULT_ANALYSES = [
    "edge_counts",
    "edge_lengths",
    "goal_side",
    "temporal_stability",
    "pitch_zones",
    "ball_zones",
]


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


def _threshold_slug(k: int) -> str:
    threshold_str = f"{float(k):g}".replace(".", "p")
    return f"distance_threshold__t{threshold_str}m"


def _run_single(
    *,
    k: int,
    data: Path,
    out: Path,
    analyses: list[str],
    live_only: bool,
) -> dict:
    """Run analysis.run for one threshold value. Returns status dict."""
    cmd = [
        sys.executable,
        "-m",
        "analysis.run",
        "--assignment",
        "distance_threshold",
        "--threshold",
        str(k),
        "--data",
        str(data),
        "--out",
        str(out),
        "--analyses",
        *analyses,
    ]
    if live_only:
        cmd.append("--live-only")
    else:
        cmd.append("--no-live-only")

    print(f"\n{'=' * 72}", flush=True)
    print(f"Running threshold k={k} m  →  {_threshold_slug(k)}", flush=True)
    print(f"Command: {' '.join(cmd)}", flush=True)
    print(f"{'=' * 72}\n", flush=True)

    result = subprocess.run(cmd, capture_output=False)
    slug = _threshold_slug(k)
    manifest = out / "edge_counts" / slug / "run_manifest.json"
    ok = result.returncode == 0 and manifest.is_file()
    status = {
        "k": k,
        "slug": slug,
        "returnCode": result.returncode,
        "success": ok,
        "manifest": str(manifest) if manifest.is_file() else None,
    }
    if not ok:
        print(f"FAILED k={k} (return code {result.returncode})", flush=True)
    return status


def run_sweep(
    *,
    k_min: int,
    k_max: int,
    data: Path,
    out: Path,
    comparison_out: Path,
    analyses: list[str],
    live_only: bool,
    compare: bool,
) -> int:
    """Run the sweep for each threshold value."""
    if k_min > k_max:
        raise ValueError("k_min must be <= k_max")

    k_values = list(range(k_min, k_max + 1))
    statuses: list[dict] = []
    for k in k_values:
        try:
            statuses.append(
                _run_single(
                    k=k,
                    data=data,
                    out=out,
                    analyses=analyses,
                    live_only=live_only,
                )
            )
        except Exception as exc:
            print(f"ERROR k={k}: {exc}", flush=True)
            statuses.append(
                {
                    "k": k,
                    "slug": _threshold_slug(k),
                    "returnCode": -1,
                    "success": False,
                    "error": str(exc),
                }
            )

    comparison_out.mkdir(parents=True, exist_ok=True)
    status_path = comparison_out / "sweep_status.json"
    status_path.write_text(
        json.dumps({"kValues": k_values, "runs": statuses}, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"\nWrote sweep status to {status_path}", flush=True)

    if compare: # compare the results of the sweep if the compare flag is set
        compare_threshold_sweep(
            k_values=k_values,
            out_dir=out,
            comparison_dir=comparison_out,
            statuses=statuses,
        )

    failed = [s for s in statuses if not s.get("success")]
    if failed:
        print(
            f"\nSweep finished with {len(failed)} failed run(s): "
            f"{[s['k'] for s in failed]}",
            flush=True,
        )
        return 1
    print("\nSweep finished successfully for all values.", flush=True)
    return 0


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    repo = _repo_root()
    parser = argparse.ArgumentParser(
        description=(
            "Run distance-threshold (k) parameter sweep using analysis.run, "
            "then aggregate comparison outputs."
        ),
    )
    parser.add_argument(
        "--k-min",
        type=int,
        default=5,
        help="Minimum threshold in metres (default: 5)",
    )
    parser.add_argument(
        "--k-max",
        type=int,
        default=15,
        help="Maximum threshold in metres (default: 15)",
    )
    parser.add_argument(
        "--data",
        type=Path,
        default=repo / "data" / "tracking.parquet",
        help="Path to tracking.parquet",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=repo / "analysis" / "output",
        help="Base analysis output directory",
    )
    parser.add_argument(
        "--comparison-out",
        type=Path,
        default=repo / "analysis" / "output" / "comparison" / "threshold_k_sweep",
        help="Directory for sweep comparison tables and plots",
    )
    parser.add_argument(
        "--analyses",
        nargs="+",
        default=DEFAULT_ANALYSES,
        choices=DEFAULT_ANALYSES,
        help="Analyses to run for each threshold value",
    )
    parser.add_argument(
        "--live-only",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Skip non-live frames (default: on)",
    )
    parser.add_argument(
        "--compare-only",
        action="store_true",
        help="Skip runs; only build comparison from existing outputs",
    )
    parser.add_argument(
        "--no-compare",
        action="store_true",
        help="Run sweep only; do not build comparison outputs",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    args.comparison_out.resolve().mkdir(parents=True, exist_ok=True)
    k_values = list(range(args.k_min, args.k_max + 1))

    if args.compare_only: # compare the results of the sweep if the compare_only flag is set
        statuses = [] 
        status_path = args.comparison_out / "sweep_status.json"
        if status_path.is_file():
            payload = json.loads(status_path.read_text(encoding="utf-8"))
            statuses = payload.get("runs") or []
        compare_threshold_sweep( # compare the results of the sweep
            k_values=k_values,
            out_dir=args.out.resolve(),
            comparison_dir=args.comparison_out.resolve(),
            statuses=statuses,
        )
        return 0

    return run_sweep( # run the sweep for each threshold value
        k_min=args.k_min,
        k_max=args.k_max,
        data=args.data.resolve(),
        out=args.out.resolve(),
        comparison_out=args.comparison_out.resolve(),
        analyses=args.analyses,
        live_only=args.live_only,
        compare=not args.no_compare,
    )


if __name__ == "__main__":
    sys.exit(main())
