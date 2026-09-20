import numpy as np
import numba


@numba.njit(cache=True)
def find_knot_span(n, p, u, knot_vector):
    """
    Finds the active index 'k' in the knot vector where u_k <= u < u_{k+1}.
    n: Number of control points - 1
    p: Degree of the spline curve
    """
    # Handle the boundary condition at the exact end of the parameter range
    if u >= knot_vector[n + 1]:
        return n

    # Binary search for the active span
    low = p
    high = n + 1
    mid = (low + high) // 2

    while u < knot_vector[mid] or u >= knot_vector[mid + 1]:
        if u < knot_vector[mid]:
            high = mid
        else:
            low = mid
        mid = (low + high) // 2

    return mid


@numba.njit(cache=True)
def evaluate_cox_de_boor(u, p, knot_vector, k):
    """
    Dynamically computes the non-zero basis functions at parameter u
    using a memory-efficient 1D workspace representation of the triangle table.

    u: Parameter value to evaluate
    p: Target degree
    knot_vector: Array of knots
    k: Active knot span index from find_knot_span
    """
    # Allocate a dynamic workspace array for the current degree level
    N = np.zeros(p + 1)
    N[0] = 1.0  # Base case: Degree 0 is active on the span

    # Left and right temporary difference buffers to avoid redundant subtractions
    left = np.zeros(p + 1)
    right = np.zeros(p + 1)

    # Dynamically build the triangular matrix upward by degree
    for j in range(1, p + 1):
        left[j] = u - knot_vector[k + 1 - j]
        right[j] = knot_vector[k + j] - u
        saved = 0.0

        for r in range(j):
            # Compute denominators and check for the 0/0 boundary exception
            denominator = right[r + 1] + left[j - r]

            if denominator == 0.0:
                N[r] = 0.0
                saved = 0.0
            else:
                temp = N[r] / denominator
                N[r] = saved + right[r + 1] * temp
                saved = left[j - r] * temp

        N[j] = saved

    return N


# --- Verification Test Context ---
# Simple quadratic spline setup (p=2), 4 control points (n=3)
mock_knots = np.array([0.0, 0.0, 0.0, 0.5, 1.0, 1.0, 1.0])
u_eval = 0.35

# 1. Locate active span index
span_idx = find_knot_span(n=3, p=2, u=u_eval, knot_vector=mock_knots)

# 2. Compute non-zero basis vector values on the fly
basis_vals = evaluate_cox_de_boor(u=u_eval, p=2, knot_vector=mock_knots, k=span_idx)

print(f"Knot Span Location Index: {span_idx}")
print(f"Non-zero Cox-de Boor basis outputs at u={u_eval}: {basis_vals}")
