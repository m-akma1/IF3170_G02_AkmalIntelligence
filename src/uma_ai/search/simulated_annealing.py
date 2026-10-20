import math
import random
import time
from typing import Dict, Any, Tuple
from ..core import model, obj_func
from .neighbor import get_random_neighbor

def simulated_annealing(
    initial_state: model.TruckState,
    t0: float = 10000.0,
    alpha: float = 0.999,
    t_min: float = 1e-3,
    max_iterations: int = 10000,
) -> Tuple[model.TruckState, Dict[str, Any]]:
    start_time = time.time()

    current_state = initial_state
    current_val = obj_func.variant_2(current_state)

    best_state = current_state
    best_val = current_val

    current_temp = t0
    iteration = 0
    stuck_count = 0

    history_objective = [current_val]
    history_exp_prob = []

    while current_temp > t_min and iteration < max_iterations:
        iteration += 1
        neighbor = get_random_neighbor(current_state)
        neighbor_val = obj_func.variant_2(neighbor)

        delta_e = neighbor_val - current_val

        if delta_e > 0:
            current_state = neighbor
            current_val = neighbor_val
        elif delta_e == 0:
            current_state = neighbor
            current_val = neighbor_val
        else:
            try:
                acceptance_prob = math.exp(delta_e / current_temp)
            except OverflowError:
                acceptance_prob = 0.0

            history_exp_prob.append(acceptance_prob)

            if random.random() < acceptance_prob:
                current_state = neighbor
                current_val = neighbor_val
            else:
                stuck_count += 1

        if current_val > best_val:
            best_val = current_val
            best_state = current_state

        history_objective.append(current_val)
        current_temp *= alpha

    elapsed_time = time.time() - start_time

    metrics = {
        "initial_t0": t0,
        "final_temp": current_temp,
        "iterations": iteration,
        "stuck_count": stuck_count,
        "duration_sec": elapsed_time,
        "best_objective": best_val,
        "history_objective": history_objective,
        "history_exp_prob": history_exp_prob,
    }

    return best_state, metrics