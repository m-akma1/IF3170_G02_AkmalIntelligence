from itertools import combinations

import uma_ai.core.model as model
import uma_ai.core.geometry as geometry


def is_inside_bound(package: model.PackageState, truck: model.TruckState) -> bool:
    """True jika paket di dalam bounding dimensi truk"""
    x0, y0, z0, x1, y1, z1 = geometry.bounds(package)
    dim = truck.truck.dim
    return (
        x0 >= 0 and y0 >= 0 and z0 >= 0
        and x1 <= dim.width and y1 <= dim.length and z1 <= dim.height
    )


def is_overlap(package1: model.PackageState, package2: model.PackageState) -> bool:
    """True jika kedua paket bertabrakan (overlap)"""
    ax0, ay0, az0, ax1, ay1, az1 = geometry.bounds(package1)
    bx0, by0, bz0, bx1, by1, bz1 = geometry.bounds(package2)
    return (
        ax0 < bx1 and ax1 > bx0
        and ay0 < by1 and ay1 > by0
        and az0 < bz1 and az1 > bz0
    )


def is_colliding(package: model.PackageState, truck: model.TruckState) -> bool:
    """True jika paket bertabrakan dengan paket lain di dalam truk."""
    return any(
        other is not package and is_overlap(package, other)
        for other in truck.packages_inside.values()
    )


def is_supported(package: model.PackageState, truck: model.TruckState) -> bool:
    """True jika paket tidak melayang (berada di lantai truk atau di atas paket lain)"""
    if package.z == 0:
        return True
    return any(
        other is not package and geometry.is_on_top_of(package, other)
        for other in truck.packages_inside.values()
    )


def is_fragile_valid(truck: model.TruckState, package: model.PackageState | None = None) -> bool:
    """
    True jika paket fragile tidak memiliki paket lain di atasnya.

    Jika package kosong, validasi semua paket fragile di dalam truk.
    Jika package diberikan, hanya validasi paket tersebut: tidak ada
    paket di atasnya (bila fragile) dan tidak berada di atas paket fragile.
    """
    inside = truck.packages_inside.values()

    if package is None:
        return not any(
            geometry.is_on_top_of(upper, lower)
            for lower in inside if lower.is_fragile
            for upper in inside if upper is not lower
        )

    for other in inside:
        if other is package:
            continue
        if package.is_fragile and geometry.is_on_top_of(other, package):
            return False
        if other.is_fragile and geometry.is_on_top_of(package, other):
            return False
    return True


def is_overweight(truck: model.TruckState, package: model.PackageState | None = None) -> bool:
    """
    True jika total berat paket di dalam truk melebihi kapasitas truk.

    Jika package diberikan, berat paket tersebut ditambahkan ke total
    (dihitung sekali saja bila sudah ada di dalam truk).
    """
    total = sum(p.weight for p in truck.packages_inside.values())
    if package is not None and not any(p is package for p in truck.packages_inside.values()):
        total += package.weight
    return total > truck.truck.max_capacity


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

    inside = truck.packages_inside
    for p in inside.values():
        if not (is_inside_bound(p, truck) and is_supported(p, truck)):
            return False
    if not is_fragile_valid(truck):
        return False
    for a, b in combinations(inside.values(), 2):
        if is_overlap(a, b):
            return False
    return not is_overweight(truck)
