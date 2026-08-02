"""Orchestrate oriented mutual-2NN alpha sweeps (behind-mode × alpha).

Runs analysis.run for each (alpha, behind_mode) with fixed k=2 mutual selection,
then aggregates comparison tables/plots. Reuses complete existing outputs unless
--force is set. Plain mutual 2NN is not re-run here; compare pulls it in as a
baseline if present under knn__k2__both_mutual.

Example:
  python -m analysis.sweep_compare.oriented_knn_sweep
  python -m analysis.sweep_compare.oriented_knn_sweep --alphas 1 1.5 2 3 --compare-only
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from analysis.assignments.oriented_knn import BEHIND_MODES
from analysis.sweep_compare.oriented_knn_compare import (
    DEFAULT_ALPHAS,
    DEFAULT_K,
    REQUIRED_ANALYSES,
    compare_oriented_knn_sweep,
    config_label,
    expand_configs,
    oriented_slug,
    run_is_complete,
)


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


def _run_single(
    *,
    k: int,
    alpha: float,
    behind_mode: str,
    data: Path,
    out: Path,
    analyses: list[str],
    live_only: bool,
) -> dict:
    """Run analysis.run for one oriented kNN configuration. Returns status dict."""
    label = config_label(alpha, behind_mode)
    slug = oriented_slug(k, alpha, behind_mode)
    cmd = [
        sys.executable,
        "-m",
        "analysis.run",
        "--assignment",
        "oriented_knn",
        "--k",
        str(k),
        "--alpha",
        f"{float(alpha):g}",
        "--behind-mode",
        behind_mode,
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
    print(f"Running oriented kNN {label}  →  {slug}", flush=True)
    print(f"Command: {' '.join(cmd)}", flush=True)
    print(f"{'=' * 72}\n", flush=True)

    result = subprocess.run(cmd, capture_output=False)
    manifest = out / "edge_counts" / slug / "run_manifest.json"
    ok = result.returncode == 0 and manifest.is_file()
    status = {
        "k": k,
        "alpha": alpha,
        "behind_mode": behind_mode,
        "label": label,
        "slug": slug,
        "returnCode": result.returncode,
        "success": ok,
        "manifest": str(manifest) if manifest.is_file() else None,
        "skipped": False,
    }
    if not ok:
        print(f"FAILED {label} (return code {result.returncode})", flush=True)
    return status


def run_sweep(
    *,
    alphas: list[float],
    behind_modes: list[str],
    k: int,
    data: Path,
    out: Path,
    comparison_out: Path,
    analyses: list[str],
    live_only: bool,
    compare: bool,
    force: bool,
) -> int:
    """Run the oriented kNN sweep for each alpha × behind-mode configuration."""
    configs = expand_configs(alphas=alphas, behind_modes=behind_modes, k=k)
    statuses: list[dict] = []
    for cfg in configs:
        slug = cfg["slug"]
        if not force and run_is_complete(slug, out):
            print(
                f"Skipping complete run {cfg['label']} → {slug} "
                "(use --force to re-run)",
                flush=True,
            )
            statuses.append(
                {
                    "k": cfg["k"],
                    "alpha": cfg["alpha"],
                    "behind_mode": cfg["behind_mode"],
                    "label": cfg["label"],
                    "slug": slug,
                    "returnCode": 0,
                    "success": True,
                    "manifest": str(out / "edge_counts" / slug / "run_manifest.json"),
                    "skipped": True,
                }
            )
            continue
        try:
            statuses.append(
                _run_single(
                    k=cfg["k"],
                    alpha=cfg["alpha"],
                    behind_mode=cfg["behind_mode"],
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
                    "alpha": cfg["alpha"],
                    "behind_mode": cfg["behind_mode"],
                    "label": cfg["label"],
                    "slug": slug,
                    "returnCode": -1,
                    "success": False,
                    "error": str(exc),
                    "skipped": False,
                }
            )

    comparison_out.mkdir(parents=True, exist_ok=True)
    status_path = comparison_out / "sweep_status.json"
    status_path.write_text(
        json.dumps(
            {
                "k": k,
                "alphas": alphas,
                "behindModes": behind_modes,
                "analyses": analyses,
                "configs": [c["label"] for c in configs],
                "runs": statuses,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"\nWrote sweep status to {status_path}", flush=True)

    if compare:
        compare_oriented_knn_sweep(
            out_dir=out,
            comparison_dir=comparison_out,
            alphas=alphas,
            behind_modes=behind_modes,
            k=k,
            include_baseline=True,
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
            "Run oriented mutual-2NN alpha sweep (behind-mode × alpha) using "
            "analysis.run, then aggregate comparison outputs."
        ),
    )
    parser.add_argument(
        "--alphas",
        type=float,
        nargs="+",
        default=list(DEFAULT_ALPHAS),
        help=(
            "Orientation stretch values to sweep "
            f"(default: {' '.join(f'{a:g}' for a in DEFAULT_ALPHAS)})"
        ),
    )
    parser.add_argument(
        "--behind-modes",
        nargs="+",
        default=list(BEHIND_MODES),
        choices=list(BEHIND_MODES),
        help="Behind-attacker modes to sweep (default: both)",
    )
    parser.add_argument(
        "--k",
        type=int,
        default=DEFAULT_K,
        help=f"Neighbour count (default: {DEFAULT_K}, mutual selection)",
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
        default=repo / "analysis" / "output" / "comparison" / "oriented_knn_sweep",
        help="Directory for sweep comparison tables and plots",
    )
    parser.add_argument(
        "--analyses",
        nargs="+",
        default=list(REQUIRED_ANALYSES),
        choices=list(REQUIRED_ANALYSES),
        help="Analyses to run for each configuration",
    )
    parser.add_argument(
        "--live-only",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Skip non-live frames (default: on)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-run configurations even if complete outputs already exist",
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

    if args.compare_only:
        statuses = []
        status_path = args.comparison_out / "sweep_status.json"
        if status_path.is_file():
            payload = json.loads(status_path.read_text(encoding="utf-8"))
            statuses = payload.get("runs") or []
        compare_oriented_knn_sweep(
            out_dir=args.out.resolve(),
            comparison_dir=args.comparison_out.resolve(),
            alphas=args.alphas,
            behind_modes=args.behind_modes,
            k=args.k,
            include_baseline=True,
            statuses=statuses,
        )
        return 0

    return run_sweep(
        alphas=args.alphas,
        behind_modes=args.behind_modes,
        k=args.k,
        data=args.data.resolve(),
        out=args.out.resolve(),
        comparison_out=args.comparison_out.resolve(),
        analyses=args.analyses,
        live_only=args.live_only,
        compare=not args.no_compare,
        force=args.force,
    )


if __name__ == "__main__":
    sys.exit(main())
