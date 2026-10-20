from __future__ import annotations

import math
import random

from uma_ai.core import model, neighbor, obj_func, state
from uma_ai.core.params import RunParams, SAParams

from .result import History, SearchResult, initial_state


def _schedule(sa: SAParams, scale: float):
    """Generator suhu untuk iterasi 1..iterations."""
    t0, t1 = sa.t_start * scale, sa.t_end * scale
    n = max(1, sa.iterations - 1)
    if sa.cooling == "linear":
        for k in range(sa.iterations):
            yield max(t0 + (t1 - t0) * k / n, 1e-12)
        return
    alpha = sa.alpha if sa.alpha is not None else (t1 / t0) ** (1 / n)
    t = t0
    for _ in range(sa.iterations):
        yield t
        t *= alpha


def run(var: model.Variable, params: RunParams, rng: random.Random,
        initial: model.TruckState | None = None) -> SearchResult:
    sa = params.sa
    if initial is None:
        initial = initial_state(var, params, rng)
    current = state.copy_state(initial)
    f0 = f = obj_func.evaluate(current, params.objective)
    best_state, best_f = state.copy_state(current), f
    scale = current.v_max if sa.t_scale == "v_max" else 1.0

    history = History("iteration", "value", "best", "temperature", "delta", "accept_prob")
    history.log(0, f, best_f, sa.t_start * scale, None, None)
    stuck = accepted_worse = no_neighbor = 0

    for it, temp in enumerate(_schedule(sa, scale), start=1):
        found = neighbor.random_neighbor(current, rng, params.neighbor)
        if found is None:
            stuck += 1
            no_neighbor += 1
            history.log(it, f, best_f, temp, None, None)
            continue

        _, snapshot = found
        delta = obj_func.evaluate(current, params.objective) - f
        prob = math.exp(delta / temp) if delta < 0 else None
        if delta > 0 or rng.random() < math.exp(delta / temp):
            f += delta
            if delta < 0:
                accepted_worse += 1
            if f > best_f:
                best_f = f
                best_state = state.copy_state(current)
        else:
            state.undo(current, snapshot)
            stuck += 1
        history.log(it, f, best_f, temp, delta, prob)

    history_dict = history.as_dict()
    return SearchResult(
        algorithm="Simulated Annealing",
        initial=initial,
        final=best_state,
        initial_value=f0,
        final_value=best_f,
        iterations=sa.iterations,
        history=history_dict,
        stats={
            "stuck_count": stuck,
            "stuck_frequency": stuck / max(1, sa.iterations),
            "no_neighbor": no_neighbor,
            "accepted_worse": accepted_worse,
            "last_value": f,
            "t_start": history_dict["temperature"][0],
            "t_final": history_dict["temperature"][-1],
            "cooling": sa.cooling,
        },
    )


def run_sa(var: model.Variable, run_params: RunParams | None = None,
           seed: int = 42) -> tuple[model.TruckState, float, int]:
    """Antarmuka lama: (state terbaik, objective terbaik, jumlah stuck)."""
    result = run(var, run_params or RunParams(), random.Random(seed))
    return result.final, result.final_value, result.stats["stuck_count"]
