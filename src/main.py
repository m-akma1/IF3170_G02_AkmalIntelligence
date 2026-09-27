
import interface as uma
import viser 
import time
import random



def renderBox(server : viser.ViserServer, box : uma.Box, id:str, wireframe = False):
    server.scene.add_box(
        name= id,
        dimensions=box.render_dimensions,
        color=(random.randint(0, 255), random.randint(0, 255), random.randint(0, 255)),
        wireframe=wireframe,
        position=(box.getCenter) 
    )
    

def main():
    server = viser.ViserServer()
    # note z itu tinggi
    TrukBox = uma.Box(0,0,0, 5,5,8)
    Truk  = uma.Truck(TrukBox,500)

    
    pack1_box = uma.Box(0,0,0, 1,1,1)
    paket1 = uma.Package("pack1",pack1_box,('x','y','z') ,10, 10, False, 0)
    
    pack2_box = uma.Box(0,0,0, 1,2,1)
    paket2 = uma.Package("pack2", pack2_box,('x','y','z'),20, 20, False, 0)
    
    pack3_box = uma.Box(0,0,0, 1,2,3)
    paket3 = uma.Package("pack3", pack3_box,('x','y','z') ,50, 10, False, 0)
    
    pack4_box = uma.Box(0,0,0, 3,3,3)
    paket4 = uma.Package("pack4", pack4_box,('x','y','z') ,20, 10, False, 0)
    
    pack5_box = uma.Box(0,0,0, 4,4,4)
    paket5 = uma.Package("pack5", pack5_box,('x','y','z') ,50, 10, False, 0)
    
    pack6_box = uma.Box(0,0,0, 5,2,1)
    paket6 = uma.Package("pack6", pack6_box,('x','y','z') ,50, 10, False, 0)

    paketDatang : list[uma.Package] = [paket1, paket2, paket3, paket4, paket5, paket6]
    
    iterasi = 0
    while (True):
        paket = paketDatang.pop()
        if (Truk.putPackage(paket) == False):
            print(iterasi)
            paket.rotateRandom()
            paket.box.setRandomPosition(TrukBox)
            paketDatang.append(paket)
            iterasi += 1
        
        if (len(paketDatang) <= 0) :
            break
        
    renderBox(server, TrukBox,"Truk Uma", True)
    
    for package in Truk.packages:
        renderBox(server, package.box, package.id)
        
       
    print("Open your browser to http://localhost:8080")
    print(f"total iterasi {iterasi}")
    print(f"total weight {Truk.current_weight}")
    print(f"total value {Truk.current_value}")
    print("Press Ctrl+C to exit")

    while True:
        time.sleep(10.0)


if __name__ == "__main__":
    main()



