import math
import random
import time
from typing import Tuple

from ..core import constraints, generator, model, neighbor, obj_func, params, state


def run_sa(
    var: model.Variable,
    run_params: params.RunParams | None = None,
    seed: int = 42,
) -> Tuple[model.TruckState, float, int]:
    p = run_params or params.RunParams()
    rng = random.Random(seed)

    current_state = generator.generate_initial_state(var)
    state.recompute(current_state)

    current_energy = obj_func.evaluate(current_state, params=p.objective)

    best_state = state.copy_state(current_state)
    best_energy = current_energy

    t0 = p.sa.t_start
    alpha = 0.999
    max_iterations = p.sa.iterations

    current_temp = t0
    stuck_count = 0

    for _ in range(1, max_iterations + 1):
        res = neighbor.random_neighbor(current_state, rng)

        if res is None:
            stuck_count += 1
            current_temp *= alpha
            continue

        _, snapshot = res

        state.recompute(current_state)

        neighbor_energy = obj_func.evaluate(current_state, params=p.objective)
        delta_e = neighbor_energy - current_energy

        if delta_e > 0 or rng.random() < math.exp(delta_e / current_temp):
            current_energy = neighbor_energy
            if current_energy > best_energy:
                best_energy = current_energy
                best_state = state.copy_state(current_state)
        else:
            state.undo(current_state, snapshot)
            stuck_count += 1

        current_temp *= alpha

    return best_state, best_energy, stuck_count