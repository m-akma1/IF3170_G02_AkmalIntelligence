import argparse
import random
import time
from pathlib import Path

import viser

from uma_ai.core import model, obj_func, params
from uma_ai.experiment import generator
from uma_ai.solvers import LOCAL_SEARCH, SOLVERS
from uma_ai.solvers.result import initial_state, run_timed

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
    parser = argparse.ArgumentParser(description="Jalan.")
    parser.add_argument("input", nargs="?", help="test case di data/input (mis. 02_tc02) atau path file JSON")
    parser.add_argument("-g", "--generate", metavar="CONFIG",
                        help="buat test case dari data/generator/CONFIG.json ke data/input, lalu jalankan")
    parser.add_argument("-p", "--param", default="default",
                        help="file parameter di data/param atau path file JSON (default: default)")
    parser.add_argument("-a", "--algo", default="ga", choices=sorted(SOLVERS),
                        help="algoritma (default: ga)")
    parser.add_argument("--no-server", action="store_true", help="tidak menjalankan server viser")
    args = parser.parse_args()
    if (args.input is None) == (args.generate is None):
        parser.error("isi tepat satu: <input> atau --generate CONFIG")
    return args


def main():
    args = _parse_args()
    if args.generate is not None:
        input_path = generator.generate_file(args.generate)
        print(f"Generate: {generator.describe(input_path)}")
    else:
        input_path = _resolve(args.input, INPUT_DIR)
    param_path = _resolve(args.param, PARAM_DIR)
    run_params = params.load_params(param_path)

    server = None if args.no_server else viser.ViserServer()

    var = model.readJSON(input_path)
    print(f"Input: {input_path.name} ({len(var.packages)} paket, {len(var.trucks)} truk)")
    print(f"Parameter: {param_path.name}")
    print(f"Algoritma: {args.algo}")

    rng = random.Random(run_params.seed)
    initial = initial_state(var, run_params, rng) if args.algo in LOCAL_SEARCH else None
    result = run_timed(SOLVERS[args.algo], var, run_params, rng, initial)
    final = result.final
    print(f"Objective : {result.initial_value} -> {result.final_value} ({result.algorithm})")
    print(f"Iterasi   : {result.iterations}")
    print(f"Durasi    : {result.duration:.2f} s")
    print(f"Statistik : {result.stats}")
    print(f"Feasible  : {obj_func.is_feasible(final)}")
    print(f"Paket     : {len(final.packages_inside)} / {len(final.ids)} di dalam truk")
    print(f"Total Weight : {final.weight} / {[t.max_capacity for t in final.trucks]}")
    print(f"Total Value  : {final.total_value}")

    OUTPUT_DIR.mkdir(exist_ok=True)
    suffix = "" if args.algo == "ga" else f"_{args.algo}"
    output_path = OUTPUT_DIR / f"{input_path.stem}_{param_path.stem}{suffix}.json"
    final_var = model.state_to_variable(final, objective_value=result.final_value)
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
