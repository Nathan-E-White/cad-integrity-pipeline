import numpy as np

import numpy as np
from typing import List, Tuple, Dict, Any, Optional

from numpy import signedinteger
from numpy._typing import _32Bit, _64Bit


class NURBSEvaluator:
    """Vectorized mathematical utilities for B-Spline and NURBS evaluation."""

    @staticmethod
    def find_span_vectorized(n: int, p: int, u: np.ndarray, knot_vector: np.ndarray) -> signedinteger[_32Bit | _64Bit]:
        """
        Finds the knot spans for an array of parameter values u using binary search.
        Returns an array of indices 'i' such that knot_vector[i] <= u < knot_vector[i+1].
        """
        # Handle boundary condition u == knot_vector[n+1]
        eps = 1e-15
        u_clipped = np.clip(u, knot_vector[p], knot_vector[n + 1] - eps)
        return np.searchsorted(knot_vector, u_clipped, side='right') - 1

    @staticmethod
    def basis_functions_vectorized(p: int, u: np.ndarray, knot_vector: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """
        Computes all non-zero basis functions for an array of parameter values u.

        Returns:
            spans: Array of shape (M,) containing the knot span index for each u.
            N: Array of shape (M, p + 1) containing basis function weights.
        """
        n = len(knot_vector) - p - 2
        spans = NURBSEvaluator.find_span_vectorized(n, p, u, knot_vector)
        num_pts = len(u)

        N = np.zeros((num_pts, p + 1))
        N[:, 0] = 1.0

        left = np.zeros((num_pts, p + 1))
        right = np.zeros((num_pts, p + 1))

        for j in range(1, p + 1):
            left[:, j] = u - knot_vector[spans - j + 1]
            right[:, j] = knot_vector[spans + j] - u
            saved = np.zeros(num_pts)

            for r in range(j):
                temp = N[:, r] / (right[:, r + 1] + left[:, j - r])
                N[:, r] = saved + right[:, r + 1] * temp
                saved = left[:, j - r] * temp

            N[:, j] = saved

        return spans, N

    @staticmethod
    def evaluate_surface(
            degree_u: int, degree_v: int,
            knots_u: np.ndarray, knots_v: np.ndarray,
            control_points: np.ndarray,  # Shape: (Nu, Nv, 4) -> (x, y, z, w) homogeneous
            u_vec: np.ndarray, v_vec: np.ndarray
    ) -> np.ndarray:
        """
        Evaluates a tensor-product NURBS surface at a grid of parameters (u, v).
        Uses tensor transformations to completely avoid nested Python loops.

        Returns:
            points: Array of shape (len(u_vec), len(v_vec), 3) containing Cartesian coordinates.
        """
        # 1. Compute basis functions for both directions
        spans_u, N_u = NURBSEvaluator.basis_functions_vectorized(degree_u, u_vec, knots_u)
        spans_v, N_v = NURBSEvaluator.basis_functions_vectorized(degree_v, v_vec, knots_v)

        # 2. Extract active control point windows for each span via advanced slicing
        Nu_pts, Nv_pts = len(u_vec), len(v_vec)
        # Gather indexed control points of shape (Nu_pts, p_u+1, Nv_pts, p_v+1, 4)
        idx_u = (spans_u[:, None] - degree_u + np.arange(degree_u + 1)).astype(int)
        idx_v = (spans_v[:, None] - degree_v + np.arange(degree_v + 1)).astype(int)

        # Tensor-product slicing using NumPy advanced indexing
        cp_window = control_points[idx_u[:, :, None, None], idx_v[None, None, :, :]]

        # 3. Contract basis weights over control net using Einstein summation
        # N_u shape: (Nu_pts, p_u+1), N_v shape: (Nv_pts, p_v+1)
        # cp_window shape: (Nu_pts, p_u+1, Nv_pts, p_v+1, 4)
        homogeneous_surface = np.einsum('ui,vj,uivjd->uvd', N_u, N_v, cp_window)

        # 4. Dehomogenize back to Cartesian coordinates (x/w, y/w, z/w)
        points = homogeneous_surface[..., :3] / homogeneous_surface[..., 3:[None]]
        return points


class BRepWire:
    """Represents an ordered collection of boundary edges forming a closed loop on a surface."""

    def __init__(self, edge_indices: List[int], orientations: List[bool]):
        self.edge_indices = np.array(edge_indices, dtype=np.int32)
        self.orientations = np.array(orientations, dtype=bool)  # True = Forward, False = Reversed

    def validate_closure(self, edges: List['BRepEdge']) -> bool:
        """Verifies topological structural integrity (shared vertices form a closed chain)."""
        if len(self.edge_indices) == 0:
            return False

        current_vertex_idx = edges[self.edge_indices[0]].v2 if not self.orientations[0] else edges[
            self.edge_indices[0]].v1
        first_vertex_idx = edges[self.edge_indices[0]].v1 if not self.orientations[0] else edges[
            self.edge_indices[0]].v2

        for idx, ori in zip(self.edge_indices[1:], self.orientations[1:]):
            edge = edges[idx]
            start = edge.v2 if not ori else edge.v1
            end = edge.v1 if not ori else edge.v2
            if start != current_vertex_idx:
                return False
            current_vertex_idx = end

        return current_vertex_idx == first_vertex_idx


class BRepEdge:
    """Represents a topological edge bounded by two vertices and mapped to a 3D/2D curve geometric backing."""

    def __init__(self, vertex_start_idx: int, vertex_end_idx: int, curve_geometry_id: int):
        self.v1 = vertex_start_idx
        self.v2 = vertex_end_idx
        self.geometry_id = curve_geometry_id
        self.pcurves: Dict[int, int] = {}  # Maps Face ID -> 2D parametric curve ID (UV Space mapping)


class BRepFace:
    """Represents a topological bounded region of a geometric surface."""

    def __init__(self, surface_geometry_id: int, outer_wire_idx: int, inner_wire_indices: Optional[List[int]] = None):
        self.surface_id = surface_geometry_id
        self.outer_wire = outer_wire_idx
        self.inner_wires = inner_wire_indices if inner_wire_indices is not None else []


class BRepTopologyModel:
    """Top-level Boundary Representation (B-Rep) structural layout data container."""

    def __init__(self):
        self.vertices: List[np.ndarray] = []  # 3D points (x, y, z)
        self.edges: List[BRepEdge] = []
        self.wires: List[BRepWire] = []
        self.faces: List[BRepFace] = []

        # Geometric Backing Storage
        self.surfaces: Dict[int, Dict[str, Any]] = {}
        self.curves_3d: Dict[int, Dict[str, Any]] = {}
        self.curves_2d: Dict[int, Dict[str, Any]] = {}

    def add_nurbs_surface(self, surf_id: int, degree_u: int, degree_v: int,
                          knots_u: np.ndarray, knots_v: np.ndarray, control_points: np.ndarray) -> int:
        """Injects a parametric NURBS surface geometry asset into the registry."""
        self.surfaces[surf_id] = {
            'type': 'NURBS',
            'degree_u': degree_u,
            'degree_v': degree_v,
            'knots_u': knots_u,
            'knots_v': knots_v,
            'control_points': control_points  # Expected shape (Nu, Nv, 4)
        }
        return surf_id

    def extract_face_mesh(self, face_idx: int, sample_resolution: int = 20) -> np.ndarray:
        """Evaluates a physical 3D mesh grid for a given B-Rep face context."""
        face = self.faces[face_idx]
        geom = self.surfaces[face.surface_id]

        if geom['type'] == 'NURBS':
            u_space = np.linspace(geom['knots_u'][geom['degree_u']], geom['knots_u'][-geom['degree_u'] - 1],
                                  sample_resolution)
            v_space = np.linspace(geom['knots_v'][geom['degree_v']], geom['knots_v'][-geom['degree_v'] - 1],
                                  sample_resolution)

            return NURBSEvaluator.evaluate_surface(
                geom['degree_u'], geom['degree_v'],
                geom['knots_u'], geom['knots_v'],
                geom['control_points'], u_space, v_space
            )
        else:
            raise NotImplementedError("Only NURBS surface types are currently bound to the evaluation engine.")


import numpy as np
from typing import Tuple


class NURBSDerivativeEvaluator:
    """Vectorized analytical derivatives, tangents, and normals for NURBS surfaces."""

    @staticmethod
    def basis_derivatives_vectorized(p: int, u: np.ndarray, knot_vector: np.ndarray, max_deriv: int = 2) -> np.ndarray:
        """
        Computes non-zero basis functions and their derivatives up to max_deriv.

        Returns:
            ders: Array of shape (max_deriv + 1, len(u), p + 1)
                  where ders[k, i, j] is the k-th derivative of the j-th active
                  basis function at parameter u[i].
        """
        from .NURBSEvaluator import NURBSEvaluator  # Assuming previous class structural mapping
        n = len(knot_vector) - p - 2
        spans = NURBSEvaluator.find_span_vectorized(n, p, u, knot_vector)
        num_pts = len(u)

        # ders shape: (max_deriv + 1, num_pts, p + 1)
        ders = np.zeros((max_deriv + 1, num_pts, p + 1))

        # Local storage for triangular execution optimization scheme
        ndu = np.zeros((num_pts, p + 1, p + 1))
        ndu[:, 0, 0] = 1.0
        left = np.zeros((num_pts, p + 1))
        right = np.zeros((num_pts, p + 1))

        for j in range(1, p + 1):
            left[:, j] = u - knot_vector[spans - j + 1]
            right[:, j] = knot_vector[spans + j] - u
            saved = np.zeros(num_pts)
            for r in range(j):
                ndu[:, j, r] = right[:, r + 1] + left[:, j - r]
                temp = ndu[:, r, j - 1] / ndu[:, j, r]
                ndu[:, r, j] = saved + right[:, r + 1] * temp
                saved = left[:, j - r] * temp
            ndu[:, j, j] = saved

        # Load the basis values themselves into the 0-th derivative slot
        ders[0, :, :] = ndu[:, :, p]

        # Compute derivatives using the standard recurrence relation matrix layout
        a = np.zeros((num_pts, 2, p + 1))
        for r in range(p + 1):
            s1, s2 = 0, 1
            a[:, 0, 0] = 1.0
            for k in range(1, max_deriv + 1):
                d = np.zeros(num_pts)
                rk = r - k
                pk = p - k
                if r >= k:
                    a[:, s2, 0] = a[:, s1, 0] / ndu[:, pk + 1, rk]
                    d = a[:, s2, 0] * ndu[:, rk, pk]

                j1 = 1 if rk >= -1 else -rk
                j2 = k - 1 if r - 1 <= pk else p - r

                for j in range(j1, j2 + 1):
                    a[:, s2, j] = (a[:, s1, j] - a[:, s1, j - 1]) / ndu[:, pk + 1, rk + j]
                    d += a[:, s2, j] * ndu[:, rk + j, pk]

                if r <= pk:
                    a[:, s2, k] = -a[:, s1, k - 1] / ndu[:, pk + 1, r]
                    d += a[:, s2, k] * ndu[:, r, pk]
                ders[k, :, r] = d
                s1, s2 = s2, s1

        # Multiply by factors factorials: p! / (p-k)!
        r_factor = float(p)
        for k in range(1, max_deriv + 1):
            ders[k, :, :] *= r_factor
            r_factor *= (p - k)

        return spans, ders

    @staticmethod
    def evaluate_surface_derivatives(
            degree_u: int, degree_v: int,
            knots_u: np.ndarray, knots_v: np.ndarray,
            control_points: np.ndarray,  # (Nu, Nv, 4) -> Homogeneous (wx, wy, wz, w)
            u_vec: np.ndarray, v_vec: np.ndarray
    ) -> np.ndarray:
        """
        Computes analytical surface derivatives up to 2nd order via Einstein Summation.

        Returns:
            surf_ders: Array of shape (3, 3, len(u_vec), len(v_vec), 3)
                       where surf_ders[k, j] is the k-th u-derivative and j-th v-derivative.
                       E.g., surf_ders[1, 0] = S_u, surf_ders[0, 1] = S_v, surf_ders[2, 0] = S_uu
        """
        Nu_pts, Nv_pts = len(u_vec), len(v_vec)
        spans_u, ders_u = NURBSDerivativeEvaluator.basis_derivatives_vectorized(degree_u, u_vec, knots_u, max_deriv=2)
        spans_v, ders_v = NURBSDerivativeEvaluator.basis_derivatives_vectorized(degree_v, v_vec, knots_v, max_deriv=2)

        idx_u = (spans_u[:, None] - degree_u + np.arange(degree_u + 1)).astype(int)
        idx_v = (spans_v[:, None] - degree_v + np.arange(degree_v + 1)).astype(int)
        cp_window = control_points[idx_u[:, :, None, None], idx_v[None, None, :, :]]

        # Contract over the 3x3 derivative combinations using advanced vectorized einsum operations
        # Homogeneous components: shape (3, 3, Nu_pts, Nv_pts, 4)
        A = np.einsum('kui,lvh,uivhd->kluvd', ders_u, ders_v, cp_window)

        # Dehomogenize derivatives using quotient rule variants mapping to Cartesian coordinates
        surf_ders = np.zeros((3, 3, Nu_pts, Nv_pts, 3))

        w = A[0, 0, ..., 3, None]  # Shape (Nu_pts, Nv_pts, 1)
        w_u = A[1, 0, ..., 3, None]
        w_v = A[0, 1, ..., 3, None]
        w_uu = A[2, 0, ..., 3, None]
        w_vv = A[0, 2, ..., 3, None]
        w_uv = A[1, 1, ..., 3, None]

        S = A[0, 0, ..., :3] / w
        surf_ders[0, 0] = S

        # First-order geometric partial components (Tangents)
        surf_ders[1, 0] = (A[1, 0, ..., :3] - w_u * S) / w  # S_u
        surf_ders[0, 1] = (A[0, 1, ..., :3] - w_v * S) / w  # S_v

        # Second-order partial components
        Su = surf_ders[1, 0]
        Sv = surf_ders[0, 1]
        surf_ders[2, 0] = (A[2, 0, ..., :3] - 2.0 * w_u * Su - w_uu * S) / w  # S_uu
        surf_ders[0, 2] = (A[0, 2, ..., :3] - 2.0 * w_v * Sv - w_vv * S) / w  # S_vv
        surf_ders[1, 1] = (A[1, 1, ..., :3] - w_u * Sv - w_v * Su - w_uv * S) / w  # S_uv

        return surf_ders

    @staticmethod
    def compute_tangents_and_normals(surf_ders: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Extracts unit tangents and normalized surface normal fields from the derivative tensor.

        Arguments:
            surf_ders: Output array from evaluate_surface_derivatives.

        Returns:
            T_u: Unit tangent field in U direction (Nu, Nv, 3)
            T_v: Unit tangent field in V direction (Nu, Nv, 3)
            Normal: Surface unit normal vector field (Nu, Nv, 3)
        """
        S_u = surf_ders[1, 0]
        S_v = surf_ders[0, 1]

        # Cross product vectorization along the last spatial axis
        raw_normal = np.cross(S_u, S_v, axis=-1)
        norm_normal = np.linalg.norm(raw_normal, axis=-1, keepdims=True)

        # Handle zero-length normal threshold scaling gracefully via epsilon clipping
        eps = 1e-14
        norm_normal = np.where(norm_normal < eps, 1.0, norm_normal)

        Normal = raw_normal / norm_normal
        T_u = S_u / np.where(np.linalg.norm(S_u, axis=-1, keepdims=True) < eps, 1.0,
                             np.linalg.norm(S_u, axis=-1, keepdims=True))
        T_v = S_v / np.where(np.linalg.norm(S_v, axis=-1, keepdims=True) < eps, 1.0,
                             np.linalg.norm(S_v, axis=-1, keepdims=True))

        return T_u, T_v, Normal


import numpy as np
from typing import Dict


class NURBSCurvatureEvaluator:
    """Computes Fundamental Forms and differential geometric curvature invariants metrics."""

    @staticmethod
    def compute_surface_curvatures(surf_ders: np.ndarray) -> Dict[str, np.ndarray]:
        """
        Calculates differential geometry metric tensors and curvatures across a grid.

        Arguments:
            surf_ders: Output tensor from evaluate_surface_derivatives of shape (3, 3, Nu, Nv, 3).

        Returns:
            A dictionary containing vectorized NumPy grids for:
            - 'E', 'F', 'G': Coefficients of the First Fundamental Form (Metric Tensor)
            - 'L', 'M', 'N': Coefficients of the Second Fundamental Form
            - 'Gaussian': Gaussian Curvature (K)
            - 'Mean': Mean Curvature (H)
            - 'Principal_Max': Maximum Principal Curvature (kappa_1)
            - 'Principal_Min': Minimum Principal Curvature (kappa_2)
        """
        # 1. Unpack analytical derivatives from structural slots
        S_u = surf_ders[1, 0, ...]  # Shape: (Nu, Nv, 3)
        S_v = surf_ders[0, 1, ...]
        S_uu = surf_ders[2, 0, ...]
        S_vv = surf_ders[0, 2, ...]
        S_uv = surf_ders[1, 1, ...]

        # 2. Compute First Fundamental Form coefficients (Metric Tensor components)
        # E = S_u . S_u,  F = S_u . S_v,  G = S_v . S_v
        E = np.einsum('ijk,ijk->ij', S_u, S_u)
        F = np.einsum('ijk,ijk->ij', S_u, S_v)
        G = np.einsum('ijk,ijk->ij', S_v, S_v)

        # 3. Compute un-normalized surface normal field via cross product vectorization
        raw_normal = np.cross(S_u, S_v, axis=-1)
        norm_normal = np.linalg.norm(raw_normal, axis=-1)

        # Guard against parametric singularities (e.g., at degenerate poles)
        eps = 1e-14
        valid_mask = norm_normal > eps
        safe_norm = np.where(valid_mask, norm_normal, 1.0)

        # Unit normal field (Nu, Nv, 3)
        n = raw_normal / safe_norm[..., None]

        # 4. Compute Second Fundamental Form coefficients
        # L = S_uu . n,  M = S_uv . n,  N = S_vv . n
        L = np.einsum('ijk,ijk->ij', S_uu, n)
        M = np.einsum('ijk,ijk->ij', S_uv, n)
        N = np.einsum('ijk,ijk->ij', S_vv, n)

        # 5. Determinants of the metric configurations
        # eg_f2 is the determinant of the First Fundamental Form matrix component (g)
        eg_f2 = E * G - F ** 2
        safe_eg_f2 = np.where(eg_f2 > eps, eg_f2, 1.0)

        # 6. Calculate Curvatures via Weingarten Equations mapping invariants
        # Gaussian Curvature: K = (LN - M^2) / (EG - F^2)
        K = (L * N - M ** 2) / safe_eg_f2

        # Mean Curvature: H = (E*N - 2*F*M + G*L) / (2 * (EG - F^2))
        H = (E * N - 2.0 * F * M + G * L) / (2.0 * safe_eg_f2)

        # 7. Extract Principal Curvatures analytically from eigenvalues
        # kappa = H +/- sqrt(H^2 - K)
        discriminant = H ** 2 - K
        # Eliminate numerical noise underneath zero thresholds inside planar zones
        discriminant = np.clip(discriminant, 0.0, None)
        sqrt_disc = np.sqrt(discriminant)

        kappa_1 = H + sqrt_disc
        kappa_2 = H - sqrt_disc

        # Handle zero-mask override for singular geometries
        K = np.where(valid_mask, K, 0.0)
        H = np.where(valid_mask, H, 0.0)
        kappa_1 = np.where(valid_mask, kappa_1, 0.0)
        kappa_2 = np.where(valid_mask, kappa_2, 0.0)

        return {
            'E': E, 'F': F, 'G': G,
            'L': L, 'M': M, 'N': N,
            'Gaussian': K,
            'Mean': H,
            'Principal_Max': kappa_1,
            'Principal_Min': kappa_2
        }


import numpy as np
from typing import Dict, Tuple, List, Optional


class RANSACPrimitiveClassifier:
    """RANSAC shape detection pipeline leveraging analytical differential geometry invariants."""

    def __init__(self, spatial_tol: float = 1e-3, normal_tol_deg: float = 5.0, curvature_tol: float = 1e-2):
        self.spatial_tol = spatial_tol
        self.normal_tol_rad = np.radians(normal_tol_deg)
        self.curvature_tol = curvature_tol

    def classify_local_topology(self, curvatures: Dict[str, np.ndarray], planar_threshold: float = 1e-3) -> np.ndarray:
        """
        Performs an initial topological classification of every point on the surface grid.
        Returns an integer label array: 0=Flat, 1=Cylindrical, 2=Spherical/Saddle/Unknown
        """
        k1 = curvatures['Principal_Max']
        k2 = curvatures['Principal_Min']

        # Absolute curvature profiles
        abs_k1 = np.abs(k1)
        abs_k2 = np.abs(k2)

        is_planar = (abs_k1 < planar_threshold) & (abs_k2 < planar_threshold)
        # Cylindrical profile: One dominant principal curvature, one flat axis
        is_cylindrical = ~is_planar & (abs_k2 < planar_threshold)

        labels = np.zeros_like(k1, dtype=np.int32)
        labels[is_cylindrical] = 1
        labels[~is_planar & ~is_cylindrical] = 2
        return labels

    def fit_plane_ransac(self, points: np.ndarray, normals: np.ndarray,
                         max_iterations: int = 200) -> Tuple[np.ndarray, np.ndarray]:
        """
        Fits a plane (ax + by + cz + d = 0) targeting flat geometric primitives.
        Expects points and normals flattened to (N, 3).
        """
        num_pts = points.shape[0]
        if num_pts < 3:
            return np.zeros(4), np.zeros(0, dtype=bool)

        best_inliers = np.zeros(num_pts, dtype=bool)
        best_model = np.zeros(4)

        for _ in range(max_iterations):
            # 1. Random sample initialization
            idx = np.random.choice(num_pts, 3, replace=False)
            p_sample = points[idx]

            # Compute plane model coefficients
            v1 = p_sample[1] - p_sample[0]
            v2 = p_sample[2] - p_sample[0]
            n_fit = np.cross(v1, v2)
            norm_n = np.linalg.norm(n_fit)
            if norm_n < 1e-7:
                continue
            n_fit /= norm_n
            d_fit = -np.dot(n_fit, p_sample[0])

            # 2. Vectorized distance evaluation
            distances = np.abs(np.dot(points, n_fit) + d_fit)
            spatial_mask = distances < self.spatial_tol

            # 3. Normal consensus checking
            normal_angles = np.arccos(np.clip(np.abs(np.dot(normals, n_fit)), 0.0, 1.0))
            normal_mask = normal_angles < self.normal_tol_rad

            inliers = spatial_mask & normal_mask
            if np.sum(inliers) > np.sum(best_inliers):
                best_inliers = inliers
                best_model = np.array([n_fit[0], n_fit[1], n_fit[2], d_fit])

        return best_model, best_inliers

    def fit_cylinder_ransac(self, points: np.ndarray, normals: np.ndarray, target_curvature: float,
                            max_iterations: int = 500) -> Tuple[
        Optional[Tuple[np.ndarray, np.ndarray, float]], np.ndarray]:
        """
        Fits a cylindrical primitive (axis origin, axis direction, radius) leveraging
        curvature estimates to constrain random sampling configurations.
        """
        num_pts = points.shape[0]
        expected_radius = 1.0 / (target_curvature + 1e-12)

        if num_pts < 2:
            return None, np.zeros(0, dtype=bool)

        best_inliers = np.zeros(num_pts, dtype=bool)
        best_geometry = None

        for _ in range(max_iterations):
            # 1. Select two sample points
            idx = np.random.choice(num_pts, 2, replace=False)
            p1, p2 = points[idx[0]], points[idx[1]]
            n1, n2 = normals[idx[0]], normals[idx[1]]

            # Cylinder axis direction must be perpendicular to surface normals
            axis_dir = np.cross(n1, n2)
            norm_axis = np.linalg.norm(axis_dir)
            if norm_axis < 1e-5:
                # Fallback: cross product of normal and point delta
                axis_dir = np.cross(n1, p2 - p1)
                norm_axis = np.linalg.norm(axis_dir)
                if norm_axis < 1e-5:
                    continue
            axis_dir /= norm_axis

            # Approximate radius directly from sample geometry consensus
            # Project points onto plane perpendicular to axis
            proj_p1 = p1 - np.dot(p1, axis_dir) * axis_dir
            proj_p2 = p2 - np.dot(p2, axis_dir) * axis_dir

            # Simple intersection point of normal lines in 2D projection
            # For a cylinder, normal lines intersect exactly along the axis line
            mid_p = 0.5 * (proj_p1 + proj_p2)
            axis_origin = mid_p + 0.5 * (expected_radius * n1 + expected_radius * n2)

            # 2. Vectorized spatial metric verification
            # Distance from arbitrary point to axis line: ||(p - p0) x axis_dir||
            v_vec = points - axis_origin
            cross_prods = np.cross(v_vec, axis_dir)
            distances_to_axis = np.linalg.norm(cross_prods, axis=-1)
            spatial_mask = np.abs(distances_to_axis - expected_radius) < self.spatial_tol

            # 3. Normal consensus checking
            # Expected normal vector is the normalized projection vector from axis
            proj_v = v_vec - np.einsum('ij,j->i', v_vec, axis_dir)[:, None]
            norm_proj_v = np.linalg.norm(proj_v, axis=-1, keepdims=True)
            expected_normals = proj_v / (norm_proj_v + 1e-12)

            normal_dot = np.abs(np.einsum('ij,ij->i', normals, expected_normals))
            normal_mask = np.arccos(np.clip(normal_dot, 0.0, 1.0)) < self.normal_tol_rad

            inliers = spatial_mask & normal_mask
            if np.sum(inliers) > np.sum(best_inliers):
                best_inliers = inliers
                best_geometry = (axis_origin, axis_dir, expected_radius)

        return best_geometry, best_inliers

    def segment_primitives(self, points_grid: np.ndarray, normals_grid: np.ndarray,
                           curvatures: Dict[str, np.ndarray]) -> List[Dict[str, Any]]:
        """
        Segments and extracts primitive assets from an evaluated surface sheet topology.
        """
        # Flatten input matrices for linear processing
        pts_f = points_grid.reshape(-1, 3)
        n_f = normals_grid.reshape(-1, 3)
        topo_labels = self.classify_local_topology(curvatures).flatten()
        k1_f = curvatures['Principal_Max'].flatten()

        unassigned_indices = np.arange(pts_f.shape[0])
        extracted_primitives = []

        # Phase 1: Target Cylindrical Fillets
        cyl_indices = unassigned_indices[topo_labels[unassigned_indices] == 1]
        if len(cyl_indices) > 10:
            # Estimate consensus seed radius curvature to bypass sliding windows
            median_k1 = np.median(k1_f[cyl_indices])
            geom, inliers_mask = self.fit_cylinder_ransac(pts_f[cyl_indices], n_f[cyl_indices], median_k1)

            if geom is not None and np.sum(inliers_mask) > 5:
                global_inliers = cyl_indices[inliers_mask]
                extracted_primitives.append({
                    'type': 'cylinder_fillet',
                    'geometry': {'origin': geom[0], 'axis': geom[1], 'radius': geom[2]},
                    'point_indices': global_inliers
                })
                unassigned_indices = np.setdiff1d(unassigned_indices, global_inliers)

        # Phase 2: Target Planar Regions
        flat_indices = unassigned_indices[topo_labels[unassigned_indices] == 0]
        if len(flat_indices) > 3:
            model, inliers_mask = self.fit_plane_ransac(pts_f[flat_indices], n_f[flat_indices])
            if np.sum(inliers_mask) > 5:
                global_inliers = flat_indices[inliers_mask]
                extracted_primitives.append({
                    'type': 'plane',
                    'geometry': {'plane_equation': model},
                    'point_indices': global_inliers
                })

        return extracted_primitives


import numpy as np
from typing import List, Dict, Any, Tuple


class CADGeometryCardEngine:
    """Translates RANSAC segmented primitives into explicit order-of-operations CAD geometry cards."""

    def __init__(self, decimal_precision: int = 4):
        self.precision = decimal_precision

    def _fmt_vec(self, vec: np.ndarray) -> List[float]:
        """Truncates arrays to uniform precision profiles for downstream standard parsing."""
        return [float(np.round(x, self.precision)) for x in vec]

    def _fmt_val(self, val: float) -> float:
        return float(np.round(val, self.precision))

    def generate_geometry_card(self, extracted_primitives: List[Dict[str, Any]],
                               flattened_points_grid: np.ndarray) -> Dict[str, Any]:
        """
        Processes primitives, computes strict spatial bounding domains, and builds
        the sequential primitive definitions list.

        Arguments:
            extracted_primitives: Output list from RANSACPrimitiveClassifier segmentation.
            flattened_points_grid: Linear array shape (N, 3) used to locate edge limits.
        """
        cad_operations = []

        for op_id, prim in enumerate(extracted_primitives):
            prim_type = prim['type']
            pt_indices = prim['point_indices']
            subset_pts = flattened_points_grid[pt_indices]

            if prim_type == 'plane':
                # Model layout: ax + by + cz + d = 0
                eq = prim['geometry']['plane_equation']
                normal = eq[:3]
                d = eq[3]

                # Compute centroid bounding constraint
                centroid = np.mean(subset_pts, axis=0)

                op_card = {
                    "op_index": op_id,
                    "primitive": "PLANE",
                    "parameters": {
                        "normal": self._fmt_vec(normal),
                        "intercept": self._fmt_val(d),
                        "reference_centroid": self._fmt_vec(centroid)
                    }
                }
                cad_operations.append(op_card)

            elif prim_type == 'cylinder_fillet':
                origin = prim['geometry']['origin']
                axis = prim['geometry']['axis']
                radius = prim['geometry']['radius']

                # Project subset points to locate precise height/length bounding limits along axis vector
                # Projection mapping coordinate value: t = (P - Origin) . Axis
                vectors_to_pts = subset_pts - origin
                t_values = np.dot(vectors_to_pts, axis)
                t_min, t_max = np.min(t_values), np.max(t_values)

                # Calculate explicit bounding faces vertices locations
                cylinder_start = origin + t_min * axis
                cylinder_end = origin + t_max * axis
                height = t_max - t_min

                op_card = {
                    "op_index": op_id,
                    "primitive": "CYLINDER",
                    "parameters": {
                        "axis_origin": self._fmt_vec(cylinder_start),
                        "axis_direction": self._fmt_vec(axis),
                        "radius": self._fmt_val(radius),
                        "length": self._fmt_val(height),
                        "axis_end": self._fmt_vec(cylinder_end)
                    }
                }
                cad_operations.append(op_card)

        return {
            "format": "Analytical_CSG_Card_v1",
            "total_primitives": len(cad_operations),
            "operations": cad_operations
        }

    def export_to_text_macro(self, card_data: Dict[str, Any]) -> str:
        """
        Parses structured operation listings into standardized clean text blocks
        suitable for STEP file mapping wrappers or custom macro interpreters.
        """
        lines = [
            "/* ==================================================== */",
            f"/* CAD GEOMETRY SPECIFICATION CARD - PRIMITIVES COUNT: {card_data['total_primitives']} */",
            "/* ==================================================== */\n"
        ]

        for op in card_data["operations"]:
            idx = op["op_index"]
            prim = op["primitive"]
            params = op["parameters"]

            if prim == "PLANE":
                n = params["normal"]
                lines.append(
                    f"OP[{idx:03d}] DEFINE PLANE;\n"
                    f"    NORMAL    = [{n[0]:.4f}, {n[1]:.4f}, {n[2]:.4f}];\n"
                    f"    INTERCEPT = {params['intercept']:.4f};\n"
                    f"    CENTROID  = [{params['reference_centroid'][0]:.4f}, {params['reference_centroid'][1]:.4f}, {params['reference_centroid'][2]:.4f}];\n"
                    f"END_OP;\n"
                )
            elif prim == "CYLINDER":
                orig = params["axis_origin"]
                wdir = params["axis_direction"]
                lines.append(
                    f"OP[{idx:03d}] DEFINE CYLINDER;\n"
                    f"    ORIGIN    = [{orig[0]:.4f}, {orig[1]:.4f}, {orig[2]:.4f}];\n"
                    f"    AXIS_DIR  = [{wdir[0]:.4f}, {wdir[1]:.4f}, {wdir[2]:.4f}];\n"
                    f"    RADIUS    = {params['radius']:.4f};\n"
                    f"    LENGTH    = {params['length']:.4f};\n"
                    f"END_OP;\n"
                )

        return "\n".join(lines)


from typing import Dict, Any, List


class STEPGeometryExportEngine:
    """Translates CSG geometry card parameters into valid ISO 10303-21 STEP exchange instances."""

    def __init__(self, start_id: int = 100):
        self.current_id = start_id
        self.step_lines: List[str] = []

    def _next_id(self) -> str:
        tid = f"#{self.current_id}"
        self.current_id += 1
        return tid

    def _emit(self, statement: str) -> str:
        entity_id = self._next_id()
        self.step_lines.append(f"{entity_id}={statement};")
        return entity_id

    def generate_step_block(self, card_data: Dict[str, Any]) -> str:
        """
        Parses geometry card operation dictionaries and generates corresponding
        topology and geometry instances compliant with advanced B-Rep schemas.
        """
        self.step_lines = []
        face_ids = []

        # 1. Establish common structural entities (Global Coordinate System Reference)
        dir_z = self._emit("DIRECTION('Global Z Axis',(0.0,0.0,1.0))")
        dir_x = self._emit("DIRECTION('Global X Axis',(1.0,0.0,0.0))")
        origin_0 = self._emit("CARTESIAN_POINT('Global Origin',(0.0,0.0,0.0))")
        global_cs = self._emit(f"AXIS2_PLACEMENT_3D('Global CS',{origin_0},{dir_z},{dir_x})")

        # 2. Iterate and expand primitive definitions into explicit STEP structures
        for op in card_data["operations"]:
            prim = op["primitive"]
            params = op["parameters"]
            idx = op["op_index"]

            if prim == "PLANE":
                normal = tuple(params["normal"])
                centroid = tuple(params["reference_centroid"])

                # Geometry Backing Layer
                pt_loc = self._emit(f"CARTESIAN_POINT('Plane Centroid',{centroid})")
                dir_norm = self._emit(f"DIRECTION('Plane Normal',{normal})")

                # Determine dummy orthogonal reference vector for plane coordinate system orientation
                ref_vec = (0.0, 0.0, 1.0) if abs(normal[2]) < 0.9 else (1.0, 0.0, 0.0)
                dir_ref = self._emit(f"DIRECTION('Plane Ref Vector',{ref_vec})")

                axis2_placement = self._emit(f"AXIS2_PLACEMENT_3D('',{pt_loc},{dir_norm},{dir_ref})")
                geom_surface = self._emit(f"PLANE('Plane Surface_{idx}',{axis2_placement})")

                # Topological Binding Layer
                # Note: True B-Rep requires explicit face bounds (loops).
                # For basic primitive visualization tracking, we initialize an open/unbounded face framework.
                adv_face = self._emit(f"ADVANCED_FACE('Face_Plane_{idx}',(),{geom_surface},.T.)")
                face_ids.append(adv_face)

            elif prim == "CYLINDER":
                axis_orig = tuple(params["axis_origin"])
                axis_dir = tuple(params["axis_direction"])
                radius = float(params["radius"])

                # Geometry Backing Layer
                pt_loc = self._emit(f"CARTESIAN_POINT('Cylinder Axis Origin',{axis_orig})")
                dir_axis = self._emit(f"DIRECTION('Cylinder Axis Direction',{axis_dir})")

                # Find an orthogonal reference vector for local coordinate attachment
                ref_vec = (0.0, 0.0, 1.0) if abs(axis_dir[2]) < 0.9 else (1.0, 0.0, 0.0)
                cross_ref = np.cross(axis_dir, ref_vec)
                ortho_ref = tuple(cross_ref / np.linalg.norm(cross_ref)) if np.linalg.norm(cross_ref) > 1e-5 else (1.0,
                                                                                                                   0.0,
                                                                                                                   0.0)
                dir_ref = self._emit(f"DIRECTION('Cylinder Ref Vector',{ortho_ref})")

                axis2_placement = self._emit(f"AXIS2_PLACEMENT_3D('',{pt_loc},{dir_axis},{dir_ref})")
                geom_surface = self._emit(f"CYLINDRICAL_SURFACE('Cylinder Surface_{idx}',{axis2_placement},{radius})")

                # Topological Binding Layer
                adv_face = self._emit(f"ADVANCED_FACE('Face_Cylinder_{idx}',(),{geom_surface},.T.)")
                face_ids.append(adv_face)

        # 3. Encapsulate individual primitive faces inside a Shell and Closed Solid
        faces_tuple = f"({','.join(face_ids)})"
        open_shell = self._emit(f"OPEN_SHELL('Retrieved Primitive Shell',{faces_tuple})")
        shell_based_surface = self._emit(f"SHELL_BASED_SURFACE_MODEL('Primitive Geometric Fragment',({open_shell}))")

        # Build diagnostic string output block
        step_output = (
                "/* ISO-10303-21 STEP DATA FRAGMENT GENERATED BY CAD ENGINE */\n"
                "DATA;\n" +
                "\n".join(self.step_lines) +
                "\nENDSEC;"
        )
        return step_output


def compute_discrete_medial_nodes(boundary_samples, internal_candidates, tolerance=1e-3):
    """
    Identifies medial axis nodes and flags structural CAD slivers
    using vectorized distance field checks.

    boundary_samples: NumPy array of shape (N, 3) representing sampled points on B-Rep faces.
    internal_candidates: NumPy array of shape (M, 3) checking internal volume points.
    """
    medial_nodes = []
    sliver_nodes = []

    # Vectorized computation of the distance matrix: Shape (M, N)
    # Computes Euclidean distance between every internal point and every boundary point
    diff = internal_candidates[:, np.newaxis, :] - boundary_samples[np.newaxis, :, :]
    distances = np.linalg.norm(diff, axis=2)

    for i, dist_profile in enumerate(distances):
        # Find the minimum distance to the boundary (the radius of the inscribed sphere)
        r_min = np.min(dist_profile)

        # Count how many boundary points share this minimum distance (within a tight epsilon)
        # A true medial axis point must be equidistant to at least 2 distinct boundary zones
        equidistant_indices = np.where(np.abs(dist_profile - r_min) < 1e-4)[0]

        # Check if the boundary hits are spatially distinct (not just adjacent samples)
        if len(equidistant_indices) >= 2:
            hits = boundary_samples[equidistant_indices]
            spatial_spread = np.max(np.linalg.norm(hits[:, np.newaxis, :] - hits[np.newaxis, :, :], axis=2))

            if spatial_spread > r_min * 0.5:  # Confirms distinct boundary touches
                node_data = {
                    "coord": internal_candidates[i],
                    "radius": r_min
                }

                # CRITICAL CAD CLEANUP CHECK: Is this an un-meshable sliver zone?
                if r_min < tolerance:
                    sliver_nodes.append(node_data)
                else:
                    medial_nodes.append(node_data)

    print(f"--- Medial Axis Evaluation Complete ---")
    print(f"Found {len(medial_nodes)} valid topological skeletal nodes.")
    print(f"Flagged {len(sliver_nodes)} micro-radius sliver zones for automated deletion.")
    return medial_nodes, sliver_nodes


# --- Mock Verification Context ---
# Simulate a narrow 3D channel with a localized pinching error (sliver zone)
mock_boundary = np.array([
    [0.0, 0.0, 0.0], [2.0, 0.0, 0.0],  # Wall A
    [0.0, 0.0005, 1.0], [2.0, 0.0005, 1.0]  # Wall B (extremely close to Wall A!)
])
mock_internal = np.array([
    [1.0, 0.00025, 0.5]
])

medial, slivers = compute_discrete_medial_nodes(mock_boundary, mock_internal, tolerance=1e-2)

import numpy as np


class SkeletalGraph:
    def __init__(self, node_coords, node_radii, boundary_contacts, adjacency_list):
        """
        node_coords: (M, 3) matrix of medial axis node positions.
        node_radii: (M,) vector containing the radius of the maximal inscribed sphere.
        boundary_contacts: List of tuples/arrays containing the (2, 3) contact points on the boundary.
        adjacency_list: Dict mapping node_idx -> list of connected node_idx.
        """
        self.coords = np.array(node_coords)
        self.radii = np.array(node_radii)
        self.boundary_contacts = boundary_contacts
        self.adj = adjacency_list
        self.num_nodes = len(node_coords)

    def compute_significance_scores(self):
        """
        Computes the structural significance (object angle measure) for each skeletal node.
        """
        scores = np.zeros(self.num_nodes)
        for i in range(self.num_nodes):
            r = self.radii[i]
            if r <= 1e-9:
                scores[i] = 0.0
                continue

            # Extract the two primary boundary contact points for this medial sphere
            y1, y2 = np.array(self.boundary_contacts[i][0]), np.array(self.boundary_contacts[i][1])
            boundary_dist = np.linalg.norm(y1 - y2)

            # Object angle ratio calculation: safely clipped to avoid numerical arcsin/arccos errors
            ratio = boundary_dist / (2.0 * r)
            ratio = np.clip(ratio, 0.0, 1.0)

            # The angle theta represents structural prominence.
            # We use the ratio directly: closer to 1 means highly structural, closer to 0 means noise.
            scores[i] = ratio

        return scores

    def prune_graph(self, significance_threshold=0.35):
        """
        Iteratively prunes insignificant leaf nodes from the skeletal graph topology.
        Leaves are nodes with degree == 1.
        """
        scores = self.compute_significance_scores()
        active_nodes = set(range(self.num_nodes))

        # Deep copy the adjacency mapping for dynamic mutation
        current_adj = {k: list(v) for k, v in self.adj.items()}

        pruning_occurred = True
        while pruning_occurred:
            pruning_occurred = False
            leaves_to_remove = []

            for node in active_nodes:
                # Identify topological leaves (dangling endpoints)
                if len(current_adj[node]) == 1:
                    # Check if its geometric significance drops below our boundary criteria
                    if scores[node] < significance_threshold:
                        leaves_to_remove.append(node)

            # Safely isolate and sever connections from the graph topology
            if leaves_to_remove:
                pruning_occurred = True
                for node in leaves_to_remove:
                    # Disconnect from neighbor
                    neighbor = current_adj[node][0]
                    current_adj[neighbor].remove(node)
                    current_adj[node] = []
                    active_nodes.remove(node)

        print(f"--- Topological Pruning Complete ---")
        print(f"Original Skeletal Nodes: {self.num_nodes} | Retained Core Nodes: {len(active_nodes)}")
        return active_nodes, current_adj


# --- Verification Simulation Context ---
# Simulate a medial skeleton branch with 3 core nodes and 2 noise-induced leaves
mock_coords = [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [2.0, 0.0, 0.0], [1.0, 0.2, 0.0], [2.0, 0.1, 0.0]]
mock_radii = [1.0, 1.0, 1.0, 0.9, 0.8]

# Boundary contacts:
# Core nodes (0, 1, 2) touch opposing walls far apart (distance ~ 2.0)
# Noise nodes (3, 4) touch tiny ripples on the same wall (distance ~ 0.05)
mock_contacts = [
    ([0.0, -1.0, 0.0], [0.0, 1.0, 0.0]),  # Node 0 (Core)
    ([1.0, -1.0, 0.0], [1.0, 1.0, 0.0]),  # Node 1 (Core)
    ([2.0, -1.0, 0.0], [2.0, 1.0, 0.0]),  # Node 2 (Core)
    ([1.0, 0.90, 0.0], [1.05, 0.92, 0.0]),  # Node 3 (Noise Leaf)
    ([2.0, 0.85, 0.0], [2.02, 0.87, 0.0])  # Node 4 (Noise Leaf)
]

# Graph Adjacency Dictionary
mock_adj = {}

skeleton = SkeletalGraph(mock_coords, mock_radii, mock_contacts, mock_adj)
core_nodes, clean_topology = skeleton.prune_graph(significance_threshold=0.35)

print(f"Surviving Core Node IDs: {list(core_nodes)}")
