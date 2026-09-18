#!/usr/bin/env python3
"""
CAD Mesh and Noisy Point Cloud Adapter for RANSAC Primitive Extraction.
Author: Nathan White
License: MIT

Implements an open-source parsing interface to load binary/ASCII STL files, 
estimate differential surface attributes (normals and principal curvatures) 
from noisy unorganized point clouds using local covariance quadric fitting, 
and stream data into the downstream RANSAC primitive segmenter.
"""

import struct
import numpy as np
from typing import Dict, Any, List, Tuple, Optional

class STLReader:
    """Reads binary or ASCII STL files and extracts unorganized triangle facets."""
    
    @staticmethod
    def load_stl(file_path: str) -> Tuple[np.ndarray, np.ndarray]:
        """
        Parses an STL file and returns unique vertices and face connectivity.
        
        Returns:
            points: Array of shape (V, 3) containing unique 3D vertex positions.
            normals: Array of shape (F, 3) containing face normal vectors.
            faces: Array of shape (F, 3) containing indices referencing vertex points.
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Target STL file not found: {file_path}")
            
        with open(file_path, 'rb') as f:
            header = f.read(5)
            
        if header == b'solid':
            return STLReader._parse_ascii(file_path)
        else:
            return STLReader._parse_binary(file_path)

    @staticmethod
    def _parse_binary(file_path: str) -> Tuple[np.ndarray, np.ndarray]:
        with open(file_path, 'rb') as f:
            f.read(80) # Skip header bytes
            num_facets = struct.unpack('<I', f.read(4))[0]
            
            # Read all facet records: 3 floats (normal) + 9 floats (3 vertices) + 2 bytes (attr) = 50 bytes
            data = f.read(num_facets * 50)
            
        raw_data = np.frombuffer(data, dtype=np.float32).reshape(num_facets, 12 + 0.5) # Hack for the 2 attribute bytes
        # Clean unpacking mapping float boundary data lines
        normals = raw_data[:, 0:3].astype(np.float64)
        v_all = raw_data[:, 3:12].reshape(-1, 3).astype(np.float64)
        
        # Consolidate duplicate vertex allocations using unique row identifiers
        points, inverse_indices = np.unique(v_all, axis=0, return_inverse=True)
        faces = inverse_indices.reshape(num_facets, 3)
        
        return points, normals, faces

    @staticmethod
    def _parse_ascii(file_path: str) -> Tuple[np.ndarray, np.ndarray]:
        vertices_list = []
        normals_list = []
        
        with open(file_path, 'r') as f:
            current_normal = [0.0, 0.0, 0.0]
            for line in f:
                tokens = line.strip().split()
                if not tokens:
                    continue
                if tokens[0] == 'facet' and tokens[1] == 'normal':
                    current_normal = [float(x) for x in tokens[2:5]]
                elif tokens[0] == 'vertex':
                    vertices_list.append([float(x) for x in tokens[1:4]])
                    normals_list.append(current_normal) # Per-vertex naive mapping allocation
                    
        v_all = np.array(vertices_list, dtype=np.float64)
        points, inverse_indices = np.unique(v_all, axis=0, return_inverse=True)
        faces = inverse_indices.reshape(-1, 3)
        
        # Re-estimate accurate face normals from true vertex loops
        v0 = points[faces[:, 0]]
        v1 = points[faces[:, 1]]
        v2 = points[faces[:, 2]]
        calculated_normals = np.cross(v1 - v0, v2 - v0)
        norms = np.linalg.norm(calculated_normals, axis=-1, keepdims=True)
        calculated_normals /= np.where(norms < 1e-12, 1.0, norms)
        
        return points, calculated_normals, faces


class PointCloudGeometryEstimator:
    """Estimates surface normals and principal curvatures from unorganized/noisy point clouds."""
    
    def __init__(self, k_neighbors: int = 15):
        self.k = k_neighbors

    def _build_naive_knn(self, points: np.ndarray) -> np.ndarray:
        """Vectorized brute-force calculation of nearest neighbor lookup arrays."""
        num_pts = len(points)
        # Compute full pair-wise distance matrices safely via matrix broadcasting
        dists = np.sum((points[:, None, :] - points[None, :, :])**2, axis=-1)
        # Sort spatial arrays and return top k indices matching local regions
        neighbors = np.argsort(dists, axis=-1)[:, :self.k]
        return neighbors

    def estimate_features(self, points: np.ndarray) -> Tuple[np.ndarray, Dict[str, np.ndarray]]:
        """
        Fits local quadric surfaces to compute smooth normals and analytical principal curvatures.
        
        Fits z = ax^2 + by^2 + cxy + dx + ey + f dynamically inside localized reference frames.
        """
        num_pts = len(points)
        estimated_normals = np.zeros_like(points)
        k_max = np.zeros(num_pts)
        k_min = np.zeros(num_pts)
        
        print(f"[*] Analyzing local geometric covariance networks (k={self.k})...")
        neighbors_matrix = self._build_naive_knn(points)
        
        for i in range(num_pts):
            local_indices = neighbors_matrix[i]
            local_pts = points[local_indices]
            
            # 1. Establish principal plane coordinates using local PCA (SVD decomposition)
            centroid = np.mean(local_pts, axis=0)
            centered_pts = local_pts - centroid
            _, _, vh = np.linalg.svd(centered_pts, full_matrices=False)
            
            # Third eigenvector corresponds to the local surface normal indicator coordinate
            z_axis = vh[2, :]
            x_axis = vh[0, :]
            y_axis = np.cross(z_axis, x_axis)
            
            # Project neighboring points into the local coordinate framework (U, V, W)
            u = np.dot(centered_pts, x_axis)
            v = np.dot(centered_pts, y_axis)
            w = np.dot(centered_pts, z_axis)
            
            # 2. Setup linear regression equations matrix for local paraboloid model fitting
            # w = a*u^2 + b*v^2 + c*u*v + d*u + e*v + f
            M = np.column_stack([u**2, v**2, u*v, u, v, np.ones_like(u)])
            
            try:
                # Solve using least-squares mapping criteria
                coeffs, _, _, _ = np.linalg.lstsq(M, w, rcond=None)
                a, b, c, d, e, _ = coeffs
                
                # 3. Derive Weingarten shape attributes analytically at local origin (u=0, v=0)
                # First fundamental components
                E = 1.0 + d**2
                F = d * e
                G = 1.0 + e**2
                
                # Second fundamental components
                denom = np.sqrt(1.0 + d**2 + e**2)
                L = 2.0 * a / denom
                M_coeff = c / denom
                N = 2.0 * b / denom
                
                eg_f2 = E * G - F**2
                K = (L * N - M_coeff**2) / eg_f2
                H = (E * N - 2.0 * F * M_coeff + G * L) / (2.0 * eg_f2)
                
                disc = np.clip(H**2 - K, 0.0, None)
                sqrt_disc = np.sqrt(disc)
                
                k_max[i] = H + sqrt_disc
                k_min[i] = H - sqrt_disc
                
                # Update normal accounting for parabolic parameter orientations
                raw_n = -d * x_axis - e * y_axis + z_axis
                estimated_normals[i] = raw_n / np.linalg.norm(raw_n)
                
            except np.linalg.LinAlgError:
                # Fallback to pure PCA configurations on algebraic failures
                estimated_normals[i] = z_axis
                k_max[i] = 0.0
                k_min[i] = 0.0
                
        # Orient normal fields uniformly relative to global geometric centers
        global_center = np.mean(points, axis=0)
        outward_vectors = points - global_center
        dots = np.einsum('ij,ij->i', estimated_normals, outward_vectors)
        estimated_normals = np.where(dots[:, None] < 0, -estimated_normals, estimated_normals)
        
        curvatures = {
            'Principal_Max': k_max,
            'Principal_Min': k_min
        }
        
        return estimated_normals, curvatures


# ==============================================================================
# INTEGRATION TESTING HARNESS
# ==============================================================================
if __name__ == "__main__":
    print("[*] Simulating a noisy unorganized point cloud sample (Flat patch + Fillet)...")
    np.random.seed(42)
    
    # Construct synthetic mixed geometry point distributions
    n_samples = 60
    t = np.linspace(0, 2, n_samples)
    x = np.linspace(0, 5, n_samples)
    T, X = np.meshgrid(t, x)
    
    pts_list = []
    for val_t in np.linspace(0, 2, 10):
        for val_x in np.linspace(0, 5, 15):
            if val_t < 1.0:
                # Plane surface segment
                pts_list.append([val_t * 5.0, val_x, 0.0])
            else:
                # Cylindrical segment sweep axis (Radius = 2.0)
                angle = (val_t - 1.0) * np.pi / 2.0
                pts_list.append([5.0 + 2.0 * np.sin(angle), val_x, 2.0 - 2.0 * np.cos(angle)])
                
    raw_cloud = np.array(pts_list)
    # Inject Gaussian sensory noise matching broken CAD laser scans
    noise = np.random.normal(0, 0.002, raw_cloud.shape)
    noisy_cloud = raw_cloud + noise
    
    # Process features via Quadric Local Estimation
    estimator = PointCloudGeometryEstimator(k_neighbors=12)
    estimated_normals, computed_curvatures = estimator.estimate_features(noisy_cloud)
    
    print("[+] Feature processing complete across noisy point data structures!")
    print(f"    Estimated Points Count:  {noisy_cloud.shape[0]}")
    print(f"    Mean Max Curvature (Cylindrical region target): {np.mean(computed_curvatures['Principal_Max'][100:]):.4f} (Target ~0.500)")
    print(f"    Mean Min Curvature (Planar zone target):       {np.mean(computed_curvatures['Principal_Min'][:50]):.4f} (Target ~0.000)")


