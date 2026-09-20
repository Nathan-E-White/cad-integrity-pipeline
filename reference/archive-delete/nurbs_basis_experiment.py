"""Small validated Cox--de Boor basis experiment.

This preserves the useful scalar method from the old Numba demonstration while
removing import-time execution and the optional JIT dependency.  Production
surface evaluation, derivative handling, and singularity reporting remain in
the integrated NURBS implementations.
"""

from __future__ import annotations

import numpy as np


def find_knot_span(control_point_count: int, degree: int, parameter: float, knots: np.ndarray) -> int:
    """Return the active B-spline span, with the upper endpoint in the last span."""
    vector = np.asarray(knots, dtype=float)
    if degree < 0 or control_point_count <= degree or len(vector) != control_point_count + degree + 1:
        raise ValueError("knot-vector length and degree do not match control-point count")
    if np.any(np.diff(vector) < 0) or not vector[degree] <= parameter <= vector[control_point_count]:
        raise ValueError("parameter is outside the valid nondecreasing knot domain")
    if parameter == vector[control_point_count]:
        return control_point_count - 1
    return int(np.searchsorted(vector, parameter, side="right") - 1)


def cox_de_boor_basis(degree: int, parameter: float, knots: np.ndarray, span: int) -> np.ndarray:
    """Return the degree+1 non-zero basis values at a validated knot span.

    Repeated-knot zero denominators contribute zero.  This routine does not
    evaluate rational weights, derivatives, or a tensor-product surface.
    """
    vector = np.asarray(knots, dtype=float)
    if degree < 0 or not degree <= span < len(vector) - degree - 1:
        raise ValueError("degree or span is invalid")
    if np.any(np.diff(vector) < 0) or not vector[span] <= parameter <= vector[span + 1]:
        raise ValueError("parameter does not belong to the supplied nondecreasing knot span")
    values = np.zeros(degree + 1)
    left = np.zeros(degree + 1)
    right = np.zeros(degree + 1)
    values[0] = 1.0
    for order in range(1, degree + 1):
        left[order] = parameter - vector[span + 1 - order]
        right[order] = vector[span + order] - parameter
        saved = 0.0
        for index in range(order):
            denominator = right[index + 1] + left[order - index]
            contribution = 0.0 if denominator == 0.0 else values[index] / denominator
            values[index] = saved + right[index + 1] * contribution
            saved = left[order - index] * contribution
        values[order] = saved
    return values
