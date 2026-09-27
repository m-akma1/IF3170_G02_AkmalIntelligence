import random
from typing import Tuple



class Box:
    
    def __init__(self,x : float,y : float,z : float, w: float, h : float, l : float):
        """Create hit boxes of the package

        Args:
            x (float): x coordinate of the lower point
            y (float): y coordinate of the lower point
            z (float): z coordinate of the lower point
            w (float): width of the box
            h (float): hight of the box
            l (float): length of the box
        """
        # titik minimum
        self.min_x = x
        self.min_y = y
        self.min_z = z
        
        # Dimensi
        self.w = w
        self.h = h
        self.l = l
        
        # Dimensi efektif
        self.dx = self.w
        self.dy = self.l
        self.dz = self.h
        
        
        # titik maksimum ujung
        self.max_x = self.min_x + self.dx
        self.max_y = self.min_y + self.dy
        self.max_z = self.min_z + self.dz
    
    def setPosition(self, x : float, y : float, z : float ):
        """set new position

        Args:
            x (float): new x coordinate
            y (float): new y coordinate
            z (float): new z coordinate
        """
        self.min_x = x
        self.min_y = y
        self.min_z = z
        
        self.max_x = self.min_x + self.dx
        self.max_y = self.min_y + self.dy
        self.max_z = self.min_z + self.dz
    
    def setRandomPosition(self, container : Box):
        valid_x = container.max_x - self.dx
        valid_y = container.max_y - self.dy
        valid_z = container.max_z - self.dz
        
        new_x = random.randint(int(container.min_x), max(container.min_x,valid_x))
        new_y = random.randint(container.min_y, max(container.min_y,valid_y))
        new_z = random.randint(container.min_z, max(container.min_z,valid_z))
        self.setPosition(new_x,new_y,new_z)
    
    def setOrientation(self, orientation:list):
        """Apply orientation into the package

        Args:
            orientation (list): current orientation that want to be applied
        """
        axis_map = {'x' : self.w, 'y' : self.l, 'z' : self.h}
        self.dx = axis_map[orientation[0]]
        self.dy = axis_map[orientation[1]]
        self.dz = axis_map[orientation[2]]
        
        self.max_x = self.min_x + self.dx
        self.max_y = self.min_y + self.dy
        self.max_z = self.min_z + self.dz
    
        
    @property
    def getCenter(self) -> Tuple:
        return (
            self.min_x + (self.dx / 2.0),
            self.min_y + (self.dy / 2.0),
            self.min_z + (self.dz / 2.0)
        )

    @property
    def render_dimensions(self) -> Tuple[float, float, float]:
        """Dimensi siap pakai untuk visualizer Viser."""
        return (self.dx, self.dy, self.dz)
        
        


class Package:
    ALL_ORIENTATIONS = [
            ['x', 'y', 'z'],
            ['x', 'z', 'y'],
            ['y', 'x', 'z'],
            ['y', 'z', 'x'],
            ['z', 'x', 'y'],
            ['z', 'y', 'x']
        ]
    def __init__(self, id : str, box : Box, orientation:tuple = ('x', 'y', 'z'), value: int = 0, weight:int = 0, fragile:bool = False, eta : int = 1):
        """_summary_

        Args:
            id (str)                        : id package
            box (Box)                       : bounding box package
            orientation (tuple, optional)   : orientation of the package. Defaults to ('x', 'y', 'z').
            value (int, optional)           : the value of the package. Defaults to 0.
            weight (int, optional)          : the weight of the package. Defaults to 0.
            fragile (bool, optional)        : is the package can be divided. Defaults to False.
            eta (int, optional)             : when the package will arrived. Defaults to 1.
        """
        self.id = id
        self.box = box
        self.orientation = orientation
        self.value = value
        self.weight = weight
        self.isFragile = fragile
        self.eta = eta
        
    @property
    def orientation(self) -> tuple:
        return self._orientation

    @orientation.setter
    def orientation(self, new_ori: tuple):
        """set the package orientation"""
        self._orientation = tuple(new_ori)
        self.box.setOrientation(self.orientation)
    
    def rotateRandom(self):
        """random rotate of the package orientation
        """
        self.orientation = random.choice(self.ALL_ORIENTATIONS)
    
    
class Truck:
    def __init__(self, maxSize : Box, maxWeight : int):
        """Main container of the packages

        Args:
            maxSize (Box): packages container maximum size hitboxes
            maxWeight (int): maximum wight that the truck can carries
        """
        self.maxSizeTruck = maxSize
        self.maxWeight = maxWeight
        self.current_weight = 0
        self.current_value = 0
        self.packages : list[Package]= []
    
    def putPackage(self, new_package : Package) -> bool:
        """Checks is packages can be put in the truck

        Args:
            new_package (Package): package that going to be put in the truck

        Returns:
            bool: true if it can be put
        """
        if self.current_weight + new_package.weight > self.maxWeight:
            return False
            
        # cek tidak keluar wadah dinding
        if not self.is_inside(new_package):
            return False
        
        # cek tidak menabrak box lain
        for package_inside in self.packages:
            if self.check_collision(package_inside.box, new_package.box):
                return False
        
        # cek tidak melayang
        if not self.is_supported(new_package):
            return False
        
        self.packages.append(new_package)
        self.current_weight += new_package.weight
        self.current_value += new_package.value
        return True
        
        
    # SAT https://fileadmin.cs.lth.se/cs/Personal/Tomas_Akenine-Moller/code/tribox_tam.pdf
    def check_collision(self, a : Box, b:Box)->bool:
        """checking collision between boxes

        Args:
            a (Box): box hit box a
            b (Box): box hit box b

        Returns:
            bool: true if collision happen
        """
        overlap_x = (a.min_x < b.max_x) and (a.max_x > b.min_x)
        overlap_y = (a.min_y < b.max_y) and (a.max_y > b.min_y)
        overlap_z = (a.min_z < b.max_z) and (a.max_z > b.min_z)
        # Tabrakan terjadi jika ketiganya overlap
        return overlap_x and overlap_y and overlap_z
    
    def is_inside(self, package: Package) -> bool:
        """Checking is the package inside of the truck's container

        Args:
            package (Package): package

        Returns:
            bool: true if is inside
        """
        box = package.box
        return (box.min_x >= self.maxSizeTruck.min_x and box.max_x <= self.maxSizeTruck.max_x and
                box.min_y >= self.maxSizeTruck.min_y and box.max_y <= self.maxSizeTruck.max_y and
                box.min_z >= self.maxSizeTruck.min_z and box.max_z <= self.maxSizeTruck.max_z)
        
    def is_supported(self, package: Package) -> bool:
        """Checking if the package is supported (not floating)

        Args:
            package (Package): package that going to be checks

        Returns:
            bool: true if it is supported by other packages
        """
        box : Box = package.box
        
        EPSILON = 1e-5
        if abs(box.min_z) <= EPSILON :
            return True
        
        for other in self.packages:
            if abs(box.min_z - other.box.max_z) <= EPSILON:
                overlap_x = (box.min_x < other.box.max_x) and (box.max_x > other.box.min_x)
                overlap_y = (box.min_y < other.box.max_y) and (box.max_y > other.box.min_y)
                if overlap_x and overlap_y :
                    return True
        return False
    
    
    
        