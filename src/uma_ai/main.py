import argparse
import time
from pathlib import Path

import viser

from uma_ai.core import model, params
from uma_ai.solvers import genetic_alg as ga

ROOT = Path(__file__).resolve().parents[2]
INPUT_DIR = ROOT / "data" / "input"
PARAM_DIR = ROOT / "data" / "param"
OUTPUT_DIR = ROOT / "output"


def _resolve(name: str, folder: Path) -> Path:
    """Nama file di `folder` (dengan atau tanpa .json), atau path file biasa."""
    path = Path(name)
    if path.is_file():
        return path
    path = folder / (name if name.endswith(".json") else f"{name}.json")
    if not path.is_file():
        available = ", ".join(sorted(p.stem for p in folder.glob("*.json")))
        raise SystemExit(f"File '{name}' tidak ditemukan di {folder}. Tersedia: {available}")
    return path


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Optimasi muatan truk peti kemas.")
    parser.add_argument("input", help="test case di data/input (mis. 02_tc02) atau path file JSON")
    parser.add_argument("-p", "--param", default="default",
                        help="file parameter di data/param atau path file JSON (default: default)")
    parser.add_argument("--no-server", action="store_true", help="tidak menjalankan server viser")
    return parser.parse_args()


def main():
    args = _parse_args()
    input_path = _resolve(args.input, INPUT_DIR)
    param_path = _resolve(args.param, PARAM_DIR)
    run_params = params.load_params(param_path)

    server = None if args.no_server else viser.ViserServer()

    var = model.readJSON(input_path)
    print(f"Input: {input_path.name} ({len(var.packages)} paket, {len(var.trucks)} truk)")
    print(f"Parameter: {param_path.name}")

    best_chrom, best_decoded, best_score, total_weight, total_value = ga.run_ga(var=var, params=run_params)
    print("Kromosom Terbaik:", best_chrom)
    print("Status Paket (Boolean Occupied):", best_decoded.package_occupied)
    print("Jumlah Clipping:", best_decoded.clip_count)
    print("Fitness Terbaik:", best_score)
    print(f"Total Weight : {best_decoded.truck_state.weight} / {[t.max_capacity for t in best_decoded.truck_state.trucks]}")
    print(f"Total Value : {total_value}")

    OUTPUT_DIR.mkdir(exist_ok=True)
    output_path = OUTPUT_DIR / f"{input_path.stem}_{param_path.stem}.json"
    final_var = model.state_to_variable(best_decoded.truck_state, objective_value=best_score)
    model.writeJSON(output_path, final_var)
    print(f"Output: {output_path.relative_to(ROOT)}")

    if server is None:
        return

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
