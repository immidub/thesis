"""Edge overlap: share of other assignments' edges contained in the current one.

For each comparison source, counts how many of its edges also appear in the
edges of the assignment passed to ``run`` (same defender/attacker pair per
frame):

    shareContained = |source ∩ current| / |source|

Default sources: threshold 5/10/15 m, knn k∈{1,2} all modes, perfect_match.

Example::

  python -m analysis.run --assignment delaunay --analyses overlap
  # → analysis/output/overlap/delaunay/
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from analysis.analyses.base import AnalysisContext
from analysis.assignments import create_assignment
from analysis.assignments.base import Edge
from analysis.assignments.knn import KNN_MODES
from analysis.assignments.meta import (
    assignment_plot_label,
    assignment_slug,
    assignment_summary_fields,
)
from analysis.data import Frame

_FAMILY_COLORS = {
    "distance_threshold": "#3d6b8c",
    "knn": "#5b8fd9",
    "perfect_match": "#c47b3a",
}

# (assignment name, kwargs) checked against the current assignment's edges.
_SOURCES: list[tuple[str, dict]] = [
    ("distance_threshold", {"threshold_m": 5.0}),
    ("distance_threshold", {"threshold_m": 10.0}),
    ("distance_threshold", {"threshold_m": 15.0}),
    *[
        ("knn", {"k": k, "mode": mode})
        for k in (1, 2)
        for mode in KNN_MODES
    ],
    ("perfect_match", {}),
]


def _pairs(edges: list[Edge]) -> set[tuple[str, str]]:
    return {(e.defender_id, e.attacker_id) for e in edges}


class OverlapAnalysis:
    name = "overlap"

    def run(
        self,
        frames: list[Frame],
        edges_by_frame: list[list[Edge]],
        ctx: AnalysisContext,
    ) -> dict:
        if len(frames) != len(edges_by_frame):
            raise ValueError("frames and edges_by_frame length mismatch")

        target_sets = [_pairs(edges) for edges in edges_by_frame]
        target_slug = assignment_slug(ctx.assignment)
        rows: list[dict] = []

        for name, kwargs in _SOURCES:
            source = create_assignment(name, **kwargs)
            slug = assignment_slug(source)
            print(f"  overlap: {slug} → {target_slug}...", flush=True)

            n_source = 0
            n_contained = 0
            for frame, target in zip(frames, target_sets):
                pairs = _pairs(source.edges_for_frame(frame))
                if not pairs:
                    continue
                n_source += len(pairs)
                n_contained += sum(1 for p in pairs if p in target)

            share = (n_contained / n_source) if n_source else 0.0
            fields = assignment_summary_fields(source)
            rows.append(
                {
                    "assignment": source.name,
                    "assignmentSlug": slug,
                    "threshold_m": fields["threshold_m"],
                    "k": fields["k"],
                    "knnMode": fields["knnMode"],
                    "nSourceEdges": n_source,
                    "nContained": n_contained,
                    "shareContained": share,
                    "shareContainedPercent": round(100.0 * share, 4),
                }
            )

        out_dir = ctx.out_dir
        out_dir.mkdir(parents=True, exist_ok=True)

        comparisons = pd.DataFrame(rows)
        csv_path = out_dir / "overlap_comparisons.csv"
        comparisons.to_csv(csv_path, index=False)

        summary = {
            "analysis": self.name,
            "definition": (
                "shareContained = fraction of source-assignment edges whose "
                "(defender_id, attacker_id) pair also appears in the current "
                "assignment in the same frame."
            ),
            **assignment_summary_fields(ctx.assignment),
            "targetSlug": target_slug,
            "nFrames": len(frames),
            "comparisons": rows,
            "outputs": {
                "comparisonsCsv": str(Path("overlap_comparisons.csv")),
                "summaryJson": str(Path("overlap_summary.json")),
            },
        }
        summary["outputs"].update(_write_plots(comparisons, summary, out_dir))

        summary_path = out_dir / "overlap_summary.json"
        summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
        return summary


def _source_label(row: dict | pd.Series) -> str:
    name = row["assignment"]
    if name == "distance_threshold":
        return f"threshold {float(row['threshold_m']):g} m"
    if name == "knn":
        mode = str(row["knnMode"]).replace("-", " ")
        return f"knn k={int(row['k'])} {mode}"
    if name == "perfect_match":
        return "perfect match"
    return str(row.get("assignmentSlug") or name)


def _write_plots(
    comparisons: pd.DataFrame,
    summary: dict,
    out_dir: Path,
) -> dict[str, str]:
    import matplotlib.pyplot as plt

    path = out_dir / "overlap_share_contained.png"
    fig, ax = plt.subplots(figsize=(9.0, 5.5))

    if not comparisons.empty:
        labels = [_source_label(row) for _, row in comparisons.iterrows()]
        shares = comparisons["shareContainedPercent"].astype(float).tolist()
        colors = [
            _FAMILY_COLORS.get(str(name), "#888888")
            for name in comparisons["assignment"]
        ]
        y = range(len(labels))
        bars = ax.barh(y, shares, color=colors, edgecolor="white", linewidth=0.6)
        ax.set_yticks(list(y), labels)
        ax.set_xlim(0, 105)
        ax.invert_yaxis()
        for bar, share in zip(bars, shares):
            ax.text(
                min(share + 1.2, 103),
                bar.get_y() + bar.get_height() / 2,
                f"{share:.1f}%",
                ha="left",
                va="center",
                fontsize=8,
                color="#333333",
            )

    ax.set_xlabel("Share of source edges contained (%)")
    ax.set_title(
        f"Edge overlap with {assignment_plot_label(summary)}"
    )
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return {"shareContainedPng": str(Path(path.name))}
