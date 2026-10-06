import uma_ai.core.model as model
from uma_ai.core import constraints
from uma_ai.core.geometry import is_on_top_of

OUTSIDE = (-1, -1, -1)

# Typedef: (package_id, (orient_id, x, y, z) , is_truck)
_Delta = tuple[str, tuple[int, int, int, int], bool]


def _valid_orient(orient_id: int) -> bool:
    return 0 <= orient_id < len(model.ORIENTATION)


def _find(truck: model.TruckState, package_id: str) -> model.PackageState | None:
    package = truck.packages_inside.get(package_id)
    return package if package is not None else truck.packages_outside.get(package_id)


def _dependants(truck: model.TruckState, package: model.PackageState) -> list[model.PackageState]:
    """Paket di dalam truk yang bertumpu langsung di atas `package`."""
    return [
        p for p in truck.packages_inside.values()
        if p is not package and is_on_top_of(p, package)
    ]


def _apply(truck: model.TruckState, changes: list[_Delta], skip_check: bool):
    """
    Menerapkan perubahan pose/lokasi beberapa paket secara atomik (rollback/no op jika tidak valid).

    Hanya memeriksa delta/perubahan yang diperiksa, paket yang berubah (jika berakhir di dalam truk),
    paket lain yang semula berada di atas paket yang berubah, dan berat jika total bertambah.
    """
    packages: dict[str, model.PackageState] = {}
    for package_id, _, _ in changes:
        package = _find(truck, package_id)
        if package is None:
            return
        packages[package_id] = package
    snapshot = {
        id: (
            id in truck.packages_inside,
            (p.orientation_id, p.x, p.y, p.z),
        )
        for id, p in packages.items()
    }

    moved = [p for p in packages.values()]
    dependants = [] if skip_check else [
        d
        for id, p in packages.items() if snapshot[id][0]
        for d in _dependants(truck, p)
        if not any(d is m for m in moved)
    ]
    weight_delta = sum(
        (packages[id].weight if inside else 0) - (packages[id].weight if snapshot[id][0] else 0)
        for id, _, inside in changes
    )

    for id, (orient_id, x, y, z), inside in changes:
        p = packages[id]
        p.orientation_id, p.x, p.y, p.z = orient_id, x, y, z
        truck.packages_inside.pop(id, None)
        truck.packages_outside.pop(id, None)
        (truck.packages_inside if inside else truck.packages_outside)[id] = p

    if skip_check:
        return

    ok = (
        all(constraints.is_valid(truck, packages[id]) for id, _, inside in changes if inside)
        and all(constraints.is_supported(d, truck) for d in dependants)
        and not (weight_delta > 0 and constraints.is_overweight(truck))
    )
    if ok:
        return

    for id, (was_inside, (orient_id, x, y, z)) in snapshot.items():
        p = packages[id]
        p.orientation_id, p.x, p.y, p.z = orient_id, x, y, z
        truck.packages_inside.pop(id, None)
        truck.packages_outside.pop(id, None)
        (truck.packages_inside if was_inside else truck.packages_outside)[id] = p


def rotate(package_id: str, truck: model.TruckState, orient_id: int, skip_check: bool = False):
    """
    Rotasi paket di dalam sesuai orientasi baru (objek dimutasi).

    No op jika objek tidak ditemukan/di luar petikemas, rotasi tidak valid, atau melanggar constraint yang ada.
    """
    package = truck.packages_inside.get(package_id)
    if package is None or not _valid_orient(orient_id) or orient_id == package.orientation_id:
        return
    _apply(truck, [(package_id, (orient_id, package.x, package.y, package.z), True)], skip_check)


def translate(package_id: str, truck: model.TruckState, delta_pos: model.Position, skip_check: bool = False):
    """
    Menggeser paket di dalam sesuai delta pos.

    No op jika objek tidak ditemukan/di luar petikemas atau hasil melanggar constraint yang ada.
    """
    package = truck.packages_inside.get(package_id)
    if package is None or delta_pos.x == delta_pos.y == delta_pos.z == 0:
        return
    pose = (
        package.orientation_id,
        package.x + delta_pos.x,
        package.y + delta_pos.y,
        package.z + delta_pos.z,
    )
    _apply(truck, [(package_id, pose, True)], skip_check)


def put_inside(package_id: str, truck: model.TruckState, pos: model.Position, orient_id: int, skip_check: bool = False):
    """
    Memasukkan paket dari luar ke dalam truk.

    No op jika paket sudah di dalam (meski posisi/orientasi berbeda), atau melanggar constraint yang ada.
    """
    if package_id not in truck.packages_outside or not _valid_orient(orient_id):
        return
    _apply(truck, [(package_id, (orient_id, pos.x, pos.y, pos.z), True)], skip_check)


def put_outside(package_id: str, truck: model.TruckState, skip_check: bool = False):
    """
    Mengeluarkan paket dari dalam ke luar truk. Orientasi dibiarkan.

    No op jika paket sudah tidak ditemukan/di luar petikemas atau melanggar constraint.
    """
    package = truck.packages_inside.get(package_id)
    if package is None:
        return
    _apply(truck, [(package_id, (package.orientation_id, *OUTSIDE), False)], skip_check)


def swap(old_pkg_id: str, new_pkg_id: str, truck: model.TruckState, pos: model.Position, orient_id: int, skip_check: bool = False):
    """
    Menukar paket pertama di dalam truk dengan pake kedua dari luar truk dengan mengeset posisi dan orientasi paket yang baru. 

    No op jika paket pertama tidak di dalam, paket kedua tidak di luar, orientasi tidak valid, atau melanggar constraint.
    """
    old = truck.packages_inside.get(old_pkg_id)
    if old is None or new_pkg_id not in truck.packages_outside or not _valid_orient(orient_id):
        return
    _apply(truck, [
        (old_pkg_id, (old.orientation_id, *OUTSIDE), False),
        (new_pkg_id, (orient_id, pos.x, pos.y, pos.z), True),
    ], skip_check)


def switch_pos(
    pkg_id1: str,
    pkg_id2: str,
    truck: model.TruckState,
    pos1: model.Position,
    orient_id1: int,
    pos2: model.Position,
    orient_id2: int,
    skip_check: bool = False,
):
    """
    Menukar dua paket di dalam truk dan mengeset posisi dan orientaasi baru kedua paket. 

    No op jika salah satu paket tidak di dalam truk, kedua id sama, orientasi tidak valid, atau melanggar constraint.
    """
    if (
        pkg_id1 == pkg_id2
        or pkg_id1 not in truck.packages_inside
        or pkg_id2 not in truck.packages_inside
        or not _valid_orient(orient_id1)
        or not _valid_orient(orient_id2)
    ):
        return
    _apply(truck, [
        (pkg_id1, (orient_id1, pos1.x, pos1.y, pos1.z), True),
        (pkg_id2, (orient_id2, pos2.x, pos2.y, pos2.z), True),
    ], skip_check)
