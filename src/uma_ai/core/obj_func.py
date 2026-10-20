from . import model, constraints

def variant_1_hard(_state: model.TruckState) -> float:
    """Hardest constraint: if any constraint is violated, return 0.0"""
    if not constraints.is_valid(_state):
        return 0.0

    total_values = sum(p.value for p in _state.packages_inside.values())
    total_weight = sum(p.weight for p in _state.packages_inside.values())

    if total_weight > _state.truck.max_capacity:
        return 0.0

    return total_values

def variant_2(_state: model.TruckState) -> float:
    """
    Fungsi objektif dengan soft penalty gradual.
    Nilai = Total Value paket di dalam - Penalty (Overlap, Floating, Overweight).
    """
    total_value = sum(p.value for p in _state.packages_inside.values())
    total_weight = sum(p.weight for p in _state.packages_inside.values())
    
    penalty = 0.0

    if total_weight > _state.truck.max_capacity:
        penalty += (total_weight - _state.truck.max_capacity) * 5.0

    for p in _state.packages_inside.values():
        if not constraints.is_inside_bound(p, _state):
            penalty += 50.0
        if not constraints.is_supported(p, _state):
            penalty += 30.0

    inside = list(_state.packages_inside.values())
    for i in range(len(inside)):
        for j in range(i + 1, len(inside)):
            if constraints.is_overlap(inside[i], inside[j]):
                penalty += 40.0

    return total_value - penalty

# TODO: More variants