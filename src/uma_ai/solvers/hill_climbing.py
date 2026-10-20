from __future__ import annotations

import random
from collections.abc import Callable

from uma_ai.core import model, neighbor, obj_func, state
from uma_ai.core.params import RunParams

from .result import History, SearchResult, initial_state

EPS = 1e-9  # toleransi delta = 0 (sideways)

# on_step(current_climb_iteration, objective_value, consecutive sideways)
_OnStep = Callable[[int, float, int], None]


def _sample(truck: model.TruckState, rng: random.Random, params: RunParams,
            f: float) -> list[tuple[neighbor.Move, float]]:
    """
    Mengambil neighbors_per_step neighbor random. Return (Move, delta), state tidak berubah.
    Sample sebagian saja karena neighbors_per_step bisa sangat besar.
    """
    samples = []
    for _ in range(params.hc.neighbors_per_step):
        found = neighbor.random_neighbor(truck, rng, params.neighbor)
        if found is None:
            continue
        move, snapshot = found
        samples.append((move, obj_func.evaluate(truck, params.objective) - f))
        state.undo(truck, snapshot)
    return samples


def _pick(samples, mode: str, sideways: int, max_sideways: int, rng: random.Random):
    """sampel terpilih atau None, sideways count, dan alasan berhenti jika None."""
    uphill = [s for s in samples if s[1] > EPS]
    if mode == "stochastic":
        return (rng.choice(uphill), False, None) if uphill else (None, False, "local_optimum")
    if uphill:
        return max(uphill, key=lambda s: s[1]), False, None
    if mode == "sideways":
        flat = [s for s in samples if abs(s[1]) <= EPS]
        if flat:
            if sideways >= max_sideways:
                return None, False, "max_sideways"
            return rng.choice(flat), True, None
    return None, False, "local_optimum"


def _climb(truck: model.TruckState, rng: random.Random, params: RunParams, mode: str,
           on_step: _OnStep) -> tuple[int, int, str, int]:
    """
    Satu climb dari state `truck` (dimutasi) sampai berhenti.

    return (iterations, evaluations, stop_reason, total_sideways).
    """
    hc = params.hc
    f = obj_func.evaluate(truck, params.objective)
    iterations = evaluations = sideways = total_sideways = 0
    while iterations < hc.max_iterations:
        samples = _sample(truck, rng, params, f)
        evaluations += len(samples)
        chosen, is_sideways, reason = _pick(samples, mode, sideways, hc.max_sideways, rng)
        if chosen is None:
            return iterations, evaluations, reason, total_sideways

        snapshot = neighbor.apply_move(truck, chosen[0])
        if snapshot is None:
            raise RuntimeError(f"Move {chosen[0].kind} failed on state {truck}")
        f = obj_func.evaluate(truck, params.objective)
        iterations += 1
        if is_sideways:
            sideways += 1
            total_sideways += 1
        else:
            sideways = 0
        on_step(iterations, f, sideways)
    return iterations, evaluations, "max_iterations", total_sideways


def _run_single(initial: model.TruckState, rng: random.Random, params: RunParams) -> SearchResult:
    mode = params.hc.variant
    truck = state.copy_state(initial)
    f0 = obj_func.evaluate(truck, params.objective)

    if mode == "sideways":
        history = History("iteration", "value", "sideways")
        history.log(0, f0, 0)
        on_step = history.log
    else:
        history = History("iteration", "value")
        history.log(0, f0)
        on_step = lambda it, f, _: history.log(it, f)

    iterations, evaluations, reason, total_sideways = _climb(truck, rng, params, mode, on_step)

    stats = {"iterations": iterations, "evaluations": evaluations, "stop_reason": reason}
    if mode == "sideways":
        stats |= {"sideways_moves": total_sideways, "max_sideways": params.hc.max_sideways}
    return SearchResult(
        algorithm=f"hc-{mode}",
        initial=initial,
        final=truck,
        initial_value=f0,
        final_value=obj_func.evaluate(truck, params.objective),
        iterations=iterations,
        history=history.as_dict(),
        stats=stats,
    )


def _run_restart(var: model.Variable, initial: model.TruckState, rng: random.Random,
                 params: RunParams) -> SearchResult:
    """Climb pertama dari `initial`, lalu tepat max_restarts kali dari state acak baru. Ambil yang terbaik."""
    hc = params.hc
    history = History("iteration", "value", "best", "restart")
    best_state, best_f = None, float("-inf")
    iterations_per_restart, stop_reasons = [], []
    total_iterations = total_evaluations = 0

    for restart in range(hc.max_restarts + 1):
        truck = state.copy_state(initial) if restart == 0 else initial_state(var, params, rng)
        f = obj_func.evaluate(truck, params.objective)
        # iterasi global = total langkah sebelumnya, jadi awal restart tampil sebagai lompatan vertikal di plot
        offset = total_iterations
        history.log(offset, f, max(best_f, f), restart)

        # best_f tetap selama climb (diperbarui setelahnya), dan climb tidak pernah turun
        def on_step(it, value, _sideways, offset=offset, restart=restart, base=best_f):
            history.log(offset + it, value, max(base, value), restart)

        iterations, evaluations, reason, _ = _climb(truck, rng, params, hc.restart_base, on_step)
        total_iterations += iterations
        total_evaluations += evaluations
        iterations_per_restart.append(iterations)
        stop_reasons.append(reason)

        f = obj_func.evaluate(truck, params.objective)
        if f > best_f:
            best_state, best_f = truck, f

    return SearchResult(
        algorithm="hc-random_restart",
        initial=initial,
        final=best_state,
        initial_value=obj_func.evaluate(initial, params.objective),
        final_value=best_f,
        iterations=total_iterations,
        history=history.as_dict(),
        stats={
            "restarts": hc.max_restarts,
            "max_restarts": hc.max_restarts,
            "iterations_per_restart": iterations_per_restart,
            "climb_stop_reasons": stop_reasons,
            "restart_base": hc.restart_base,
            "evaluations": total_evaluations,
            "stop_reason": "max_restarts",
        },
    )


def run(var: model.Variable, params: RunParams, rng: random.Random,
        initial: model.TruckState | None = None) -> SearchResult:
    """
    Menjalankan Hill Climbing sesuai params.hc.variant. `initial` tidak diubah.
    """
    if initial is None:
        initial = initial_state(var, params, rng)
    if params.hc.variant == "random_restart":
        return _run_restart(var, initial, rng, params)
    return _run_single(initial, rng, params)


run_hc = run
