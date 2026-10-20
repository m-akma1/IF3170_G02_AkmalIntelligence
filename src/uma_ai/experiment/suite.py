from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from uma_ai.core.params import RunParams, load_params

ROOT = Path(__file__).resolve().parents[3]
INPUT_DIR = ROOT / "data" / "input"
PARAM_DIR = ROOT / "data" / "param"
SUITE_DIR = ROOT / "data" / "experiment"
OUTPUT_DIR = ROOT / "output" / "experiments"


class ExperimentSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    algorithm: str                                   # kunci di solvers.SOLVERS ("hc", "sa", "ga")
    override: dict = Field(default_factory=dict)     # digabung (deep merge) ke parameter dasar
    runs: int | None = None                          # None = runs milik suite


class Suite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = ""                                   # "" = nama file suite
    input: str                                       # test case di data/input atau path JSON
    param: str = "default"                           # parameter dasar di data/param atau path JSON
    runs: int = 3
    seed: int = 3170                                 # seed run ke-k = seed + k
    experiments: list[ExperimentSpec]


def resolve(name: str, folder: Path) -> Path:
    """Nama file di `folder` (dengan atau tanpa .json), atau path file biasa."""
    path = Path(name)
    if path.is_file():
        return path
    path = folder / (name if name.endswith(".json") else f"{name}.json")
    if not path.is_file():
        available = ", ".join(sorted(p.stem for p in folder.glob("*.json")))
        raise SystemExit(f"File '{name}' tidak ditemukan di {folder}. Tersedia: {available}")
    return path


def load_suite(name: str) -> Suite:
    path = resolve(name, SUITE_DIR)
    with open(path, encoding="utf-8") as file:
        suite = Suite.model_validate(json.load(file))
    if not suite.name:
        suite.name = path.stem
    return suite


def _merge(base: dict, override: dict) -> dict:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def experiment_params(suite: Suite, spec: ExperimentSpec) -> RunParams:
    """Parameter dasar suite + override eksperimen, divalidasi ulang (kunci salah langsung error)."""
    base = load_params(resolve(suite.param, PARAM_DIR)).model_dump()
    return RunParams.model_validate(_merge(base, spec.override))
