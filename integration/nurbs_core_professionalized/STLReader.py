#!/usr/bin/env python3
"""STL ingestion and local differential geometry estimation.

Author: Nathan White
License: MIT

The legacy ``load_stl`` and ``estimate_features`` tuple interfaces are preserved.
Use ``read`` and ``estimate`` for structured results and diagnostics. Lengths are
in the input coordinate system; STL does not supply units. Curvature has inverse
length units. No library function configures logging or writes to stdout.
"""

from __future__ import annotations

import io
import logging
import os
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Literal

import numpy as np
from numpy.typing import ArrayLike, NDArray
from scipy.spatial import cKDTree

__all__ = [
    "STLReader", "STLParseError", "STLReadReport", "MeshData",
    "PointCloudGeometryEstimator", "FeatureEstimationResult",
]

LOGGER = logging.getLogger(__name__)
LOGGER.addHandler(logging.NullHandler())
FloatArray = NDArray[np.float64]
IntArray = NDArray[np.int64]
BoolArray = NDArray[np.bool_]
STLFormat = Literal["auto", "ascii", "binary"]
Orientation = Literal["centroid", "canonical", "none"]

# align=False is essential: each little-endian facet occupies exactly 50 bytes.
_FACET_DTYPE = np.dtype([
    ("normal", "<f4", (3,)),
    ("vertices", "<f4", (3, 3)),
    ("attribute", "<u2"),
], align=False)


class STLParseError(ValueError):
    """Malformed STL input, non-finite geometry, or an exceeded resource limit."""


def _integer(value: int, name: str, minimum: int = 1) -> int:
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, (int, np.integer)):
        raise ValueError(f"{name} must be an integer")
    if value < minimum:
        raise ValueError(f"{name} must be >= {minimum}")
    return int(value)


def _points(value: ArrayLike, name: str = "points") -> FloatArray:
    if np.iscomplexobj(value):
        raise ValueError(f"{name} must be real-valued")
    data = np.asarray(value, dtype=np.float64)
    if data.ndim != 2 or data.shape[1] != 3:
        raise ValueError(f"{name} must have shape (N, 3); got {data.shape}")
    if not np.isfinite(data).all():
        raise ValueError(f"{name} must contain only finite coordinates")
    return data


@dataclass(frozen=True, slots=True)
class STLReadReport:
    """Ingestion provenance. No unit or watertightness claim is inferred."""

    source: str
    format: str
    input_facets: int
    loaded_facets: int
    dropped_degenerate_facets: int
    unique_vertices: int


@dataclass(frozen=True, slots=True)
class MeshData:
    """Indexed triangle mesh; arrays are owned by the result and remain writable.

    ``face_normals`` are recomputed from winding for both file encodings. Stored
    STL normals and vendor-specific attribute/color bytes are not trusted or
    preserved. Deduplication is exact, not tolerance-based welding.
    """

    points: FloatArray
    face_normals: FloatArray
    faces: IntArray
    report: STLReadReport

    def as_tuple(self) -> tuple[FloatArray, FloatArray, IntArray]:
        return self.points, self.face_normals, self.faces

    def vertex_normals(self) -> FloatArray:
        """Area-weighted winding normals; zero means cancellation/undefined.

        This averages across creases. It is an orientation hint, not a claim
        that a vertex at a sharp edge has a unique differential normal.
        """
        result = np.zeros_like(self.points)
        tri = self.points[self.faces]
        cross = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
        for corner in range(3):
            np.add.at(result, self.faces[:, corner], cross)
        lengths = np.linalg.norm(result, axis=1, keepdims=True)
        np.divide(result, lengths, out=result, where=lengths > 0)
        return result


class STLReader:
    """Strict, bounded ASCII/binary STL reader with consistent return shapes."""

    @staticmethod
    def load_stl(
        file_path: str | os.PathLike[str],
        *,
        format: STLFormat = "auto",
        max_facets: int = 2_000_000,
        max_file_bytes: int = 256 * 1024 * 1024,
        degenerate_policy: Literal["drop", "error"] = "drop",
        area_tolerance: float = 0.0,
    ) -> tuple[FloatArray, FloatArray, IntArray]:
        """Return ``(vertices[V,3], face_normals[F,3], faces[F,3])``.

        Resource limits apply to input, not peak process memory. Indexed mesh
        construction and vertex deduplication require additional allocations.
        ``area_tolerance`` is in squared input length units.
        """
        return STLReader.read(
            file_path, format=format, max_facets=max_facets,
            max_file_bytes=max_file_bytes, degenerate_policy=degenerate_policy,
            area_tolerance=area_tolerance,
        ).as_tuple()

    @staticmethod
    def read(
        file_path: str | os.PathLike[str],
        *,
        format: STLFormat = "auto",
        max_facets: int = 2_000_000,
        max_file_bytes: int = 256 * 1024 * 1024,
        degenerate_policy: Literal["drop", "error"] = "drop",
        area_tolerance: float = 0.0,
    ) -> MeshData:
        """Load one file; reject truncation, trailing binary data, and bad syntax.

        Auto-detection first checks the binary length/count relationship, so a
        binary header beginning with ``solid`` is not mistaken for ASCII.
        Explicit ``format`` is available for genuinely ambiguous input.
        ASCII supports multiple complete ``solid ... endsolid`` blocks.
        """
        max_facets = _integer(max_facets, "max_facets")
        max_file_bytes = _integer(max_file_bytes, "max_file_bytes")
        if format not in ("auto", "ascii", "binary"):
            raise ValueError("format must be 'auto', 'ascii', or 'binary'")
        if degenerate_policy not in ("drop", "error"):
            raise ValueError("degenerate_policy must be 'drop' or 'error'")
        if not np.isfinite(area_tolerance) or area_tolerance < 0:
            raise ValueError("area_tolerance must be finite and nonnegative")
        path = Path(file_path)
        with path.open("rb") as stream:
            size = os.fstat(stream.fileno()).st_size
            if size > max_file_bytes:
                raise STLParseError(f"{path}: {size} bytes exceeds max_file_bytes")
            header = stream.read(84)
            count = struct.unpack("<I", header[80:84])[0] if len(header) == 84 else None
            exact_binary = count is not None and size == 84 + 50 * count
            selected = format
            if selected == "auto":
                if exact_binary:
                    selected = "binary"
                elif header.lstrip(b"\xef\xbb\xbf \t\r\n").lower().startswith(b"solid"):
                    selected = "ascii"
                else:
                    selected = "binary"
            stream.seek(0)
            if selected == "binary":
                triangles = STLReader._read_binary(stream, size, max_facets)
            else:
                triangles = STLReader._read_ascii(stream, max_facets)
        if not np.isfinite(triangles).all():
            raise STLParseError(f"{path}: STL vertices contain NaN or infinity")
        input_facets = len(triangles)
        edges1 = triangles[:, 1] - triangles[:, 0]
        edges2 = triangles[:, 2] - triangles[:, 0]
        with np.errstate(over="ignore", invalid="ignore"):
            cross = np.cross(edges1, edges2)
            doubled_area = np.linalg.norm(cross, axis=1)
        if not np.isfinite(doubled_area).all():
            raise STLParseError(f"{path}: coordinates exceed safe float64 area range")
        valid = doubled_area > 2.0 * area_tolerance
        dropped = int(np.count_nonzero(~valid))
        if dropped and degenerate_policy == "error":
            raise STLParseError(f"{path}: found {dropped} degenerate/below-tolerance facets")
        triangles = triangles[valid]
        face_normals = cross[valid] / doubled_area[valid, None]
        points, inverse = np.unique(triangles.reshape(-1, 3), axis=0, return_inverse=True)
        faces = inverse.reshape(-1, 3).astype(np.int64, copy=False)
        report = STLReadReport(
            str(path), selected, input_facets, len(faces), dropped, len(points),
        )
        LOGGER.info(
            "Read %s STL: %d vertices, %d facets, %d degenerate facets dropped",
            selected, len(points), len(faces), dropped,
        )
        return MeshData(points, face_normals, faces, report)

    @staticmethod
    def _read_binary(stream: BinaryIO, size: int, max_facets: int) -> FloatArray:
        header = stream.read(84)
        if len(header) != 84:
            raise STLParseError("binary STL requires an 80-byte header and a 4-byte count")
        count = struct.unpack("<I", header[80:84])[0]
        if count > max_facets:
            raise STLParseError(f"binary facet count {count} exceeds max_facets={max_facets}")
        expected = 84 + 50 * count
        if size != expected:
            raise STLParseError(f"binary STL byte length is {size}; count requires {expected}")
        records = np.fromfile(stream, dtype=_FACET_DTYPE, count=count)
        if len(records) != count or stream.read(1):
            raise STLParseError("binary STL changed or was truncated during reading")
        return records["vertices"].astype(np.float64)

    @staticmethod
    def _read_ascii(stream: BinaryIO, max_facets: int) -> FloatArray:
        state = "outside"
        triangles: list[list[list[float]]] = []
        vertices: list[list[float]] = []
        saw_solid = False
        text = io.TextIOWrapper(stream, encoding="utf-8-sig", errors="strict", newline=None)
        line_number = 0
        try:
            while True:
                # Bound an individual allocation even on malicious single-line files.
                line = text.readline(16_385)
                if not line:
                    break
                line_number += 1
                if len(line) > 16_384:
                    raise STLParseError(f"ASCII STL line {line_number} exceeds 16384 characters")
                tokens = line.strip().split()
                if not tokens:
                    continue
                words = [token.lower() for token in tokens]
                error = f"ASCII STL line {line_number}: unexpected {tokens[0]!r} in {state}"
                if state == "outside" and words[0] == "solid":
                    state, saw_solid = "solid", True
                elif state == "solid" and words[0] == "endsolid":
                    state = "outside"
                elif state == "solid" and words[:2] == ["facet", "normal"] and len(words) == 5:
                    # Validate syntax; geometry normals are recomputed from winding.
                    normal = np.asarray([float(x) for x in tokens[2:]], dtype=np.float64)
                    if not np.isfinite(normal).all():
                        raise STLParseError(f"ASCII STL line {line_number}: non-finite normal")
                    if len(triangles) >= max_facets:
                        raise STLParseError("ASCII facet count exceeds max_facets")
                    state, vertices = "facet", []
                elif state == "facet" and words == ["outer", "loop"]:
                    state = "vertices"
                elif state == "vertices" and words[0] == "vertex" and len(words) == 4:
                    if len(vertices) == 3:
                        raise STLParseError(
                            f"ASCII STL line {line_number}: more than three vertices"
                        )
                    vertices.append([float(x) for x in tokens[1:]])
                elif state == "vertices" and words == ["endloop"] and len(vertices) == 3:
                    state = "endloop"
                elif state == "endloop" and words == ["endfacet"]:
                    triangles.append(vertices)
                    state = "solid"
                else:
                    raise STLParseError(error)
        except (UnicodeDecodeError, ValueError) as exc:
            if isinstance(exc, STLParseError):
                raise
            raise STLParseError(f"invalid ASCII STL near line {line_number}: {exc}") from exc
        finally:
            # The outer context manager owns the binary stream.
            text.detach()
        if not saw_solid or state != "outside":
            raise STLParseError(f"incomplete ASCII STL: final parser state is {state!r}")
        return np.asarray(triangles, dtype=np.float64).reshape(-1, 3, 3)

    @staticmethod
    def _parse_binary(file_path: str | os.PathLike[str]) -> tuple[FloatArray, FloatArray, IntArray]:
        """Compatibility wrapper for the former private parser."""
        return STLReader.load_stl(file_path, format="binary")

    @staticmethod
    def _parse_ascii(file_path: str | os.PathLike[str]) -> tuple[FloatArray, FloatArray, IntArray]:
        """Compatibility wrapper for the former private parser."""
        return STLReader.load_stl(file_path, format="ascii")


@dataclass(frozen=True, slots=True)
class FeatureEstimationResult:
    """Arrays share point order; ``valid_mask`` governs curvature usability.

    A failed quadratic fit retains a PCA normal when possible, but returns NaN
    curvature, never fabricated zero/planar curvature. Arrays remain writable.
    """

    normals: FloatArray
    principal_max: FloatArray
    principal_min: FloatArray
    valid_mask: BoolArray
    fit_rmse: FloatArray
    condition_number: FloatArray
    neighbor_count: IntArray

    @property
    def curvatures(self) -> dict[str, NDArray]:
        return {
            "Principal_Max": self.principal_max,
            "Principal_Min": self.principal_min,
            "Valid": self.valid_mask,
        }

    def as_tuple(self) -> tuple[FloatArray, dict[str, NDArray]]:
        return self.normals, self.curvatures


class PointCloudGeometryEstimator:
    """Weighted, query-centered quadratic fits in local PCA tangent frames.

    KD-tree queries are batched: no N-by-N distance matrix is constructed.
    ``k_neighbors`` includes the query point, matching the original convention.
    ``max_radius`` and ``max_fit_rmse`` use input length units. The centroid
    orientation default preserves the old heuristic; it is NOT an orientation
    solver for concave/open surfaces. Prefer winding-based ``reference_normals``
    or a scanner ``viewpoint`` when these are known.
    """

    def __init__(
        self,
        k_neighbors: int = 15,
        *,
        batch_size: int = 1024,
        workers: int = 1,
        max_condition: float = 1e8,
        max_radius: float | None = None,
        max_fit_rmse: float | None = None,
        orientation: Orientation = "centroid",
    ) -> None:
        self.k = _integer(k_neighbors, "k_neighbors", 6)
        self.batch_size = _integer(batch_size, "batch_size")
        if workers != -1:
            workers = _integer(workers, "workers")
        self.workers = workers
        if not np.isfinite(max_condition) or max_condition <= 1:
            raise ValueError("max_condition must be finite and > 1")
        for name, value in (("max_radius", max_radius), ("max_fit_rmse", max_fit_rmse)):
            if value is not None and (not np.isfinite(value) or value <= 0):
                raise ValueError(f"{name} must be finite and positive")
        if orientation not in ("centroid", "canonical", "none"):
            raise ValueError("orientation must be 'centroid', 'canonical', or 'none'")
        self.max_condition = float(max_condition)
        self.max_radius = max_radius
        self.max_fit_rmse = max_fit_rmse
        self.orientation = orientation

    def estimate_features(
        self,
        points: ArrayLike,
        *,
        reference_normals: ArrayLike | None = None,
        viewpoint: ArrayLike | None = None,
    ) -> tuple[FloatArray, dict[str, NDArray]]:
        """Legacy tuple interface; the curvature mapping now also contains ``Valid``."""
        return self.estimate(
            points, reference_normals=reference_normals, viewpoint=viewpoint,
        ).as_tuple()

    def estimate(
        self,
        points: ArrayLike,
        *,
        reference_normals: ArrayLike | None = None,
        viewpoint: ArrayLike | None = None,
    ) -> FeatureEstimationResult:
        points = _points(points)
        count = len(points)
        if reference_normals is not None and viewpoint is not None:
            raise ValueError("provide reference_normals or viewpoint, not both")
        reference = None
        if reference_normals is not None:
            reference = _points(reference_normals, "reference_normals")
            if reference.shape != points.shape:
                raise ValueError("reference_normals must have the same shape as points")
        view = None
        if viewpoint is not None:
            view = np.asarray(viewpoint, dtype=np.float64)
            if view.shape != (3,) or not np.isfinite(view).all():
                raise ValueError("viewpoint must be a finite 3-vector")

        normals = np.zeros((count, 3), dtype=np.float64)
        k_max = np.full(count, np.nan)
        k_min = np.full(count, np.nan)
        valid = np.zeros(count, dtype=bool)
        rmses = np.full(count, np.nan)
        conditions = np.full(count, np.inf)
        n_neighbors = np.zeros(count, dtype=np.int64)
        if count:
            tree = cKDTree(points)
            k = min(self.k, count)
            LOGGER.info("Estimating features for %d points with k=%d", count, k)
            for first in range(0, count, self.batch_size):
                stop = min(first + self.batch_size, count)
                distances, neighbors = tree.query(
                    points[first:stop], k=list(range(1, k + 1)), workers=self.workers,
                    distance_upper_bound=self.max_radius if self.max_radius is not None else np.inf,
                )
                for offset, (dist, indices) in enumerate(zip(distances, neighbors, strict=True)):
                    i = first + offset
                    indices = indices[np.isfinite(dist)]
                    n_neighbors[i] = len(indices)
                    if len(indices) < 3:
                        continue
                    # PCA can be centered at its centroid, but the polynomial
                    # coordinates must be centered at the query, not the centroid.
                    patch = points[indices] - points[i]
                    scale = float(np.max(np.linalg.norm(patch, axis=1)))
                    if scale == 0 or not np.isfinite(scale):
                        continue
                    patch = patch / scale
                    centered = patch - np.mean(patch, axis=0)
                    try:
                        _, singular, vh = np.linalg.svd(centered, full_matrices=False)
                    except np.linalg.LinAlgError:
                        continue
                    if singular[0] == 0 or singular[1] <= 1e-12 * singular[0]:
                        continue
                    z_axis, x_axis = vh[2], vh[0]
                    y_axis = np.cross(z_axis, x_axis)
                    normals[i] = z_axis  # PCA fallback, curvature remains invalid.
                    if len(indices) < 6:
                        continue
                    u, v, w = patch @ x_axis, patch @ y_axis, patch @ z_axis
                    matrix = np.column_stack((u * u, v * v, u * v, u, v, np.ones_like(u)))
                    sqrt_weights = np.exp(-np.sum(patch * patch, axis=1))
                    try:
                        coefficients, _, rank, sv = np.linalg.lstsq(
                            matrix * sqrt_weights[:, None], w * sqrt_weights, rcond=None,
                        )
                    except np.linalg.LinAlgError:
                        continue
                    condition = float(sv[0] / sv[-1]) if sv[-1] > 0 else np.inf
                    conditions[i] = condition
                    if rank < 6 or condition > self.max_condition:
                        continue
                    residual = matrix @ coefficients - w
                    rmses[i] = float(np.sqrt(np.mean(residual**2)) * scale)
                    if self.max_fit_rmse is not None and rmses[i] > self.max_fit_rmse:
                        continue
                    a, b, c, d, e, _ = coefficients
                    E, F, G = 1.0 + d * d, d * e, 1.0 + e * e
                    denom = np.sqrt(1.0 + d * d + e * e)
                    L, M, N = 2.0 * a / denom, c / denom, 2.0 * b / denom
                    determinant = 1.0 + d * d + e * e
                    gaussian = (L * N - M * M) / determinant
                    mean = (E * N - 2.0 * F * M + G * L) / (2.0 * determinant)
                    root = np.sqrt(max(0.0, mean * mean - gaussian))
                    k_max[i], k_min[i] = (mean + root) / scale, (mean - root) / scale
                    normals[i] = (-d * x_axis - e * y_axis + z_axis) / denom
                    valid[i] = np.isfinite(k_max[i]) and np.isfinite(k_min[i])

        if count:
            # Deterministic fallback resolves the zero-dot ambiguity on planes.
            dominant = normals[np.arange(count), np.argmax(np.abs(normals), axis=1)]
            flip = dominant < 0
            if self.orientation == "none":
                flip[:] = False
            elif self.orientation == "centroid":
                directions = points - np.mean(points, axis=0)
                dot = np.einsum("ij,ij->i", normals, directions)
                significant = np.abs(dot) > 1e-12 * np.linalg.norm(directions, axis=1)
                flip[significant] = dot[significant] < 0
            if reference is not None or view is not None:
                if reference is not None:
                    directions = reference
                else:
                    assert view is not None  # Guaranteed by the branch above.
                    directions = view - points
                dot = np.einsum("ij,ij->i", normals, directions)
                significant = np.abs(dot) > 1e-12 * np.linalg.norm(directions, axis=1)
                flip[significant] = dot[significant] < 0
            normals[flip] *= -1.0
            # Normal reversal changes BOTH signs and the algebraic ordering.
            old_max = k_max[flip].copy()
            k_max[flip], k_min[flip] = -k_min[flip], -old_max
        k_max[~valid] = np.nan
        k_min[~valid] = np.nan
        LOGGER.info("Quadratic features valid for %d/%d points", np.count_nonzero(valid), count)
        return FeatureEstimationResult(normals, k_max, k_min, valid, rmses, conditions, n_neighbors)


if __name__ == "__main__":
    import argparse
    import json
    from dataclasses import asdict

    parser = argparse.ArgumentParser(description="Inspect an STL without fitting or exporting CAD")
    parser.add_argument("input", type=Path)
    args = parser.parse_args()
    try:
        print(json.dumps(asdict(STLReader.read(args.input).report), indent=2))
    except (OSError, ValueError) as exc:
        parser.exit(2, f"error: {exc}\n")
