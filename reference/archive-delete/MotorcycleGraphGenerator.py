import numpy as np


class Motorcycle:
    def __init__(self, motorcycle_id, start_vertex_id, initial_edge_id, mesh):
        self.id = motorcycle_id
        self.current_vertex = start_vertex_id
        self.active = True
        self.path = [start_vertex_id]

        # Determine the initial direction vector based on the mesh geometry
        v_start = mesh.vertices[start_vertex_id]
        v_next = mesh.vertices[mesh.edges[initial_edge_id][1]]
        self.direction = (v_next - v_start) / np.linalg.norm(v_next - v_start)
        self.next_edge = initial_edge_id

    def step(self, mesh, global_tracks):
        if not self.active:
            return

        # Move to the destination vertex of the current active edge
        next_vertex = mesh.edges[self.next_edge][1]

        # CRASH CONDITION 1: Has this vertex already been crossed by another motorcycle?
        if next_vertex in global_tracks and global_tracks[next_vertex] != self.id:
            self.active = False
            self.path.append(next_vertex)
            print(f"💥 Motorcycle {self.id} crashed into a pre-existing track at Vertex {next_vertex}")
            return

        # Record the track position
        self.path.append(next_vertex)
        global_tracks[next_vertex] = self.id
        self.current_vertex = next_vertex

        # Determine the next edge heading in the same direction vector
        outgoing_edges = mesh.vertex_adjacency[next_vertex]
        if not outgoing_edges:
            self.active = False  # Reached a boundary wall
            print(f"🛑 Motorcycle {self.id} reached a boundary wall at Vertex {next_vertex}")
            return

        best_edge = None
        max_alignment = -1.0

        for edge_id in outgoing_edges:
            v_a = mesh.vertices[mesh.edges[edge_id][0]]
            v_b = mesh.vertices[mesh.edges[edge_id][1]]
            edge_vec = (v_b - v_a) / (np.linalg.norm(v_b - v_a) + 1e-9)

            alignment = np.dot(self.direction, edge_vec)
            if alignment > max_alignment:
                max_alignment = alignment
                best_edge = edge_id

        # CRASH CONDITION 2: Structural divergence (cannot continue straight line path)
        if max_alignment < 0.707:  # Angle tolerance limit (~45 degrees)
            self.active = False
            print(f"🛑 Motorcycle {self.id} halted due to surface curvature limits at Vertex {next_vertex}")
        else:
            self.next_edge = best_edge


class DiscreteMesh:
    """Represents a simplified quad geometric topology structure."""

    def __init__(self, vertices, edges):
        self.vertices = np.array(vertices)  # Shape: (N, 2)
        self.edges = edges  # List of tuples: (vertex_start, vertex_end)
        self.vertex_adjacency = {i: [] for i in range(len(vertices))}

        # Populate adjacency maps
        for edge_idx, (start, end) in enumerate(edges):
            self.vertex_adjacency[start].append(edge_idx)

    def find_extraordinary_vertices(self):
        """Identifies initialization seeds where valence != 4."""
        seeds = []
        for vertex_id, connected_edges in self.vertex_adjacency.items():
            if len(connected_edges) != 4 and len(connected_edges) > 0:
                seeds.append(vertex_id)
        return seeds


# --- Simulation Runner Execution Pipeline ---
def execute_motorcycle_partition(mesh):
    extraordinary_seeds = mesh.find_extraordinary_vertices()
    print(f"Found {len(extraordinary_seeds)} extraordinary vertices to use as seeds: {extraordinary_seeds}")

    motorcycles = []
    global_tracks = {}  # Maps Vertex IDs to the Motorcycle ID that claimed it
    motorcycle_counter = 0

    # Spawn motorcycles out from each irregular seed in all available directions
    for seed in extraordinary_seeds:
        for outbound_edge_id in mesh.vertex_adjacency[seed]:
            moto = Motorcycle(motorcycle_counter, seed, outbound_edge_id, mesh)
            motorcycles.append(moto)
            global_tracks[seed] = motorcycle_counter
            motorcycle_counter += 1

    # Run the particle system until all tracks stop or collide
    iterations = 0
    while any(m.active for m in motorcycles) and iterations < 50:
        for moto in motorcycles:
            if moto.active:
                moto.step(mesh, global_tracks)
        iterations += 1

    print(f"\n--- Layout Generation Complete after {iterations} steps ---")
    partitions = {m.id: m.path for m in motorcycles}
    return partitions


# --- Mock Execution Context ---
# Construct a 2D mesh grid system representing a parameterized CAD face patch
mock_vertices = [
    [0.0, 0.0], [1.0, 0.0], [2.0, 0.0],  # 0, 1, 2
    [0.0, 1.0], [1.0, 1.0], [2.0, 1.0],  # 3, 4, 5 (Vertex 4 is valence 4)
    [0.0, 2.0], [1.0, 2.0], [2.0, 2.0]  # 6, 7, 8
]

# Directed edge connectivity tracks
mock_edges = [
    (0, 1), (1, 2), (3, 4), (4, 5), (6, 7), (7, 8),  # Horizontal paths
    (0, 3), (3, 6), (1, 4), (4, 7), (2, 5), (5, 8)  # Vertical paths
]

mesh_domain = DiscreteMesh(mock_vertices, mock_edges)
layout_tracks = execute_motorcycle_partition(mesh_domain)

for moto_id, trace_path in layout_tracks.items():
    print(f"Partition Line {moto_id}: Path Nodes Taken -> {trace_path}")
