"""Marking metrics by attack-oriented 12×8 pitch grid cells (attacker location).

Coordinates are rotated per frame so the team in possession always attacks
toward +x (opponent goal on the right). A 180° flip (-x, -y) is used when
needed so for example left/right wings stay consistent across teams and period side-switches.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from analysis.analyses.base import AnalysisContext
from analysis.assignments.base import Edge
from analysis.assignments.meta import assignment_plot_label, assignment_summary_fields
from analysis.data import Frame
from analysis.pitch import (
    PITCH_ZONE_COLS,
    PITCH_ZONE_ROWS,
    attack_oriented_xy,
    home_goalkeeper_on_positive_x_by_period,
    pitch_cell,
    pitch_cell_center,
    pitch_cell_id,
)
from analysis.zone_metrics import (
    accumulate_zone_frame,
    attacker_degrees,
    edge_lengths_by_attacker,
    finalize_zone_stats,
    style_ax,
)


class PitchZonesAnalysis:
    name = "pitch_zones"

    def run(
        self,
        frames: list[Frame],
        edges_by_frame: list[list[Edge]],
        ctx: AnalysisContext,
    ) -> dict:
        if len(frames) != len(edges_by_frame):
            raise ValueError("frames and edges_by_frame length mismatch")

        gk_on_positive_x_by_period = home_goalkeeper_on_positive_x_by_period(frames)

        totals: dict[str, dict] = {}
        assigned_frames = 0

        for frame, edges in zip(frames, edges_by_frame):
            defending = frame.defending_team
            if defending is None:
                continue
            assigned_frames += 1
            attacking = "away" if defending == "home" else "home"
            attackers = frame.outfield_players(attacking)
            degrees = attacker_degrees(edges)
            lengths = edge_lengths_by_attacker(edges)
            home_gk_on_pos_x = gk_on_positive_x_by_period[frame.period]

            zone_of_attacker: dict[str, str] = {}
            for attacker in attackers:
                x_att, y_att = attack_oriented_xy(
                    attacker.x,
                    attacker.y,
                    attacking_team=attacking,
                    home_goalkeeper_on_positive_x_flag=home_gk_on_pos_x,
                )
                col, row = pitch_cell(x_att, y_att)
                zone_of_attacker[attacker.player_id] = pitch_cell_id(col, row)

            accumulate_zone_frame(
                zone_of_attacker=zone_of_attacker,
                degrees=degrees,
                lengths_by_attacker=lengths,
                totals=totals,
            )

        zone_order = [
            pitch_cell_id(col, row)
            for row in range(PITCH_ZONE_ROWS)
            for col in range(PITCH_ZONE_COLS)
        ]
        rows = finalize_zone_stats(
            totals, assigned_frames=assigned_frames, zone_order=zone_order
        )

        # Attach grid indices / centres for plotting (in attack-oriented space).
        enriched: list[dict] = []
        for row in rows:
            label = row["zone"]
            col = int(label.split("_")[0][1:])
            r = int(label.split("_")[1][1:])
            cx, cy = pitch_cell_center(col, r)
            enriched.append({**row, "col": col, "row": r, "centerX": cx, "centerY": cy})

        per_zone = pd.DataFrame(enriched)
        out_dir = ctx.out_dir
        out_dir.mkdir(parents=True, exist_ok=True)
        csv_path = out_dir / "pitch_zones_summary.csv"
        per_zone.to_csv(csv_path, index=False)

        summary = {
            "analysis": "pitch_zones",
            **assignment_summary_fields(ctx.assignment),
            "grid": {"cols": PITCH_ZONE_COLS, "rows": PITCH_ZONE_ROWS},
            "assignedFrames": assigned_frames,
            "anchor": "attacker_position_attack_oriented",
            "orientation": {
                "attackDirection": "+x (right)",
                "opponentGoal": "right side of plot (high column)",
                "ownHalf": "left side of plot (low column)",
                "note": (
                    "Per frame, attacker (x,y) is mapped so the team in possession "
                    "always attacks toward +x. When they attack toward -x in absolute "
                    "pitch coords, a 180 rotation (-x, -y) is applied so left/right "
                    "wings stay consistent across teams and period side-switches."
                ),
            },
            "metricsNote": (
                "Attackers are binned by attack-oriented pitch cell. Assignments/edge "
                "lengths are those edges whose attacker lies in the cell."
            ),
            "zones": enriched,
            "outputs": {
                "summaryCsv": str(Path("pitch_zones_summary.csv")),
                "summaryJson": str(Path("pitch_zones_summary.json")),
            },
        }

        plot_paths = _write_plots(per_zone, summary, out_dir)
        summary["outputs"].update(plot_paths)

        (out_dir / "pitch_zones_summary.json").write_text(
            json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        return summary


def _grid_matrix(per_zone: pd.DataFrame, column: str) -> np.ndarray:
    mat = np.full((PITCH_ZONE_ROWS, PITCH_ZONE_COLS), np.nan, dtype=np.float64)
    if per_zone.empty:
        return mat
    for _, row in per_zone.iterrows():
        value = row[column]
        if value is None or (isinstance(value, float) and np.isnan(value)):
            continue
        mat[int(row["row"]), int(row["col"])] = float(value)
    return mat


def _annotate_attack_direction(ax) -> None:
    """Show that plots are attack-oriented: own half left, opponent goal right."""
    ax.set_xlabel("Pitch cell column (own half → opponent goal)")
    ax.set_ylabel("Pitch cell row (width)")
    ax.text(
        0.0,
        1.02,
        "own half",
        transform=ax.transAxes,
        ha="left",
        va="bottom",
        fontsize=8,
        color="#555555",
    )
    ax.text(
        1.0,
        1.02,
        "opponent goal",
        transform=ax.transAxes,
        ha="right",
        va="bottom",
        fontsize=8,
        color="#555555",
    )


def _write_plots(per_zone: pd.DataFrame, summary: dict, out_dir: Path) -> dict[str, str]:
    import matplotlib.pyplot as plt

    assignment_label = assignment_plot_label(summary)
    outputs: dict[str, str] = {}

    heatmaps = [
        ("meanDegree", "Mean degree", "pitch_zones_mean_degree.png", "viridis"),
        ("pctUnmarkedAttackers", "% unmarked attackers", "pitch_zones_pct_unmarked.png", "YlOrRd"),
        ("meanEdgeLength", "Mean edge length (m)", "pitch_zones_mean_edge_length.png", "magma"),
        (
            "meanAssignmentsPerAssignedFrame",
            "Mean assignments / frame",
            "pitch_zones_mean_assignments.png",
            "Blues",
        ),
        (
            "meanAssignmentsPerFrameWithAttackerInZone",
            "Mean assignments / frame with attacker in zone",
            "pitch_zones_mean_assignments_when_present.png",
            "PuBu",
        ),
        ("doubleMarkingRate", "Double-marking rate (%)", "pitch_zones_double_marking.png", "Oranges"),
        (
            "tripleOrMoreMarkingRate",
            "3+ marking rate (%)",
            "pitch_zones_triple_or_more_marking.png",
            "Reds",
        ),
    ]

    for column, title, filename, cmap in heatmaps:
        path = out_dir / filename
        fig, ax = plt.subplots(figsize=(10, 5.6))
        mat = _grid_matrix(per_zone, column)
        masked = np.ma.masked_invalid(mat)
        im = ax.imshow(
            masked,
            origin="lower",
            aspect="equal",
            cmap=cmap,
            interpolation="nearest",
        )
        ax.set_xticks(range(PITCH_ZONE_COLS))
        ax.set_yticks(range(PITCH_ZONE_ROWS))
        ax.set_title(f"{title} — {assignment_label}")
        _annotate_attack_direction(ax)
        fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
        fig.tight_layout()
        fig.savefig(path, dpi=150, bbox_inches="tight")
        plt.close(fig)
        outputs[column + "Png"] = str(Path(filename))

    return outputs
