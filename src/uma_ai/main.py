import sys
import time
from pathlib import Path

import viser

from uma_ai.core import model
from uma_ai.solvers import GA as ga

DEFAULT_INPUT = Path(__file__).resolve().parents[2] / "data" / "input" / "01_uma.json"


def main():
    server = viser.ViserServer()

    input_path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_INPUT
    var = model.readJSON(input_path)
    print(f"Total paket yabg ada: {len(var.packages)}")
    
    best_chrom, best_decoded, best_score, total_weight, total_value = ga.run_ga(
        var=var,
        pop_size=50,
        generations=100,
        crossover_rate=0.8,
    )
    print("Kromosom Terbaik:", best_chrom)
    print("Status Paket (Boolean Occupied):", best_decoded.package_occupied)
    print("Jumlah Clipping:", best_decoded.clip_count)
    print("Fitness Terbaik:", best_score)
    print(f"Total Weight : {best_decoded.truck_state.weight} / {[t.max_capacity for t in best_decoded.truck_state.trucks]}")
    print(f"Total Value : {total_value}")

    output_path = sys.argv[2] if len(sys.argv) > 2 else "output_result.json"
    final_var = model.state_to_variable(best_decoded.truck_state, objective_value=best_score)
    model.writeJSON(output_path, final_var)
    
    
    
    server.scene.add_icosphere(
        name="/hello_sphere",
        radius=0.5,
        color=(255, 0, 0),  # Red
        position=(0.0, 0.0, 0.0),
    )

    print("Open your browser to http://localhost:8080")
    print("Press Ctrl+C to exit")

    while True:
        time.sleep(10.0)


if __name__ == "__main__":
    main()