"""Real STEP exchange and explicit UV/XYZ data for front-end consumers.

STEP stores planar triangular CAD faces, not an invented smooth B-spline fit.
The JSON sidecar is this package's documented interchange schema (not a CAD
standard); it retains UV coordinates, 3D positions, and parent polygon IDs.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence, Optional
import json
import os
import tempfile
import threading

import numpy as np

from mesh_healing_engine import MeshHealingEngine, MeshError, ParameterizationError, _finite_array

_STEP_LOCK = threading.Lock()
_UNITS = {"mm": "MM", "cm": "CM", "m": "M", "in": "INCH", "ft": "FT", "um": "UM"}


def _destination(filename: str | Path) -> Path:
    path = Path(filename)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _atomic_json(path: Path, value):
    path = _destination(path)
    fd, tmp = tempfile.mkstemp(prefix=f'.{path.name}.', suffix='.tmp', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            json.dump(value, stream, allow_nan=False, indent=2)
            stream.write('\n')
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def export_frontend_json(engine: MeshHealingEngine, filename: str | Path,
                         coords_2d: Mapping[int, Sequence[float]], *,
                         units: str = "mm", face_ids=None) -> Path:
    """Export exact mesh indexing and BOTH UV/XYZ; no implicit normalization.

    Vertex IDs may be noncontiguous when exporting a subset. Indices in
    triangles/polygons reference positions in vertex_ids, not global mesh IDs.
    """
    if units not in _UNITS:
        raise MeshError(f"Supported units: {', '.join(_UNITS)}")
    triangles, parents = engine.triangulated_faces(face_ids)
    if not len(triangles):
        raise MeshError("Cannot export an empty mesh")
    ids = sorted(set(map(int, triangles.ravel())))
    local = {v: i for i, v in enumerate(ids)}
    try:
        uv = np.array([_finite_array(coords_2d[v], (2,), "UV") for v in ids])
    except KeyError as exc:
        raise MeshError(f"Missing UV for vertex {exc.args[0]}") from exc
    quality = engine.validate_uv(coords_2d, face_ids=face_ids)
    if not quality.locally_valid:
        raise ParameterizationError("Refusing to export a flipped/collapsed UV chart")
    polygon_ids = list(range(len(engine.faces))) if face_ids is None else list(face_ids)
    value = {
        "schema": "mesh-healing-uv/1.0",
        "geometry_kind": "piecewise_linear_surface",
        "units_xyz": units,
        "units_uv": "parameter_units",
        "vertex_ids": ids,
        "positions": engine.v3d[ids].tolist(),
        "uv": uv.tolist(),
        "triangles": [[local[int(v)] for v in t] for t in triangles],
        "triangle_parent_faces": parents.tolist(),
        "polygon_ids": polygon_ids,
        "polygons": [[local[v] for v in engine.faces[f]] for f in polygon_ids],
        "uv_bounds": {"min": uv.min(axis=0).tolist(), "max": uv.max(axis=0).tolist()},
        "orientation": "counterclockwise_uv",
        "note": "UV is not rescaled to [0,1]. STEP files do not carry this original UV chart.",
    }
    path = _destination(filename)
    _atomic_json(path, value)
    return path


@dataclass(frozen=True)
class StepExportResult:
    path: Path
    triangle_faces: int
    imported_faces: int
    imported_shells: int
    imported_solids: int
    space: str
    units: str
    roundtrip_valid: bool
    area_relative_error: float
    bounds_absolute_error: float


def export_step(engine: MeshHealingEngine, filename: str | Path, *,
                coords_2d: Optional[Mapping[int, Sequence[float]]] = None,
                space: str = "xyz", units: str = "mm",
                uv_scale: float = 1.0, sewing_tolerance: float = 1e-7,
                sew: bool = True, face_ids=None) -> StepExportResult:
    """Export actual CAD face topology using CadQuery/OpenCascade, then reimport.

    space='xyz': original piecewise-linear 3D surface.
    space='uv': flattened chart embedded as (uv_scale*u, uv_scale*v, 0).
      uv_scale is physical `units` per parameter unit; it is NOT inferred.
    Input geometry and sewing_tolerance use the declared physical units.

    Reimport verifies B-rep validity, face count, area, and bounds before an
    atomic rename. Open patches are exported as open surfaces, not fake solids.
    No fitted surfaces, analytic feature recovery, or construction history.
    """
    if space not in ('xyz', 'uv'):
        raise MeshError("space must be 'xyz' or 'uv'")
    if units not in _UNITS:
        raise MeshError(f"Supported units: {', '.join(_UNITS)}")
    if not np.isfinite(uv_scale) or uv_scale <= 0:
        raise MeshError("uv_scale must be finite and strictly positive")
    if not np.isfinite(sewing_tolerance) or sewing_tolerance <= 0:
        raise MeshError("sewing_tolerance must be finite and strictly positive")
    if space == 'uv' and coords_2d is None:
        raise MeshError("A UV STEP export requires coords_2d")
    try:
        import cadquery as cq
        from OCP.BRepBuilderAPI import BRepBuilderAPI_Sewing
        from OCP.IFSelect import IFSelect_RetDone
    except ImportError as exc:
        raise ImportError("STEP export needs CadQuery/OpenCascade: pip install 'cadquery>=2.8,<3'") from exc
    triangles, _ = engine.triangulated_faces(face_ids)
    if not len(triangles):
        raise MeshError("Cannot export an empty surface")
    selected_faces = engine.faces if face_ids is None else [engine.faces[i] for i in face_ids]
    if not MeshHealingEngine(engine.v3d, selected_faces).topology_report().is_oriented_manifold:
        raise MeshError("STEP export requires an oriented manifold patch; preprocess first")
    positions = engine.v3d.copy()
    if coords_2d is not None:
        quality = engine.validate_uv(coords_2d, face_ids=face_ids)
        if not quality.locally_valid:
            raise ParameterizationError("Cannot export a folded/collapsed UV chart")
    if space == 'uv':
        for v in np.unique(triangles):
            uv = _finite_array(coords_2d[int(v)], (2,), 'UV')
            positions[int(v)] = (uv_scale * uv[0], uv_scale * uv[1], 0.0)
    # Build in millimeters for a fixed OCCT internal unit; export with an explicit unit.
    to_mm = {"mm": 1., "cm": 10., "m": 1000., "in": 25.4, "ft": 304.8, "um": 0.001}[units]
    positions *= to_mm
    if not np.all(np.isfinite(positions)):
        raise MeshError("Coordinate/unit conversion overflowed; rescale the model")
    tol_mm = sewing_tolerance * to_mm
    # OCCT construction at scales below its geometric tolerance is unsafe.
    for tri in triangles:
        p = positions[tri]
        lengths = [np.linalg.norm(p[(i + 1) % 3] - p[i]) for i in range(3)]
        if min(lengths) <= max(10 * tol_mm, 1e-6):
            raise MeshError("STEP triangle is too small relative to sewing/kernel tolerance; rescale explicitly")
    faces = []
    for tri in triangles:
        wire = cq.Wire.makePolygon([cq.Vector(*map(float, positions[v])) for v in tri], close=True)
        faces.append(cq.Face.makeFromWires(wire))
    if sew:
        sewing = BRepBuilderAPI_Sewing(tol_mm, True, True, True, False)
        for face in faces:
            sewing.Add(face.wrapped)
        sewing.Perform()
        shape = cq.Shape.cast(sewing.SewedShape())
    else:
        shape = cq.Compound.makeCompound(faces)
    if not shape.isValid() or len(shape.Faces()) != len(triangles):
        raise MeshError("OpenCascade construction altered/invalidated the requested face topology")
    expected_area = sum(float(np.linalg.norm(np.cross(positions[t[1]] - positions[t[0]],
                                                      positions[t[2]] - positions[t[0]]))) / 2
                        for t in triangles)
    path = _destination(filename)
    fd, temporary = tempfile.mkstemp(prefix=f'.{path.stem}.', suffix='.step', dir=path.parent)
    os.close(fd)
    try:
        # OCCT exchange settings include process-global state. Serialize our own calls.
        with _STEP_LOCK:
            status = shape.exportStep(temporary, unit='MM', outputUnit=_UNITS[units])
            if status != IFSelect_RetDone:
                raise RuntimeError(f"STEP writer failed with status {status}")
            imported = cq.importers.importStep(temporary).val()
        if not imported.isValid():
            raise RuntimeError("Reimported STEP fails B-rep validation")
        imported_faces = len(imported.Faces())
        if imported_faces != len(triangles):
            raise RuntimeError("STEP round-trip changed the number of triangular faces")
        # CadQuery's importer converts file units back to internal millimeters.
        area_error = abs(imported.Area() - expected_area) / expected_area
        bounds = imported.BoundingBox()
        active_positions = positions[np.unique(triangles)]
        expected_bounds = np.r_[active_positions.min(axis=0), active_positions.max(axis=0)]
        actual_bounds = np.array([bounds.xmin, bounds.ymin, bounds.zmin,
                                  bounds.xmax, bounds.ymax, bounds.zmax])
        bound_error_mm = float(np.max(np.abs(actual_bounds - expected_bounds)))
        extent_mm = float(np.max(np.ptp(active_positions, axis=0)))
        bound_limit = max(10 * tol_mm, 1e-7 * max(extent_mm, 1.0))
        if area_error > 1e-7 or bound_error_mm > bound_limit:
            raise RuntimeError(f"STEP round-trip geometry mismatch: area={area_error:g}, bounds={bound_error_mm:g} mm")
        result = StepExportResult(path, len(triangles), imported_faces,
                                  len(imported.Shells()), len(imported.Solids()),
                                  space, units, True, area_error, bound_error_mm / to_mm)
        os.replace(temporary, path)
        return result
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


class UVSurfaceMap:
    """Piecewise-affine evaluator of a SINGLE UV chart: (u,v) -> (x,y,z).

    The caller can provide triangle IDs from a frontend BVH/picking operation.
    The included locate() is deliberately simple O(queries * triangles), not a
    large-mesh point-location accelerator. Out-of-chart points raise errors;
    shared-edge hits use the first triangle only when all candidate XYZ values
    agree. Overlapping charts with conflicting XYZ are rejected as ambiguous.
    """
    def __init__(self, engine: MeshHealingEngine, coords_2d, *, face_ids=None):
        self.engine = engine
        self._signature = engine._fingerprint()
        self._revision = engine._revision
        self.triangles, self.parent_faces = engine.triangulated_faces(face_ids)
        if not len(self.triangles):
            raise MeshError("UV surface map needs at least one triangle")
        if not engine.validate_uv(coords_2d, face_ids=face_ids).locally_valid:
            raise ParameterizationError("UV surface map requires an orientation-preserving, noncollapsed chart")
        self.uv = np.array([[_finite_array(coords_2d[int(v)], (2,), 'UV') for v in t]
                            for t in self.triangles])
        self.xyz = engine.v3d[self.triangles].copy()
        self.origins = self.uv[:, 0]
        # Rows of coefficients satisfy [u-u0, v-v0] @ inverse_edges = [b1,b2].
        edges = self.uv[:, 1:] - self.uv[:, :1]
        self.inverse_edges = np.linalg.inv(edges)

    def _fresh(self):
        if self.engine._revision != self._revision or self.engine._fingerprint() != self._signature:
            from mesh_healing_engine import StaleSystemError
            raise StaleSystemError("Mesh changed; rebuild the UV evaluator")

    def evaluate(self, uv_queries, triangle_ids, *, tolerance: float = 1e-9) -> np.ndarray:
        self._fresh()
        if not np.isfinite(tolerance) or tolerance < 0:
            raise MeshError("Barycentric tolerance must be finite and nonnegative")
        queries = np.asarray(uv_queries, dtype=float)
        ids = np.asarray(triangle_ids)
        if queries.ndim != 2 or queries.shape[1] != 2 or not np.all(np.isfinite(queries)):
            raise MeshError("uv_queries must be a finite (Q,2) array")
        if ids.shape != (len(queries),) or not np.issubdtype(ids.dtype, np.integer):
            raise MeshError("triangle_ids must be an integer vector with one ID per query")
        if np.any(ids < 0) or np.any(ids >= len(self.triangles)):
            raise MeshError("triangle ID out of bounds")
        bc12 = np.einsum('qi,qij->qj', queries - self.origins[ids], self.inverse_edges[ids])
        barycentric = np.column_stack((1 - bc12.sum(axis=1), bc12))
        if np.any(barycentric < -tolerance) or np.any(barycentric > 1 + tolerance):
            raise MeshError("UV query lies outside its supplied triangle")
        return np.einsum('qi,qij->qj', barycentric, self.xyz[ids])

    def locate(self, uv_queries, *, tolerance: float = 1e-9) -> np.ndarray:
        self._fresh()
        if not np.isfinite(tolerance) or tolerance < 0:
            raise MeshError("Barycentric tolerance must be finite and nonnegative")
        queries = np.asarray(uv_queries, dtype=float)
        if queries.ndim != 2 or queries.shape[1] != 2 or not np.all(np.isfinite(queries)):
            raise MeshError("uv_queries must be a finite (Q,2) array")
        ids = []
        for q in queries:
            bc12 = np.einsum('ti,tij->tj', q - self.origins, self.inverse_edges)
            bc = np.column_stack((1 - bc12.sum(axis=1), bc12))
            candidates = np.flatnonzero(np.all(bc >= -tolerance, axis=1)
                                        & np.all(bc <= 1 + tolerance, axis=1))
            if not len(candidates):
                raise MeshError(f"UV query {q.tolist()} lies outside this chart")
            if len(candidates) > 1:
                xyz = np.einsum('ti,tij->tj', bc[candidates], self.xyz[candidates])
                scale = max(np.max(np.ptp(self.xyz.reshape(-1, 3), axis=0)), np.finfo(float).tiny)
                if np.max(np.linalg.norm(xyz - xyz[0], axis=1)) > 1e-8 * scale:
                    raise ParameterizationError("Ambiguous UV query: overlapping triangles map to different XYZ")
            ids.append(int(candidates[0]))
        return np.array(ids, dtype=np.int64)

    def sample(self, uv_queries, *, tolerance: float = 1e-9) -> np.ndarray:
        return self.evaluate(uv_queries, self.locate(uv_queries, tolerance=tolerance), tolerance=tolerance)
