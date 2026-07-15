"""Marking metrics by ball-centric zones (attacker location vs ball)."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from analysis.analyses.base import AnalysisContext
from analysis.assignments.base import Edge
from analysis.data import Frame
from analysis.pitch import (
    BALL_ZONE_COOPERATION_M,
    BALL_ZONE_NEAR_M,
    ball_zone,
)
from analysis.zone_metrics import (
    accumulate_zone_frame,
    attacker_degrees,
    edge_lengths_by_attacker,
    finalize_zone_stats,
    style_ax,
)

BALL_ZONE_ORDER = ["zone1_near", "zone2_cooperation", "zone3_far"]
BALL_ZONE_LABELS = {
    "zone1_near": f"Zone 1 (≤{BALL_ZONE_NEAR_M:.0f} m)",
    "zone2_cooperation": f"Zone 2 ({BALL_ZONE_NEAR_M:.0f}–{BALL_ZONE_COOPERATION_M:.0f} m)",
    "zone3_far": f"Zone 3 (>{BALL_ZONE_COOPERATION_M:.0f} m)",
}


class BallZonesAnalysis:
    name = "ball_zones"

    def run(
        self,
        frames: list[Frame],
        edges_by_frame: list[list[Edge]],
        ctx: AnalysisContext,
    ) -> dict:
        if len(frames) != len(edges_by_frame):
            raise ValueError("frames and edges_by_frame length mismatch")

        totals: dict[str, dict] = {}
        assigned_frames = 0
        skipped_no_ball = 0

        for frame, edges in zip(frames, edges_by_frame):
            defending = frame.defending_team
            if defending is None:
                continue
            if frame.ball is None:
                skipped_no_ball += 1
                continue

            assigned_frames += 1
            attacking = "away" if defending == "home" else "home"
            attackers = frame.outfield_players(attacking)
            degrees = attacker_degrees(edges)
            lengths = edge_lengths_by_attacker(edges)
            bx, by = frame.ball.x, frame.ball.y

            zone_of_attacker: dict[str, str] = {}
            for attacker in attackers:
                dist = float(np.hypot(attacker.x - bx, attacker.y - by))
                zone_of_attacker[attacker.player_id] = ball_zone(dist)

            accumulate_zone_frame(
                zone_of_attacker=zone_of_attacker,
                degrees=degrees,
                lengths_by_attacker=lengths,
                totals=totals,
            )

        rows = finalize_zone_stats(
            totals, assigned_frames=assigned_frames, zone_order=BALL_ZONE_ORDER
        )
        for row in rows:
            row["label"] = BALL_ZONE_LABELS.get(row["zone"], row["zone"])

        per_zone = pd.DataFrame(rows)
        out_dir = ctx.out_dir
        out_dir.mkdir(parents=True, exist_ok=True)
        csv_path = out_dir / "ball_zones_summary.csv"
        per_zone.to_csv(csv_path, index=False)

        summary = {
            "analysis": "ball_zones",
            "assignment": ctx.assignment.name,
            "threshold_m": getattr(ctx.assignment, "threshold_m", None),
            "zonesDefinition": {
                "zone1_near": f"attacker–ball distance ≤ {BALL_ZONE_NEAR_M} m",
                "zone2_cooperation": (
                    f"{BALL_ZONE_NEAR_M} m < distance ≤ {BALL_ZONE_COOPERATION_M} m"
                ),
                "zone3_far": f"distance > {BALL_ZONE_COOPERATION_M} m",
                "partition": "mutually exclusive",
            },
            "assignedFrames": assigned_frames,
            "skippedAssignedFramesNoBall": skipped_no_ball,
            "anchor": "attacker_position_relative_to_ball",
            "zones": rows,
            "outputs": {
                "summaryCsv": str(Path("ball_zones_summary.csv")),
                "summaryJson": str(Path("ball_zones_summary.json")),
            },
        }

        plot_paths = _write_plots(per_zone, summary, out_dir)
        summary["outputs"].update(plot_paths)

        (out_dir / "ball_zones_summary.json").write_text(
            json.dumps(summary, indent=2) + "\n", encoding="utf-8"
        )
        return summary


def _write_plots(per_zone: pd.DataFrame, summary: dict, out_dir: Path) -> dict[str, str]:
    import matplotlib.pyplot as plt

    assignment = summary.get("assignment", "assignment")
    outputs: dict[str, str] = {}
    labels = [BALL_ZONE_LABELS.get(z, z) for z in per_zone["zone"].tolist()]

    charts = [
        ("meanAttackerDegree", "Mean attacker degree", "ball_zones_mean_degree.png"),
        ("pctUnmarkedAttackers", "% unmarked attackers", "ball_zones_pct_unmarked.png"),
        ("meanEdgeLength", "Mean edge length (m)", "ball_zones_mean_edge_length.png"),
        (
            "meanAssignmentsPerAssignedFrame",
            "Mean assignments / frame",
            "ball_zones_mean_assignments.png",
        ),
        ("doubleMarkingRate", "Double-marking rate (%)", "ball_zones_double_marking.png"),
        ("totalAssignments", "Total assignments", "ball_zones_total_assignments.png"),
    ]

    colors = ["#c0392b", "#3d6b8c", "#7f8c8d"]

    for column, title, filename in charts:
        path = out_dir / filename
        fig, ax = plt.subplots(figsize=(7.2, 4.2))
        values = []
        for v in per_zone[column].tolist():
            if v is None or (isinstance(v, float) and np.isnan(v)):
                values.append(0.0)
            else:
                values.append(float(v))
        bars = ax.bar(labels, values, color=colors[: len(labels)], edgecolor="white", width=0.65)
        for bar, v, raw in zip(bars, values, per_zone[column].tolist()):
            if raw is None or (isinstance(raw, float) and np.isnan(raw)):
                continue
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height(),
                f"{v:.2f}" if abs(v) < 1000 else f"{v:,.0f}",
                ha="center",
                va="bottom",
                fontsize=8,
                color="#333333",
            )
        ax.set_ylabel(title)
        ax.set_title(f"{title} — {assignment}")
        style_ax(ax)
        fig.tight_layout()
        fig.savefig(path, dpi=150)
        plt.close(fig)
        outputs[column + "Png"] = str(Path(filename))

    return outputs
