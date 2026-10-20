from . import genetic_alg, hill_climbing
from .result import Solver

SOLVERS: dict[str, Solver] = {
    "hc": hill_climbing.run,
    "ga": genetic_alg.run,
}

LOCAL_SEARCH = {"hc", "sa"}