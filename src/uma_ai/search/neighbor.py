import copy
import random
from ..core import model, state

def clone_truck_state(truck_state: model.TruckState) -> model.TruckState:
    inside_clone = {
        pkg_id: copy.copy(pkg)
        for pkg_id, pkg in truck_state.packages_inside.items()
    }
    outside_clone = {
        pkg_id: copy.copy(pkg)
        for pkg_id, pkg in truck_state.packages_outside.items()
    }
    return model.TruckState(
        truck=truck_state.truck,
        packages_inside=inside_clone,
        packages_outside=outside_clone
    )

def get_random_neighbor(current_state: model.TruckState) -> model.TruckState:
    neighbor = clone_truck_state(current_state)
    
    inside_ids = list(neighbor.packages_inside.keys())
    outside_ids = list(neighbor.packages_outside.keys())
    
    if not inside_ids:
        if outside_ids:
            pkg_id = random.choice(outside_ids)
            pkg = neighbor.packages_outside[pkg_id]
            pos = model.Position(
                x=random.randint(0, max(0, neighbor.truck.dim.width - pkg.width)),
                y=random.randint(0, max(0, neighbor.truck.dim.length - pkg.length)),
                z=0
            )
            orient_id = random.randint(0, 5)
            state.put_inside(pkg_id, neighbor, pos, orient_id, skip_check=True)
        return neighbor

    action = random.choice([0, 1, 2, 3])
    
    if action == 0 and outside_ids:
        # Swap inside - outside
        old_pkg_id = random.choice(inside_ids)
        new_pkg_id = random.choice(outside_ids)
        old_pkg = neighbor.packages_inside[old_pkg_id]
        pos = model.Position(x=old_pkg.x, y=old_pkg.y, z=old_pkg.z)
        state.swap(old_pkg_id, new_pkg_id, neighbor, pos, old_pkg.orientation_id, skip_check=True)

    elif action == 1 and len(inside_ids) >= 2:
        # Swap inside - inside
        pkg_id1, pkg_id2 = random.sample(inside_ids, 2)
        p1 = neighbor.packages_inside[pkg_id1]
        p2 = neighbor.packages_inside[pkg_id2]
        pos1 = model.Position(x=p1.x, y=p1.y, z=p1.z)
        pos2 = model.Position(x=p2.x, y=p2.y, z=p2.z)
        state.switch_pos(
            pkg_id1, pkg_id2, neighbor,
            pos2, p2.orientation_id,
            pos1, p1.orientation_id,
            skip_check=True
        )

    elif action == 2:
        # Random positioning
        pkg_id = random.choice(inside_ids)
        pkg = neighbor.packages_inside[pkg_id]
        
        new_x = random.randint(0, max(0, neighbor.truck.dim.width - pkg.width))
        new_y = random.randint(0, max(0, neighbor.truck.dim.length - pkg.length))
        new_z = random.randint(0, max(0, neighbor.truck.dim.height - pkg.height))
        
        delta_pos = model.Position(
            x=new_x - pkg.x,
            y=new_y - pkg.y,
            z=new_z - pkg.z
        )
        state.translate(pkg_id, neighbor, delta_pos, skip_check=True)

    elif action == 3:
        # Rotate
        pkg_id = random.choice(inside_ids)
        current_orient = neighbor.packages_inside[pkg_id].orientation_id
        possible_orients = [i for i in range(6) if i != current_orient]
        new_orient = random.choice(possible_orients)
        state.rotate(pkg_id, neighbor, new_orient, skip_check=True)

    else:
        if len(inside_ids) > 1:
            pkg_id = random.choice(inside_ids)
            state.put_outside(pkg_id, neighbor, skip_check=True)

    return neighbor