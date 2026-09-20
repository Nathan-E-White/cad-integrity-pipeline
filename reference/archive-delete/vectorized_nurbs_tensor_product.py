import numpy as np


def simulate_nurbs_tensor_product():
    # 1. Define a 4x4 grid of 3D Control Points (The Control Net)
    # This grid controls a single tensor-product surface patch
    control_points = np.zeros((4, 4, 3))
    for i in range(4):
        for j in range(4):
            # Base grid layout in X and Y
            control_points[i, j, 0] = i * 1.0
            control_points[i, j, 1] = j * 1.0

    # Pull up the center control points in Z to create a smooth dome shape
    control_points[1, 1, 2] = 1.5
    control_points[1, 2, 2] = 2.0
    control_points[2, 1, 2] = 2.0
    control_points[2, 2, 2] = 1.5

    # 2. Simulate evaluating basis functions for a specific parametric location (u, v)
    # Let's say at this specific (u,v), the 1D B-spline blending values are:
    N_u = np.array([0.1, 0.4, 0.4, 0.1])  # Blending along rows (u-direction)
    M_v = np.array([0.05, 0.45, 0.45, 0.05])  # Blending along columns (v-direction)

    # 3. THE TENSOR PRODUCT STEP
    # Compute the 2D weight matrix by taking the outer product of the 1D basis vectors
    tensor_weights = np.outer(N_u, M_v)  # Resulting shape: (4, 4)

    # 4. Blending the Control Points
    # Multiply the tensor weights across the 3D control point grid
    surface_point = np.zeros(3)
    for i in range(4):
        for j in range(4):
            surface_point += tensor_weights[i, j] * control_points[i, j]

    print("--- Tensor Product Evaluation ---")
    print(f"Bidirectional Blending Matrix:\n{tensor_weights}\n")
    print(f"Resulting 3D Coordinate on NURBS Surface: {surface_point}")


simulate_nurbs_tensor_product()


def vectorized_nurbs_tensor_product():
    # Setup dimensions
    # 4x4 Control Net (I=4, J=4)
    # Evaluating a 50x50 resolution mesh on the surface (K=50, L=50)
    I, J = 4, 4
    K, L = 50, 50

    # 1. Initialize a 4x4 grid of 3D Control Points
    P = np.zeros((I, J, 3))
    x, y = np.meshgrid(np.linspace(0, 3, I), np.linspace(0, 3, J), indexing='ij')
    P[:, :, 0] = x
    P[:, :, 1] = y
    P[1:3, 1:3, 2] = 2.0  # Pull up center points to create a dome shape

    # Optional: Define weights for Rational B-Splines (NURBS)
    # If all weights = 1, it behaves as a standard B-Spline.
    W = np.ones((I, J))
    W[1, 1] = 2.5  # Heavy weight pulls the surface closer to this control point

    # 2. Simulate dense basis matrices (normally evaluated via Cox-de Boor algorithm)
    # N maps 50 parameter steps to 4 control rows. M maps 50 steps to 4 control columns.
    N = np.random.rand(K, I)
    M = np.random.rand(L, J)

    # Normalize rows so basis functions sum to 1 at any given point
    N /= N.sum(axis=1, keepdims=True)
    M /= M.sum(axis=1, keepdims=True)

    # 3. HIGH-PERFORMANCE VECTORIZED TENSOR PRODUCT
    # For regular B-Splines (Non-Rational), this is simply a matrix contraction:
    # We can use np.einsum or sequential matrix multiplication via np.tensordot

    # Inject weights for full NURBS logic: Apply weight scalar directly to 3D points
    P_weighted = P * W[:, :, np.newaxis]

    # Compute numerator: Shape (K, L, 3)
    # Matrix multiply N with P_weighted along Axis 0, then multiply result with M
    numerator = np.tensordot(N, P_weighted, axes=(1, 0))  # Shape (K, J, 3)
    numerator = np.einsum('kjc,lc->klc', numerator, M)  # Shape (K, L, 3)

    # Compute denominator (rational blending matrix scaling factor): Shape (K, L)
    denominator = N @ W @ M.T

    # Final surface calculation using broadcasting
    S = numerator / denominator[:, :, np.newaxis]

    print("--- NumPy Vectorized Evaluation Complete ---")
    print(f"Input Control Points Shape: {P.shape}")
    print(f"Evaluated 3D Surface Mesh Shape: {S.shape}")
    return S


surface_mesh = vectorized_nurbs_tensor_product()
