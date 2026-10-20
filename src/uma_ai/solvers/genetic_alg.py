import random
from collections.abc import Callable
from dataclasses import dataclass

from uma_ai.core import model, obj_func, state
from uma_ai.core.container import Container
from uma_ai.core.params import GAParams, RunParams

from .result import History, SearchResult


@dataclass
class DecodedState:
    """Membuat data hasil tranlasi kromosom ke bentuk fisik kontainer"""
    truck_state: model.TruckState
    grid_occupied: list[Container]   # indeks okupansi per truk
    package_occupied: list[bool]     # per paket, urutan input
    total_weight: int
    total_value: int
    clip_count: int = 0              # decoder tidak pernah menghasilkan overlap


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


def _largest_dim(var: model.Variable) -> model.Dimension:
    """Gen (x, y) diambil dalam truk terbesar; decoder menjepitnya ke tiap truk."""
    return model.Dimension(
        width=max(t.dim.width for t in var.trucks),
        length=max(t.dim.length for t in var.trucks),
        height=max(t.dim.height for t in var.trucks),
    )


def _random_valid_gene(pkg: model.Package, truck_dim: model.Dimension,
                       rng: random.Random = random) -> tuple[int, int, int]:
    """Memilih (x, y, orient_id) yang dijamin tidak keluar dari dinding truk."""
    valid_orients = [
        o for o in range(len(model.ORIENTATION))
        if _get_safe_bounds(pkg, o, truck_dim) is not None
    ]
    if not valid_orients:
        # paket memang lebih besar dari truk di semua orientasi
        return 0, 0, 0

    o_i = rng.choice(valid_orients)
    bounds = _get_safe_bounds(pkg, o_i, truck_dim)
    assert bounds is not None
    max_x, max_y, _ = bounds

    return rng.randint(0, max_x), rng.randint(0, max_y), o_i


def create_chromosome(var: model.Variable, rng: random.Random = random, sequences: list[int] | None = None) -> list[int]:
    """Membuat kromosom 4N yang sejak awal bebas out-of-bounds. sequences: urutan tetap (default acak)."""
    n = len(var.packages)
    if sequences is None:
        sequences = list(range(1, n + 1))
        rng.shuffle(sequences)

    dim = _largest_dim(var)
    chromosome: list[int] = []
    for i in range(n):
        x_i, y_i, o_i = _random_valid_gene(var.packages[i], dim, rng)
        s_i = sequences[i]
        chromosome.extend([x_i, y_i, o_i, s_i])

    return chromosome


def _eta_sequences(var: model.Variable, rng: random.Random) -> list[int]:
    """Sequence urut ETA naik (acak untuk ETA sama): decoder mengisi dari pintu, jadi yang turun duluan di depan."""
    order = sorted(range(len(var.packages)), key=lambda i: (var.packages[i].eta, rng.random()))
    sequences = [0] * len(order)
    for rank, i in enumerate(order, start=1):
        sequences[i] = rank
    return sequences


def init_population(var: model.Variable, pop_size: int, rng: random.Random = random,
                    eta_seed_frac: float = 0.0) -> list[list[int]]:
    """Membuat populasi awal sebanyak pop_size individu (sebagian diurutkan berdasarkan ETA)."""
    n_seeded = int(round(eta_seed_frac * pop_size))
    return [
        create_chromosome(var, rng, _eta_sequences(var, rng) if k < n_seeded else None)
        for k in range(pop_size)
    ]



# Decoding


def decode_chromosome(chromosome: list[int], var: model.Variable,
                      template: model.TruckState | None = None,
                      max_candidates: int | None = 64) -> DecodedState:
    """
    Decoder bebas clipping lewat `state.pack`:
    1. Urutkan paket berdasarkan gen sequence.
    2. Lewati paket yang membuat truk overweight.
    3. Coba (x, y, orient) gen dengan gravitasi (x, y dijepit ke dalam truk).
    4. Jika gagal, coba extreme point terdekat, lalu truk berikutnya.
    5. Jika tetap tidak muat, paket tetap di packages_outside.

    template: state kosong untuk disalin (lebih cepat daripada membangun dari var setiap decode).
    """
    n = len(var.packages)
    truck_state = state.copy_state(template) if template is not None else state.empty_state(var)

    prefs = {}
    genes = []
    for i in range(n):
        base = 4 * i
        pkg_id = var.packages[i].id
        prefs[pkg_id] = (chromosome[base], chromosome[base + 1], chromosome[base + 2])
        genes.append((chromosome[base + 3], pkg_id))
    genes.sort()

    state.pack(truck_state, [pkg_id for _, pkg_id in genes], prefs, max_candidates)

    return DecodedState(
        truck_state=truck_state,
        grid_occupied=truck_state.containers,
        package_occupied=[p.id in truck_state.packages_inside for p in var.packages],
        total_weight=sum(truck_state.weight),
        total_value=truck_state.total_value,
    )



# operator genetic algorithems


def roulette_wheel_selection(
    population: list[list[int]],
    fitnesses: list[float],
    rng: random.Random = random,
) -> list[int]:
    """Seleksi menggunakan Roulette Wheel Selection."""
    min_fit = min(fitnesses)
    if min_fit < 0:
        adjusted_fitnesses = [f - min_fit + 1e-6 for f in fitnesses]
    else:
        adjusted_fitnesses = fitnesses

    total_fitness = sum(adjusted_fitnesses)

    if total_fitness == 0:
        return rng.choice(population)[:]

    cumulative_prob = 0.0
    roll = rng.random()

    for i, fit in enumerate(adjusted_fitnesses):
        prob = fit / total_fitness
        cumulative_prob += prob
        if roll < cumulative_prob:
            return population[i][:]

    return population[-1][:]


def tournament_selection(
    population: list[list[int]],
    fitnesses: list[float],
    k: int = 3,
    rng: random.Random = random,
) -> list[int]:
    """Seleksi turnamen: individu terbaik dari k individu acak."""
    picked = rng.sample(range(len(population)), min(k, len(population)))
    return population[max(picked, key=lambda i: fitnesses[i])][:]


def _order_crossover_seq(seq1: list[int], seq2: list[int], rng: random.Random = random) -> list[int]:
    """Order Crossover (OX) khusus untuk gen sequence agar tetap unik 1..N tanpa duplikat."""
    size = len(seq1)
    if size <= 1:
        return seq1[:]

    a, b = sorted(rng.sample(range(size), 2))
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


def crossover(parent1: list[int], parent2: list[int], rng: random.Random = random) -> tuple[list[int], list[int]]:
    """
    Mengawinkan 2 induk:
    - Gen (x, y, orient) ditukar dengan Uniform Crossover per paket.
    - Gen (sequence) ditukar dengan Order Crossover (OX) agar tidak ada urutan ganda.
    """
    n = len(parent1) // 4
    child1 = parent1[:]
    child2 = parent2[:]

    for i in range(n):
        if rng.random() < 0.5:
            base = 4 * i
            child1[base:base + 3], child2[base:base + 3] = (
                parent2[base:base + 3],
                parent1[base:base + 3],
            )

    seq1 = [parent1[4 * i + 3] for i in range(n)]
    seq2 = [parent2[4 * i + 3] for i in range(n)]

    new_seq1 = _order_crossover_seq(seq1, seq2, rng)
    new_seq2 = _order_crossover_seq(seq2, seq1, rng)

    for i in range(n):
        child1[4 * i + 3] = new_seq1[i]
        child2[4 * i + 3] = new_seq2[i]

    return child1, child2


def mutate(chromosome: list[int], var: model.Variable, mutation_rate: float = 0.1,
           rng: random.Random = random, shift: int = 0):
    """
    Mutasi dengan tetap menjaga batas koordinat agar tidak melewati dinding truk.

    shift > 0: separuh mutasi pose hanya menggeser (x, y) maksimal sejauh shift.
    """
    n = len(var.packages)
    dim = _largest_dim(var)
    for i in range(n):
        base = 4 * i
        pkg = var.packages[i]

        # jika orientasi atau posisi (x, y) terkena mutasi, generate ulang dalam batas aman
        if rng.random() < mutation_rate:
            if shift > 0 and rng.random() < 0.5:
                chromosome[base] = max(0, chromosome[base] + rng.randint(-shift, shift))
                chromosome[base + 1] = max(0, chromosome[base + 1] + rng.randint(-shift, shift))
            else:
                x_new, y_new, o_new = _random_valid_gene(pkg, dim, rng)
                chromosome[base] = x_new
                chromosome[base + 1] = y_new
                chromosome[base + 2] = o_new

        # swap mutation untuk sequence agar tidak pernah duplikat
        if n > 1 and rng.random() < mutation_rate:
            j = rng.randint(0, n - 1)
            chromosome[base + 3], chromosome[4 * j + 3] = (
                chromosome[4 * j + 3],
                chromosome[base + 3],
            )


def evaluate_fitness(decoded: DecodedState, params=None) -> float:
    """
    Objective function sesuai params (default variant_3). Hasil decode selalu valid, jadi
    yang membedakan individu hanya nilai dan penalti urutan bongkar (ETA).
    """
    return obj_func.evaluate(decoded.truck_state, params)


def run_ga(
    var: model.Variable,
    pop_size: int | None = None,
    generations: int | None = None,
    crossover_rate: float | None = None,
    mutation_rate: float | None = None,
    *,
    params: RunParams | None = None,
    rng: random.Random | None = None,
    on_generation: Callable[[int, float, list[float], list[DecodedState]], None] | None = None,
) -> tuple[list[int], DecodedState, float, int, int]:
    """
    Menjalankan Genetic Algorithm.

    on_generation(generation, best_fitness, fitnesses, decoded_pop) call per generasi.
    
    returns (best_chromosome, best_decoded, best_fitness, total_weight, total_value).
    """
    ga = params.ga if params is not None else GAParams()
    objective = params.objective if params is not None else None
    pop_size = ga.pop_size if pop_size is None else pop_size
    generations = ga.generations if generations is None else generations
    crossover_rate = ga.crossover_rate if crossover_rate is None else crossover_rate
    if mutation_rate is None:
        mutation_rate = ga.mutation_rate if ga.mutation_rate is not None else 1 / max(1, len(var.packages))
    if rng is None:
        rng = random.Random(params.seed) if params is not None and params.seed is not None else random

    def select(population, fitnesses):
        if ga.selection == "tournament":
            return tournament_selection(population, fitnesses, ga.tournament_k, rng)
        return roulette_wheel_selection(population, fitnesses, rng)

    min_support = objective.min_support if objective is not None else 0.5
    template = state.empty_state(var, min_support)
    population = init_population(var, pop_size, rng, ga.eta_seed_frac)
    best_chromosome: list[int] = []
    best_decoded: DecodedState | None = None
    best_fitness = float("-inf")

    for gen in range(generations):
        decoded_pop = [decode_chromosome(ind, var, template, ga.max_candidates) for ind in population]
        fitnesses = [evaluate_fitness(dec, objective) for dec in decoded_pop]

        gen_best_idx = max(range(pop_size), key=lambda idx: fitnesses[idx])
        if fitnesses[gen_best_idx] > best_fitness:
            best_fitness = fitnesses[gen_best_idx]
            best_chromosome = population[gen_best_idx][:]
            best_decoded = decoded_pop[gen_best_idx]
        if on_generation is not None:
            on_generation(gen, best_fitness, fitnesses, decoded_pop)

        ranked = sorted(range(pop_size), key=lambda idx: fitnesses[idx], reverse=True)
        next_population: list[list[int]] = [best_chromosome[:]]
        next_population += [population[idx][:] for idx in ranked[:max(0, ga.elitism - 1)]]

        while len(next_population) < pop_size:
            p1 = select(population, fitnesses)
            p2 = select(population, fitnesses)

            if rng.random() < crossover_rate:
                c1, c2 = crossover(p1, p2, rng)
            else:
                c1, c2 = p1[:], p2[:]

            mutate(c1, var, mutation_rate, rng, ga.shift_mutation)
            mutate(c2, var, mutation_rate, rng, ga.shift_mutation)

            next_population.append(c1)
            if len(next_population) < pop_size:
                next_population.append(c2)

        population = next_population

    assert best_decoded is not None
    return (
        best_chromosome,
        best_decoded,
        best_fitness,
        best_decoded.total_weight,
        best_decoded.total_value,
    )


def run(var: model.Variable, params: RunParams, rng: random.Random,
        initial: model.TruckState | None = None) -> SearchResult:
    """
    `run_ga` dengan format hasil bersama (lihat result.py). `initial` diabaikan karena GA
    berbasis populasi: state awal = individu terbaik generasi 0.
    History per generasi: fitness maksimum dan rata-rata populasi, serta terbaik sejauh ini.
    """
    history = History("iteration", "value", "max", "mean", "best")
    first: list[DecodedState] = []

    def on_generation(gen, best_fitness, fitnesses, decoded_pop):
        gen_max = max(fitnesses)
        if gen == 0:
            first.append(decoded_pop[fitnesses.index(gen_max)])
        history.log(gen, gen_max, gen_max, sum(fitnesses) / len(fitnesses), best_fitness)

    _, best_decoded, best_fitness, _, _ = run_ga(var, params=params, rng=rng, on_generation=on_generation)
    initial_decoded = first[0]
    return SearchResult(
        algorithm="ga",
        initial=initial_decoded.truck_state,
        final=best_decoded.truck_state,
        initial_value=evaluate_fitness(initial_decoded, params.objective),
        final_value=best_fitness,
        iterations=params.ga.generations,
        history=history.as_dict(),
        stats={"pop_size": params.ga.pop_size, "generations": params.ga.generations},
    )
