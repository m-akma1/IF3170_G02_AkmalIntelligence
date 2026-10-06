from __future__ import annotations
from dataclasses import dataclass
from itertools import chain
from pydantic import BaseModel, Field, model_validator
from typing import Optional
import json

class Dimension(BaseModel):
    width: int
    length: int
    height: int


class Orientation(BaseModel):
    """
    Valid value only permutation of (x, y, z).
    """
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
    id: str
    dim: Dimension
    orient: Orientation
    value: int
    weight: int
    is_fragile: bool
    eta: int

    # For final state representation
    is_inside: Optional[bool] = False
    pos: Optional[Position] = Position(x=-1, y=-1, z=-1)


class Truck(BaseModel):
    dim: Dimension
    max_capacity: int

    # For fimal state representation
    objective_value: Optional[float] = 0.0


@dataclass
class Variable:
    truck: Truck
    packages: list[Package]


def readJSON(path: str) -> Variable:
    with open(path, "r", encoding="utf-8") as file:
        data = json.load(file)

    # TODO: Meticulous data validation

    return Variable(
        truck=Truck(**data["truck"]),
        packages=[Package(**package) for package in data["packages"]],
    )


def writeJSON(path: str, var: Variable):
    data = {
        "truck": var.truck.model_dump(),
        "packages": [package.model_dump() for package in var.packages],
    }

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

@dataclass
class PackageState:
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

@dataclass
class TruckState:
    truck: Truck
    packages_inside: dict[str, PackageState]
    packages_outside: dict[str, PackageState]

def variable_to_state(var: Variable) -> TruckState:
    inside = {}
    outside = {}
    for p in var.packages:
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
        )

        if p.is_inside:
            inside[p.id] = package
        else:
            outside[p.id] = package
    
    return TruckState(
        truck=var.truck,
        packages_inside=inside,
        packages_outside=outside
    )


def state_to_variable(state: TruckState) -> Variable:
    packages = []

    for id, p in chain(state.packages_inside.items(), state.packages_outside.items()):
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
            pos=Position(x=p.x, y=p.y, z=p.z)
        ))
    
    # TODO: Add the final objective value to truck somehow

    return Variable(
        truck=state.truck,
        packages=packages
    )