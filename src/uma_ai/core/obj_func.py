from . import model, constraints
from .params import ObjectiveParams

_DEFAULT = ObjectiveParams()


def is_feasible(_state: model.TruckState) -> bool:
    """True jika semua hard constraint terpenuhi."""
    return not (_state.n_floating or _state.n_fragile_pairs or constraints.overweight_amount(_state))


def variant_1_hard(_state: model.TruckState, params: ObjectiveParams | None = None) -> float:
    """Hardest constraint: if any constraint is violated, return 0.0"""
    return float(_state.total_value) if is_feasible(_state) else 0.0


def variant_2(_state: model.TruckState, params: ObjectiveParams | None = None) -> float:
    """Tumpuan dan fragile hard (0.0 jika dilanggar), kelebihan berat menjadi penalti."""
    p = params or _DEFAULT
    if _state.n_floating or _state.n_fragile_pairs:
        return 0.0
    return _state.total_value - p.c_weight * _state.vw_max * constraints.overweight_amount(_state)


def variant_3(_state: model.TruckState, params: ObjectiveParams | None = None) -> float:
    """Semua soft: nilai dikurangi penalti melayang, fragile, kelebihan berat, dan urutan bongkar (ETA)."""
    p = params or _DEFAULT
    v = _state.v_max
    return (
        _state.total_value
        - p.c_floating * v * _state.n_floating
        - p.c_fragile * v * _state.n_fragile_pairs
        - p.c_weight * _state.vw_max * constraints.overweight_amount(_state)
        - p.c_eta * v * _state.n_eta_pairs
    )


def variant_4(_state: model.TruckState, params: ObjectiveParams | None = None) -> float:
    """variant_3 ditambah penalti alas yang tertumpu kurang dari min_support (persentase minimum untuk disupport)."""
    p = params or _DEFAULT
    tau = _state.min_support
    support_penalty = p.c_support * _state.v_max * _state.support_deficit / tau if tau > 0 else 0.0
    return variant_3(_state, p) - support_penalty


def variant_5(_state: model.TruckState, params: ObjectiveParams | None = None) -> float:
    """
    variant_4 ditambah tie-breaker kerapatan: paket yang jauh dari lantai dan dinding belakang
    sedikit mengurangi nilai, untuk heuristik HC agar punya arah).
    """
    p = params or _DEFAULT
    volume = sum(t.dim.width * t.dim.length * t.dim.height for t in _state.trucks)
    return variant_4(_state, p) - p.c_compact * _state.v_max * _state.compactness / volume

def variant_6_unscaled(_state: model.TruckState, params: ObjectiveParams | None = None) -> float:
    """
    Variant sederhana (unscaled penalty):
    Mengurangi total value murni dengan jumlah pelanggaran langsung tanpa pengali v_max.
    """
    p = params or _DEFAULT
    return (
        _state.total_value
        - p.c_floating * _state.n_floating
        - p.c_fragile * _state.n_fragile_pairs
        - p.c_weight * constraints.overweight_amount(_state)
        - p.c_eta * _state.n_eta_pairs
    )

VARIANTS = {1: variant_1_hard, 2: variant_2, 3: variant_3, 4: variant_4, 5: variant_5, 6: variant_6_unscaled}


def evaluate(_state: model.TruckState, params: ObjectiveParams | None = None) -> float:
    p = params or _DEFAULT
    return VARIANTS[p.variant](_state, p)
