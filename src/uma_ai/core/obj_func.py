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
    if not constraints.is_valid(_state):
        return 0.0

    total_values = sum(p.value for p in _state.packages_inside.values())
    total_weight = sum(p.weight for p in _state.packages_inside.values())

    weight_penalty = max(0, total_weight - _state.truck.max_capacity) * 10 # param1

    return total_values - weight_penalty

# TODO: More variants