from __future__ import annotations

import copy
import dataclasses
import random
from bisect import bisect_left, insort
from dataclasses import dataclass

from . import model, geometry, constraints

OUTSIDE = (-1, -1, -1)

# Typedef: (package_id, (orient_id, x, y, z), truck_id), truck_id -1 = di luar truk
_Delta = tuple[str, tuple[int, int, int, int], int]

# Typedef: package_id -> (package, truck_id, orient_id, x, y, z) sebelum perubahan
_Poses = dict[str, tuple[model.PackageState, int, int, int, int, int]]


@dataclass
class Snapshot:
    """Data untuk membatalkan satu perubahan dengan `undo`."""
    poses: _Poses
    totals: tuple
    settled: int = 0  # jumlah paket yang ikut jatuh karena gravitasi

# --- Helpers ---

def _valid_orient(orient_id: int) -> bool:
    return 0 <= orient_id < len(model.ORIENTATION)


def _find(truck: model.TruckState, package_id: str) -> model.PackageState | None:
    return truck.find(package_id)


def _dependants(truck: model.TruckState, package: model.PackageState) -> set[model.PackageState]:
    """Paket di dalam truk yang bertumpu langsung di atas `package`."""
    x0, y0, _, x1, y1, z1 = geometry.bounds(package)
    found = truck.containers[package.truck_id].owners_in(x0, x1, y0, y1, z1, z1 + 1)
    found.discard(package)
    return found

# Running Total

def _totals(truck: model.TruckState) -> tuple:
    return (
        truck.total_value, list(truck.weight), truck.n_fragile_pairs, truck.n_eta_pairs,
        truck.n_floating, truck.support_deficit, truck.compactness,
    )


def _restore_totals(truck: model.TruckState, totals: tuple):
    (
        truck.total_value, weight, truck.n_fragile_pairs, truck.n_eta_pairs,
        truck.n_floating, truck.support_deficit, truck.compactness,
    ) = totals
    truck.weight = list(weight)


def _support_terms(truck: model.TruckState, package: model.PackageState) -> tuple[int, float]:
    """Persentase tumpuan terhadap min_support untuk satu paket."""
    dx, dy, _ = geometry.extents(package)
    supported = truck.containers[package.truck_id].support_area(package.x, package.y, package.z, dx, dy)
    floating = 1 if package.z > 0 and supported == 0 else 0
    return floating, max(0.0, truck.min_support - supported / (dx * dy))


def _add_support(truck: model.TruckState, packages, sign: int):
    for p in packages:
        floating, deficit = _support_terms(truck, p)
        truck.n_floating += sign * floating
        truck.support_deficit += sign * deficit


def _compact(truck: model.TruckState, package: model.PackageState) -> float:
    """Volume x jarak relatif dari lantai dan dinding belakang (0 = di lantai, menempel dinding)."""
    dx, dy, dz = geometry.extents(package)
    container = truck.containers[package.truck_id]
    far = (package.z / container.height + (container.length - package.y - dy) / container.length) / 2
    return dx * dy * dz * far


def _eta_pairs(truck: model.TruckState, package: model.PackageState) -> int:
    return constraints.eta_blocking_count(truck, package) if truck.track_eta else 0


def _paint(truck: model.TruckState, package: model.PackageState, on: bool):
    dx, dy, dz = geometry.extents(package)
    truck.containers[package.truck_id].mark(
        package, package.x, package.y, package.z, dx, dy, dz, package.is_fragile, on
    )


def _lift(truck: model.TruckState, package: model.PackageState) -> set[model.PackageState]:
    """Mengeluarkan paket dari grid. Mengembalikan paket yang tadinya bertumpu di atasnya."""
    above = _dependants(truck, package)
    truck.n_fragile_pairs -= constraints.fragile_pair_count(truck, package)
    truck.n_eta_pairs -= _eta_pairs(truck, package)
    _add_support(truck, above | {package}, -1)
    truck.compactness -= _compact(truck, package)

    _paint(truck, package, False)

    _add_support(truck, above, +1)
    truck.total_value -= package.value
    truck.weight[package.truck_id] -= package.weight
    del truck.packages_inside[package.id]
    truck.packages_outside[package.id] = package
    package.truck_id = -1
    package.x, package.y, package.z = OUTSIDE
    return above


def _place(truck: model.TruckState, package: model.PackageState, truck_id: int, orient_id: int,
           x: int, y: int, z: int) -> set[model.PackageState]:
    """Memasukkan paket ke grid (posisi harus sudah valid). Mengembalikan paket yang ada di atasnya."""
    package.truck_id, package.orientation_id = truck_id, orient_id
    package.x, package.y, package.z = x, y, z
    above = _dependants(truck, package)
    _add_support(truck, above, -1)

    _paint(truck, package, True)

    _add_support(truck, above | {package}, +1)
    truck.n_fragile_pairs += constraints.fragile_pair_count(truck, package)
    truck.n_eta_pairs += _eta_pairs(truck, package)
    truck.compactness += _compact(truck, package)
    truck.total_value += package.value
    truck.weight[truck_id] += package.weight
    del truck.packages_outside[package.id]
    truck.packages_inside[package.id] = package
    return above

# --- Public API untuk perubahan

def recompute(truck: model.TruckState):
    """Menghitung ulang seluruh total dari grid (dipakai saat membangun state)."""
    truck.total_value = 0
    truck.weight = [0] * len(truck.trucks)
    truck.n_floating, truck.support_deficit, truck.compactness = 0, 0.0, 0.0
    for p in truck.packages_inside.values():
        truck.total_value += p.value
        truck.weight[p.truck_id] += p.weight
        truck.compactness += _compact(truck, p)
    _add_support(truck, truck.packages_inside.values(), +1)
    truck.n_fragile_pairs = constraints.fragile_pair_count(truck)
    truck.n_eta_pairs = constraints.eta_blocking_count(truck) if truck.track_eta else 0


# Aksi (Mutasi State)

def undo(truck: model.TruckState, snapshot: Snapshot):
    """Mengembalikan state persis seperti sebelum aksi yang menghasilkan `snapshot`."""
    for p, *_ in snapshot.poses.values():
        if p.truck_id >= 0:
            _paint(truck, p, False)
            del truck.packages_inside[p.id]
            truck.packages_outside[p.id] = p
    for p, truck_id, orient_id, x, y, z in snapshot.poses.values():
        p.truck_id, p.orientation_id, p.x, p.y, p.z = truck_id, orient_id, x, y, z
        if truck_id >= 0:
            _paint(truck, p, True)
            del truck.packages_outside[p.id]
            truck.packages_inside[p.id] = p
    _restore_totals(truck, snapshot.totals)


def _pose(p: model.PackageState) -> tuple[model.PackageState, int, int, int, int, int]:
    return p, p.truck_id, p.orientation_id, p.x, p.y, p.z


def _settle(truck: model.TruckState, candidates, poses: _Poses) -> int:
    """Menjatuhkan paket melayang di `candidates` (bertingkat) dan mencatat pose lamanya."""
    queue = list(candidates)
    moved = 0
    while queue:
        p = queue.pop()
        if p.truck_id < 0 or p.z == 0 or constraints.support_area(p, truck) > 0:
            continue
        poses.setdefault(p.id, _pose(p))
        t, o, x, y, z = p.truck_id, p.orientation_id, p.x, p.y, p.z
        dx, dy, _ = geometry.extents(p)
        above = _lift(truck, p)
        z = truck.containers[t].fall_z(x, y, z, dx, dy)
        above |= _place(truck, p, t, o, x, y, z)
        queue.extend(above)
        moved += 1
    return moved


def _apply(truck: model.TruckState, changes: list[_Delta], skip_check: bool,
           drop: bool = False, settle: bool = True) -> Snapshot | None:
    """
    Menerapkan perubahan pose/lokasi beberapa paket secara atomik (rollback/no op jika tidak valid).

    drop=True: z target diabaikan, (x, y) dijepit ke dalam truk, lalu z dihitung dengan gravitasi
    setelah semua paket yang berubah diangkat (hasilnya pasti tidak overlap dan tertumpu).
    settle=True: paket lain yang kehilangan tumpuan ikut jatuh.

    Jika tidak skip_check, memeriksa paket yang berubah (jika berakhir di dalam truk),
    paket lain yang semula berada di atas paket yang berubah, dan berat jika total bertambah.

    Mengembalikan Snapshot untuk `undo`, atau None jika no op.
    """
    packages: dict[str, model.PackageState] = {}
    for package_id, _, _ in changes:
        package = _find(truck, package_id)
        if package is None:
            return None
        packages[package_id] = package

    snapshot = Snapshot(poses={id: _pose(p) for id, p in packages.items()}, totals=_totals(truck))
    weight_before = list(truck.weight)

    touched: set[model.PackageState] = set()
    for p in packages.values():
        if p.truck_id >= 0:
            touched |= _lift(truck, p)

    for package_id, (orient_id, x, y, z), truck_id in changes:
        p = packages[package_id]
        if truck_id < 0:
            p.orientation_id = orient_id
            continue
        if truck_id >= len(truck.containers):
            undo(truck, snapshot)
            return None
        container = truck.containers[truck_id]
        dx, dy, dz = p.extents[orient_id]
        if drop:
            x = min(max(x, 0), container.width - dx)
            y = min(max(y, 0), container.length - dy)
            z = container.drop_z(x, y, dx, dy, dz)
            if z is None:
                undo(truck, snapshot)
                return None
        elif not container.fits(x, y, z, dx, dy, dz):
            undo(truck, snapshot)
            return None
        touched |= _place(truck, p, truck_id, orient_id, x, y, z)
        touched.add(p)

    if settle:
        snapshot.settled = _settle(truck, touched, snapshot.poses)

    if skip_check:
        return snapshot

    ok = (
        all(constraints.is_valid(truck, packages[id]) for id, _, truck_id in changes if truck_id >= 0)
        and all(constraints.is_supported(d, truck) for d in touched if d.truck_id >= 0)
        and not (
            any(w > before for w, before in zip(truck.weight, weight_before))
            and constraints.is_overweight(truck)
        )
    )
    if ok:
        return snapshot

    undo(truck, snapshot)
    return None


def rotate(package_id: str, truck: model.TruckState, orient_id: int, skip_check: bool = False,
           drop: bool = False, settle: bool = True, anchor: model.Position | None = None) -> Snapshot | None:
    """
    Rotasi paket di dalam sesuai orientasi baru (objek dimutasi).

    anchor: pojok (x, y, z) baru setelah rotasi; default pojok paket saat ini.

    No op jika objek tidak ditemukan/di luar petikemas, rotasi tidak valid, atau melanggar constraint yang ada.
    """
    package = truck.packages_inside.get(package_id)
    if package is None or not _valid_orient(orient_id) or (orient_id == package.orientation_id and anchor is None):
        return None
    x, y, z = (anchor.x, anchor.y, anchor.z) if anchor is not None else (package.x, package.y, package.z)
    return _apply(truck, [(package_id, (orient_id, x, y, z), package.truck_id)], skip_check, drop, settle)


def translate(package_id: str, truck: model.TruckState, delta_pos: model.Position, skip_check: bool = False,
              drop: bool = False, settle: bool = True) -> Snapshot | None:
    """
    Menggeser paket di dalam sesuai delta pos (drop=True: delta z diabaikan, z dihitung gravitasi).

    No op jika objek tidak ditemukan/di luar petikemas atau hasil melanggar constraint yang ada.
    """
    package = truck.packages_inside.get(package_id)
    if package is None or delta_pos.x == delta_pos.y == delta_pos.z == 0:
        return None
    pose = (
        package.orientation_id,
        package.x + delta_pos.x,
        package.y + delta_pos.y,
        package.z + delta_pos.z,
    )
    return _apply(truck, [(package_id, pose, package.truck_id)], skip_check, drop, settle)


def put_inside(package_id: str, truck: model.TruckState, pos: model.Position, orient_id: int,
               skip_check: bool = False, truck_id: int = 0, drop: bool = False,
               settle: bool = True) -> Snapshot | None:
    """
    Memasukkan paket dari luar (atau dari truk lain) ke dalam truk `truck_id`.

    No op jika paket sudah di dalam truk yang sama (meski posisi/orientasi berbeda), atau melanggar constraint yang ada.
    """
    package = _find(truck, package_id)
    if package is None or package.truck_id == truck_id or not _valid_orient(orient_id):
        return None
    return _apply(truck, [(package_id, (orient_id, pos.x, pos.y, pos.z), truck_id)], skip_check, drop, settle)


def put_outside(package_id: str, truck: model.TruckState, skip_check: bool = False,
                settle: bool = True) -> Snapshot | None:
    """
    Mengeluarkan paket dari dalam ke luar truk. Orientasi dibiarkan.

    No op jika paket sudah tidak ditemukan/di luar petikemas atau melanggar constraint.
    """
    package = truck.packages_inside.get(package_id)
    if package is None:
        return None
    return _apply(truck, [(package_id, (package.orientation_id, *OUTSIDE), -1)], skip_check, settle=settle)


def swap(old_pkg_id: str, new_pkg_id: str, truck: model.TruckState, pos: model.Position, orient_id: int,
         skip_check: bool = False, truck_id: int | None = None, drop: bool = False,
         settle: bool = True) -> Snapshot | None:
    """
    Menukar paket pertama di dalam truk dengan pake kedua dari luar truk dengan mengeset posisi dan orientasi paket yang baru.

    truck_id: truk tujuan paket kedua; default truk paket pertama.

    No op jika paket pertama tidak di dalam, paket kedua tidak di luar, orientasi tidak valid, atau melanggar constraint.
    """
    old = truck.packages_inside.get(old_pkg_id)
    if old is None or new_pkg_id not in truck.packages_outside or not _valid_orient(orient_id):
        return None
    target = old.truck_id if truck_id is None else truck_id
    return _apply(truck, [
        (old_pkg_id, (old.orientation_id, *OUTSIDE), -1),
        (new_pkg_id, (orient_id, pos.x, pos.y, pos.z), target),
    ], skip_check, drop, settle)


def switch_pos(
    pkg_id1: str,
    pkg_id2: str,
    truck: model.TruckState,
    pos1: model.Position,
    orient_id1: int,
    pos2: model.Position,
    orient_id2: int,
    skip_check: bool = False,
    truck_id1: int | None = None,
    truck_id2: int | None = None,
    drop: bool = False,
    settle: bool = True,
) -> Snapshot | None:
    """
    Menukar dua paket di dalam truk dan mengeset posisi dan orientaasi baru kedua paket.

    truck_id1/truck_id2: truk tujuan masing-masing paket; default truknya sendiri.
    Dengan drop=True, paket pertama ditempatkan lebih dulu.

    No op jika salah satu paket tidak di dalam truk, kedua id sama, orientasi tidak valid, atau melanggar constraint.
    """
    p1 = truck.packages_inside.get(pkg_id1)
    p2 = truck.packages_inside.get(pkg_id2)
    if (
        pkg_id1 == pkg_id2
        or p1 is None
        or p2 is None
        or not _valid_orient(orient_id1)
        or not _valid_orient(orient_id2)
    ):
        return None
    t1 = p1.truck_id if truck_id1 is None else truck_id1
    t2 = p2.truck_id if truck_id2 is None else truck_id2
    return _apply(truck, [
        (pkg_id1, (orient_id1, pos1.x, pos1.y, pos1.z), t1),
        (pkg_id2, (orient_id2, pos2.x, pos2.y, pos2.z), t2),
    ], skip_check, drop, settle)


# Pembentukan dan perbaikan state

def empty_state(var: model.Variable, min_support: float = 0.5) -> model.TruckState:
    """State dengan semua paket di luar truk (posisi pada input diabaikan)."""
    truck = model.variable_to_state(var, min_support)
    for p in list(truck.packages_inside.values()):
        _lift(truck, p)
    return truck


def copy_state(truck: model.TruckState) -> model.TruckState:
    """Salinan independen (paket, grid, dan total)"""
    clones = {id: copy.copy(truck.find(id)) for id in truck.ids}
    remap = {id(truck.find(pid)): c for pid, c in clones.items()}
    containers = []
    for c in truck.containers:
        other = c.copy()
        other.owner = [remap[id(o)] if o is not None else None for o in other.owner]
        containers.append(other)
    return dataclasses.replace(
        truck,
        packages_inside={pid: clones[pid] for pid in truck.packages_inside},
        packages_outside={pid: clones[pid] for pid in truck.packages_outside},
        ids=list(truck.ids),
        containers=containers,
        weight=list(truck.weight),
    )


def random_state(
    var: model.Variable,
    rng: random.Random | None = None,
    mode: str = "drop",
    tries: int = 5,
    p_in: float = 1.0,
    weight_ratio: float | None = 1.0,
    min_support: float = 0.5,
) -> model.TruckState:
    """
    State awal acak.

    mode="drop": paket diambil dengan urutan acak (peluang p_in), lalu dicoba hingga `tries` kali
    pada truk, orientasi, dan (x, y) acak dengan gravitasi; berhenti mengisi truk jika berat
    melebihi weight_ratio x kapasitas (None = tanpa batas). Tidak pernah overlap atau melayang.
    mode="density": seperti "drop", tetapi paket diambil berurutan dari nilai per volume
    terbesar (urutan generator SA awal); pose tetap acak.
    mode="ep": urutan dan orientasi acak, ditempatkan dengan `pack` (jauh lebih padat).
    """
    rng = rng or random.Random()
    truck = empty_state(var, min_support)
    order = list(truck.ids)
    rng.shuffle(order)

    if mode == "ep":
        for package_id in order:
            p = truck.packages_outside[package_id]
            p.orientation_id = rng.choice(p.unique_orients)
        return pack(truck, order)
    if mode == "density":
        def density(package_id: str) -> float:
            p = truck.packages_outside[package_id]
            return p.value / (p.width * p.length * p.height)
        order.sort(key=density, reverse=True)
    elif mode != "drop":
        raise ValueError(f"Unknown random_state mode '{mode}'")

    for package_id in order:
        if rng.random() >= p_in:
            continue
        p = truck.packages_outside[package_id]
        for _ in range(tries):
            t = rng.randrange(len(truck.trucks))
            cap = truck.trucks[t].max_capacity
            if weight_ratio is not None and truck.weight[t] + p.weight > weight_ratio * cap:
                continue
            o = rng.choice(p.unique_orients)
            dx, dy, dz = p.extents[o]
            container = truck.containers[t]
            if dx > container.width or dy > container.length or dz > container.height:
                continue
            x = rng.randint(0, container.width - dx)
            y = rng.randint(0, container.length - dy)
            z = container.drop_z(x, y, dx, dy, dz)
            if z is not None:
                _place(truck, p, t, o, x, y, z)
                break
    return truck


def _pack_candidates(container, eps: list[tuple[int, int]], px: int, py: int, dx: int, dy: int,
                     preferred: bool, limit: int | None):
    """(x, y) calon: preferensi lebih dulu, lalu extreme point (terdekat di y dari preferensi)."""
    if preferred:
        yield min(max(px, 0), container.width - dx), min(max(py, 0), container.length - dy)
    hi = bisect_left(eps, (py, px)) if preferred else 0
    lo = hi - 1
    count = 0
    while (lo >= 0 or hi < len(eps)) and (limit is None or count < limit):
        if hi < len(eps) and (lo < 0 or not preferred or eps[hi][0] - py <= py - eps[lo][0]):
            k = hi
        else:
            k = lo
        ey, ex = eps[k]
        if container.is_full(ex, ey):
            del eps[k]
            if k < hi:
                lo -= 1
                hi -= 1
            continue
        if k == hi:
            hi += 1
        else:
            lo -= 1
        count += 1
        yield min(ex, container.width - dx), min(ey, container.length - dy)


def pack(
    truck: model.TruckState,
    order: list[str],
    prefs: dict[str, tuple[int, int, int]] | None = None,
    max_candidates: int | None = 64,
) -> model.TruckState:
    """
    Penempatan konstruktif berurutan (decoder GA dan inisialisasi "ep"); paket harus di luar truk.

    prefs: package_id -> (x, y, orient_id) preferensi. Tanpa prefs, orientasi paket saat ini dipakai
    dan extreme point diurutkan dari depan (y kecil).

    Tiap paket: lewati jika melebihi kapasitas truk; coba (x, y) preferensi dengan gravitasi;
    jika gagal, coba hingga `max_candidates` extreme point terdekat; lalu truk berikutnya;
    jika tetap gagal, paket tetap di luar. Hasil selalu valid (tidak overlap, tertumpu,
    fragile dan berat terpenuhi).
    """
    eps = [[(0, 0)] for _ in truck.trucks]  # extreme point (y, x), terurut
    for package_id in order:
        p = truck.packages_outside.get(package_id)
        if p is None:
            continue
        if prefs is not None:
            px, py, o = prefs[package_id]
        else:
            px, py, o = 0, 0, p.orientation_id
        dx, dy, dz = p.extents[o]

        for t, container in enumerate(truck.containers):
            if truck.weight[t] + p.weight > truck.trucks[t].max_capacity:
                continue
            if dx > container.width or dy > container.length or dz > container.height:
                continue
            spot = None
            for x, y in _pack_candidates(container, eps[t], px, py, dx, dy, prefs is not None, max_candidates):
                z = container.drop_z(x, y, dx, dy, dz)
                if z is None:
                    continue
                if z > 0 and container.fragile_owners(x, y, dx, dy, z - 1):
                    continue
                if p.is_fragile and container.owners_in(x, x + dx, y, y + dy, z + dz, z + dz + 1):
                    continue
                spot = (x, y, z)
                break
            if spot is not None:
                x, y, z = spot
                _place(truck, p, t, o, x, y, z)
                insort(eps[t], (y, x + dx))
                insort(eps[t], (y + dy, x))
                break
    return truck


def repair(truck: model.TruckState, settle: bool = True) -> model.TruckState:
    """
    Memperbaiki state sampai memenuhi semua hard constraint (variant_1_hard > 0), dari atas:
    keluarkan paket termurah per berat di truk overweight (yang tidak menumpu paket lain),
    keluarkan paket yang menindih paket fragile, lalu jatuhkan paket yang melayang.
    """
    while True:
        over = [t for t, w in enumerate(truck.weight) if w > truck.trucks[t].max_capacity]
        if over:
            in_truck = [p for p in truck.packages_inside.values() if p.truck_id == over[0]]
            free = [p for p in in_truck if not _dependants(truck, p)] or in_truck
            victim = min(free, key=lambda p: p.value / p.weight if p.weight else float("inf"))
            put_outside(victim.id, truck, skip_check=True, settle=settle)
            continue
        if truck.n_fragile_pairs:
            uppers = [p for p in truck.packages_inside.values() if p.z > 0 and constraints.fragile_below(p, truck)]
            victim = max(uppers, key=lambda p: p.z)
            put_outside(victim.id, truck, skip_check=True, settle=settle)
            continue
        if truck.n_floating:
            floating = [p for p in truck.packages_inside.values() if not constraints.is_supported(p, truck)]
            _settle(truck, floating, {})
            continue
        return truck
