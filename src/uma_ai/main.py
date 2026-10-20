import argparse
import colorsys
import random
import time
from pathlib import Path

import viser

from uma_ai.core import constraints, geometry, model, obj_func, params
from uma_ai.experiment import generator
from uma_ai.solvers import LOCAL_SEARCH, SOLVERS
from uma_ai.solvers.result import SearchResult, initial_state, run_timed

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


def _package_color(pkg: model.PackageState, index: int, total: int) -> tuple[int, int, int]:
    """Menentukan warna paket (merah untuk fragile, variasi warna pastel/cerah untuk non-fragile)."""
    if pkg.is_fragile:
        return (230, 57, 70)  # Merah untuk paket fragile
    hue = ((index * 0.618033988749895) % 1.0) * 0.7 + 0.15
    r, g, b = colorsys.hls_to_rgb(hue, 0.58, 0.65)
    return int(r * 255), int(g * 255), int(b * 255)


def visualize_result(server: viser.ViserServer, result: SearchResult) -> None:
    """Memvisualisasikan hasil state dari algoritma yang dipilih menggunakan Viser."""
    state = result.final
    server.scene.reset()

    # informasi hasil algoritma di panel viser
    with server.gui.add_folder("Ringkasan Hasil Algoritma"):
        weights_str = ", ".join(
            f"Truk {i}: {w}/{t.max_capacity}"
            for i, (w, t) in enumerate(zip(state.weight, state.trucks))
        )
        server.gui.add_markdown(
            f"**Algoritma:** `{result.algorithm}`\n\n"
            f"**Objective:** `{result.initial_value:.2f}` -> `{result.final_value:.2f}`\n\n"
            f"**Iterasi:** `{result.iterations}` ({result.duration:.2f} s)\n\n"
            f"**Feasible:** `{obj_func.is_feasible(state)}`\n\n"
            f"**Paket Terangkut:** `{len(state.packages_inside)} / {len(state.ids)}`\n\n"
            f"**Total Value:** `{state.total_value}`\n\n"
            f"**Berat:** {weights_str}"
        )
        show_labels = server.gui.add_checkbox("Tampilkan Label Paket", initial_value=False)
        show_wireframe = server.gui.add_checkbox("Tampilkan Garis Tepi Paket", initial_value=True)
        opacity_slider = server.gui.add_slider(
            "Opasitas Paket", min=0.2, max=1.0, step=0.05, initial_value=0.9
        )
        fragile_btn = server.gui.add_button("Tampilkan Hanya Fragile")

    # offset posisi X untuk setiap truk
    truck_offsets: list[float] = []
    current_x = 0.0
    gap = 2.0
    for truck in state.trucks:
        truck_offsets.append(current_x)
        current_x += truck.dim.width + gap

    # Render kontainer truk
    for idx, truck in enumerate(state.trucks):
        w, l, h = truck.dim.width, truck.dim.length, truck.dim.height
        ox = truck_offsets[idx]
        center = (ox + w / 2.0, l / 2.0, h / 2.0)

        server.scene.add_box(
            name=f"/trucks/truck_{idx}/container",
            dimensions=(w, l, h),
            position=center,
            color=(40, 40, 40),
            wireframe=True,
        )
        server.scene.add_box(
            name=f"/trucks/truck_{idx}/floor",
            dimensions=(w, l, 0.02),
            position=(ox + w / 2.0, l / 2.0, -0.01),
            color=(180, 180, 180),
            opacity=0.4,
        )
        server.scene.add_label(
            name=f"/trucks/truck_{idx}/label",
            text=f"Truk {idx} ({w}x{l}x{h} | W: {state.weight[idx]}/{truck.max_capacity})",
            position=(ox + w / 2.0, l / 2.0, h + 0.4),
        )

    # paket yang berada di dalam truk
    package_nodes: list[tuple[model.PackageState, viser.BoxHandle, viser.BoxHandle, viser.LabelHandle]] = []
    total_pkgs = max(len(state.packages_inside), 1)
    only_fragile = False

    for i, pkg in enumerate(state.packages_inside.values()):
        t_idx = pkg.truck_id if 0 <= pkg.truck_id < len(state.trucks) else 0
        ox = truck_offsets[t_idx]
        dx, dy, dz = geometry.extents(pkg)
        center = (
            ox + pkg.x + dx / 2.0,
            pkg.y + dy / 2.0,
            pkg.z + dz / 2.0,
        )
        color = _package_color(pkg, i, total_pkgs)

        box = server.scene.add_box(
            name=f"/packages/{pkg.id}/mesh",
            dimensions=(dx, dy, dz),
            position=center,
            color=color,
            opacity=opacity_slider.value,
        )
        wf = server.scene.add_box(
            name=f"/packages/{pkg.id}/wireframe",
            dimensions=(dx, dy, dz),
            position=center,
            color=(20, 20, 20),
            wireframe=True,
            visible=show_wireframe.value,
        )
        tag = " [FRAGILE]" if pkg.is_fragile else ""
        lbl = server.scene.add_label(
            name=f"/packages/{pkg.id}/label",
            text=f"{pkg.id}{tag} (V:{pkg.value}, W:{pkg.weight}, ETA:{pkg.eta})",
            position=center,
            visible=show_labels.value,
        )
        package_nodes.append((pkg, box, wf, lbl))

    def _sync_visibility() -> None:
        for pkg, box, wf, lbl in package_nodes:
            is_shown = pkg.is_fragile if only_fragile else True
            box.visible = is_shown
            wf.visible = is_shown and show_wireframe.value
            lbl.visible = is_shown and show_labels.value

    @fragile_btn.on_click
    def _(_) -> None:
        nonlocal only_fragile
        only_fragile = not only_fragile
        _sync_visibility()

    @show_labels.on_update
    def _(_) -> None:
        _sync_visibility()

    @show_wireframe.on_update
    def _(_) -> None:
        _sync_visibility()

    @opacity_slider.on_update
    def _(_) -> None:
        for _, box, _, _ in package_nodes:
            box.opacity = opacity_slider.value


def main():
    args = _parse_args()
    if args.generate is not None:
        input_path = generator.generate_file(args.generate)
        print(f"Generate: {generator.describe(input_path)}")
    else:
        input_path = _resolve(args.input, INPUT_DIR)
    param_path = _resolve(args.param, PARAM_DIR)
    run_params = params.load_params(param_path)

    server = viser.ViserServer()

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
    print(f"Pelanggaran : overweight {constraints.overweight_amount(final)}, floating {final.n_floating}, "
          f"fragile {final.n_fragile_pairs}, ETA {final.n_eta_pairs}")
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

    visualize_result(server, result)

    print("Open your browser to http://localhost:8080")
    print("Press Ctrl+C to exit")

    while True:
        time.sleep(10.0)


if __name__ == "__main__":
    main()
