import sys
import time
from pathlib import Path

SRC_PATH = Path(__file__).resolve().parents[1]
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

# Cek ketersediaan modul viser
try:
    import viser
    HAS_VISER = True
except ImportError:
    HAS_VISER = False
    print("[WARNING] Modul 'viser' tidak ditemukan. Menjalankan program dalam mode CLI tanpa visualisasi 3D.")

from uma_ai.core import constraints, model, params
from uma_ai.solvers import GA as ga
from uma_ai.solvers import SA as sa

DEFAULT_INPUT = Path(__file__).resolve().parents[2] / "data" / "input" / "01_uma.json"


def main():
    server = None
    if HAS_VISER:
        server = viser.ViserServer()

    input_path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_INPUT
    solver_choice = sys.argv[2].lower() if len(sys.argv) > 2 else "sa"
    output_path = sys.argv[3] if len(sys.argv) > 3 else "output_result.json"

    var = model.readJSON(input_path)
    print(f"Total paket yang ada: {len(var.packages)}")

    if solver_choice == "ga":
        print("\n=== Menjalankan Genetic Algorithm (GA) ===")
        best_chrom, best_decoded, best_score, total_weight, total_value = ga.run_ga(
            var=var,
            pop_size=50,
            generations=100,
            crossover_rate=0.8,
        )
        final_truck_state = best_decoded.truck_state
        print("Kromosom Terbaik:", best_chrom)
        print("Status Paket (Boolean Occupied):", best_decoded.package_occupied)
        print("Jumlah Clipping:", best_decoded.clip_count)
        print("Fitness Terbaik:", best_score)
        print(f"Total Weight : {final_truck_state.weight} / {[t.max_capacity for t in final_truck_state.trucks]}")
        print(f"Total Value  : {total_value}")

    else:
        print("\n=== Menjalankan Simulated Annealing (SA) ===")
        run_params = params.RunParams()
        run_params.objective.variant = 6
        run_params.sa.iterations = 10000

        best_state, best_energy, stuck_count = sa.run_sa(var, run_params)
        final_truck_state = best_state

        print("Best Objective Value :", best_energy)
        print("Total Value          :", final_truck_state.total_value)
        print("Overweight           :", constraints.overweight_amount(final_truck_state))
        print("Floating Count       :", final_truck_state.n_floating)
        print("Fragile Pairs        :", final_truck_state.n_fragile_pairs)
        print("ETA Pairs            :", final_truck_state.n_eta_pairs)
        print("Stuck Count          :", stuck_count)
        print(f"Total Weight         : {final_truck_state.weight} / {[t.max_capacity for t in final_truck_state.trucks]}")
        print(f"Total Paket di Dalam : {len(final_truck_state.packages_inside)}")

    final_var = model.state_to_variable(final_truck_state, objective_value=best_score if solver_choice == "ga" else best_energy)
    model.writeJSON(output_path, final_var)
    print(f"\nHasil berhasil disimpan ke: {output_path}")

    if HAS_VISER and server is not None:
        server.scene.add_icosphere(
            name="/hello_sphere",
            radius=0.5,
            color=(255, 0, 0),
            position=(0.0, 0.0, 0.0),
        )

        print("\nOpen your browser to http://localhost:8080")
        print("Press Ctrl+C to exit")

        while True:
            time.sleep(10.0)


if __name__ == "__main__":
    main()