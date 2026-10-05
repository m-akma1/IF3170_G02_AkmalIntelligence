import random

class State:
    def __init__(self, num_packages: int, sequences = None, orientations = None):
        self.num_packing = num_packages
        self.fitness:float = -float('inf')
        
        # urutan prioritas penempatan
        if sequences == None:
            self.sequences = random.sample(range(num_packages), num_packages)
        else:
            self.sequences = sequences
        
        # orientasi paket
        if orientations == None:
            self.orientation = [random.randint(0, 5) for _ in range(num_packages)]
        else:
            self.orientation = orientations
    
    def clone(self) -> 'State':
        cloned = State(self.num_packing, self.sequences, self.orientation)
        cloned.fitness = self.fitness
        return cloned
        