"""Shared types for marking assignments."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from analysis.data import Frame


@dataclass(frozen=True)
class Edge:
    defender_id: str
    attacker_id: str
    length_m: float


class Assignment(Protocol):
    name: str

    def edges_for_frame(self, frame: Frame) -> list[Edge]:
        ...
