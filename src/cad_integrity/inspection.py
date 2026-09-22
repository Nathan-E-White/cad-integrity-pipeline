"""Renderer-independent, owned polygonal inspection results."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal
from uuid import uuid4

import numpy as np

from .arrays import FloatArray, IntArray, floats, integers
from .errors import InvalidGeometry, ResourceLimitExceeded
from .models import PolyhedralBRep
from .pipeline import RepairResult, fingerprint
from .topology import TopologyReport

if TYPE_CHECKING:
    from .adapters.ocp import FaceTessellation

EntityKind = Literal["vertex", "edge", "polygonal_face"]


@dataclass(frozen=True, slots=True)
class ProjectionLimits:
    max_vertices: int = 250_000
    max_edges: int = 1_500_000
    max_faces: int = 500_000
    max_display_triangles: int = 1_000_000
    max_payload_bytes: int = 2_000_000_000

    def __post_init__(self) -> None:
        if any(
            type(value) is not int or value < 1
            for value in (
                self.max_vertices,
                self.max_edges,
                self.max_faces,
                self.max_display_triangles,
                self.max_payload_bytes,
            )
        ):
            raise ValueError("Inspection limits must be positive integers")

    def preflight(self, breps: tuple[PolyhedralBRep | InspectionGeometryInput, ...]) -> None:
        total_values = 0
        for brep in breps:
            expanded = int(np.maximum(np.diff(brep.face_offsets) - 2, 0).sum())
            for name, count, limit in (
                ("vertices", len(brep.vertices), self.max_vertices),
                ("edges", len(brep.edges), self.max_edges),
                ("faces", brep.face_count, self.max_faces),
                ("display triangles", expanded, self.max_display_triangles),
            ):
                if count > limit or count > np.iinfo(np.int32).max:
                    raise ResourceLimitExceeded(
                        f"Inspection {name} budget exceeded: {count} > {limit}"
                    )
            # Conservative JSON numeric storage allowance, including repeated
            # boundaries/memberships and two independently owned stages.
            total_values += (
                brep.vertices.size
                + brep.edges.size
                + brep.face_offsets.size
                + brep.face_coedges.size * 4
                + expanded * 4
                + 2 * len(brep.vertices)
                + 5 * len(brep.edges)
                + 2 * brep.face_count
            )
        if total_values * 32 > self.max_payload_bytes:
            raise ResourceLimitExceeded("Inspection payload budget exceeded")


def _immutable(values: np.ndarray) -> np.ndarray:
    return np.frombuffer(values.tobytes(), dtype=values.dtype).reshape(values.shape)


@dataclass(frozen=True, slots=True)
class InspectionGeometryInput:
    """Raw display input that may retain unresolved references, never chain admission.

    Offsets must identify finite face records. Edge/vertex references may be
    unresolved; the display projector reports those locally without inventing
    connectivity or weakening PolyhedralBRep's numerical admission contract.
    """

    vertices: FloatArray
    edges: IntArray
    face_offsets: IntArray
    face_coedges: IntArray

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "vertices", _immutable(floats(self.vertices, name="vertices", width=3))
        )
        object.__setattr__(self, "edges", _immutable(integers(self.edges, name="edges", width=2)))
        for name in ("face_offsets", "face_coedges"):
            object.__setattr__(self, name, _immutable(integers(getattr(self, name), name=name)))
        offsets = self.face_offsets
        if (
            not len(offsets)
            or offsets[0] != 0
            or offsets[-1] != len(self.face_coedges)
            or np.any(offsets < 0)
            or np.any(np.diff(offsets) < 0)
        ):
            raise InvalidGeometry("Display face offsets must identify ordered source records")

    @property
    def face_count(self) -> int:
        return len(self.face_offsets) - 1


@dataclass(frozen=True, slots=True)
class DisplayIssue:
    face_id: int
    code: str
    detail: str


@dataclass(frozen=True, slots=True)
class DisplayGeometry:
    triangles: IntArray
    triangle_source_faces: IntArray
    boundary_segments: IntArray
    boundary_source_faces: IntArray
    issues: tuple[DisplayIssue, ...]

    def __post_init__(self) -> None:
        for name in (
            "triangles",
            "triangle_source_faces",
            "boundary_segments",
            "boundary_source_faces",
        ):
            object.__setattr__(self, name, _immutable(getattr(self, name)))
        object.__setattr__(self, "issues", tuple(self.issues))


def triangulate_for_inspection(
    brep: PolyhedralBRep | InspectionGeometryInput, *, limits: ProjectionLimits = ProjectionLimits()
) -> DisplayGeometry:
    """Emit provenance while triangulating, with independent per-face failures."""
    limits.preflight((brep,))
    if isinstance(brep, InspectionGeometryInput):
        return _raw_display_geometry(brep)
    if np.all(np.diff(brep.face_offsets) == 3):
        # Restricted NPZs contain only triangles. Resolve their oriented coedges
        # in bounded arrays instead of repeating polygon checks a million times.
        tokens = brep.face_coedges.reshape(-1, 3)
        pairs = brep.edges[np.abs(tokens) - 1]
        starts = np.where(tokens < 0, pairs[:, :, 1], pairs[:, :, 0])
        ends = np.where(tokens < 0, pairs[:, :, 0], pairs[:, :, 1])
        valid = np.all(ends == np.roll(starts, -1, axis=1), axis=1)
        xyz = brep.vertices[starts]
        normal = np.cross(xyz[:, 1] - xyz[:, 0], xyz[:, 2] - xyz[:, 0])
        valid &= np.any(normal != 0, axis=1) & np.all(np.isfinite(normal), axis=1)
        triangle_owners = np.arange(brep.face_count, dtype=np.int64)
        triangle_segments = np.stack((starts[~valid], ends[~valid]), axis=-1).reshape(-1, 2)
        triangle_issues = tuple(
            DisplayIssue(
                int(face), "unsupported_face", "Degenerate triangle or discontinuous face boundary"
            )
            for face in triangle_owners[~valid]
        )
        return DisplayGeometry(
            starts[valid],
            triangle_owners[valid],
            triangle_segments,
            np.repeat(triangle_owners[~valid], 3),
            triangle_issues,
        )
    triangles: list[tuple[int, int, int]] = []
    owners: list[int] = []
    segments: list[tuple[int, int]] = []
    boundaries: list[int] = []
    issues: list[DisplayIssue] = []
    for face in range(brep.face_count):
        endpoints = brep.directed_endpoints(face)
        try:
            emitted = brep.triangulate_face(face)
        except InvalidGeometry as exc:
            segments.extend((int(a), int(b)) for a, b in endpoints)
            boundaries.extend([face] * len(endpoints))
            issues.append(DisplayIssue(face, "unsupported_face", str(exc)))
        else:
            triangles.extend(emitted)
            owners.extend([face] * len(emitted))
    return DisplayGeometry(
        np.asarray(triangles, dtype=np.int64).reshape(-1, 3),
        np.asarray(owners, dtype=np.int64),
        np.asarray(segments, dtype=np.int64).reshape(-1, 2),
        np.asarray(boundaries, dtype=np.int64),
        tuple(issues),
    )


def _raw_display_geometry(raw: InspectionGeometryInput) -> DisplayGeometry:
    triangles: list[tuple[int, int, int]] = []
    owners: list[int] = []
    boundaries: list[tuple[int, int]] = []
    boundary_owners: list[int] = []
    issues: list[DisplayIssue] = []
    for face in range(raw.face_count):
        first, last = raw.face_offsets[face : face + 2]
        pairs: list[tuple[int, int]] = []
        unresolved = False
        for value in raw.face_coedges[first:last]:
            token = int(value)
            edge = abs(token) - 1
            if edge < 0 or edge >= len(raw.edges):
                unresolved = True
                continue
            pair = tuple(int(v) for v in raw.edges[edge])
            if any(v < 0 or v >= len(raw.vertices) for v in pair):
                unresolved = True
                continue
            pairs.append((pair[0], pair[1]) if token > 0 else (pair[1], pair[0]))
        if unresolved:
            boundaries.extend(pairs)
            boundary_owners.extend([face] * len(pairs))
            issues.append(
                DisplayIssue(
                    face,
                    "unresolved_reference",
                    "Face contains unresolved edge or vertex references",
                )
            )
            continue
        try:
            if len(pairs) < 3 or any(
                pair[1] != pairs[(i + 1) % len(pairs)][0] for i, pair in enumerate(pairs)
            ):
                raise InvalidGeometry("Face does not form a closed boundary")
            ids = [pair[0] for pair in pairs]
            local = PolyhedralBRep.from_polygons(raw.vertices[ids], [range(len(ids))])
            if len(set(ids)) != len(ids):
                raise InvalidGeometry("Face repeats a source vertex")
            emitted = local.triangulate_face(0)
            triangles.extend((ids[a], ids[b], ids[c]) for a, b, c in emitted)
            owners.extend([face] * len(emitted))
        except InvalidGeometry as exc:
            boundaries.extend(pairs)
            boundary_owners.extend([face] * len(pairs))
            issues.append(DisplayIssue(face, "unsupported_face", str(exc)))
    return DisplayGeometry(
        np.asarray(triangles, dtype=np.int64).reshape(-1, 3),
        np.asarray(owners, dtype=np.int64),
        np.asarray(boundaries, dtype=np.int64).reshape(-1, 2),
        np.asarray(boundary_owners, dtype=np.int64),
        tuple(issues),
    )


@dataclass(frozen=True, slots=True)
class CategoryMembership:
    category: str
    kind: EntityKind
    entity_ids: tuple[int, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "entity_ids", tuple(self.entity_ids))


_CATEGORIES: tuple[tuple[str, EntityKind, str], ...] = (
    ("nonmanifold_vertices", "vertex", "nonmanifold_vertex_ids"),
    ("unused_vertices", "vertex", "unused_vertex_ids"),
    ("boundary_edges", "edge", "boundary_edge_ids"),
    ("nonmanifold_edges", "edge", "nonmanifold_edge_ids"),
    ("winding_conflicts", "edge", "inconsistent_orientation_edge_ids"),
    ("unused_edges", "edge", "unused_edge_ids"),
    ("collapsed_edges", "edge", "collapsed_edge_ids"),
    ("invalid_faces", "polygonal_face", "invalid_face_ids"),
    ("duplicate_faces", "polygonal_face", "duplicate_face_ids"),
)


@dataclass(frozen=True, slots=True)
class MeshScope:
    mesh_id: str
    revision: str


@dataclass(frozen=True, slots=True)
class MeshInspection:
    stage: Literal["original", "candidate"]
    scope: MeshScope
    frame_id: str
    length_unit: str
    vertices: FloatArray
    edges: IntArray
    face_offsets: IntArray
    face_coedges: IntArray
    categories: tuple[CategoryMembership, ...]
    display: DisplayGeometry

    def __post_init__(self) -> None:
        object.__setattr__(self, "categories", tuple(self.categories))
        # Immutable bytes own the storage: setflags(write=True) cannot reopen it.
        for name in ("vertices", "edges", "face_offsets", "face_coedges"):
            values = getattr(self, name)
            owned = _immutable(values)
            object.__setattr__(self, name, owned)


@dataclass(frozen=True, slots=True)
class InspectionSnapshot:
    original: MeshInspection
    candidate: MeshInspection | None


def project_polygonal_inspection(
    result: RepairResult, *, limits: ProjectionLimits = ProjectionLimits()
) -> InspectionSnapshot:
    """Own computed polygonal data without backend lookups or side effects."""
    limits.preflight(
        (result.original,) + ((result.candidate,) if result.candidate is not None else ())
    )

    def project(
        brep: PolyhedralBRep, report: TopologyReport, stage: Literal["original", "candidate"]
    ) -> MeshInspection:
        return MeshInspection(
            stage,
            MeshScope(stage, fingerprint(brep)),
            "source",
            brep.length_unit,
            brep.vertices,
            brep.edges,
            brep.face_offsets,
            brep.face_coedges,
            tuple(
                CategoryMembership(name, kind, getattr(report, field))
                for name, kind, field in _CATEGORIES
            ),
            triangulate_for_inspection(brep, limits=limits),
        )

    return InspectionSnapshot(
        project(result.original, result.report.before, "original"),
        project(result.candidate, result.report.after, "candidate")
        if result.candidate is not None and result.report.after is not None
        else None,
    )


@dataclass(frozen=True, slots=True)
class NativeMeshInspection:
    """Owned native-face display; tessellation vertices are not native entities."""

    stage: Literal["original", "candidate"]
    scope: MeshScope
    projection_id: str
    frame_id: str
    length_unit: str
    vertices: FloatArray
    face_count: int
    display: DisplayGeometry

    def __post_init__(self) -> None:
        object.__setattr__(self, "vertices", _immutable(self.vertices))


@dataclass(frozen=True, slots=True)
class NativeInspectionSnapshot:
    original: NativeMeshInspection | None
    candidate: NativeMeshInspection | None


def project_native_inspection(
    display: FaceTessellation, *, stage: Literal["original", "candidate"], revision: str,
    limits: ProjectionLimits = ProjectionLimits(),
) -> NativeMeshInspection:
    """Mint a snapshot-local scope; copy only checked display data, never shape handles."""
    mesh = display.mesh
    counts = (len(mesh.vertices), display.source_face_count, len(mesh.triangles))
    if any(count > limit for count, limit in zip(counts, (
        limits.max_vertices, limits.max_faces, limits.max_display_triangles,
    ), strict=True)):
        raise ResourceLimitExceeded("Native inspection geometry budget exceeded")
    if (mesh.vertices.size + mesh.triangles.size + len(display.triangle_face_ids)
            + display.source_face_count * 4) * 32 > limits.max_payload_bytes:
        raise ResourceLimitExceeded("Native inspection payload budget exceeded")
    owners = display.triangle_face_ids
    if (owners.shape != (len(mesh.triangles),) or np.any(owners < 0)
            or np.any(owners >= display.source_face_count)
            or any(i < 0 or i >= display.source_face_count for i in display.missing_face_ids)):
        raise InvalidGeometry("Native display face correspondence is invalid")
    geometry = DisplayGeometry(
        mesh.triangles, owners, np.empty((0, 2), dtype=np.int64),
        np.empty(0, dtype=np.int64),
        tuple(DisplayIssue(i, "missing_triangulation", "Native face interior unavailable")
              for i in display.missing_face_ids),
    )
    return NativeMeshInspection(
        stage, MeshScope(f"native-{uuid4().hex}", revision), uuid4().hex,
        "source", mesh.length_unit, mesh.vertices, display.source_face_count, geometry,
    )


def encode_inspection(snapshot: InspectionSnapshot | NativeInspectionSnapshot | None) -> dict[str, object]:
    """Versioned browser delivery; v1 triangle targets keep their old meaning."""
    meshes = []
    if snapshot is not None:
        for mesh in (snapshot.original, snapshot.candidate):
            if mesh is None:
                continue
            meshes.append(
                {
                    "id": mesh.scope.mesh_id,
                    "revision": mesh.scope.revision,
                    "stage": mesh.stage,
                    "frame_id": mesh.frame_id,
                    "length_unit": mesh.length_unit,
                    "positions": mesh.vertices.ravel().tolist(),
                    "edges": [] if isinstance(mesh, NativeMeshInspection) else mesh.edges.ravel().tolist(),
                    "face_count": mesh.face_count if isinstance(mesh, NativeMeshInspection) else len(mesh.face_offsets) - 1,
                    **({"face_kind": "native_face", "projection_id": mesh.projection_id}
                       if isinstance(mesh, NativeMeshInspection) else {}),
                    "triangles": mesh.display.triangles.ravel().tolist(),
                    "triangle_source_faces": mesh.display.triangle_source_faces.tolist(),
                    "boundary_segments": mesh.display.boundary_segments.ravel().tolist(),
                    "boundary_source_faces": mesh.display.boundary_source_faces.tolist(),
                    "categories": [
                        {"id": c.category, "kind": c.kind, "entity_ids": list(c.entity_ids)}
                        for c in (() if isinstance(mesh, NativeMeshInspection) else mesh.categories)
                    ],
                    "issues": [
                        {"face_id": i.face_id, "code": i.code, "detail": i.detail}
                        for i in mesh.display.issues
                    ],
                }
            )
    return {"schema_version": 3 if isinstance(snapshot, NativeInspectionSnapshot) else 2, "meshes": meshes}
