import random
from dataclasses import dataclass
from core import model, geometry, constraints, state, obj_func


@dataclass
class DecodedState:
    """Membuat data hasil tranlasi kromosom ke bentuk fisik kontainer"""
    truck_state: model.TruckState
    grid_occupied: list[list[list[bool]]]
    package_occupied: list[bool]
    total_weight: int
    total_value: int
    clip_count: int = 0


# Helper Bounds

def _get_safe_bounds(
    pkg: model.Package,
    orient_id: int,
    truck_dim: model.Dimension
) -> tuple[int, int, int] | None:
    """
    Mengembalikan batas maksimal (max_x, max_y, max_z) yang aman untuk paket pada orient_id.
    Mengembalikan None jika pada orientasi tersebut ukuran paket melebihi dimensi truk.
    """
    orient = model.ORIENTATION[orient_id]
    size = {
        orient["w"]: pkg.dim.width,
        orient["l"]: pkg.dim.length,
        orient["h"]: pkg.dim.height,
    }
    dx, dy, dz = size["x"], size["y"], size["z"]

    if dx > truck_dim.width or dy > truck_dim.length or dz > truck_dim.height:
        return None

    return truck_dim.width - dx, truck_dim.length - dy, truck_dim.height - dz


def _random_valid_gene(pkg: model.Package, truck_dim: model.Dimension) -> tuple[int, int, int]:
    """Memilih (x, y, orient_id) yang dijamin tidak keluar dari dinding truk."""
    valid_orients = [
        o for o in range(len(model.ORIENTATION))
        if _get_safe_bounds(pkg, o, truck_dim) is not None
    ]
    if not valid_orients:
        # paket memang lebih besar dari truk di semua orientasi
        return 0, 0, 0

    o_i = random.choice(valid_orients)
    bounds = _get_safe_bounds(pkg, o_i, truck_dim)
    assert bounds is not None
    max_x, max_y, _ = bounds

    return random.randint(0, max_x), random.randint(0, max_y), o_i


def create_chromosome(var: model.Variable) -> list[int]:
    """Membuat kromosom 4N yang sejak awal bebas out-of-bounds."""
    n = len(var.packages)
    sequences = list(range(1, n + 1))
    random.shuffle(sequences)

    chromosome: list[int] = []
    for i in range(n):
        x_i, y_i, o_i = _random_valid_gene(var.packages[i], var.truck.dim)
        s_i = sequences[i]
        chromosome.extend([x_i, y_i, o_i, s_i])

    return chromosome


def init_population(var: model.Variable, pop_size: int) -> list[list[int]]:
    """Membuat populasi awal sebanyak pop_size individu."""
    return [create_chromosome(var) for _ in range(pop_size)]



# Decoding dengan anticlipping

def _is_box_free(
    grid: list[list[list[bool]]],
    x0: int, y0: int, z0: int,
    dx: int, dy: int, dz: int
) -> bool:
    """Mengecek apakah ruang 3D pada [x0..x0+dx, y0..y0+dy, z0..z0+dz] kosong."""
    for x in range(x0, x0 + dx):
        for y in range(y0, y0 + dy):
            for z in range(z0, z0 + dz):
                if grid[x][y][z]:
                    return False
    return True


def _is_box_supported(
    grid: list[list[list[bool]]],
    x0: int, y0: int, z0: int,
    dx: int, dy: int
) -> bool:
    """Mengecek apakah alas paket menyentuh lantai (z0 == 0) atau disangga minimal 1 blok di bawahnya."""
    if z0 == 0:
        return True
    z_below = z0 - 1
    for x in range(x0, x0 + dx):
        for y in range(y0, y0 + dy):
            if grid[x][y][z_below]:
                return True
    return False


def _fill_box(
    grid: list[list[list[bool]]],
    x0: int, y0: int, z0: int,
    dx: int, dy: int, dz: int,
    val: bool = True
):
    """Mengisi grid matrix dengan nilai boolean (True saat paket ditaruh)."""
    for x in range(x0, x0 + dx):
        for y in range(y0, y0 + dy):
            for z in range(z0, z0 + dz):
                grid[x][y][z] = val


def _find_lowest_z_at_xy(
    grid: list[list[list[bool]]],
    truck_state: model.TruckState,
    pkg_state: model.PackageState,
    x: int, y: int,
    dx: int, dy: int, dz: int,
    h: int
) -> int | None:
    """
    Scan dari atas (h - dz) ke bawah (0) pada titik (x, y).
    Mengembalikan z valid terendah, atau None jika kolom (x, y) penuh/terhalang.
    """
    lowest_valid_z = None
    for z in range(h - dz, -1, -1):
        # tidak tabrakan/clipping dengan paket lain
        if not _is_box_free(grid, x, y, z, dx, dy, dz):
            continue

        # tertumpu di lantai (z=0) atau di atas paket lain
        if not _is_box_supported(grid, x, y, z, dx, dy):
            continue

        # tidak menindih paket fragile
        pkg_state.x, pkg_state.y, pkg_state.z = x, y, z
        if not constraints.is_fragile_valid(truck_state, pkg_state):
            continue

        lowest_valid_z = z

    pkg_state.x, pkg_state.y, pkg_state.z = state.OUTSIDE
    return lowest_valid_z


def decode_chromosome(chromosome: list[int], var: model.Variable) -> DecodedState:
    """
    Decoder bebas clipping:
    1. Cek kapasitas berat terlebih dahulu (cegah overweight).
    2. Clamp (x, y) agar di dalam dinding truk.
    3. Coba taruh di (clamped_x, clamped_y).
    4. Jika penuh/clipping di titik tersebut, geser cari titik (x', y') terdekat yang kosong.
    5. Jika seluruh ruang truk sudah tidak muat, taruh dengan aman di packages_outside.
    """
    n = len(var.packages)
    w = var.truck.dim.width
    l = var.truck.dim.length
    h = var.truck.dim.height

    truck_state = model.variable_to_state(var)
    for pkg_id in list(truck_state.packages_inside.keys()):
        state.put_outside(pkg_id, truck_state, skip_check=True)

    grid_occupied = [[[False for _ in range(h)] for _ in range(l)] for _ in range(w)]
    package_occupied = [False] * n

    genes = []
    for i in range(n):
        base = 4 * i
        genes.append((
            chromosome[base + 3],  # s_i (sequence)
            i,                     # index paket
            chromosome[base],      # x_i
            chromosome[base + 1],  # y_i
            chromosome[base + 2],  # o_i
        ))

    genes.sort(key=lambda item: item[0])

    for s_i, idx, x_i, y_i, o_i in genes:
        pkg_id = var.packages[idx].id
        pkg_state = truck_state.packages_outside[pkg_id]

        # cegah pelanggaran berat truk sejak awal
        if constraints.is_overweight(truck_state, pkg_state):
            continue

        pkg_state.orientation_id = o_i
        dx, dy, dz = geometry.extents(pkg_state)

        # lewati orientasi melebihi ukuran truk
        if dx > w or dy > l or dz > h:
            continue

        clamped_x = max(0, min(x_i, w - dx))
        clamped_y = max(0, min(y_i, l - dy))

        # coba taruh tepat di koordinat gen (clamped_x, clamped_y)
        target_x, target_y = clamped_x, clamped_y
        best_z = _find_lowest_z_at_xy(
            grid_occupied, truck_state, pkg_state,
            target_x, target_y, dx, dy, dz, h
        )

        # Fallback Anti-Clipping jika di (clamped_x, clamped_y) penuh,
        # geser cari koordinat (cx, cy) terdekat yang masih punya ruang kosong
        if best_z is None:
            candidate_coords = [
                (cx, cy)
                for cx in range(w - dx + 1)
                for cy in range(l - dy + 1)
                if (cx, cy) != (clamped_x, clamped_y)
            ]
            # urutkan dari yang jarak pergeserannya paling dekat dengan (clamped_x, clamped_y)
            candidate_coords.sort(key=lambda pt: abs(pt[0] - clamped_x) + abs(pt[1] - clamped_y))

            for cx, cy in candidate_coords:
                z_cand = _find_lowest_z_at_xy(
                    grid_occupied, truck_state, pkg_state,
                    cx, cy, dx, dy, dz, h
                )
                if z_cand is not None:
                    target_x, target_y, best_z = cx, cy, z_cand
                    break

        # masukkan ke truk jika ditemukan posisi valid
        if best_z is not None:
            pos = model.Position(x=target_x, y=target_y, z=best_z)
            state.put_inside(pkg_id, truck_state, pos, o_i, skip_check=True)
            _fill_box(grid_occupied, target_x, target_y, best_z, dx, dy, dz, True)
            package_occupied[idx] = True

    total_weight = sum(p.weight for p in truck_state.packages_inside.values())
    total_value = sum(p.value for p in truck_state.packages_inside.values())

    return DecodedState(
        truck_state=truck_state,
        grid_occupied=grid_occupied,
        package_occupied=package_occupied,
        total_weight=total_weight,
        total_value=total_value,
    )



# operator genetic algorithems


def roulette_wheel_selection(
    population: list[list[int]],
    fitnesses: list[float]
) -> list[int]:
    """Seleksi menggunakan Roulette Wheel Selection."""
    min_fit = min(fitnesses)
    if min_fit < 0:
        adjusted_fitnesses = [f - min_fit + 1e-6 for f in fitnesses]
    else:
        adjusted_fitnesses = fitnesses

    total_fitness = sum(adjusted_fitnesses)

    if total_fitness == 0:
        return random.choice(population)[:]

    cumulative_prob = 0.0
    roll = random.random()

    for i, fit in enumerate(adjusted_fitnesses):
        prob = fit / total_fitness
        cumulative_prob += prob
        if roll < cumulative_prob:
            return population[i][:]

    return population[-1][:]


def _order_crossover_seq(seq1: list[int], seq2: list[int]) -> list[int]:
    """Order Crossover (OX) khusus untuk gen sequence agar tetap unik 1..N tanpa duplikat."""
    size = len(seq1)
    if size <= 1:
        return seq1[:]

    a, b = sorted(random.sample(range(size), 2))
    child_seq = [-1] * size
    child_seq[a:b + 1] = seq1[a:b + 1]

    used = set(child_seq[a:b + 1])
    fill_values = [val for val in seq2 if val not in used]

    fill_idx = 0
    for i in range(size):
        if child_seq[i] == -1:
            child_seq[i] = fill_values[fill_idx]
            fill_idx += 1

    return child_seq


def crossover(parent1: list[int], parent2: list[int]) -> tuple[list[int], list[int]]:
    """
    Mengawinkan 2 induk:
    - Gen (x, y, orient) ditukar dengan Uniform Crossover per paket.
    - Gen (sequence) ditukar dengan Order Crossover (OX) agar tidak ada urutan ganda.
    """
    n = len(parent1) // 4
    child1 = parent1[:]
    child2 = parent2[:]

    for i in range(n):
        if random.random() < 0.5:
            base = 4 * i
            child1[base:base + 3], child2[base:base + 3] = (
                parent2[base:base + 3],
                parent1[base:base + 3],
            )

    seq1 = [parent1[4 * i + 3] for i in range(n)]
    seq2 = [parent2[4 * i + 3] for i in range(n)]

    new_seq1 = _order_crossover_seq(seq1, seq2)
    new_seq2 = _order_crossover_seq(seq2, seq1)

    for i in range(n):
        child1[4 * i + 3] = new_seq1[i]
        child2[4 * i + 3] = new_seq2[i]

    return child1, child2


def mutate(chromosome: list[int], var: model.Variable, mutation_rate: float = 0.1):
    """Mutasi dengan tetap menjaga batas koordinat agar tidak melewati dinding truk."""
    n = len(var.packages)
    for i in range(n):
        base = 4 * i
        pkg = var.packages[i]

        # jika orientasi atau posisi (x, y) terkena mutasi, generate ulang dalam batas aman
        if random.random() < mutation_rate:
            x_new, y_new, o_new = _random_valid_gene(pkg, var.truck.dim)
            chromosome[base] = x_new
            chromosome[base + 1] = y_new
            chromosome[base + 2] = o_new

        # swap mutation untuk sequence agar tidak pernah duplikat
        if n > 1 and random.random() < mutation_rate:
            j = random.randint(0, n - 1)
            chromosome[base + 3], chromosome[4 * j + 3] = (
                chromosome[4 * j + 3],
                chromosome[base + 3],
            )


def evaluate_fitness(decoded: DecodedState) -> float:
    """
    Karena state dijamin 100% valid dan bebas clipping,
    kita bisa langsung menggunakan variant_1_hard dari obj_func.py
    """
    return obj_func.variant_1_hard(decoded.truck_state)


def run_ga(
    var: model.Variable,
    pop_size: int = 50,
    generations: int = 100,
    crossover_rate: float = 0.8,
    mutation_rate: float = 0.1,
) -> tuple[list[int], DecodedState, float, int, int]:
    """
    Menjalankan siklus Genetic Algorithm anti-clipping.
    Mengembalikan (kromosom_terbaik, decoded_state_terbaik, fitness_terbaik, total_weight, total_value).
    """
    population = init_population(var, pop_size)
    best_chromosome: list[int] = []
    best_decoded: DecodedState | None = None
    best_fitness = float("-inf")

    for gen in range(generations):
        decoded_pop = [decode_chromosome(ind, var) for ind in population]
        fitnesses = [evaluate_fitness(dec) for dec in decoded_pop]

        gen_best_idx = max(range(pop_size), key=lambda idx: fitnesses[idx])
        if fitnesses[gen_best_idx] > best_fitness:
            best_fitness = fitnesses[gen_best_idx]
            best_chromosome = population[gen_best_idx][:]
            best_decoded = decoded_pop[gen_best_idx]

        next_population: list[list[int]] = [best_chromosome[:]]

        while len(next_population) < pop_size:
            p1 = roulette_wheel_selection(population, fitnesses)
            p2 = roulette_wheel_selection(population, fitnesses)

            if random.random() < crossover_rate:
                c1, c2 = crossover(p1, p2)
            else:
                c1, c2 = p1[:], p2[:]

            mutate(c1, var, mutation_rate)
            mutate(c2, var, mutation_rate)

            next_population.append(c1)
            if len(next_population) < pop_size:
                next_population.append(c2)

        population = next_population

    assert best_decoded is not None
    best_decoded.truck_state.truck.objective_value = best_fitness
    return (
        best_chromosome,
        best_decoded,
        best_fitness,
        best_decoded.total_weight,
        best_decoded.total_value,
    )
