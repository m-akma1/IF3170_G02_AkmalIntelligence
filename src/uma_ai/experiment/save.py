"""Menyimpan hasil satu run: state awal/akhir, riwayat, dan ringkasan."""
from __future__ import annotations

import csv
import json
from pathlib import Path

from uma_ai.core import constraints, model, obj_func
from uma_ai.solvers.result import SearchResult


def write_state(path: Path, truck: model.TruckState, value: float):
    """Format sama dengan input (bisa dibaca ulang dengan model.readJSON)."""
    model.writeJSON(path, model.state_to_variable(truck, objective_value=value))


def write_history(path: Path, history: dict[str, list]):
    columns = list(history)
    with open(path, "w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(columns)
        for row in zip(*history.values()):
            writer.writerow("" if v is None else v for v in row)


def summarize(result: SearchResult, experiment: str, run: int, seed: int, input_name: str) -> dict:
    final = result.final
    return {
        "experiment": experiment,
        "run": run,
        "seed": seed,
        "input": input_name,
        "algorithm": result.algorithm,
        "initial_value": result.initial_value,
        "final_value": result.final_value,
        "duration_s": round(result.duration, 4),
        "iterations": result.iterations,
        "feasible": obj_func.is_feasible(final),
        "packages_inside": len(final.packages_inside),
        "packages_total": len(final.ids),
        "total_value": final.total_value,
        "total_weight": sum(final.weight),
        "capacity": sum(t.max_capacity for t in final.trucks),
        "overweight": constraints.overweight_amount(final),
        "fragile_pairs": final.n_fragile_pairs,
        "eta_pairs": final.n_eta_pairs,
        "floating": final.n_floating,
        **result.stats,
    }


def save_run(out_dir: Path, result: SearchResult, summary: dict, params: dict):
    out_dir.mkdir(parents=True, exist_ok=True)
    write_state(out_dir / "initial.json", result.initial, result.initial_value)
    write_state(out_dir / "final.json", result.final, result.final_value)
    write_history(out_dir / "history.csv", result.history)
    with open(out_dir / "summary.json", "w", encoding="utf-8") as file:
        json.dump({**summary, "params": params}, file, indent=2)


def write_summary_table(path: Path, rows: list[dict]):
    """Satu baris per run; nilai list/dict ditulis sebagai JSON."""
    columns = list(dict.fromkeys(key for row in rows for key in row))
    with open(path, "w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow({
                k: json.dumps(v) if isinstance(v, (list, dict)) else v for k, v in row.items()
            })
