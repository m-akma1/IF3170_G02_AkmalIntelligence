from __future__ import annotations
from dataclasses import dataclass, field
from pydantic import BaseModel, ConfigDict, Field, model_validator
from typing import Optional
import json

from .container import Container

class Dimension(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    width: int = Field(...,alias="w")
    length: int = Field(...,alias="l")
    height: int = Field(...,alias="h")


class Orientation(BaseModel):
    """
    Valid value only permutation of (x, y, z).
    """
    model_config = ConfigDict(populate_by_name=True)
    width: str = Field(..., alias="w")
    length: str = Field(..., alias="l")
    height: str = Field(..., alias="h")

    @model_validator(mode="after")
    def validator(self) -> "Orientation":
        current_values = sorted([self.width, self.length, self.height])
        expected_values = ["x", "y", "z"]

        if current_values != expected_values:
            raise ValueError(
                f"Orientation must be a strict permutation of ('x', 'y', 'z'). "
                f"Got: width='{self.width}', length='{self.length}', height='{self.height}'"
            )

        return self


class Position(BaseModel):
    """
    Origin ada di pojok depan kiri bawah truk, relatif ke truk.
    Anchor paket pasti sama (pojok depan kiri bawah) meski dirotasi.

    x positif geser ke kanan
    y positif geser ke belakang (makin menjauhi pintu truk)
    z positif geser ke atas

    Paket di luar truk default diisi koordinat (-1, -1, -1).
    """
    x: int
    y: int
    z: int


class Package(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    dim: Dimension = Field(...,alias="dimension")
    orient: Orientation = Field(...,alias="orientation")
    value: int
    weight: int
    is_fragile: bool
    eta: int

    # For final state representation
    is_inside: Optional[bool] = False
    pos: Optional[Position] = Position(x=-1, y=-1, z=-1)
    truck_id: Optional[int] = -1


class Truck(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    dim: Dimension = Field(...,alias="dimension")
    max_capacity: int

    # For fimal state representation
    objective_value: Optional[float] = 0.0


@dataclass
class Variable:
    trucks: list[Truck]
    packages: list[Package]


def readJSON(path: str) -> Variable:
    """Membaca input. Menerima satu truk (`"truck"`) atau beberapa truk (`"trucks"`)."""
    with open(path, "r", encoding="utf-8") as file:
        data = json.load(file)

    # TODO: Meticulous data validation
    trucks = data["trucks"] if "trucks" in data else [data["truck"]]

    return Variable(
        trucks=[Truck(**truck) for truck in trucks],
        packages=[Package(**package) for package in data["packages"]],
    )


def writeJSON(path: str, var: Variable):
    trucks = [truck.model_dump(by_alias=True) for truck in var.trucks]
    data = {"truck": trucks[0]} if len(trucks) == 1 else {"trucks": trucks}
    data["packages"] = [package.model_dump(by_alias=True) for package in var.packages]

    with open(path, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=2)

ORIENTATION = [
    {"w": "x", "l": "y", "h": "z"},  # 0: xyz
    {"w": "x", "l": "z", "h": "y"},  # 1: xzy
    {"w": "y", "l": "x", "h": "z"},  # 2: yxz
    {"w": "y", "l": "z", "h": "x"},  # 3: yzx
    {"w": "z", "l": "x", "h": "y"},  # 4: zxy
    {"w": "z", "l": "y", "h": "x"},  # 5: zyx
]


def _rotate(orient_id: int, axis: str) -> int:
    """Rotasi 90 derajat terhadap sumbu `axis` menukar dua sumbu lainnya."""
    a, b = {"x": ("y", "z"), "y": ("x", "z"), "z": ("x", "y")}[axis]
    swap = {a: b, b: a}
    return ORIENTATION.index({k: swap.get(v, v) for k, v in ORIENTATION[orient_id].items()})


# ROTATION[orient_id][axis] -> orient_id setelah rotasi 90 derajat terhadap sumbu x (0), y (1), atau z (2)
ROTATION = [[_rotate(o, axis) for axis in "xyz"] for o in range(len(ORIENTATION))]


def _extents(width: int, length: int, height: int, orient_id: int) -> tuple[int, int, int]:
    orient = ORIENTATION[orient_id]
    size = {orient["w"]: width, orient["l"]: length, orient["h"]: height}
    return size["x"], size["y"], size["z"]


@dataclass(eq=False)
class PackageState:
    """
    eq=False: kesetaraan berdasarkan identitas (seperti `other is package` di constraints),
    sehingga objek bisa dipakai di set dan sebagai pemilik sel di Container.
    """
    width: int
    length: int
    height: int
    orientation_id: int
    x: int
    y: int
    z: int
    value: int
    weight: int
    is_fragile: bool
    eta: int

    id: str = ""
    truck_id: int = -1  # -1 = di luar truk

    # Cache: (dx, dy, dz) tiap orientasi, dan orientasi dengan extents berbeda
    extents: tuple[tuple[int, int, int], ...] = field(init=False, repr=False)
    unique_orients: tuple[int, ...] = field(init=False, repr=False)

    def __post_init__(self):
        self.extents = tuple(
            _extents(self.width, self.length, self.height, o) for o in range(len(ORIENTATION))
        )
        seen: dict[tuple[int, int, int], int] = {}
        for o, e in enumerate(self.extents):
            seen.setdefault(e, o)
        self.unique_orients = tuple(seen.values())


@dataclass
class TruckState:
    trucks: list[Truck]
    packages_inside: dict[str, PackageState]
    packages_outside: dict[str, PackageState]

    # Urutan paket sesuai urutan input dan indeks per truk
    ids: list[str] = field(default_factory=list)
    containers: list[Container] = field(default_factory=list)

    # Total berjalan, dijaga secara inkremental oleh state.py
    total_value: int = 0
    weight: list[int] = field(default_factory=list)
    n_fragile_pairs: int = 0
    n_eta_pairs: int = 0
    n_floating: int = 0
    support_deficit: float = 0.0
    compactness: float = 0.0

    # Pengaturan yang memengaruhi total di atas
    support_tau: float = 0.5 # Batas minimum persentase alas paket (variant)
    track_eta: bool = True

    # Skala untuk normalisasi penalti objective function
    v_max: int = 1
    vw_max: float = 1.0

    def find(self, package_id: str) -> PackageState | None:
        package = self.packages_inside.get(package_id)
        return package if package is not None else self.packages_outside.get(package_id)


def variable_to_state(var: Variable, support_tau: float = 0.5) -> TruckState:
    """
    Paket dengan `is_inside` dimuat di posisi `pos` pada truk `truck_id` (default 0),
    sehingga hasil `writeJSON` bisa dibaca ulang sebagai state.
    """
    containers = [Container(t.dim.width, t.dim.length, t.dim.height) for t in var.trucks]
    inside = {}
    outside = {}
    for p in var.packages:
        if p.id in inside or p.id in outside:
            raise ValueError(f"Duplicate package id '{p.id}'")
        orient = {
            "w": p.orient.width,
            "l": p.orient.length,
            "h": p.orient.height,
        }
        orient_id = ORIENTATION.index(orient)

        package = PackageState(
            width=p.dim.width,
            length=p.dim.length,
            height=p.dim.height,
            orientation_id=orient_id,
            x=-1,
            y=-1,
            z=-1,
            value=p.value,
            weight=p.weight,
            is_fragile=p.is_fragile,
            eta=p.eta,
            id=p.id,
        )

        if p.is_inside:
            t = p.truck_id if p.truck_id is not None and p.truck_id >= 0 else 0
            x, y, z = p.pos.x, p.pos.y, p.pos.z
            dx, dy, dz = package.extents[orient_id]
            if not containers[t].fits(x, y, z, dx, dy, dz):
                raise ValueError(f"Package '{p.id}' is out of bounds or overlaps another package")
            package.truck_id, package.x, package.y, package.z = t, x, y, z
            containers[t].mark(package, x, y, z, dx, dy, dz, package.is_fragile, True)
            inside[p.id] = package
        else:
            outside[p.id] = package

    packages = var.packages
    truck_state = TruckState(
        trucks=var.trucks,
        packages_inside=inside,
        packages_outside=outside,
        ids=[p.id for p in packages],
        containers=containers,
        weight=[0] * len(var.trucks),
        support_tau=support_tau,
        track_eta=len({p.eta for p in packages}) > 1,
        v_max=max((p.value for p in packages), default=1) or 1,
        vw_max=max((p.value / p.weight for p in packages if p.weight > 0), default=1.0) or 1.0,
    )

    from . import state  # state mengimpor model, jadi impor di sini untuk menghindari siklus
    state.recompute(truck_state)
    return truck_state


def state_to_variable(state: TruckState, objective_value: float | None = None) -> Variable:
    packages = []

    for id in state.ids:
        p = state.find(id)
        orient = Orientation(
            w=ORIENTATION[p.orientation_id]["w"],
            l=ORIENTATION[p.orientation_id]["l"],
            h=ORIENTATION[p.orientation_id]["h"],
        )

        packages.append(Package(
            id=id,
            dim=Dimension(width=p.width, length=p.length, height=p.height),
            orient=orient,
            value=p.value,
            weight=p.weight,
            is_fragile=p.is_fragile,
            eta=p.eta,
            is_inside=id in state.packages_inside,
            pos=Position(x=p.x, y=p.y, z=p.z),
            truck_id=p.truck_id,
        ))

    trucks = state.trucks
    if objective_value is not None:
        trucks = [t.model_copy(update={"objective_value": objective_value}) for t in trucks]

    return Variable(
        trucks=trucks,
        packages=packages
    )
