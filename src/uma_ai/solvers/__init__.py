from . import genetic_alg, hill_climbing, simulated_annealing
from .result import Solver

SOLVERS: dict[str, Solver] = {
    "hc": hill_climbing.run,
    "sa": simulated_annealing.run,
    "ga": genetic_alg.run,
}

LOCAL_SEARCH = {"hc", "sa"}
