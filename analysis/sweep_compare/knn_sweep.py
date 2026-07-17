"""Orchestrate kNN assignment parameter sweeps (mode × k).

Runs the existing single-configuration analysis command for each combination
of kNN mode and neighbour count, then aggregates results for comparison.

Example:
  python -m analysis.sweep_compare.knn_sweep
  python -m analysis.sweep_compare.knn_sweep --k-values 1 2 3 --compare-only
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from analysis.assignments.knn import KNN_MODES
from analysis.sweep_compare.knn_compare import (
    DEFAULT_K_VALUES,
    compare_knn_sweep,
    config_label,
    expand_configs,
    knn_slug,
)

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


def _run_single(
    *,
    k: int,
    mode: str,
    data: Path,
    out: Path,
    analyses: list[str],
    live_only: bool,
) -> dict:
    """Run analysis.run for one kNN configuration. Returns status dict."""
    label = config_label(mode, k)
    slug = knn_slug(k, mode)
    cmd = [
        sys.executable,
        "-m",
        "analysis.run",
        "--assignment",
        "knn",
        "--k",
        str(k),
        "--knn-mode",
        mode,
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
    print(f"Running kNN {label}  →  {slug}", flush=True)
    print(f"Command: {' '.join(cmd)}", flush=True)
    print(f"{'=' * 72}\n", flush=True)

    result = subprocess.run(cmd, capture_output=False)
    manifest = out / "edge_counts" / slug / "run_manifest.json"
    ok = result.returncode == 0 and manifest.is_file()
    status = {
        "k": k,
        "mode": mode,
        "label": label,
        "slug": slug,
        "returnCode": result.returncode,
        "success": ok,
        "manifest": str(manifest) if manifest.is_file() else None,
    }
    if not ok:
        print(f"FAILED {label} (return code {result.returncode})", flush=True)
    return status


def run_sweep(
    *,
    k_values: list[int],
    modes: list[str],
    data: Path,
    out: Path,
    comparison_out: Path,
    analyses: list[str],
    live_only: bool,
    compare: bool,
) -> int:
    """Run the sweep for each kNN configuration."""
    configs = expand_configs(k_values=k_values, modes=modes)
    statuses: list[dict] = []
    for cfg in configs:
        try:
            statuses.append(
                _run_single(
                    k=cfg["k"],
                    mode=cfg["mode"],
                    data=data,
                    out=out,
                    analyses=analyses,
                    live_only=live_only,
                )
            )
        except Exception as exc:
            print(f"ERROR {cfg['label']}: {exc}", flush=True)
            statuses.append(
                {
                    "k": cfg["k"],
                    "mode": cfg["mode"],
                    "label": cfg["label"],
                    "slug": cfg["slug"],
                    "returnCode": -1,
                    "success": False,
                    "error": str(exc),
                }
            )

    comparison_out.mkdir(parents=True, exist_ok=True)
    status_path = comparison_out / "sweep_status.json"
    status_path.write_text(
        json.dumps(
            {
                "kValues": k_values,
                "modes": modes,
                "configs": [c["label"] for c in configs],
                "runs": statuses,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"\nWrote sweep status to {status_path}", flush=True)

    if compare: # compare the results of the sweep if the compare flag is set
        compare_knn_sweep(
            out_dir=out,
            comparison_dir=comparison_out,
            k_values=k_values,
            modes=modes,
            statuses=statuses,
        )

    failed = [s for s in statuses if not s.get("success")]
    if failed:
        print(
            f"\nSweep finished with {len(failed)} failed run(s): "
            f"{[s['label'] for s in failed]}",
            flush=True,
        )
        return 1
    print("\nSweep finished successfully for all configurations.", flush=True)
    return 0


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    repo = _repo_root()
    parser = argparse.ArgumentParser(
        description=(
            "Run kNN assignment parameter sweep (mode × k) using analysis.run, "
            "then aggregate comparison outputs."
        ),
    )
    parser.add_argument(
        "--k-values",
        type=int,
        nargs="+",
        default=list(DEFAULT_K_VALUES),
        help=f"Neighbour counts to sweep (default: {' '.join(map(str, DEFAULT_K_VALUES))})",
    )
    parser.add_argument(
        "--modes",
        nargs="+",
        default=list(KNN_MODES),
        choices=list(KNN_MODES),
        help="kNN modes to sweep (default: all four)",
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
        default=repo / "analysis" / "output" / "comparison" / "knn_sweep",
        help="Directory for sweep comparison tables and plots",
    )
    parser.add_argument(
        "--analyses",
        nargs="+",
        default=DEFAULT_ANALYSES,
        choices=DEFAULT_ANALYSES,
        help="Analyses to run for each configuration",
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

    if args.compare_only: # compare the results of the sweep if the compare_only flag is set
        statuses = []
        status_path = args.comparison_out / "sweep_status.json"
        if status_path.is_file():
            payload = json.loads(status_path.read_text(encoding="utf-8"))
            statuses = payload.get("runs") or []
        compare_knn_sweep( # compare the results of the sweep
            out_dir=args.out.resolve(),
            comparison_dir=args.comparison_out.resolve(),
            k_values=args.k_values,
            modes=args.modes,
            statuses=statuses,
        )
        return 0

    return run_sweep( # run the sweep for each kNN configuration
        k_values=args.k_values,
        modes=args.modes,
        data=args.data.resolve(),
        out=args.out.resolve(),
        comparison_out=args.comparison_out.resolve(),
        analyses=args.analyses,
        live_only=args.live_only,
        compare=not args.no_compare,
    )


if __name__ == "__main__":
    sys.exit(main())
