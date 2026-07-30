"""Momentum λ overlap sweep vs Euclidean edges.

Compares threshold (10 m), mutual 2NN, and perfect matching at
λ ∈ {0.5, 1, 1.5, 2} against the same method with λ = 0 (Euclidean).

Metrics (edge multisets aggregated over frames):
  shareContained = |Euc ∩ Mom| / |Euc|     (retained Euclidean edges)
  shareDropped   = |Euc − Mom| / |Euc|
  shareNew       = |Mom − Euc| / |Mom|
  jaccard        = |∩| / |∪|
  countRatio     = |Mom| / |Euc|

Example:
  python -m analysis.sweep_compare.momentum_overlap
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from analysis.assignments import create_assignment
from analysis.assignments.base import Edge
from analysis.data import Frame, iter_frames, load_tracking

LAMBDAS = (0.5, 1.0, 1.5, 2.0)

# (label, assignment name, kwargs for Euclidean / momentum base)
METHODS: list[tuple[str, str, dict]] = [
    ("threshold 10 m", "distance_threshold", {"threshold_m": 10.0}),
    ("mutual 2NN", "knn", {"k": 2, "mode": "both-mutual"}),
    ("perfect match", "perfect_match", {}),
]

_COLORS = {
    "threshold 10 m": "#3d6b8c",
    "mutual 2NN": "#5b8fd9",
    "perfect match": "#c47b3a",
}


def _pairs(edges: list[Edge]) -> set[tuple[str, str]]:
    return {(e.defender_id, e.attacker_id) for e in edges}


def _overlap_counts(
    euc_sets: list[set[tuple[str, str]]],
    momentum,
    frames: list[Frame],
) -> tuple[int, int, int]:
    """Return (n_euclid, n_momentum, n_contained)."""
    n_euc = 0
    n_mom = 0
    n_contained = 0
    for frame, euc in zip(frames, euc_sets):
        mom = _pairs(momentum.edges_for_frame(frame))
        if not euc and not mom:
            continue
        n_euc += len(euc)
        n_mom += len(mom)
        n_contained += len(euc & mom)
    return n_euc, n_mom, n_contained


def _metric_row(
    *,
    label: str,
    name: str,
    lam: float,
    n_euc: int,
    n_mom: int,
    n_contained: int,
) -> dict:
    n_dropped = n_euc - n_contained
    n_new = n_mom - n_contained
    n_union = n_euc + n_mom - n_contained
    share_contained = (n_contained / n_euc) if n_euc else 0.0
    share_dropped = (n_dropped / n_euc) if n_euc else 0.0
    share_new = (n_new / n_mom) if n_mom else 0.0
    jaccard = (n_contained / n_union) if n_union else 0.0
    count_ratio = (n_mom / n_euc) if n_euc else 0.0
    return {
        "method": label,
        "assignment": name,
        "momentum_lambda": lam,
        "nEuclideanEdges": n_euc,
        "nMomentumEdges": n_mom,
        "nContained": n_contained,
        "nDropped": n_dropped,
        "nNew": n_new,
        "shareContained": share_contained,
        "shareContainedPercent": round(100.0 * share_contained, 4),
        "shareDropped": share_dropped,
        "shareDroppedPercent": round(100.0 * share_dropped, 4),
        "shareNew": share_new,
        "shareNewPercent": round(100.0 * share_new, 4),
        "jaccard": jaccard,
        "jaccardPercent": round(100.0 * jaccard, 4),
        "countRatio": count_ratio,
    }


def run_sweep(
    frames: list[Frame],
    lambdas: tuple[float, ...] = LAMBDAS,
) -> pd.DataFrame:
    rows: list[dict] = []
    for label, name, base_kwargs in METHODS:
        euclidean = create_assignment(name, **base_kwargs, momentum_lambda=0.0)
        print(f"\n{label}: Euclidean baseline...", flush=True)
        euc_sets = [_pairs(euclidean.edges_for_frame(f)) for f in frames]
        for lam in lambdas:
            momentum = create_assignment(name, **base_kwargs, momentum_lambda=lam)
            print(f"  λ={lam:g}...", flush=True)
            n_euc, n_mom, n_contained = _overlap_counts(euc_sets, momentum, frames)
            rows.append(
                _metric_row(
                    label=label,
                    name=name,
                    lam=lam,
                    n_euc=n_euc,
                    n_mom=n_mom,
                    n_contained=n_contained,
                )
            )
    return pd.DataFrame(rows)


def _style_lambda_axis(ax, lambdas: list[float]) -> None:
    ax.set_xticks(lambdas)
    ax.set_xticklabels([f"{lam:g}" for lam in lambdas])
    ax.set_xlabel("Momentum λ")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)


def _write_metric_plot(
    df: pd.DataFrame,
    *,
    column: str,
    ylabel: str,
    title: str,
    out_path: Path,
    ylim: tuple[float, float] | None = None,
) -> None:
    import matplotlib.pyplot as plt

    lambdas = sorted(df["momentum_lambda"].unique().tolist())
    fig, ax = plt.subplots(figsize=(7.5, 4.5))
    for method, group in df.groupby("method", sort=False):
        ax.plot(
            group["momentum_lambda"],
            group[column],
            marker="o",
            label=method,
            color=_COLORS.get(str(method), "#888888"),
        )
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    if ylim is not None:
        ax.set_ylim(*ylim)
    ax.legend(frameon=False)
    _style_lambda_axis(ax, lambdas)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def _write_plots(df: pd.DataFrame, out_dir: Path) -> dict[str, str]:
    specs = [
        (
            "shareContainedPercent",
            "Share of Euclidean edges retained (%)",
            "Retained Euclidean edges",
            "momentum_overlap_retained.png",
            (0.0, 105.0),
        ),
        (
            "shareNewPercent",
            "Share of momentum edges that are new (%)",
            "New momentum edges",
            "momentum_overlap_new.png",
            (0.0, 105.0),
        ),
        (
            "jaccardPercent",
            "Jaccard overlap (%)",
            "Jaccard overlap",
            "momentum_overlap_jaccard.png",
            (0.0, 105.0),
        ),
        (
            "countRatio",
            "Edge count ratio |Mom| / |Euc|",
            "Edge count ratio",
            "momentum_overlap_count_ratio.png",
            None,
        ),
    ]
    outputs: dict[str, str] = {}
    for column, ylabel, title, filename, ylim in specs:
        path = out_dir / filename
        _write_metric_plot(
            df,
            column=column,
            ylabel=ylabel,
            title=title,
            out_path=path,
            ylim=ylim,
        )
        key = {
            "momentum_overlap_retained.png": "retainedPng",
            "momentum_overlap_new.png": "newPng",
            "momentum_overlap_jaccard.png": "jaccardPng",
            "momentum_overlap_count_ratio.png": "countRatioPng",
        }[filename]
        outputs[key] = filename

    # Keep the original retained-share filename as an alias of the retained plot.
    share_alias = out_dir / "momentum_overlap_share.png"
    retained = out_dir / "momentum_overlap_retained.png"
    share_alias.write_bytes(retained.read_bytes())
    outputs["sharePng"] = share_alias.name
    return outputs



def main(argv: list[str] | None = None) -> int:
    repo = Path(__file__).resolve().parent.parent.parent
    parser = argparse.ArgumentParser(
        description="Overlap of momentum-adjusted edges vs Euclidean (λ=0)",
    )
    parser.add_argument(
        "--data",
        type=Path,
        default=repo / "data" / "tracking.parquet",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=repo / "analysis" / "output" / "momentum_overlap",
    )
    parser.add_argument(
        "--live-only",
        action=argparse.BooleanOptionalAction,
        default=True,
    )
    args = parser.parse_args(argv)

    out_dir = args.out.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Loading {args.data}...", flush=True)
    df = load_tracking(args.data)
    frames = list(iter_frames(df, live_only=args.live_only))
    print(f"  {len(frames)} frames", flush=True)

    comparisons = run_sweep(frames)
    csv_path = out_dir / "momentum_overlap_comparisons.csv"
    comparisons.to_csv(csv_path, index=False)

    plot_outputs = _write_plots(comparisons, out_dir)

    summary = {
        "definition": {
            "shareContained": "|Euc ∩ Mom| / |Euc|",
            "shareDropped": "|Euc − Mom| / |Euc|",
            "shareNew": "|Mom − Euc| / |Mom|",
            "jaccard": "|∩| / |∪|",
            "countRatio": "|Mom| / |Euc|",
            "note": "Euclidean is the same assignment with λ=0; counts sum over frames.",
        },
        "lambdas": list(LAMBDAS),
        "methods": [m[0] for m in METHODS],
        "nFrames": len(frames),
        "liveOnly": args.live_only,
        "comparisons": comparisons.to_dict(orient="records"),
        "outputs": {
            "comparisonsCsv": str(csv_path.name),
            **plot_outputs,
        },
    }
    summary_path = out_dir / "momentum_overlap_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    print(f"\nWrote {csv_path}", flush=True)
    for key in (
        "retainedPng",
        "newPng",
        "jaccardPng",
        "countRatioPng",
        "sharePng",
    ):
        print(f"Wrote {out_dir / plot_outputs[key]}", flush=True)
    cols = [
        "method",
        "momentum_lambda",
        "shareContainedPercent",
        "shareDroppedPercent",
        "shareNewPercent",
        "jaccardPercent",
        "countRatio",
    ]
    print(comparisons[cols].to_string(index=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
