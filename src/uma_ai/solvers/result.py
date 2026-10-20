from __future__ import annotations

import random
import time
from collections.abc import Callable
from dataclasses import dataclass, field

from uma_ai.core import model, state
from uma_ai.core.params import RunParams


@dataclass
class SearchResult:
    """
    Common interface untuk semua algoritma (HC, SA, GA).
    """
    algorithm: str
    initial: model.TruckState
    final: model.TruckState
    initial_value: float
    final_value: float
    iterations: int
    duration: float = 0.0  # detik, diisi oleh run_timed
    history: dict[str, list] = field(default_factory=dict)
    stats: dict = field(default_factory=dict)


class History:
    """Penyimpan riwayat per kolom"""

    def __init__(self, *columns: str):
        self.columns = columns
        self._data: list[list] = [[] for _ in columns]

    def log(self, *values):
        for column, value in zip(self._data, values, strict=True):
            column.append(value)

    def __len__(self) -> int:
        return len(self._data[0]) if self._data else 0

    def as_dict(self) -> dict[str, list]:
        return dict(zip(self.columns, self._data))


# Solver(var, params, rng, initial) -> SearchResult. initial = None, state awal dibuat sendiri
Solver = Callable[[model.Variable, RunParams, random.Random, model.TruckState | None], SearchResult]


def initial_state(var: model.Variable, params: RunParams, rng: random.Random) -> model.TruckState:
    """State awal acak sesuai params.init (dipakai bersama oleh runner, HC, dan SA)."""
    init = params.init
    return state.random_state(
        var, rng, mode=init.mode, tries=init.tries, p_in=init.p_in,
        weight_ratio=init.weight_ratio, min_support=params.objective.min_support,
    )


def run_timed(solver: Solver, var: model.Variable, params: RunParams, rng: random.Random,
              initial: model.TruckState | None = None) -> SearchResult:
    """Menjalankan solver dan mengukur durasi pencarian saja (tanpa membuat state awal atau menyimpan)."""
    start = time.perf_counter()
    result = solver(var, params, rng, initial)
    result.duration = time.perf_counter() - start
    return result
