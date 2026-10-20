from __future__ import annotations

import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class _Params(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ObjectiveParams(_Params):
    """
    Bobot penalti dinormalisasi: c_* x v_max (nilai paket terbesar yang muat di truk) per pelanggaran,
    kecuali berat: c_weight x vw_max (rasio nilai/berat terbesar) per unit kelebihan berat.
    Dengan c = 1, satu pelanggaran selalu lebih mahal dari paket mana pun.
    """
    variant: Literal[1, 2, 3, 4, 5] = 3
    c_floating: float = 1.0
    c_fragile: float = 1.0
    c_weight: float = 1.0
    c_eta: float = 0.01         # per pasangan LIFO (urutan bongkar) yang dilanggar
    c_support: float = 1.0      # variant_4: per paket yang alasnya tidak tertumpu sama sekali
    min_support: float = 0.5    # variant_4: rasio alas minimal yang harus tertumpu
    c_compact: float = 1.0      # variant_5: tie-breaker kerapatan (lantai dan dinding belakang)
    adaptive: bool = False      # solver menaikkan bobot penalti seiring iterasi


class InitParams(_Params):
    """Argumen `state.random_state`."""
    mode: Literal["drop", "ep"] = "drop"
    tries: int = 5
    p_in: float = 1.0
    weight_ratio: float | None = 1.0


class NeighborParams(_Params):
    """Peluang tiap jenis neighbor dan kebijakannya (lihat neighbor.py)."""
    w_relocate: float = 0.35
    w_outside: float = 0.10
    w_rotate: float = 0.20
    w_switch: float = 0.15      # tukar dua paket di dalam truk
    w_swap: float = 0.20        # tukar paket di dalam dengan paket di luar
    target_random: float = 1.0  # bobot tujuan relokasi: (x, y) acak,
    target_near: float = 1.0    # dekat posisi sekarang (dalam near_radius),
    target_ep: float = 1.0      # atau pojok paket lain (extreme point)
    near_radius: int = 2
    rotate_policy: Literal["strict", "redrop", "reanchor"] = "reanchor"
    swap_orient_tries: int = 6  # 1 = hanya orientasi saat ini
    similar_partner: bool = True
    partner_samples: int = 8
    settle: bool = True


class GAParams(_Params):
    pop_size: int = 50
    generations: int = 100
    crossover_rate: float = 0.8
    mutation_rate: float | None = None  # None = 1 / jumlah paket
    shift_mutation: int = 0             # > 0: mutasi geser (x, y) maksimal sejauh ini
    elitism: int = 1
    selection: Literal["roulette", "tournament"] = "roulette"
    tournament_k: int = 3
    eta_seed_frac: float = 0.0          # porsi populasi awal yang diurutkan berdasarkan ETA
    max_candidates: int | None = 64     # extreme point yang dicoba decoder per paket per truk


class HCParams(_Params):
    variant: Literal["steepest", "stochastic", "sideways", "random_restart"] = "steepest"
    neighbors_per_step: int = 50
    max_iterations: int = 10_000  # batas pengaman per climb
    max_sideways: int = 100       # sideways berturut-turut (reset setiap langkah naik)
    max_restarts: int = 10
    restart_base: Literal["steepest", "stochastic", "sideways"] = "steepest"  # climb tiap restart


class SAParams(_Params):
    t_start: float = 0.5
    t_end: float = 0.005
    cooling: Literal["geometric", "linear"] = "geometric"
    iterations: int = 100_000


class RunParams(_Params):
    seed: int | None = None
    objective: ObjectiveParams = Field(default_factory=ObjectiveParams)
    init: InitParams = Field(default_factory=InitParams)
    neighbor: NeighborParams = Field(default_factory=NeighborParams)
    ga: GAParams = Field(default_factory=GAParams)
    hc: HCParams = Field(default_factory=HCParams)
    sa: SAParams = Field(default_factory=SAParams)


def load_params(path: str) -> RunParams:
    with open(path, "r", encoding="utf-8") as file:
        return RunParams.model_validate(json.load(file))


def write_params(path: str, params: RunParams):
    with open(path, "w", encoding="utf-8") as file:
        json.dump(params.model_dump(), file, indent=2)
