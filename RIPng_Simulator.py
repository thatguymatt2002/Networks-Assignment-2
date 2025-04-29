# Colors
RESET = "\033[0m"
BOLD = "\033[1m"
CYAN = "\033[96m"
RED = "\033[91m"
GREEN = "\033[92m"

def colored(text, color_code):
    return f"{color_code}{text}{RESET}"

class RoutingTableEntry:
    def __init__(self, destination, subnet_mask, next_hop, metric, timeout=3):
        self.destination = destination
        self.subnet_mask = subnet_mask
        self.next_hop = next_hop
        self.metric = metric
        self.timeout = timeout  # Aging counter
        self.garbage_timer = None

    def __repr__(self):
        return f"{self.destination}\t{self.subnet_mask}\t{self.next_hop}\t{self.metric}\t{self.timeout}"

class Router:
    def __init__(self, router_id):
        self.router_id = router_id
        self.neighbors = []  # list of neighbor Router objects
        self.routing_table = {}  # key: destination, value: RoutingTableEntry

    def add_direct_connection(self, destination_network, subnet_mask):
        entry = RoutingTableEntry(destination_network, subnet_mask, next_hop=self.router_id, metric=0)
        self.routing_table[destination_network] = entry

    def add_neighbor(self, neighbor_router):
        self.neighbors.append(neighbor_router)

    def send_routing_update(self):
        updates = {}
        for neighbor in self.neighbors:
            update_for_neighbor = {}
            for dest, entry in self.routing_table.items():
                # Split Horizon (don't send updates back to the neighbor from which they were received)
                if entry.metric < 16 and entry.next_hop == neighbor.router_id:
                    continue
                update_for_neighbor[dest] = (entry.metric, self.router_id)
            updates[neighbor.router_id] = update_for_neighbor
        return updates

    def receive_routing_update(self, from_router, update):
        updated = False
        for dest, (received_metric, sender_id) in update.items():
            new_metric = min(received_metric + 1, 16)  # Don't allow metrics > 16

            # Check if this router already knows the route
            if dest in self.routing_table:
                existing_entry = self.routing_table[dest]

                if existing_entry.next_hop == sender_id:
                    # We're using this neighbor as next hop already
                    existing_entry.metric = new_metric
                    existing_entry.timeout = 3

                    if new_metric == 16:
                        existing_entry.garbage_timer = 2
                        print(colored(f"[INFO] Route to {dest} marked unreachable on router {self.router_id}.", RED))
                    else:
                        existing_entry.garbage_timer = None  # Route revived

                    updated = True

                elif new_metric < existing_entry.metric:
                    # Better path offered by a different neighbor
                    self.routing_table[dest] = RoutingTableEntry(dest, '/24', sender_id, new_metric)
                    updated = True

            else:
                # New destination entirely
                self.routing_table[dest] = RoutingTableEntry(dest, '/24', sender_id, new_metric)
                updated = True

        return updated

    def display_routing_table(self):
        print(colored(f"Routing Table for {self.router_id}", BOLD + CYAN))
        print(f"{'Destination':<15}{'Subnet':<10}{'Next Hop':<10}{'Metric':<8}{'Timeout'}")
        print("-" * 60)
        for entry in self.routing_table.values():
            line = f"{entry.destination:<15}{entry.subnet_mask:<10}{entry.next_hop:<10}{entry.metric:<8}{entry.timeout}"
            print(colored(line, GREEN))
        print()

    def age_routes(self):
        for dest, entry in list(self.routing_table.items()):
            if entry.metric == 0:
                continue  # Don't age directly connected routes

            if entry.metric < 16:
                # Age active routes
                entry.timeout -= 1
                if entry.timeout <= 0:
                    entry.metric = 16  # Mark as unreachable
                    entry.garbage_timer = 2  # Start garbage collection timer
                    print(colored(f"[INFO] Route to {dest} marked unreachable on router {self.router_id}.", RED))
            else:
                # Already unreachable, age the garbage timer
                if entry.garbage_timer is not None:
                    entry.garbage_timer -= 1
                    if entry.garbage_timer <= 0:
                        print(colored(f"[INFO] Route to {dest} removed from router {self.router_id}.", RED))
                        del self.routing_table[dest]

class NetworkSimulator:
    def __init__(self):
        self.routers = {}

    def add_router(self, router):
        self.routers[router.router_id] = router

    def simulate_round(self):
        # Each router prepares updates for each neighbor
        all_updates = {}
        for router in self.routers.values():
            all_updates[router.router_id] = router.send_routing_update()

        # Each router receives updates
        for router in self.routers.values():
            for neighbor in router.neighbors:
                update = all_updates[neighbor.router_id].get(router.router_id, {})
                router.receive_routing_update(neighbor.router_id, update)

        # After updates, age the routes
        for router in self.routers.values():
            router.age_routes()

    def display_all_tables(self):
        for router in self.routers.values():
            router.display_routing_table()

def main():
    # Create Routers
    routerA = Router('A')
    routerB = Router('B')
    routerC = Router('C')
    routerD = Router('D')
    routerE = Router('E')

    # Connect routers (neighbors)
    routerA.add_neighbor(routerB)
    routerA.add_neighbor(routerC)
    routerB.add_neighbor(routerA)
    routerB.add_neighbor(routerD)
    routerC.add_neighbor(routerA)
    routerD.add_neighbor(routerB)
    routerE.add_neighbor(routerD)
    routerD.add_neighbor(routerE)

    # Add directly connected networks
    routerA.add_direct_connection('10.0.0.0', '/24')
    routerB.add_direct_connection('20.0.0.0', '/24')
    routerC.add_direct_connection('30.0.0.0', '/24')
    routerD.add_direct_connection('40.0.0.0', '/24')
    routerE.add_direct_connection('50.0.0.0', '/24')

    # Create network simulator
    network = NetworkSimulator()
    network.add_router(routerA)
    network.add_router(routerB)
    network.add_router(routerC)
    network.add_router(routerD)
    network.add_router(routerE)

    print("=== Initial Routing Tables ===")
    network.display_all_tables()

    # Simulate a few rounds of updates
    rounds = 5
    for round in range(rounds):
        input(f"=== Press ENTER to simulate Round {round+1} ===")
        network.simulate_round()
        network.display_all_tables()

    input(f"=== Press ENTER to trigger event ===")
    print("\n[EVENT] Router E is now offline!\n")
    
    del network.routers['E']
    routerD.neighbors = [n for n in routerD.neighbors if n.router_id != 'E']
    rounds = 5

    for round in range(rounds):
        input(f"=== Press ENTER to simulate Round {round+1} after E is offline ===")
        network.simulate_round()
        network.display_all_tables()


if __name__ == "__main__":
    main()