import random
from . import model, geometry

def generate_initial_state(var: model.Variable) -> model.TruckState:
    """
    Menghasilkan initial state dengan menjatuhkan paket dari atas truk.
    Diurutkan berdasarkan rasio value / volume (kepadatan nilai) tertinggi.
    """
    truck_state = model.variable_to_state(var)
    
    def value_density(pkg: model.Package) -> float:
        vol = pkg.dim.width * pkg.dim.length * pkg.dim.height
        return pkg.value / vol if vol > 0 else 0
        
    sorted_packages = sorted(var.packages, key=value_density, reverse=True)
    
    dim_truck = truck_state.truck.dim
    
    for p in sorted_packages:
        pkg_state = truck_state.packages_outside.get(p.id)
        if not pkg_state:
            continue
            
        pkg_state.orientation_id = random.randint(0, 5)
        dx, dy, dz = geometry.extents(pkg_state)
        max_x = dim_truck.width - dx
        max_y = dim_truck.length - dy
        
        if max_x < 0 or max_y < 0:
            continue
            
        pkg_state.x = random.randint(0, max_x)
        pkg_state.y = random.randint(0, max_y)
        
        max_z = 0
        for inside_pkg in truck_state.packages_inside.values():
            if geometry.overlap_xy(pkg_state, inside_pkg):
                _, _, _, _, _, top_z_inside = geometry.bounds(inside_pkg)
                if top_z_inside > max_z:
                    max_z = top_z_inside
                    
        pkg_state.z = max_z
        
        if pkg_state.z + dz > dim_truck.height:
            pkg_state.x, pkg_state.y, pkg_state.z = -1, -1, -1
            continue
            
        truck_state.packages_outside.pop(p.id)
        truck_state.packages_inside[p.id] = pkg_state
        
    return truck_state