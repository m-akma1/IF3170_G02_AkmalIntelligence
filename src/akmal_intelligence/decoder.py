import copy
import akmal_intelligence.interface as uma
from akmal_intelligence.state import State

class PlacementDecoder:
    """Menerjemahkan State menjadi koordinat fisik di dalam truck
    """
    
    @staticmethod
    def decode_and_evaluate(state:State, truck_temp: uma.Truck, packages_temp: list[uma.Package]) -> float:
        
        truck = copy.deepcopy(truck_temp)
        coming_packages = [copy.deepcopy(p) for p in packages_temp]
        
        candidate_points = [(0,0,0)]
        
        placed = False
        best_point = None
        
        for idx in state.sequences:
            package = coming_packages[idx]
            orien_idx = state.orientation[idx]
            
            package.orientation = uma.Package.ALL_ORIENTATIONS[orien_idx]
            
            # mengutamakan Z terendah, Y kemudian X
            candidate_points.sort(key=lambda pt: (pt[2], pt[1], pt[0]))
            
            for pt in candidate_points:
                package.box.setPosition(pt[0], pt[1], pt[2])
                
                # cek valid posisi valid menurut batasan fisik truk
                if (truck.current_weight + package.weight <= truck.maxWeight) and truck.is_inside(package) and not any(truck.check_collision(p.box, package.box) for p in truck.packages) and truck.is_supported(package):
                    best_point = pt
                    placed = True
                    break
            
            if placed and best_point is not None:
                truck.putPackage(package)
                candidate_points = [p for p in candidate_points if p != best_point]
                
                # heurisik paket berikutnya ditaruh disampingnya
                box = package.box
                new_box_point = [
                    (box.max_x, box.min_y, box.min_z),
                    (box.min_x, box.max_y, box.min_z)
                ]
                
                # heuristik jika bukan fragile bisa ditaruh dibagian atasnya
                if not package.isFragile:
                    new_box_point.append((box.min_x, box.min_y,box.max_z))
                
                for np in new_box_point:
                    if np not in candidate_points and np[0] < truck.maxSizeTruck.max_x and np[1] < truck.maxSizeTruck.max_y:
                        candidate_points.append(np)
                
        fitness = float(truck.current_value)
        penalty_eta = 0
        for p_under in truck.packages:
            for p_above in truck.packages:
                if (p_under == p_above):
                    continue
                
                if (p_above.box.min_z >= p_under.box.max_z and truck.check_collision(uma.Box(p_under.box.w, 1,p_under.box.l, p_under.box.min_x, p_under.box.min_y, p_under.box.min_z), p_above.box)):
                    if p_under.eta < p_above.eta:
                        penalty_eta += 50 * (p_above.eta - p_under.eta)
        state.fitness = fitness - penalty_eta
        return state.fitness
                
            
            
            