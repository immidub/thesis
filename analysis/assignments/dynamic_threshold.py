"""Compactness-based dynamic distance threshold.

Extension of the fixed distance threshold: instead of one global radius, the
threshold is recomputed per frame from how compact the players currently are.

Compactness(frame) = the mean, over all outfield defenders, of the distance to their nearest outfield attacker

The frame threshold is then

    t(frame) = clip(scale * compactness(frame), min_threshold_m, max_threshold_m)

"""

from __future__ import annotations

import csv
import math
from pathlib import Path

import numpy as np

from analysis.assignments.base import Edge
from analysis.data import Frame


class DynamicThresholdAssignment:
    name = "dynamic_threshold"

    def __init__(
        self,
        scale: float = 1.5,
        min_threshold_m: float = 5.0,
        max_threshold_m: float = 15.0,
    ) -> None:
        if scale <= 0:
            raise ValueError("scale must be positive")
        if min_threshold_m <= 0:
            raise ValueError("min_threshold_m must be positive")
        if max_threshold_m < min_threshold_m:
            raise ValueError("max_threshold_m must be >= min_threshold_m")
        self.scale = float(scale)
        self.min_threshold_m = float(min_threshold_m)
        self.max_threshold_m = float(max_threshold_m)
        # One row per assigned frame: period, frameIdx, gameClock,
        # compactness_m, threshold_m. Filled during edges_for_frame.
        self.frame_thresholds: list[dict] = []

    def threshold_for_frame(self, compactness_m: float) -> float:
        raw = self.scale * compactness_m
        return min(max(raw, self.min_threshold_m), self.max_threshold_m)

    def write_variation_outputs(self, out_dir: Path) -> None:
        """Write the per-frame threshold log (CSV) and its distribution plot.
        """
        if not self.frame_thresholds:
            return

        var_dir = out_dir / "variations" / self.name
        var_dir.mkdir(parents=True, exist_ok=True)

        csv_path = var_dir / "frame_thresholds.csv"
        fieldnames = ["period", "frameIdx", "gameClock", "compactness_m", "threshold_m"]
        with csv_path.open("w", encoding="utf-8", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(self.frame_thresholds)
        print(f"Wrote {csv_path}", flush=True)

        plot_path = var_dir / "threshold_distribution.png"
        self.write_threshold_distribution_plot(plot_path)
        print(f"Wrote {plot_path}", flush=True)

        thresholds = np.array(
            [row["threshold_m"] for row in self.frame_thresholds], dtype=np.float64
        )
        p5, p95 = (float(v) for v in np.percentile(thresholds, [5, 95]))
        at_min = float((thresholds <= self.min_threshold_m).mean() * 100.0)
        at_max = float((thresholds >= self.max_threshold_m).mean() * 100.0)
        print(
            "frame_thresholds: "
            f"n={len(thresholds)} mean={thresholds.mean():.2f}m "
            f"median={float(np.median(thresholds)):.2f}m "
            f"p5={p5:.2f}m p95={p95:.2f}m "
            f"atMin={at_min:.1f}% atMax={at_max:.1f}%",
            flush=True,
        )

    def write_threshold_distribution_plot(self, path: Path) -> None:
        """Histogram of the per-frame thresholds chosen so far (share of frames)."""
        import matplotlib.pyplot as plt

        from analysis.assignments.meta import assignment_plot_label

        if not self.frame_thresholds:
            return

        thresholds = np.array(
            [row["threshold_m"] for row in self.frame_thresholds], dtype=np.float64
        )
        n = len(thresholds)
        bin_edges = np.arange(
            self.min_threshold_m, self.max_threshold_m + 0.5, 0.5
        )

        fig, ax = plt.subplots(figsize=(8.5, 4.2))
        ax.hist(
            thresholds,
            bins=bin_edges,
            weights=np.full(n, 100.0 / n),
            color="#3d6b8c",
            edgecolor="white",
            linewidth=0.6,
        )

        mean_t = float(thresholds.mean())
        median_t = float(np.median(thresholds))
        p5, p95 = (float(v) for v in np.percentile(thresholds, [5, 95]))
        ax.axvline(mean_t, color="#c0392b", linewidth=1.4, label=f"mean {mean_t:.2f} m")
        ax.axvline(
            median_t,
            color="#e67e22",
            linewidth=1.4,
            linestyle="--",
            label=f"median {median_t:.2f} m",
        )
        for value, label in ((p5, f"p5 {p5:.2f} m"), (p95, f"p95 {p95:.2f} m")):
            ax.axvline(value, color="#7f8c8d", linewidth=1.0, linestyle=":", label=label)

        pct_at_min = float((thresholds <= self.min_threshold_m).mean() * 100.0)
        pct_at_max = float((thresholds >= self.max_threshold_m).mean() * 100.0)
        ax.text(
            0.99,
            0.97,
            (
                f"n = {n} frames\n"
                f"clipped at {self.min_threshold_m:g} m: {pct_at_min:.1f}%\n"
                f"clipped at {self.max_threshold_m:g} m: {pct_at_max:.1f}%"
            ),
            transform=ax.transAxes,
            ha="right",
            va="top",
            fontsize=8.5,
            color="#444444",
        )

        ax.set_xlabel("Chosen threshold (m)")
        ax.set_ylabel("Share of frames (%)")
        ax.set_title(f"Per-frame threshold distribution — {assignment_plot_label(self)}")
        ax.legend(loc="upper left", fontsize=8.5, frameon=False)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        fig.tight_layout()
        fig.savefig(path, dpi=150)
        plt.close(fig)

    def edges_for_frame(self, frame: Frame) -> list[Edge]:
        defending = frame.defending_team
        if defending is None:
            return []

        attacking = "away" if defending == "home" else "home"
        defenders = frame.outfield_players(defending)
        attackers = frame.outfield_players(attacking)
        if not defenders or not attackers:
            return []

        def_xy = np.array([[p.x, p.y] for p in defenders], dtype=np.float64)
        att_xy = np.array([[p.x, p.y] for p in attackers], dtype=np.float64)
        # (n_def, n_att) squared distances
        delta = def_xy[:, None, :] - att_xy[None, :, :]
        dist_sq = np.einsum("ijk,ijk->ij", delta, delta)

        # Frame compactness: mean nearest-attacker distance across defenders.
        nearest_att_dist = np.sqrt(dist_sq.min(axis=1))
        compactness_m = float(nearest_att_dist.mean())
        threshold_m = self.threshold_for_frame(compactness_m)

        self.frame_thresholds.append(
            {
                "period": frame.period,
                "frameIdx": frame.frame_idx,
                "gameClock": frame.game_clock,
                "compactness_m": compactness_m,
                "threshold_m": threshold_m,
            }
        )

        threshold_sq = threshold_m * threshold_m
        i_idx, j_idx = np.nonzero(dist_sq <= threshold_sq)

        edges: list[Edge] = []
        for i, j in zip(i_idx.tolist(), j_idx.tolist()):
            edges.append(
                Edge(
                    defender_id=defenders[i].player_id,
                    attacker_id=attackers[j].player_id,
                    length_m=math.sqrt(float(dist_sq[i, j])),
                )
            )
        return edges
