from __future__ import annotations

import itertools
import random
from typing import NamedTuple

from . import model, state
from .params import NeighborParams

_DEFAULT = NeighborParams()


class Move(NamedTuple):
    kind: str      # nama aksi di state.py
    kwargs: dict   # argumen aksi selain truck


_ACTIONS = {
    "translate": state.translate,
    "put_inside": state.put_inside,
    "put_outside": state.put_outside,
    "rotate": state.rotate,
    "swap": state.swap,
    "switch_pos": state.switch_pos,
}


def apply_move(truck: model.TruckState, move: Move) -> state.Snapshot | None:
    return _ACTIONS[move.kind](truck=truck, **move.kwargs)


def _pos(x: int, y: int) -> model.Position:
    # z diabaikan karena drop=True; model_construct melewati validasi pydantic (jalur panas)
    return model.Position.model_construct(x=x, y=y, z=0)


def _plan(truck: model.TruckState, move: Move):
    """(paket yang diangkat, penempatan berurutan (paket, truk, orient, x, y)) dari aksi drop."""
    a, find = move.kwargs, truck.find
    if move.kind == "translate":
        p, d = find(a["package_id"]), a["delta_pos"]
        return [p], [(p, p.truck_id, p.orientation_id, p.x + d.x, p.y + d.y)]
    if move.kind == "put_inside":
        p, pos = find(a["package_id"]), a["pos"]
        return [p] if p.truck_id >= 0 else [], [(p, a["truck_id"], a["orient_id"], pos.x, pos.y)]
    if move.kind == "rotate":
        p, anchor = find(a["package_id"]), a.get("anchor")
        x, y = (anchor.x, anchor.y) if anchor is not None else (p.x, p.y)
        return [p], [(p, p.truck_id, a["orient_id"], x, y)]
    if move.kind == "swap":
        old, new, pos = find(a["old_pkg_id"]), find(a["new_pkg_id"]), a["pos"]
        t = old.truck_id if a.get("truck_id") is None else a["truck_id"]
        return [old], [(new, t, a["orient_id"], pos.x, pos.y)]
    if move.kind == "switch_pos":
        p1, p2 = find(a["pkg_id1"]), find(a["pkg_id2"])
        t1 = p1.truck_id if a.get("truck_id1") is None else a["truck_id1"]
        t2 = p2.truck_id if a.get("truck_id2") is None else a["truck_id2"]
        return [p1, p2], [
            (p1, t1, a["orient_id1"], a["pos1"].x, a["pos1"].y),
            (p2, t2, a["orient_id2"], a["pos2"].x, a["pos2"].y),
        ]
    return None


def _drops(truck: model.TruckState, move: Move) -> bool:
    """
    Simulasi murah (tanpa mutasi) apakah semua penempatan gravitasi sebuah aksi berhasil:
    sama persis dengan `state._apply(drop=True)`, tetapi hanya membaca bitmask kolom.
    """
    plan = _plan(truck, move)
    if plan is None or not move.kwargs.get("drop"):
        return True
    lifted, placements = plan
    placed = []  # (truck, x, y, z, dx, dy, dz) hasil simulasi sejauh ini
    for p, t, o, x, y in placements:
        if not 0 <= t < len(truck.containers):
            return False
        c = truck.containers[t]
        dx, dy, dz = p.ext[o]
        if dx > c.width or dy > c.length or dz > c.height:
            return False
        x, y = min(max(x, 0), c.width - dx), min(max(y, 0), c.length - dy)
        cols, L = c.cols, c.length
        m = 0
        for xx in range(x, x + dx):
            for yy in range(y, y + dy):
                col = cols[xx * L + yy]
                for e in lifted:
                    if e.truck_id == t:
                        edx, edy, edz = e.extents[e.orientation_id]
                        if e.x <= xx < e.x + edx and e.y <= yy < e.y + edy:
                            col &= ~(((1 << edz) - 1) << e.z)
                for pt, px, py, pz, pdx, pdy, pdz in placed:
                    if pt == t and px <= xx < px + pdx and py <= yy < py + pdy:
                        col |= ((1 << pdz) - 1) << pz
                m |= col
        window = (1 << dz) - 1
        z = next((z for z in range(c.height - dz + 1) if not (m >> z) & window), None)
        if z is None:
            return False
        placed.append((t, x, y, z, dx, dy, dz))
    return True


def _random_inside(truck: model.TruckState, rng: random.Random, tries: int = 30) -> model.PackageState | None:
    if not truck.packages_inside:
        return None
    for _ in range(tries):
        p = truck.find(rng.choice(truck.ids))
        if p.truck_id >= 0:
            return p
    return next(iter(truck.packages_inside.values()))


def _partner(truck: model.TruckState, rng: random.Random, p: model.PackageState, inside: bool,
             prm: NeighborParams) -> model.PackageState | None:
    """Paket acak di dalam/luar truk; jika similar_partner, pilih yang luas alasnya paling mirip."""
    wanted = prm.partner_samples if prm.similar_partner else 1
    found = []
    for _ in range(5 * wanted + 10):
        q = truck.find(rng.choice(truck.ids))
        if q is not p and (q.truck_id >= 0) == inside:
            found.append(q)
            if len(found) == wanted:
                break
    if not found:
        return None
    dx, dy, _ = p.extents[p.orientation_id]
    area = dx * dy
    return min(found, key=lambda q: abs(q.extents[q.orientation_id][0] * q.extents[q.orientation_id][1] - area))


def _relocate(truck, rng, p, prm, common) -> list[Move]:
    kind = rng.choices(("random", "near", "ep"), (prm.target_random, prm.target_near, prm.target_ep))[0]
    target = None
    if kind == "near" and p.truck_id >= 0:
        r = prm.near_radius
        target = p.truck_id, p.x + rng.randint(-r, r), p.y + rng.randint(-r, r)
    elif kind == "ep":
        q = _random_inside(truck, rng)
        if q is not None and q is not p:
            qdx, qdy, _ = q.extents[q.orientation_id]
            target = (q.truck_id, q.x + qdx, q.y) if rng.random() < 0.5 else (q.truck_id, q.x, q.y + qdy)
    if target is None:
        t = rng.randrange(len(truck.trucks))
        dim = truck.trucks[t].dim
        dx, dy, _ = p.extents[p.orientation_id]
        target = t, rng.randint(0, max(0, dim.width - dx)), rng.randint(0, max(0, dim.length - dy))

    t, x, y = target
    if p.truck_id == t:
        if (x, y) == (p.x, p.y):
            return []
        delta = model.Position(x=x - p.x, y=y - p.y, z=0)
        return [Move("translate", dict(package_id=p.id, delta_pos=delta, **common))]
    return [Move("put_inside", dict(package_id=p.id, pos=_pos(x, y), orient_id=p.orientation_id,
                                    truck_id=t, **common))]


def _rotate(truck, rng, p, prm, common) -> list[Move]:
    o = p.orientation_id
    axes = [a for a in range(3) if p.extents[model.ROTATION[o][a]] != p.extents[o]]
    if not axes:
        return []
    o2 = model.ROTATION[o][rng.choice(axes)]
    if prm.rotate_policy == "strict":
        return [Move("rotate", dict(package_id=p.id, orient_id=o2, **{**common, "drop": False}))]
    if prm.rotate_policy == "redrop":
        return [Move("rotate", dict(package_id=p.id, orient_id=o2, **common))]
    # reanchor: berputar pada salah satu dari empat pojok alas lama
    (dx, dy, _), (dx2, dy2, _) = p.extents[o], p.extents[o2]
    anchors = dict.fromkeys([
        (p.x, p.y), (p.x + dx - dx2, p.y), (p.x, p.y + dy - dy2), (p.x + dx - dx2, p.y + dy - dy2),
    ])
    return [
        Move("rotate", dict(package_id=p.id, orient_id=o2, anchor=_pos(ax, ay), **common))
        for ax, ay in anchors
    ]


def _orient_pairs(rng, p, q, tries: int) -> list[tuple[int, int]]:
    first = (p.orientation_id, q.orientation_id)
    rest = [pair for pair in itertools.product(p.unique_orients, q.unique_orients) if pair != first]
    rng.shuffle(rest)
    return [first] + rest[:max(0, tries - 1)]


def _switch(truck, rng, p, prm, common) -> list[Move]:
    q = _partner(truck, rng, p, True, prm)
    if q is None:
        return []
    return [
        Move("switch_pos", dict(
            pkg_id1=p.id, pkg_id2=q.id,
            pos1=_pos(q.x, q.y), orient_id1=o1, pos2=_pos(p.x, p.y), orient_id2=o2,
            truck_id1=q.truck_id, truck_id2=p.truck_id, **common,
        ))
        for o1, o2 in _orient_pairs(rng, p, q, prm.swap_orient_tries)
    ]


def _swap(truck, rng, p, prm, common) -> list[Move]:
    q = _partner(truck, rng, p, False, prm)
    if q is None:
        return []
    rest = [o for o in q.unique_orients if o != q.orientation_id]
    rng.shuffle(rest)
    orients = [q.orientation_id] + rest[:max(0, prm.swap_orient_tries - 1)]
    return [
        Move("swap", dict(old_pkg_id=p.id, new_pkg_id=q.id, pos=_pos(p.x, p.y), orient_id=o,
                          truck_id=p.truck_id, **common))
        for o in orients
    ]


def _outside(truck, rng, p, prm, common) -> list[Move]:
    return [Move("put_outside", dict(package_id=p.id, skip_check=True, settle=prm.settle))]


_KINDS = {
    "relocate": _relocate,
    "outside": _outside,
    "rotate": _rotate,
    "switch": _switch,
    "swap": _swap,
}


def random_move_candidates(truck: model.TruckState, rng: random.Random,
                           params: NeighborParams | None = None) -> list[Move]:
    """Calon aksi satu neighbor acak, dicoba berurutan sampai ada yang berhasil."""
    prm = params or _DEFAULT
    kind = rng.choices(
        list(_KINDS),
        (prm.w_relocate, prm.w_outside, prm.w_rotate, prm.w_switch, prm.w_swap),
    )[0]
    if kind == "relocate":
        p = truck.find(rng.choice(truck.ids))
    else:
        p = _random_inside(truck, rng)
        if p is None:
            return []
    common = dict(skip_check=True, drop=True, settle=prm.settle)
    return _KINDS[kind](truck, rng, p, prm, common)


def random_neighbor(truck: model.TruckState, rng: random.Random,
                    params: NeighborParams | None = None) -> tuple[Move, state.Snapshot] | None:
    """
    Menerapkan satu neighbor acak ke `truck` (dimutasi).

    Mengembalikan (Move yang berhasil, Snapshot untuk state.undo), atau None jika tidak ada
    calon yang valid (state tidak berubah).
    """
    for move in random_move_candidates(truck, rng, params):
        if not _drops(truck, move):
            continue
        snapshot = apply_move(truck, move)
        if snapshot is not None:
            return move, snapshot
    return None
