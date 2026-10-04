
import interface as uma
import umaIO as uma_reader
import viser 
import time
import copy
from decoder import PlacementDecoder
from solvers.genetic import GeneticSolver



def renderBox(server : viser.ViserServer, box : uma.Box, id:str, wireframe = False, fragile = False, color = (255,255,255)):
    server.scene.add_box(
        name= id,
        dimensions= box.render_dimensions,
        color= (255,0,0) if fragile else color,
        wireframe=wireframe,
        position=(box.getCenter) 
    )
    

def main():
    server = viser.ViserServer()
    Truk, paketDatang = uma_reader.readJsonUmaIncomingPackets("data/uma.json")
    print(Truk.maxSizeTruck)
    print(f"Jumlah paket : {len(paketDatang)}")
    renderBox(server, Truk.maxSizeTruck,"Truk Uma", True)
    
    print("Menjalankan genetic Algorithms ...")
    solver = GeneticSolver(Truk, paketDatang, pop_size=20, generations=30)
    best_solution = solver.solverGA()
    
    final_truck = copy.deepcopy(Truk)
    candidate_packages = [copy.deepcopy(p) for p in paketDatang]
    # Gunakan state terbaik yang didapat
    candidate_points = [(0, 0, 0)]
    for idx in best_solution.sequences:
        pkg = candidate_packages[idx]
        pkg.orientation = uma.Package.ALL_ORIENTATIONS[best_solution.orientation[idx]]
        candidate_points.sort(key=lambda pt: (pt[2], pt[1], pt[0]))
        
        placed = False
        best_pt = None
        for pt in candidate_points:
            pkg.box.setPosition(pt[0], pt[1], pt[2])
            if (final_truck.current_weight + pkg.weight <= final_truck.maxWeight and
                final_truck.is_inside(pkg) and
                not any(final_truck.check_collision(p.box, pkg.box) for p in final_truck.packages) and
                final_truck.is_supported(pkg)):
                best_pt = pt
                placed = True
                break
        if placed and best_pt:
            final_truck.putPackage(pkg)
            candidate_points.remove(best_pt)
            bx = pkg.box
            candidate_points.extend([
                (bx.max_x, bx.min_y, bx.min_z),
                (bx.min_x, bx.max_y, bx.min_z)
            ])
            if not pkg.isFragile:
                candidate_points.append((bx.min_x, bx.min_y, bx.max_z))
    
    # Tampilkan hasil di Viser
    for pkg in final_truck.packages:
        renderBox(server, pkg.box, pkg.id, fragile=pkg.isFragile, color=pkg.color)
       
    print(f"Optimal Total Value: {final_truck.current_value}")
    print(f"Total Weight: {final_truck.current_weight} / {final_truck.maxWeight}")
    print("Buka browser di http://localhost:8080. Tekan Ctrl+C untuk keluar.")

    while True:
        time.sleep(10.0)


if __name__ == "__main__":
    main()



