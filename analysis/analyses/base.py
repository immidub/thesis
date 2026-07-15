"""Shared types for whole-match analyses."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from analysis.assignments.base import Assignment, Edge
from analysis.data import Frame


@dataclass(frozen=True)
class AnalysisContext:
    assignment: Assignment
    out_dir: Path


class Analysis(Protocol):
    name: str

    def run(
        self,
        frames: list[Frame],
        edges_by_frame: list[list[Edge]],
        ctx: AnalysisContext,
    ) -> dict:
        """Run analysis and write outputs under ctx.out_dir. Return a summary dict."""
        ...
