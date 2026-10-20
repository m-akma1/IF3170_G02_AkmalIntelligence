import time
import viser
from core import model
import uma_ai.solvers.GA as ga


def main():
    server = viser.ViserServer()
    
    
    var = model.readJSON("../../data/input/01_uma.json")
    print(f"Total paket yabg ada: {len(var.packages)}")
    
    best_chrom, best_decoded, best_score, total_weight, total_value = ga.run_ga(
        var=var,
        pop_size=50,
        generations=100,
        crossover_rate=0.8,
        mutation_rate=0.1,
    )
    print("Kromosom Terbaik:", best_chrom)
    print("Status Paket (Boolean Occupied):", best_decoded.package_occupied)
    print("Jumlah Clipping:", best_decoded.clip_count)
    print("Fitness Terbaik:", best_score)
    print(f"Total Weight : {total_weight} / {best_decoded.truck_state.truck.max_capacity}")
    print(f"Total Value : {total_value}")

    final_var = model.state_to_variable(best_decoded.truck_state)
    model.writeJSON("output_result.json", final_var)
    
    
    
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