from __future__ import annotations

import json
import random
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from uma_ai.core import model
from uma_ai.core.params import RunParams
from uma_ai.solvers import LOCAL_SEARCH, SOLVERS
from uma_ai.solvers.result import initial_state, run_timed

from . import plots, save
from .suite import INPUT_DIR, OUTPUT_DIR, Suite, experiment_params, resolve

SEARCH_SEED_OFFSET = 1000


def _job(job: tuple) -> tuple[str, int, dict, dict]:
    """Satu run (bisa dijalankan di proses lain)."""
    experiment, algorithm, params_dict, input_path, run, seed, out_dir = job
    var = model.readJSON(input_path)
    params = RunParams.model_validate({**params_dict, "seed": seed})

    initial = initial_state(var, params, random.Random(seed)) if algorithm in LOCAL_SEARCH else None
    rng = random.Random(seed + SEARCH_SEED_OFFSET)
    result = run_timed(SOLVERS[algorithm], var, params, rng, initial)

    out_dir = Path(out_dir)
    summary = save.summarize(result, experiment, run, seed, Path(input_path).stem)
    save.save_run(out_dir, result, summary, params.model_dump())
    title = f"{experiment}, run {run}"
    plots.plot_objective(result.history, algorithm, out_dir / "objective.png", title)
    if "accept_prob" in result.history:
        plots.plot_accept_prob(result.history, out_dir / "accept_prob.png", title)
    return experiment, run, summary, result.history


def _report(summary: dict):
    print(
        f"  {summary['experiment']:<20} run {summary['run']}: "
        f"{summary['initial_value']:.1f} -> {summary['final_value']:.1f}, "
        f"{summary['iterations']} iterasi, {summary['duration_s']:.2f} s",
        flush=True,
    )


def _collect_summaries(suite_dir: Path) -> list[dict]:
    """Semua summary.json di folder suite (termasuk run lama), tanpa params."""
    rows = []
    for path in sorted(suite_dir.glob("*/run_*/summary.json")):
        with open(path, encoding="utf-8") as file:
            row = json.load(file)
        row.pop("params", None)
        rows.append(row)
    rows.sort(key=lambda r: (r["experiment"], r["run"]))
    return rows


def run_suite(suite: Suite, jobs: int = 1, only: set[str] | None = None,
              input_name: str | None = None) -> Path:
    input_path = resolve(input_name or suite.input, INPUT_DIR)

    suite_dir = OUTPUT_DIR / (suite.name if input_name is None else f"{suite.name}_{input_path.stem}")
    print(f"Suite {suite.name}: input {input_path.name}, output {suite_dir}")

    specs = []
    for spec in suite.experiments:
        if only and spec.name not in only:
            continue
        if spec.algorithm not in SOLVERS:
            print(f"  [lewati] {spec.name}: algoritma '{spec.algorithm}' belum tersedia", file=sys.stderr)
            continue
        specs.append(spec)

    work = []
    for spec in specs:
        params = experiment_params(suite, spec).model_dump()
        for k in range(spec.runs or suite.runs):
            run, seed = k + 1, suite.seed + k
            out_dir = suite_dir / spec.name / f"run_{run}"
            work.append((spec.name, spec.algorithm, params, str(input_path), run, seed, str(out_dir)))

    histories: dict[str, dict[int, dict]] = {spec.name: {} for spec in specs}
    if jobs > 1:
        with ProcessPoolExecutor(max_workers=jobs) as pool:
            for experiment, run, summary, history in pool.map(_job, work):
                histories[experiment][run] = history
                _report(summary)
    else:
        for job in work:
            experiment, run, summary, history = _job(job)
            histories[experiment][run] = history
            _report(summary)

    for spec in specs:
        runs = histories[spec.name]
        plots.plot_overlay(
            [runs[r] for r in sorted(runs)], spec.algorithm,
            suite_dir / spec.name / "overlay.png", f"{spec.name}, semua run",
        )

    if specs:
        save.write_summary_table(suite_dir / "summary.csv", _collect_summaries(suite_dir))
    return suite_dir
