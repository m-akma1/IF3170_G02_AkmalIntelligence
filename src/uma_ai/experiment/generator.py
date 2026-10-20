from __future__ import annotations

import argparse
import json
import math
import random
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from uma_ai.core import model

from .suite import INPUT_DIR, ROOT, resolve

GENERATOR_DIR = ROOT / "data" / "generator"

_AXES = ("x", "y", "z")


class _Spec(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Dist(_Spec):
    """
    Distribusi satu atribut, clamped ke [low, high].

    uniform: rata di [low, high]; triangular: puncak di `mode` (default tengah);
    normal: mean `mu` (default tengah), simpangan `sigma` (default (high - low) / 4);
    lognormal: median `mu` (default sqrt(low x high), low > 0), sigma dalam skala log (default 0.5).
    """
    low: float
    high: float
    dist: Literal["uniform", "triangular", "normal", "lognormal"] = "uniform"
    mode: float | None = None
    mu: float | None = None
    sigma: float | None = None

    @model_validator(mode="before")
    @classmethod
    def _shorthand(cls, data):
        if isinstance(data, (int, float)):
            return {"low": data, "high": data}
        if isinstance(data, (list, tuple)) and len(data) == 2:
            return {"low": data[0], "high": data[1]}
        return data

    @model_validator(mode="after")
    def _check(self):
        if self.low > self.high:
            raise ValueError(f"low ({self.low}) > high ({self.high})")
        if self.dist == "lognormal" and self.low <= 0:
            raise ValueError("lognormal butuh low > 0")
        return self

    def sample(self, rng: random.Random) -> float:
        lo, hi = self.low, self.high
        if lo == hi:
            return lo
        if self.dist == "triangular":
            x = rng.triangular(lo, hi, self.mode if self.mode is not None else (lo + hi) / 2)
        elif self.dist == "normal":
            x = rng.gauss(self.mu if self.mu is not None else (lo + hi) / 2,
                          self.sigma if self.sigma is not None else (hi - lo) / 4)
        elif self.dist == "lognormal":
            median = self.mu if self.mu is not None else math.sqrt(lo * hi)
            x = rng.lognormvariate(math.log(median), self.sigma if self.sigma is not None else 0.5)
        else:
            x = rng.uniform(lo, hi)
        return min(max(x, lo), hi)

    def sample_int(self, rng: random.Random) -> int:
        if self.dist == "uniform":  # tiap bilangan bulat peluangnya sama
            return rng.randint(math.ceil(self.low), math.floor(self.high))
        return round(self.sample(rng))


class PackageClass(_Spec):
    """Satu kelas paket; id = <name>_<nomor urut 3 digit>."""
    name: str
    share: float = 1.0                  # bobot pembagian sisa paket antar kelas
    count: int | None = None            # jumlah tetap (di luar pembagian share)
    side: Dist = Field(default_factory=lambda: Dist(low=1, high=3))
    width: Dist | None = None           # None = pakai side
    length: Dist | None = None
    height: Dist | None = None
    value: Dist | None = None           # nilai langsung, atau
    value_density: Dist | None = None   # nilai per unit volume
    weight: Dist | None = None          # berat langsung, atau
    weight_density: Dist | None = None  # berat per unit volume
    fragile_prob: float = 0.0
    eta: Dist = Field(default_factory=lambda: Dist(low=0, high=5))

    @model_validator(mode="after")
    def _check(self):
        if (self.value is None) == (self.value_density is None):
            raise ValueError(f"kelas '{self.name}': isi tepat satu dari value / value_density")
        if (self.weight is None) == (self.weight_density is None):
            raise ValueError(f"kelas '{self.name}': isi tepat satu dari weight / weight_density")
        return self


class TruckSpec(_Spec):
    dimension: dict[str, int]           # {"w": ..., "l": ..., "h": ...}
    max_capacity: int
    count: int = 1


class GeneratorParams(_Spec):
    name: str = ""                      # nama file output di data/input ("" = nama file konfigurasi)
    seed: int = 3170
    trucks: list[TruckSpec]
    n_packages: int | None = None       # jumlah paket total, atau
    volume_ratio: float | None = None   # total volume paket sebanding dengan rasio x total volume truk
    weight_ratio: float | None = None   # jika diisi, berat diskalakan agar total ~ rasio x total kapasitas
    random_orientation: bool = True     # orientasi awal acak (False = w-x, l-y, h-z)
    shuffle: bool = True                # urutan paket diacak (False = urut per kelas)
    classes: list[PackageClass]
    extra_packages: list[dict] = Field(default_factory=list)  # paket tetap (format input), mis. jebakan

    @model_validator(mode="after")
    def _check(self):
        if (self.n_packages is None) == (self.volume_ratio is None):
            raise ValueError("isi tepat satu dari n_packages / volume_ratio")
        if not self.classes:
            raise ValueError("classes kosong")
        return self


def _orientation(rng: random.Random, random_orientation: bool) -> dict[str, str]:
    axes = list(_AXES)
    if random_orientation:
        rng.shuffle(axes)
    return dict(zip(("w", "l", "h"), axes))


def _make_package(cls: PackageClass, index: int, rng: random.Random, random_orientation: bool) -> dict:
    w = max(1, (cls.width or cls.side).sample_int(rng))
    l = max(1, (cls.length or cls.side).sample_int(rng))
    h = max(1, (cls.height or cls.side).sample_int(rng))
    volume = w * l * h
    value = cls.value.sample(rng) if cls.value is not None else volume * cls.value_density.sample(rng)
    weight = cls.weight.sample(rng) if cls.weight is not None else volume * cls.weight_density.sample(rng)
    return {
        "id": f"{cls.name}_{index:03d}",
        "dimension": {"w": w, "l": l, "h": h},
        "orientation": _orientation(rng, random_orientation),
        "value": max(0, round(value)),
        "weight": max(1, round(weight)),
        "is_fragile": rng.random() < cls.fragile_prob,
        "eta": max(0, cls.eta.sample_int(rng)),
    }


def _split(total: int, shares: list[float]) -> list[int]:
    """Bagi `total` sesuai bobot (largest remainder), jumlahnya tepat `total`."""
    s = sum(shares)
    if total <= 0 or s <= 0:
        return [0] * len(shares)
    raw = [total * x / s for x in shares]
    counts = [int(r) for r in raw]
    order = sorted(range(len(raw)), key=lambda i: raw[i] - counts[i], reverse=True)
    for i in order[:total - sum(counts)]:
        counts[i] += 1
    return counts


def generate(params: GeneratorParams, seed: int | None = None) -> dict:
    """Mengembalikan test case dalam format input (dict siap ditulis sebagai JSON)."""
    rng = random.Random(params.seed if seed is None else seed)
    trucks = [
        {"dimension": dict(t.dimension), "max_capacity": t.max_capacity}
        for t in params.trucks for _ in range(t.count)
    ]
    truck_volume = sum(t["dimension"]["w"] * t["dimension"]["l"] * t["dimension"]["h"] for t in trucks)
    capacity = sum(t["max_capacity"] for t in trucks)

    counters = {cls.name: 0 for cls in params.classes}

    def new(cls: PackageClass) -> dict:
        counters[cls.name] += 1
        return _make_package(cls, counters[cls.name], rng, params.random_orientation)

    packages = [new(cls) for cls in params.classes for _ in range(cls.count or 0)]
    shared = [cls for cls in params.classes if cls.count is None]
    if params.n_packages is not None:
        remaining = params.n_packages - len(packages)
        for cls, n in zip(shared, _split(remaining, [c.share for c in shared])):
            packages += [new(cls) for _ in range(n)]
    elif shared:
        target = params.volume_ratio * truck_volume

        def volume(p):
            d = p["dimension"]
            return d["w"] * d["l"] * d["h"]
        total = sum(volume(p) for p in packages)
        while total < target:
            p = new(rng.choices(shared, [c.share for c in shared])[0])
            packages.append(p)
            total += volume(p)

    if params.weight_ratio is not None and packages:
        factor = params.weight_ratio * capacity / sum(p["weight"] for p in packages)
        for p in packages:
            p["weight"] = max(1, round(p["weight"] * factor))

    packages += [dict(p) for p in params.extra_packages]
    if params.shuffle:
        rng.shuffle(packages)

    data = {"truck": trucks[0]} if len(trucks) == 1 else {"trucks": trucks}
    data["packages"] = packages
    return data


def load_generator(name: str) -> tuple[GeneratorParams, Path]:
    path = resolve(name, GENERATOR_DIR)
    with open(path, encoding="utf-8") as file:
        params = GeneratorParams.model_validate(json.load(file))
    if not params.name:
        params.name = path.stem
    return params, path


def generate_file(name: str, seed: int | None = None, out: str | Path | None = None) -> Path:
    """Membuat test case dari konfigurasi `name` dan menulisnya (default data/input/<name>.json)."""
    params, _ = load_generator(name)
    data = generate(params, seed)
    out_path = Path(out) if out is not None else INPUT_DIR / f"{params.name}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=2)
    model.readJSON(out_path)  # validasi: hasil harus terbaca sebagai input
    return out_path


def describe(path: Path) -> str:
    var = model.readJSON(path)
    volume = sum(t.dim.width * t.dim.length * t.dim.height for t in var.trucks)
    capacity = sum(t.max_capacity for t in var.trucks)
    pv = sum(p.dim.width * p.dim.length * p.dim.height for p in var.packages)
    pw = sum(p.weight for p in var.packages)
    fragile = sum(p.is_fragile for p in var.packages)
    return (f"{path.name}: {len(var.packages)} paket, {len(var.trucks)} truk, "
            f"volume {pv / volume:.2f}x, berat {pw / capacity:.2f}x kapasitas, {fragile} fragile")


def main():
    parser = argparse.ArgumentParser(description="Membuat test case acak dari konfigurasi generator.")
    parser.add_argument("config", nargs="+", help="konfigurasi di data/generator (mis. 03_gen_small) atau path JSON")
    parser.add_argument("-s", "--seed", type=int, help="ganti seed konfigurasi")
    parser.add_argument("-o", "--out", help="path output (hanya untuk satu konfigurasi)")
    args = parser.parse_args()
    if args.out and len(args.config) > 1:
        parser.error("--out hanya untuk satu konfigurasi")
    for name in args.config:
        print(describe(generate_file(name, args.seed, args.out)))


if __name__ == "__main__":
    main()
