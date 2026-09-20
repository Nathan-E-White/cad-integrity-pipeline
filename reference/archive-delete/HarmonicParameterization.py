import numpy as np
import scipy.sparse as sparse
import scipy.sparse.linalg as splinalg


def compute_harmonic_parameterization(vertices, faces, boundary_indices):
    """
    Computes a 2D harmonic mapping for a 3D surface patch to isolate and
    repair topological distortions.

    vertices: NumPy array of shape (V, 3)
    faces: NumPy array of shape (F, 3)
    boundary_indices: List of vertex indices forming the outer loop of the face.
    """
    num_vertices = len(vertices)

    # 1. Initialize a sparse adjacency-based Laplace matrix
    # Using uniform weights for simplicity in representation (Tutte's Embedding)
    L = sparse.lil_matrix((num_vertices, num_vertices))

    for face in faces:
        for i in range(3):
            v_curr = face[i]
            v_next = face[(i + 1) % 3]

            # Populate graph laplacian off-diagonals
            L[v_curr, v_next] = -1.0
            L[v_next, v_curr] = -1.0

    # Compute diagonal elements (sum of connected rows)
    for i in range(num_vertices):
        L[i, i] = -np.sum(L[i, :])

    # 2. Setup Boundary Conditions (Dirichlet)
    # Map the boundary vertices uniformly to a 2D unit circle
    uv_coords = np.zeros((num_vertices, 2))
    num_boundary_pts = len(boundary_indices)

    for idx, b_v in enumerate(boundary_indices):
        angle = 2.0 * np.pi * idx / num_boundary_pts
        uv_coords[b_v, 0] = np.cos(angle)
        uv_coords[b_v, 1] = np.sin(angle)

        # Modify Laplacian row to isolate boundary condition equations
        L[b_v, :] = 0.0
        L[b_v, b_v] = 1.0

    # 3. Solve the Linear System independently for U and V parameters
    L_csr = L.tocsr()

    # Setup Right Hand Side (RHS) targets
    rhs_u = np.zeros(num_vertices)
    rhs_v = np.zeros(num_vertices)
    rhs_u[boundary_indices] = uv_coords[boundary_indices, 0]
    rhs_v[boundary_indices] = uv_coords[boundary_indices, 1]

    # Execute high-performance sparse linear solver
    u_solution = splinalg.spsolve(L_csr, rhs_u)
    v_solution = splinalg.spsolve(L_csr, rhs_v)

    parameterized_mesh_2d = np.column_stack((u_solution, v_solution))

    print("--- Harmonic Parameterization Concluded ---")
    print(f"Mapped {num_vertices} spatial 3D nodes into a flat 2D parametric workspace.")
    return parameterized_mesh_2d


# --- Verification Simulation Context ---
# Simple mock open geometry setup (5 vertices forming a pyramid top shape)
mock_3d_vertices = np.array([
    [0.0, 0.0, 1.0],  # 0: Peak apex node
    [-1.0, -1.0, 0.0], [1.0, -1.0, 0.0], [1.0, 1.0, 0.0], [-1.0, 1.0, 0.0]  # 1, 2, 3, 4 Base outer edge
])
mock_faces = np.array([[0, 1, 2], [0, 2, 3], [0, 3, 4], [0, 4, 1]])
mock_boundary = [1, 2, 3, 4]

uv_layout = compute_harmonic_parameterization(mock_3d_vertices, mock_faces, mock_boundary)
print(f"Apex point 0 flattened 2D location vector: {uv_layout[0]}")
