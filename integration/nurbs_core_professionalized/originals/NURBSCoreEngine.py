#!/usr/bin/env python3
"""
Automated CAD Translation, Feature Segmentation, and STEP Export Pipeline.
Author: Nathan White
License: MIT

Deploys vectorized analytical differential geometry invariants, RANSAC multi-constraint
pruning, and structured STEP (AP203/AP214) boundary representation string generation.
"""

import os
import sys
import numpy as np
from typing import Dict, Any, List, Tuple, Optional


# ==============================================================================
# 1. VECTORIZED NURBS & DIFFERENTIAL GEOMETRY PIPELINE
# ==============================================================================


class NURBSCoreEngine:
    """Vectorized mathematical utilities for NURBS evaluation and derivative calculations."""

    @staticmethod
    def find_span_vectorized(
        n: int, p: int, u: np.ndarray, knot_vector: np.ndarray
    ) -> np.ndarray:
        eps = 1e-15
        u_clipped = np.clip(u, knot_vector[p], knot_vector[n + 1] - eps)
        return np.searchsorted(knot_vector, u_clipped, side='right') - 1

    @staticmethod
    def basis_derivatives_vectorized(
        p: int,
        u: np.ndarray,
        knot_vector: np.ndarray,
        max_deriv: int = 2,
    ) -> Tuple[np.ndarray, np.ndarray]:
        n = len(knot_vector) - p - 2
        spans = NURBSCoreEngine.find_span_vectorized(n, p, u, knot_vector)
        num_pts = len(u)

        ders = np.zeros((max_deriv + 1, num_pts, p + 1))
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

        ders[0, :, :] = ndu[:, :, p]
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

        r_factor = float(p)
        for k in range(1, max_deriv + 1):
            ders[k, :, :] *= r_factor
            r_factor *= (p - k)

        return spans, ders

    @staticmethod
    def evaluate_surface_geometry(
        degree_u: int,
        degree_v: int,
        knots_u: np.ndarray,
        knots_v: np.ndarray,
        control_points: np.ndarray,
        u_vec: np.ndarray,
        v_vec: np.ndarray,
    ) -> Tuple[np.ndarray, np.ndarray, Dict[str, np.ndarray]]:
        """Computes analytical Cartesian surface coordinates, normals, and metric curvatures."""
        Nu_pts, Nv_pts = len(u_vec), len(v_vec)
        spans_u, ders_u = NURBSCoreEngine.basis_derivatives_vectorized(
            degree_u, u_vec, knots_u, max_deriv=2
        )
        spans_v, ders_v = NURBSCoreEngine.basis_derivatives_vectorized(
            degree_v, v_vec, knots_v, max_deriv=2
        )

        idx_u = (spans_u[:, None] - degree_u + np.arange(degree_u + 1)).astype(int)
        idx_v = (spans_v[:, None] - degree_v + np.arange(degree_v + 1)).astype(int)
        cp_window = control_points[idx_u[:, :, None, None], idx_v[None, None, :, :]]

        A = np.einsum('kui,lvh,uivhd->kluvd', ders_u, ders_v, cp_window)

        w = A[0, 0, ..., 3, None]
        w_u = A[1, 0, ..., 3, None]
        w_v = A[0, 1, ..., 3, None]
        w_uu = A[2, 0, ..., 3, None]
        w_vv = A[0, 2, ..., 3, None]
        w_uv = A[1, 1, ..., 3, None]

        points = A[0, 0, ..., :3] / w

        S_u = (A[1, 0, ..., :3] - w_u * points) / w
        S_v = (A[0, 1, ..., :3] - w_v * points) / w
        S_uu = (A[2, 0, ..., :3] - 2.0 * w_u * S_u - w_uu * points) / w
        S_vv = (A[0, 2, ..., :3] - 2.0 * w_v * S_v - w_vv * points) / w
        S_uv = (A[1, 1, ..., :3] - w_u * S_v - w_v * S_u - w_uv * points) / w

        raw_normal = np.cross(S_u, S_v, axis=-1)
        norm_normal = np.linalg.norm(raw_normal, axis=-1)
        eps = 1e-14
        valid_mask = norm_normal > eps
        n = raw_normal / np.where(valid_mask, norm_normal, 1.0)[..., None]

        E = np.einsum('ijk,ijk->ij', S_u, S_u)
        F = np.einsum('ijk,ijk->ij', S_u, S_v)
        G = np.einsum('ijk,ijk->ij', S_v, S_v)
        L = np.einsum('ijk,ijk->ij', S_uu, n)
        M = np.einsum('ijk,ijk->ij', S_uv, n)
        N = np.einsum('ijk,ijk->ij', S_vv, n)

        eg_f2 = E * G - F ** 2
        safe_eg_f2 = np.where(eg_f2 > eps, eg_f2, 1.0)

        K = (L * N - M ** 2) / safe_eg_f2
        H = (E * N - 2.0 * F * M + G * L) / (2.0 * safe_eg_f2)

        disc = np.clip(H ** 2 - K, 0.0, None)
        sqrt_disc = np.sqrt(disc)
        kappa_1 = H + sqrt_disc
        kappa_2 = H - sqrt_disc

        curvatures = {
            'Principal_Max': np.where(valid_mask, kappa_1, 0.0),
            'Principal_Min': np.where(valid_mask, kappa_2, 0.0)
        }

        return points, n, curvatures


# ==============================================================================
# 2. RANSAC PRIMITIVE GEOMETRY SEGMENTER
# ==============================================================================


class RANSACPrimitiveClassifier:
    """Identifies and isolates planar and cylindrical structures from differential features."""

    def __init__(self, spatial_tol: float = 0.005, normal_tol_deg: float = 3.0):
        self.spatial_tol = spatial_tol
        self.normal_tol_rad = np.radians(normal_tol_deg)

    def classify_local_topology(
        self,
        curvatures: Dict[str, np.ndarray],
        planar_threshold: float = 0.05,
    ) -> np.ndarray:
        k1 = curvatures['Principal_Max']
        k2 = curvatures['Principal_Min']
        is_planar = (np.abs(k1) < planar_threshold) & (np.abs(k2) < planar_threshold)
        is_cylindrical = ~is_planar & (np.abs(k2) < planar_threshold)

        labels = np.zeros_like(k1, dtype=np.int32)
        labels[is_cylindrical] = 1
        labels[~is_planar & ~is_cylindrical] = 2
        return labels

    def fit_plane_ransac(
        self,
        points: np.ndarray,
        normals: np.ndarray,
        max_iter: int = 150,
    ) -> Tuple[np.ndarray, np.ndarray]:
        num_pts = points.shape[0]
        if num_pts < 3:
            return np.zeros(4), np.zeros(0, dtype=bool)

        best_inliers = np.zeros(num_pts, dtype=bool)
        best_model = np.zeros(4)

        for _ in range(max_iter):
            idx = np.random.choice(num_pts, 3, replace=False)
            p_sample = points[idx]
            v1 = p_sample[1] - p_sample[0]
            v2 = p_sample[2] - p_sample[0]
            n_fit = np.cross(v1, v2)
            norm = np.linalg.norm(n_fit)
            if norm < 1e-6:
                continue
            n_fit /= norm
            d_fit = -np.dot(n_fit, p_sample[0])

            distances = np.abs(np.dot(points, n_fit) + d_fit)
            spatial_mask = distances < self.spatial_tol
            normal_angles = np.arccos(np.clip(np.abs(np.dot(normals, n_fit)), 0.0, 1.0))
            inliers = spatial_mask & (normal_angles < self.normal_tol_rad)

            if np.sum(inliers) > np.sum(best_inliers):
                best_inliers = inliers
                best_model = np.array([n_fit[0], n_fit[1], n_fit[2], d_fit])

        return best_model, best_inliers

    def fit_cylinder_ransac(
        self,
        points: np.ndarray,
        normals: np.ndarray,
        target_curvature: float,
        max_iter: int = 300,
    ) -> Tuple[Optional[Tuple[np.ndarray, np.ndarray, float]], np.ndarray]:
        num_pts = points.shape[0]
        expected_radius = 1.0 / (abs(target_curvature) + 1e-12)
        if num_pts < 2:
            return None, np.zeros(0, dtype=bool)

        best_inliers = np.zeros(num_pts, dtype=bool)
        best_geometry = None

        for _ in range(max_iter):
            idx = np.random.choice(num_pts, 2, replace=False)
            p1, p2 = points[idx[0]], points[idx[1]]
            n1, n2 = normals[idx[0]], normals[idx[1]]

            axis_dir = np.cross(n1, n2)
            norm_axis = np.linalg.norm(axis_dir)
            if norm_axis < 1e-4:
                axis_dir = np.cross(n1, p2 - p1)
                norm_axis = np.linalg.norm(axis_dir)
                if norm_axis < 1e-4:
                    continue
            axis_dir /= norm_axis

            proj_p1 = p1 - np.dot(p1, axis_dir) * axis_dir
            axis_origin = proj_p1 - n1 * expected_radius

            v_vec = points - axis_origin
            cross_prods = np.cross(v_vec, axis_dir)
            distances_to_axis = np.linalg.norm(cross_prods, axis=-1)
            spatial_mask = np.abs(distances_to_axis - expected_radius) < self.spatial_tol

            proj_v = v_vec - np.dot(v_vec, axis_dir)[:, None]
            norm_proj = np.linalg.norm(proj_v, axis=-1, keepdims=True)
            expected_n = proj_v / (norm_proj + 1e-12)

            normal_dot = np.abs(np.einsum('ij,ij->i', normals, expected_n))
            normal_mask = np.arccos(np.clip(normal_dot, 0.0, 1.0)) < self.normal_tol_rad
            inliers = spatial_mask & normal_mask
            if np.sum(inliers) > np.sum(best_inliers):
                best_inliers = inliers
                best_geometry = (axis_origin, axis_dir, expected_radius)

        return best_geometry, best_inliers

    def segment_primitives(
        self,
        points: np.ndarray,
        normals: np.ndarray,
        curvatures: Dict[str, np.ndarray]
    ) -> List[Dict[str, Any]]:
        pts_f = points.reshape(-1, 3)
        n_f = normals.reshape(-1, 3)
        labels = self.classify_local_topology(curvatures).flatten()
        k1_f = curvatures['Principal_Max'].flatten()
        unassigned = np.arange(pts_f.shape[0])
        primitives = []

        # Segment Cylindrical Fillets
        cyl_idx = unassigned[labels[unassigned] == 1]
        if len(cyl_idx) > 10:
            median_k = np.median(k1_f[cyl_idx])
            geom, inliers = self.fit_cylinder_ransac(
                pts_f[cyl_idx], n_f[cyl_idx], median_k
            )
            if geom is not None and np.sum(inliers) > 10:
                global_inliers = cyl_idx[inliers]
                primitives.append({
                    'type': 'cylinder_fillet',
                    'geometry': {
                        'origin': geom[0],
                        'axis': geom[1],
                        'radius': geom[2]
                    },
                    'point_indices': global_inliers
                })
                unassigned = np.setdiff1d(unassigned, global_inliers)

        # Segment Planes
        flat_idx = unassigned[labels[unassigned] == 0]
        if len(flat_idx) > 3:
            eq, inliers = self.fit_plane_ransac(pts_f[flat_idx], n_f[flat_idx])
            if np.sum(inliers) > 5:
                global_inliers = flat_idx[inliers]
                primitives.append({
                    'type': 'plane',
                    'geometry': {'plane_equation': eq},
                    'point_indices': global_inliers
                })

        return primitives


# ==============================================================================
# 3. INTERMEDIATE SPECIFICATION CARD ENGINE
# ==============================================================================


class CADGeometryCardEngine:
    """Resolves computational boundaries and formats unified CSG operation descriptions."""

    def __init__(self, precision: int = 4):
        self.prec = precision

    def compute_cards(
        self,
        primitives: List[Dict[str, Any]],
        flattened_pts: np.ndarray
    ) -> Dict[str, Any]:
        operations = []
        for op_id, prim in enumerate(primitives):
            pt_idx = prim['point_indices']
            subset = flattened_pts[pt_idx]

            if prim['type'] == 'plane':
                eq = prim['geometry']['plane_equation']
                operations.append({
                    "op_index": op_id,
                    "primitive": "PLANE",
                    "parameters": {
                        "normal": [float(np.round(x, self.prec)) for x in eq[:3]],
                        "intercept": float(np.round(eq[3], self.prec)),
                        "reference_centroid": [
                            float(np.round(x, self.prec))
                            for x in np.mean(subset, axis=0)
                        ]
                    }
                })

            elif prim['type'] == 'cylinder_fillet':
                orig = prim['geometry']['origin']
                axis = prim['geometry']['axis']
                rad = prim['geometry']['radius']
                vecs = subset - orig
                t_vals = np.dot(vecs, axis)
                t_min, t_max = np.min(t_vals), np.max(t_vals)
                operations.append({
                    "op_index": op_id,
                    "primitive": "CYLINDER",
                    "parameters": {
                        "axis_origin": [
                            float(np.round(x, self.prec))
                            for x in (orig + t_min * axis)
                        ],
                        "axis_direction": [
                            float(np.round(x, self.prec)) for x in axis
                        ],
                        "radius": float(np.round(rad, self.prec)),
                        "length": float(np.round(t_max - t_min, self.prec))
                    }
                })

        return {"total_primitives": len(operations), "operations": operations}


# ==============================================================================
# 4. ISO-10303-21 STEP EXCHANGE FILE EXPORTER
# ==============================================================================


class STEPGeometryExportEngine:
    """Translates macro specifications into explicit topological exchange data instances."""

    def __init__(self, start_id: int = 10):
        self.curr_id = start_id
        self.lines: List[str] = []

    def _emit(self, syntax: str) -> str:
        tid = f"#{self.curr_id}"
        self.lines.append(f"{tid}={syntax};")
        self.curr_id += 1
        return tid

    def export(self, card_data: Dict[str, Any]) -> str:
        self.lines = []
        face_ids = []
        z_glob = self._emit("DIRECTION('Global Z Axis',(0.0,0.0,1.0))")
        x_glob = self._emit("DIRECTION('Global X Axis',(1.0,0.0,0.0))")
        orig_glob = self._emit("CARTESIAN_POINT('Global Origin',(0.0,0.0,0.0))")
        self._emit(
            f"AXIS2_PLACEMENT_3D('Global Reference Frame',{orig_glob},{z_glob},{x_glob})"
        )

        for op in card_data["operations"]:
            prim = op["primitive"]
            params = op["parameters"]
            idx = op["op_index"]

            if prim == "PLANE":
                n = tuple(params["normal"])
                c = tuple(params["reference_centroid"])
                pt = self._emit(f"CARTESIAN_POINT('Centroid{idx}',{c})")
                dn = self._emit(f"DIRECTION('Normal{idx}',{n})")
                ref = (
                    (0.0, 0.0, 1.0)
                    if abs(n[0]) > 0.9 or abs(n[1]) > 0.9
                    else (1.0, 0.0, 0.0)
                )
                dr = self._emit(f"DIRECTION('Ref{idx}',{ref})")
                placement = self._emit(f"AXIS2_PLACEMENT_3D('',{pt},{dn},{dr})")
                surf = self._emit(f"PLANE('Surface_Plane{idx}',{placement})")
                face_ids.append(
                    self._emit(f"ADVANCED_FACE('Face_Plane{idx}',(),{surf},.T.)")
                )

            elif prim == "CYLINDER":
                o = tuple(params["axis_origin"])
                d = tuple(params["axis_direction"])
                r = params["radius"]
                pt = self._emit(f"CARTESIAN_POINT('Origin{idx}',{o})")
                da = self._emit(f"DIRECTION('Axis{idx}',{d})")
                ref = (0.0, 1.0, 0.0) if abs(d[2]) > 0.9 else (0.0, 0.0, 1.0)
                dr = self._emit(f"DIRECTION('Ref{idx}',{ref})")
                placement = self._emit(f"AXIS2_PLACEMENT_3D('',{pt},{da},{dr})")
                surf = self._emit(
                    f"CYLINDRICAL_SURFACE('Surface_Cyl{idx}',{placement},{r})"
                )
                face_ids.append(
                    self._emit(f"ADVANCED_FACE('Face_Cylinder{idx}',(),{surf},.T.)")
                )

        shell = self._emit(f"OPEN_SHELL('Healed Extract Shell',({','.join(face_ids)}))")
        self._emit(
            f"SHELL_BASED_SURFACE_MODEL('Analytical Fragment Model',({shell}))"
        )
        return (
            "ISO-10303-21;\nHEADER;\n"
            "FILE_DESCRIPTION(('Extracted B-Rep Geometric Primitives'),'2;1');\n"
            "FILE_NAME('primitives.stp','2026-09-17T09:00:00',('Nathan White'),('Pipeline Engine'),"
            "'Processor v1.0','Open-Source Script Fragment','');\n"
            "FILE_SCHEMA(('CONFIG_CONTROL_DESIGN'));\nENDSEC;\nDATA;\n"
            + "\n".join(self.lines)
            + "\nENDSEC;\nEND-ISO-10303-21;\n"
        )


# ==============================================================================
# 5. EXECUTION PIPELINE HARNESS
# ==============================================================================


def main():
    print("[*] Generating structural geometry simulation grid...")
    # 1. Synthesize explicit analytical primitives: a plane transitioning into
    # a cylindrical fillet patch
    grid_res = 30
    u_vals = np.linspace(0.0, 1.0, grid_res)
    v_vals = np.linspace(0.0, 1.0, grid_res)

    # Target values: Cylinder with radius=5.0 tracking along Z-axis, flat surface adjacent
    points = np.zeros((grid_res, grid_res, 3))
    normals = np.zeros((grid_res, grid_res, 3))
    # Initialize mock curvature fields mapping directly to standard profiles
    k_max = np.zeros((grid_res, grid_res))
    k_min = np.zeros((grid_res, grid_res))

    for i, u in enumerate(u_vals):
        for j, v in enumerate(v_vals):
            if u < 0.5:
                # Planar segment configuration
                points[i, j] = [u * 10.0, v * 10.0, 0.0]
                normals[i, j] = [0.0, 0.0, 1.0]
                k_max[i, j] = 0.001
                k_min[i, j] = 0.000
            else:
                # Cylindrical Fillet patch configuration (Radius = 5.0 -> Curvature = 0.2)
                theta = (u - 0.5) * np.pi / 2.0
                points[i, j] = [
                    5.0 + 5.0 * np.sin(theta), v * 10.0, 5.0 - 5.0 * np.cos(theta)
                ]
                normals[i, j] = [-np.sin(theta), 0.0, np.cos(theta)]
                k_max[i, j] = 0.200
                k_min[i, j] = 0.000

    curvatures = {'Principal_Max': k_max, 'Principal_Min': k_min}
    flattened_pts = points.reshape(-1, 3)

    # 2. Segment spatial items via differential parameters
    print("[*] Launching multi-constraint RANSAC classifier engine...")
    segmenter = RANSACPrimitiveClassifier(spatial_tol=0.01, normal_tol_deg=2.0)
    primitives = segmenter.segment_primitives(points, normals, curvatures)
    print(
        f"    -> Successfully isolated {len(primitives)} structural primitive entities."
    )

    # 3. Compute intermediate specification tokens
    print("[*] Synthesizing structural CAD parameters metadata card...")
    card_engine = CADGeometryCardEngine(precision=4)
    geometry_card = card_engine.compute_cards(primitives, flattened_pts)

    # 4. Generate formal standardized file entries
    print("[*] Rendering macro parameters down to official STEP exchange text blocks...")
    step_engine = STEPGeometryExportEngine(start_id=100)
    step_file_content = step_engine.export(geometry_card)

    output_filename = "extracted_primitives.stp"
    with open(output_filename, "w") as f:
        f.write(step_file_content)
    print(
        f"[+] Diagnostic STEP pipeline complete! File saved successfully: '{output_filename}'\n"
    )

    # Output an overview summary text dump to stdout
    print("=== EXPORTED INSTANCES PREVIEW ===")
    for line in step_file_content.splitlines()[10:25]:
        print(line)
    print("==================================")


if __name__ == "__main__":
    main()
