from . import model, geometry
from .container import Container


def _container(truck: model.TruckState, package: model.PackageState) -> Container:
    """Container truk milik paket untuk setup multitruk"""
    return truck.containers[package.truck_id if package.truck_id >= 0 else 0]


def _capacity(truck: model.TruckState, truck_id: int) -> int:
    return truck.trucks[truck_id].max_capacity


def is_inside_bound(package: model.PackageState, truck: model.TruckState) -> bool:
    """True jika paket di dalam bounding dimensi truk"""
    dx, dy, dz = geometry.extents(package)
    return _container(truck, package).in_bound(package.x, package.y, package.z, dx, dy, dz)


def is_overlap(package1: model.PackageState, package2: model.PackageState) -> bool:
    """True jika kedua paket bertabrakan (overlap) di truk yang sama"""
    if package1.truck_id != package2.truck_id:
        return False
    ax0, ay0, az0, ax1, ay1, az1 = geometry.bounds(package1)
    bx0, by0, bz0, bx1, by1, bz1 = geometry.bounds(package2)
    return (
        ax0 < bx1 and ax1 > bx0
        and ay0 < by1 and ay1 > by0
        and az0 < bz1 and az1 > bz0
    )


def is_colliding(package: model.PackageState, truck: model.TruckState) -> bool:
    """True jika paket bertabrakan dengan paket lain di dalam truk."""
    x0, y0, z0, x1, y1, z1 = geometry.bounds(package)
    owners = _container(truck, package).owners_in(x0, x1, y0, y1, z0, z1)
    owners.discard(package)
    return bool(owners)


def support_area(package: model.PackageState, truck: model.TruckState) -> int:
    """Luas alas paket yang tertumpu lantai atau paket lain (dalam sel)."""
    dx, dy, _ = geometry.extents(package)
    return _container(truck, package).support_area(package.x, package.y, package.z, dx, dy)


def support_ratio(package: model.PackageState, truck: model.TruckState) -> float:
    """Persentase alas paket yang tertumpu, antara 0 dan 1."""
    dx, dy, _ = geometry.extents(package)
    return support_area(package, truck) / (dx * dy)


def is_supported(package: model.PackageState, truck: model.TruckState) -> bool:
    """True jika paket tidak melayang (berada di lantai truk atau di atas paket lain)"""
    return package.z == 0 or support_area(package, truck) > 0


def fragile_below(package: model.PackageState, truck: model.TruckState) -> set:
    """Paket fragile yang langsung ditindih `package`."""
    dx, dy, _ = geometry.extents(package)
    return _container(truck, package).fragile_owners(package.x, package.y, dx, dy, package.z - 1)


def _above(package: model.PackageState, truck: model.TruckState) -> set:
    x0, y0, _, x1, y1, z1 = geometry.bounds(package)
    owners = _container(truck, package).owners_in(x0, x1, y0, y1, z1, z1 + 1)
    owners.discard(package)
    return owners


def fragile_pair_count(truck: model.TruckState, package: model.PackageState | None = None) -> int:
    """
    Jumlah pasangan (atas, bawah) yang bersentuhan dengan paket bawah fragile.

    Jika package diberikan, hanya memeriksa paket tersebut.
    Jika kosong, memeriksa semua paket di dalam truk.
    """
    if package is None:
        return sum(len(fragile_below(p, truck)) for p in truck.packages_inside.values())

    count = len(fragile_below(package, truck) - {package})
    if package.is_fragile:
        count += len(_above(package, truck))
    return count


def is_fragile_valid(truck: model.TruckState, package: model.PackageState | None = None) -> bool:
    """
    True jika paket fragile tidak memiliki paket lain di atasnya.

    Jika package kosong, validasi semua paket fragile di dalam truk.
    Jika package diberikan, hanya validasi paket tersebut: tidak ada
    paket di atasnya (bila fragile) dan tidak berada di atas paket fragile.
    """
    return fragile_pair_count(truck, package) == 0


def _lane_owners(package: model.PackageState, truck: model.TruckState, front: bool) -> set:
    """
    Paket di lajur depan (antara paket dan pintu, y lebih kecil) atau lajur belakang paket,
    pada rentang x dan z yang sama.
    """
    x0, y0, z0, x1, y1, z1 = geometry.bounds(package)
    container = _container(truck, package)
    if front:
        return container.lane_owners(x0, x1, 0, y0, z0, z1)
    return container.lane_owners(x0, x1, y1, container.length, z0, z1)


def eta_blocking_count(truck: model.TruckState, package: model.PackageState | None = None) -> int:
    """
    Jumlah pasangan LIFO yang tidak urut: paket q berada di depan paket p (lebih dekat ke pintu) 
    tetapi q.eta > p.eta, sehingga q menghalangi p.

    Jika package diberikan, hanya pasangan yang melibatkan paket tersebut.
    Jika kosong, memeriksa semua paket di dalam truk.
    """
    if package is None:
        return sum(
            sum(1 for q in _lane_owners(p, truck, True) if q.eta > p.eta)
            for p in truck.packages_inside.values()
        )

    blocked = sum(1 for q in _lane_owners(package, truck, True) if q.eta > package.eta)
    blocking = sum(1 for r in _lane_owners(package, truck, False) if package.eta > r.eta)
    return blocked + blocking


def overweight_amount(truck: model.TruckState) -> int:
    """Total kelebihan berat dari seluruh truk."""
    return sum(max(0, w - _capacity(truck, t)) for t, w in enumerate(truck.weight))


def is_overweight(truck: model.TruckState, package: model.PackageState | None = None) -> bool:
    """
    True jika total berat paket di dalam truk melebihi kapasitas truk.

    Jika package diberikan, hanya truk tempat paket tersebut dimasukkan yang diperiksa,
    dan berat paket ditambahkan bila paket belum ada di dalam truk tersebut.

    Jika paket di luar truk (truck_id = -1), diperiksa apakah memasukkannya ke truk 0
    akan melebihi kapasitas truk 0.
    """
    if package is None:
        return overweight_amount(truck) > 0

    t = package.truck_id if package.truck_id >= 0 else 0
    total = truck.weight[t]
    if truck.packages_inside.get(package.id) is not package or package.truck_id != t:
        total += package.weight
    return total > _capacity(truck, t)


def is_valid(truck: model.TruckState, package: model.PackageState | None = None) -> bool:
    """
    True jika semua paket di dalam truk valid:
    di dalam batas, tidak melayang, tidak bertabrakan, paket fragile valid,
    serta truk tidak overweight.

    Jika package diberikan, pengecekan hanya paket tersebut yang diperiksa,
    kecuali is_overweight.
    """
    if package is not None:
        return (
            is_inside_bound(package, truck)
            and not is_colliding(package, truck)
            and is_supported(package, truck)
            and is_fragile_valid(truck, package)
        )

    for p in truck.packages_inside.values():
        if not (is_inside_bound(p, truck) and is_supported(p, truck)) or is_colliding(p, truck):
            return False
    return is_fragile_valid(truck) and not is_overweight(truck)
