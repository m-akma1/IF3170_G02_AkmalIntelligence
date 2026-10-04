import random
import interface as uma
from state import State
from decoder import PlacementDecoder

class GeneticSolver:
    def __init__(self, truck : uma.Truck, packages : list[uma.Package], pop_size :int = 30 , generations: int = 30, mutation_rate: float = 0.5):
        self.truck = truck
        self.packages = packages
        self.pop_size = pop_size
        self.generation =generations
        self.mutation_rate = mutation_rate
        self.population : list[State] = [State(len(packages)) for _ in range(pop_size)]
    
    def crossover_ox(self, parent1: list[int], parent2:list[int]) -> list[int]:
        
        size = len(parent1)
        a,b = sorted(random.sample(range(size), 2))
        child = [-1] * size
        child[a:b+1] = parent1[a:b+1]
        p2_idx  = 0
        for i in range(size):
            if child[i] == -1:
                while parent2[p2_idx] in child:
                    p2_idx += 1
                child[i] = parent2[p2_idx]
        return child
    
    def mutate(self, ind : State):
        if random.random() < self.mutation_rate:
            i, j = random.sample(range(ind.num_packing) , 2)
            ind.sequences[i], ind.sequences[j] = ind.sequences[j], ind.sequences[i]
        
        if random.random()< self.mutation_rate:
            idx = random.randint(0, ind.num_packing - 1)
            ind.orientation[idx] = random.randint(0,5)
    
    def solverGA(self) -> State:
        for ind in self.population:
            PlacementDecoder.decode_and_evaluate(ind, self.truck, self.packages)
        
        best_ind = max(self.population, key=lambda x:x.fitness)
        
        for gen in range(self.generation):
            self.population.sort(key=lambda x:x.fitness, reverse=True)
            new_pop = self.population[:2] # elitisme ambil 2 yang terbaik
            
            while len(new_pop) < self.pop_size:
                p1 = max(random.sample(self.population,3), key=lambda x:x.fitness)
                p2 = max(random.sample(self.population,3), key=lambda x:x.fitness)
                
                # crossover
                child_seq = self.crossover_ox(p1.sequences, p2.sequences)
                child_ori = [
                    p1.orientation[i] if random.random() < 0.5 else p2.orientation[i] for i in range(ind.num_packing)
                ]
                
                child = State(len(self.packages), child_seq, child_ori)
                self.mutate(child)
                PlacementDecoder.decode_and_evaluate(child, self.truck, self.packages)
                new_pop.append(child)
            
            self.population = new_pop
            current_best = max(self.population, key=lambda x:x.fitness)
            if current_best.fitness > best_ind.fitness:
                best_ind = current_best.clone()
            
            print(f"Gen {gen + 1}/{self.generation} - Best Fitness: {best_ind.fitness}")
            
        return best_ind

    def get_initial_best_state(self):
        """Mengevaluasi populasi awal dan mengembalikan individu terbaik sebelum evolusi dimulai."""
        for ind in self.population:
            PlacementDecoder.decode_and_evaluate(ind, self.truck, self.packages)
        return max(self.population, key=lambda x: x.fitness).clone()

    def solve_with_history(self):
        """Menjalankan GA sambil merekam fitness terbaik di setiap generasi."""
        history = []
        best_ind = max(self.population, key=lambda x: x.fitness).clone()

        for gen in range(self.generation):
            self.population.sort(key=lambda x: x.fitness, reverse=True)
            new_pop = [self.population[0].clone(), self.population[1].clone()]  # Elitisme

            while len(new_pop) < self.pop_size:
                p1 = max(random.sample(self.population, 3), key=lambda x: x.fitness)
                p2 = max(random.sample(self.population, 3), key=lambda x: x.fitness)

                child_seq = self.crossover_ox(p1.sequences, p2.sequences)
                child_ori = [
                    p1.orientation[i] if random.random() < 0.5 else p2.orientation[i]
                    for i in range(len(self.packages))
                ]

                child = State(len(self.packages), child_seq, child_ori)
                self.mutate(child)
                PlacementDecoder.decode_and_evaluate(child, self.truck, self.packages)
                new_pop.append(child)

            self.population = new_pop
            current_best = max(self.population, key=lambda x: x.fitness)
            if current_best.fitness > best_ind.fitness:
                best_ind = current_best.clone()

            history.append(best_ind.fitness)

        return best_ind, history
            