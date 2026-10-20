import random
from . import model, geometry

def generate_initial_state(var: model.Variable) -> model.TruckState:
    """Menghasilkan initial state acak berstruktur multi-truk non-uniform dengan metode drop."""
    truck_state = model.variable_to_state(var)
    sorted_packages = sorted(
        var.packages,
        key=lambda p: (p.value / (p.dim.width * p.dim.length * p.dim.height)) if (p.dim.width * p.dim.length * p.dim.height) > 0 else 0,
        reverse=True
    )
    
    n_trucks = len(truck_state.trucks)
    
    for p in sorted_packages:
        pkg_state = truck_state.packages_outside.get(p.id)
        if not pkg_state:
            continue
            
        truck_indices = list(range(n_trucks))
        random.shuffle(truck_indices)
        
        placed = False
        for target_truck_idx in truck_indices:
            dim_truck = truck_state.trucks[target_truck_idx].dim
            
            for _ in range(6):
                pkg_state.orientation_id = random.randint(0, 5)
                dx, dy, dz = geometry.extents(pkg_state)
                
                max_x = dim_truck.width - dx
                max_y = dim_truck.length - dy
                
                if max_x < 0 or max_y < 0 or dz > dim_truck.height:
                    continue
                    
                pkg_state.x = random.randint(0, max_x)
                pkg_state.y = random.randint(0, max_y)
                
                max_z = 0
                for inside_pkg in truck_state.packages_inside.values():
                    if inside_pkg.truck_id == target_truck_idx and geometry.overlap_xy(pkg_state, inside_pkg):
                        _, _, _, _, _, top_z_inside = geometry.bounds(inside_pkg)
                        if top_z_inside > max_z:
                            max_z = top_z_inside
                            
                pkg_state.z = max_z
                
                if pkg_state.z + dz <= dim_truck.height:
                    pkg_state.truck_id = target_truck_idx
                    truck_state.packages_outside.pop(p.id)
                    truck_state.packages_inside[p.id] = pkg_state
                    placed = True
                    break
                    
            if placed:
                break
                
        if not placed:
            pkg_state.x, pkg_state.y, pkg_state.z = -1, -1, -1
            pkg_state.truck_id = -1
            
    return truck_state