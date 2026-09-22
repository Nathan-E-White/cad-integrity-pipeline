"""Native STEP audit/repair/export using OCP (Open CASCADE Python bindings).

The native TopoDS shape is authoritative. It is never reconstructed from polygonal
arrays, mesh vertices, or endpoint chords. Supported repair scope is a single part
or an existing solid collection: ambiguous shell nesting is refused.

This module is an optional, synchronous adapter. Native parsing/meshing is not a
security sandbox; deploy it in resource-limited worker processes for untrusted uploads.
"""
from __future__ import annotations

import hashlib
import importlib.metadata
import logging
import math
import os
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from threading import RLock
from typing import Any

import numpy as np

from ..arrays import IntArray, positive
from ..errors import (
    ExportRejected,
    KernelOperationFailed,
    MissingOptionalDependency,
    RepairRejected,
    ResourceLimitExceeded,
)
from ..models import TriangleMesh
from ..pipeline import StageEvent

try:
    from OCP.BRep import BRep_Builder, BRep_Tool
    from OCP.BRepAdaptor import BRepAdaptor_Curve, BRepAdaptor_Surface
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Check
    from OCP.BRepBuilderAPI import (
        BRepBuilderAPI_Copy,
        BRepBuilderAPI_MakeSolid,
        BRepBuilderAPI_Sewing,
    )
    from OCP.BRepCheck import BRepCheck_Analyzer, BRepCheck_NoError, BRepCheck_Shell
    from OCP.BRepExtrema import BRepExtrema_DistShapeShape
    from OCP.BRepGProp import BRepGProp
    from OCP.BRepLib import BRepLib
    from OCP.BRepMesh import BRepMesh_IncrementalMesh
    from OCP.BRepTools import BRepTools
    from OCP.GProp import GProp_GProps
    from OCP.IFSelect import IFSelect_RetDone
    from OCP.ShapeExtend import ShapeExtend_FAIL
    from OCP.ShapeFix import ShapeFix_Shape
    from OCP.STEPControl import STEPControl_AsIs, STEPControl_Reader, STEPControl_Writer
    from OCP.TColStd import TColStd_SequenceOfAsciiString
    from OCP.TopAbs import (
        TopAbs_EDGE,
        TopAbs_FACE,
        TopAbs_REVERSED,
        TopAbs_SHELL,
        TopAbs_SOLID,
        TopAbs_VERTEX,
    )
    from OCP.TopExp import TopExp, TopExp_Explorer
    from OCP.TopLoc import TopLoc_Location
    from OCP.TopoDS import TopoDS, TopoDS_Compound, TopoDS_Shape
    from OCP.TopTools import TopTools_IndexedMapOfShape
except ImportError as exc:
    raise MissingOptionalDependency("Install cad-integrity-lab[cad] to use the native STEP adapter") from exc

logger = logging.getLogger(__name__)
# STEP translator configuration has process-global state in OCCT. This module serializes
# its own translator operations; it cannot protect unrelated OCP calls made by other code.
_TRANSLATOR_LOCK = RLock()


def _map(shape: TopoDS_Shape, kind: Any) -> Any:
    result = TopTools_IndexedMapOfShape()
    TopExp.MapShapes_s(shape, kind, result)
    return result


def _shapes(shape: TopoDS_Shape, kind: Any) -> list[TopoDS_Shape]:
    mapping = _map(shape, kind)
    return [mapping.FindKey(i) for i in range(1, mapping.Extent()+1)]


def _volume(shape: TopoDS_Shape) -> float:
    properties = GProp_GProps()
    BRepGProp.VolumeProperties_s(shape, properties)
    return float(properties.Mass())


def _area(shape: TopoDS_Shape) -> float:
    properties = GProp_GProps()
    BRepGProp.SurfaceProperties_s(shape, properties)
    return float(properties.Mass())


@dataclass(frozen=True, slots=True)
class KernelPolicy:
    precision_mm: float = 1e-6
    maximum_tolerance_mm: float = 1e-3
    expected_solids: int = 1
    run_self_interference_check: bool = True
    max_input_bytes: int = 50_000_000
    max_relative_area_change: float = 1e-4
    max_relative_volume_change: float = 1e-4
    allow_face_count_change: bool = False

    def __post_init__(self) -> None:
        positive(self.precision_mm, "precision_mm")
        positive(self.maximum_tolerance_mm, "maximum_tolerance_mm")
        positive(self.max_relative_area_change, "max_relative_area_change", allow_zero=True)
        positive(self.max_relative_volume_change, "max_relative_volume_change", allow_zero=True)
        if self.precision_mm > self.maximum_tolerance_mm:
            raise ValueError("precision_mm cannot exceed maximum_tolerance_mm")
        if any(isinstance(v, bool) or not isinstance(v, int) or v < 1
               for v in (self.expected_solids, self.max_input_bytes)):
            raise ValueError("Expected solid count and input-byte budget must be positive integers")


@dataclass(frozen=True, slots=True)
class StepDocument:
    shape: TopoDS_Shape  # Native handles are mutable; do not share across worker processes.
    source: Path
    source_sha256: str
    source_unit_names: tuple[str, ...]
    roots_transferred: int
    length_unit: str = "mm"
    import_scope: str = "OCCT_imported_shape_not_unmodified_generator_internal_state"


@dataclass(frozen=True, slots=True)
class KernelReport:
    kernel_binding_version: str
    valid_by_brepcheck: bool
    self_interference_check_passed: bool | None
    vertex_count: int
    edge_count: int
    face_count: int
    shell_count: int
    solid_count: int
    free_edge_ids: tuple[int, ...]
    nonmanifold_edge_ids: tuple[int, ...]
    unowned_edge_ids: tuple[int, ...]
    unowned_vertex_ids: tuple[int, ...]
    degenerate_edge_count: int
    shells_closed_and_oriented: bool
    every_face_belongs_to_solid: bool
    solid_volumes_mm3: tuple[float, ...]
    surface_area_mm2: float
    maximum_entity_tolerance_mm: float
    surface_types: tuple[tuple[str, int], ...]
    acceptance_reasons: tuple[str, ...]
    accepted_under_policy: bool
    homology: None = None
    homology_scope: str = "not_computed_for_general_trimmed_native_faces"
    certification: str = "none_kernel_policy_checks_only"


@dataclass(frozen=True, slots=True)
class NativeEdgeOwnership:
    """Locally indexed edge evidence; IDs are only valid for this source shape."""

    edge_id: int
    face_ids: tuple[int, ...]
    face_occurrence_count: int
    closed_on_face_ids: tuple[int, ...]
    vertex_ids: tuple[int, ...]
    degenerate: bool


@dataclass(frozen=True, slots=True)
class FreeBoundaryWire:
    """A derived connected group of free native edges, with retained provenance."""

    wire_id: int
    edge_ids: tuple[int, ...]
    vertex_ids: tuple[int, ...]
    face_ids: tuple[int, ...]
    scope: str = "derived_connected_free_edge_group_not_OCCT_wire_reconstruction"


@dataclass(frozen=True, slots=True)
class PeriodicFaceEvidence:
    face_id: int
    surface_type: str
    u_periodic: bool
    v_periodic: bool
    degenerate_edge_ids: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class ToleranceDistribution:
    entity_kind: str
    count: int
    minimum_mm: float | None
    maximum_mm: float | None


@dataclass(frozen=True, slots=True)
class CandidatePairEvidence:
    """A bounded distance observation, never a statement of intended adjacency."""

    first_edge_id: int
    second_edge_id: int
    minimum_distance_mm: float


@dataclass(frozen=True, slots=True)
class UnsupportedFact:
    status: str
    reason: str


@dataclass(frozen=True, slots=True)
class ClassificationConfidence:
    level: str
    basis: str
    limitations: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class NativeDefectReport:
    """Read-only native topology evidence; no repair candidate is selected here."""

    audit: KernelReport
    source_fingerprint_sha256: str
    edge_ownership: tuple[NativeEdgeOwnership, ...]
    free_boundary_wires: tuple[FreeBoundaryWire, ...]
    periodic_faces: tuple[PeriodicFaceEvidence, ...]
    shell_face_ids: tuple[tuple[int, ...], ...]
    tolerance_distribution: tuple[ToleranceDistribution, ...]
    candidate_pairs: tuple[CandidatePairEvidence, ...]
    candidate_pair_comparisons: int
    candidate_pair_comparison_limit_reached: bool
    candidate_pair_scope: str
    classification_confidence: ClassificationConfidence
    self_intersection: UnsupportedFact
    design_intent: UnsupportedFact
    source_scope: str = "read_only_OCCT_topology_and_distance_evidence"


def _tolerance_distribution(entity_kind: str, values: list[float]) -> ToleranceDistribution:
    return ToleranceDistribution(entity_kind, len(values), min(values, default=None), max(values, default=None))


def _native_shape_fingerprint(shape: TopoDS_Shape) -> str:
    descriptor, filename = tempfile.mkstemp(prefix=".cad-integrity-fingerprint-", suffix=".brep")
    os.close(descriptor)
    temporary = Path(filename)
    try:
        if not BRepTools.Write_s(shape, str(temporary)):
            raise KernelOperationFailed("OCCT could not serialize shape fingerprint evidence")
        with temporary.open("rb") as stream:
            return hashlib.file_digest(stream, "sha256").hexdigest()
    finally:
        temporary.unlink(missing_ok=True)


def classify_native_defects(shape: TopoDS_Shape, policy: KernelPolicy = KernelPolicy(), *,
                            max_candidate_pair_comparisons: int = 256) -> NativeDefectReport:
    """Return bounded native evidence without changing *shape* or selecting a repair.

    Candidate pairs are free edges whose OCCT minimum distance is at most the
    named repair precision.  They are observations only: proximity cannot recover
    feature history or establish that two entities were intended to be joined.
    """
    if (isinstance(max_candidate_pair_comparisons, bool)
            or not isinstance(max_candidate_pair_comparisons, int)
            or max_candidate_pair_comparisons < 0):
        raise ValueError("max_candidate_pair_comparisons must be a nonnegative integer")
    audit = audit_shape(shape, policy)
    fingerprint = _native_shape_fingerprint(shape)
    vertices = _map(shape, TopAbs_VERTEX)
    edges = _map(shape, TopAbs_EDGE)
    faces = _shapes(shape, TopAbs_FACE)
    face_map = _map(shape, TopAbs_FACE)
    edge_faces: list[set[int]] = [set() for _ in range(edges.Extent())]
    edge_occurrences = [0 for _ in range(edges.Extent())]
    closed_on_faces: list[set[int]] = [set() for _ in range(edges.Extent())]
    edge_vertices: list[tuple[int, ...]] = []
    periodic: list[PeriodicFaceEvidence] = []
    edge_tolerances: list[float] = []
    face_tolerances: list[float] = []
    vertex_tolerances: list[float] = []
    degenerate_ids = {i for i in range(edges.Extent())
                      if BRep_Tool.Degenerated_s(TopoDS.Edge_s(edges.FindKey(i+1)))}
    free_ids = set(audit.free_edge_ids)
    for edge_id in range(edges.Extent()):
        edge = TopoDS.Edge_s(edges.FindKey(edge_id+1))
        edge_tolerances.append(float(BRep_Tool.Tolerance_s(edge)))
        edge_vertices.append(tuple(vertices.FindIndex(vertex)-1 for vertex in _shapes(edge, TopAbs_VERTEX)))
    for face_id, face_shape in enumerate(faces):
        face = TopoDS.Face_s(face_shape)
        face_tolerances.append(float(BRep_Tool.Tolerance_s(face)))
        adaptor = BRepAdaptor_Surface(face)
        face_degenerate: list[int] = []
        explorer = TopExp_Explorer(face, TopAbs_EDGE)
        while explorer.More():
            edge_id = edges.FindIndex(explorer.Current())-1
            edge_faces[edge_id].add(face_id)
            edge_occurrences[edge_id] += 1
            if BRep_Tool.IsClosed_s(TopoDS.Edge_s(edges.FindKey(edge_id+1)), face):
                closed_on_faces[edge_id].add(face_id)
            if edge_id in degenerate_ids:
                face_degenerate.append(edge_id)
            explorer.Next()
        periodic.append(PeriodicFaceEvidence(face_id, adaptor.GetType().name,
                                             bool(adaptor.IsUPeriodic()), bool(adaptor.IsVPeriodic()),
                                             tuple(sorted(face_degenerate))))
    for vertex_id in range(vertices.Extent()):
        vertex_tolerances.append(float(BRep_Tool.Tolerance_s(TopoDS.Vertex_s(vertices.FindKey(vertex_id+1)))))
    ownership = tuple(NativeEdgeOwnership(edge_id, tuple(sorted(edge_faces[edge_id])), edge_occurrences[edge_id],
                                          tuple(sorted(closed_on_faces[edge_id])), edge_vertices[edge_id],
                                          edge_id in degenerate_ids)
                      for edge_id in range(edges.Extent()))
    free_by_vertex: dict[int, set[int]] = {}
    for edge_id in free_ids:
        for vertex_id in edge_vertices[edge_id]:
            free_by_vertex.setdefault(vertex_id, set()).add(edge_id)
    remaining = set(free_ids)
    free_wires: list[FreeBoundaryWire] = []
    while remaining:
        pending = [min(remaining)]
        component: set[int] = set()
        while pending:
            edge_id = pending.pop()
            if edge_id not in remaining:
                continue
            remaining.remove(edge_id)
            component.add(edge_id)
            for vertex_id in edge_vertices[edge_id]:
                pending.extend(free_by_vertex[vertex_id] & remaining)
        component_vertices = tuple(sorted({vertex_id for edge_id in component for vertex_id in edge_vertices[edge_id]}))
        component_faces = tuple(sorted({face_id for edge_id in component for face_id in edge_faces[edge_id]}))
        free_wires.append(FreeBoundaryWire(len(free_wires), tuple(sorted(component)), component_vertices, component_faces))
    shell_faces = tuple(tuple(sorted(face_map.FindIndex(face)-1 for face in _shapes(shell, TopAbs_FACE)))
                        for shell in _shapes(shape, TopAbs_SHELL))
    candidates: list[CandidatePairEvidence] = []
    comparisons = 0
    possible_comparisons = len(audit.free_edge_ids)*(len(audit.free_edge_ids)-1)//2
    for offset, first_id in enumerate(audit.free_edge_ids):
        if comparisons >= max_candidate_pair_comparisons:
            break
        first = edges.FindKey(first_id+1)
        for second_id in audit.free_edge_ids[offset+1:]:
            if comparisons >= max_candidate_pair_comparisons:
                break
            comparisons += 1
            distance = BRepExtrema_DistShapeShape(first, edges.FindKey(second_id+1))
            distance.Perform()
            if not distance.IsDone():
                continue
            value = float(distance.Value())
            if math.isfinite(value) and value <= policy.precision_mm:
                candidates.append(CandidatePairEvidence(first_id, second_id, value))
    return NativeDefectReport(
        audit, fingerprint, ownership, tuple(free_wires), tuple(periodic), shell_faces,
        (_tolerance_distribution("face", face_tolerances),
         _tolerance_distribution("edge", edge_tolerances),
         _tolerance_distribution("vertex", vertex_tolerances)),
        tuple(candidates), comparisons, comparisons < possible_comparisons,
        "Pairs are bounded OCCT edge-distance observations within policy.precision_mm; max_candidate_pair_comparisons caps comparisons, not design intent or repair selection.",
        ClassificationConfidence(
            "kernel_evidence_only",
            "Locally indexed OCCT topology, tolerances, periodicity, and completed distance witnesses.",
            ("No intended mate or feature history is inferred from proximity.",
             "No dedicated native self-intersection pair classifier is established.",
             "This is not a general CAD-validity or engineering-certification claim."),
        ),
        UnsupportedFact("not_established", "This adapter does not run a dedicated native self-intersection classifier."),
        UnsupportedFact("not_established", "Geometric proximity cannot establish intended adjacency or feature history."),
    )


def read_step(path: str | Path, *, max_bytes: int = 50_000_000) -> StepDocument:
    source = Path(path).expanduser().resolve(strict=True)
    if not source.is_file() or source.suffix.lower() not in {".step", ".stp"}:
        raise ValueError("Expected a regular .step or .stp file")
    if source.stat().st_size > max_bytes:
        raise ResourceLimitExceeded("STEP input exceeds the configured byte budget")
    # Hash in bounded chunks rather than duplicating a potentially large upload in RAM.
    digest = hashlib.sha256()
    with source.open("rb") as stream:
        while chunk := stream.read(1 << 20):
            digest.update(chunk)
    with _TRANSLATOR_LOCK:
        reader = STEPControl_Reader()
        if reader.ReadFile(str(source)) != IFSelect_RetDone:
            raise KernelOperationFailed(f"OCCT could not read STEP input {source.name}")
        length = TColStd_SequenceOfAsciiString()
        angle = TColStd_SequenceOfAsciiString()
        solid_angle = TColStd_SequenceOfAsciiString()
        reader.FileUnits(length, angle, solid_angle)
        units = tuple(length.Value(i).ToCString() for i in range(1, length.Length()+1))
        # OCCT's system-length unit is expressed in millimetres. Normalize to mm.
        reader.SetSystemLengthUnit(1.0)
        expected_roots = reader.NbRootsForTransfer()
        transferred = int(reader.TransferRoots())
        if expected_roots < 1 or transferred != expected_roots or reader.NbShapes() < 1:
            raise KernelOperationFailed("STEP transfer was empty or incomplete")
        shape = reader.OneShape()
        if shape.IsNull():
            raise KernelOperationFailed("STEP transfer produced a null shape")
    return StepDocument(shape, source, digest.hexdigest(), units, transferred)


def audit_shape(shape: TopoDS_Shape, policy: KernelPolicy = KernelPolicy()) -> KernelReport:
    if shape.IsNull():
        raise KernelOperationFailed("Cannot audit a null shape")
    vertices = _map(shape, TopAbs_VERTEX)
    edges = _map(shape, TopAbs_EDGE)
    faces = _shapes(shape, TopAbs_FACE)
    shells = _shapes(shape, TopAbs_SHELL)
    solids = _shapes(shape, TopAbs_SOLID)
    counts = np.zeros(edges.Extent(), dtype=np.int64)
    on_faces_vertices: set[int] = set()
    types: dict[str, int] = {}
    tolerances = []
    for face_shape in faces:
        face = TopoDS.Face_s(face_shape)
        name = BRepAdaptor_Surface(face).GetType().name
        types[name] = types.get(name, 0)+1
        tolerances.append(float(BRep_Tool.Tolerance_s(face)))
        # Count oriented occurrences, NOT distinct face neighbors. A seam can appear
        # twice on the SAME periodic face and is not necessarily a free boundary.
        explorer = TopExp_Explorer(face, TopAbs_EDGE)
        while explorer.More():
            edge_id = edges.FindIndex(explorer.Current())-1
            if edge_id < 0:
                raise KernelOperationFailed("Inconsistent native edge index map")
            counts[edge_id] += 1
            explorer.Next()
        for vertex in _shapes(face, TopAbs_VERTEX):
            on_faces_vertices.add(vertices.FindIndex(vertex)-1)
    degenerated: set[int] = set()
    for i in range(edges.Extent()):
        edge = TopoDS.Edge_s(edges.FindKey(i+1))
        tolerances.append(float(BRep_Tool.Tolerance_s(edge)))
        if BRep_Tool.Degenerated_s(edge):
            degenerated.add(i)
    for i in range(vertices.Extent()):
        tolerances.append(float(BRep_Tool.Tolerance_s(TopoDS.Vertex_s(vertices.FindKey(i+1)))))
    max_tolerance = max(tolerances, default=0.0)
    closed_oriented = bool(shells)
    for shell in shells:
        check = BRepCheck_Shell(TopoDS.Shell_s(shell))
        if check.Closed() != BRepCheck_NoError or check.Orientation() != BRepCheck_NoError:
            closed_oriented = False
    solid_faces = TopTools_IndexedMapOfShape()
    for solid in solids:
        TopExp.MapShapes_s(solid, TopAbs_FACE, solid_faces)
    all_faces_owned = bool(faces) and all(solid_faces.Contains(face) for face in faces)
    checker = BRepCheck_Analyzer(shape, True)
    checker.SetExactMethod(True)
    valid = bool(checker.IsValid())
    interference = (bool(BRepAlgoAPI_Check(shape, True, True).IsValid())
                    if policy.run_self_interference_check else None)
    free = tuple(i for i, count in enumerate(counts) if count == 1 and i not in degenerated)
    multiple = tuple(i for i, count in enumerate(counts) if count > 2 and i not in degenerated)
    unowned = tuple(int(i) for i in np.flatnonzero(counts == 0))
    unowned_vertices = tuple(sorted(set(range(vertices.Extent()))-on_faces_vertices))
    volumes = tuple(_volume(solid) for solid in solids)
    area = _area(shape)
    reasons = []
    if not valid:
        reasons.append("BRepCheck reported an invalid shape")
    if interference is not True:
        reasons.append("Self-interference/Boolean suitability check failed or was not run")
    if len(solids) != policy.expected_solids:
        reasons.append(f"Expected {policy.expected_solids} solid(s), found {len(solids)}")
    if not closed_oriented:
        reasons.append("Not every shell is closed and coherently oriented")
    if not all_faces_owned:
        reasons.append("Some faces do not belong to a solid")
    if free or multiple or unowned or unowned_vertices:
        reasons.append("Free, nonmanifold, or unowned topology remains")
    if not volumes or any(not math.isfinite(v) or v <= 0 for v in volumes):
        reasons.append("Each accepted solid must have finite positive signed volume")
    if not math.isfinite(area) or area <= 0:
        reasons.append("Surface area is nonpositive or nonfinite")
    if not math.isfinite(max_tolerance) or max_tolerance > policy.maximum_tolerance_mm:
        reasons.append("Entity tolerance exceeds the configured millimetre budget")
    return KernelReport(importlib.metadata.version("cadquery-ocp"), valid, interference,
                        vertices.Extent(), edges.Extent(), len(faces), len(shells), len(solids),
                        free, multiple, unowned, unowned_vertices, len(degenerated), closed_oriented,
                        all_faces_owned, volumes, area, max_tolerance, tuple(sorted(types.items())),
                        tuple(reasons), not reasons)


@dataclass(frozen=True, slots=True)
class NativeRepairResult:
    candidate: TopoDS_Shape
    before: KernelReport
    after: KernelReport
    operations: tuple[str, ...]
    geometry_fidelity_certified: bool = False


@dataclass(frozen=True, slots=True)
class SelectedNativeSewingResult:
    """A private, classifier-backed local sewing attempt and its kernel evidence."""

    candidate: TopoDS_Shape
    before: KernelReport
    after: KernelReport
    source_fingerprint_sha256: str
    selected_wire_ids: tuple[int, ...]
    selected_edge_ids: tuple[int, ...]
    operations: tuple[str, ...]
    selection_scope: str = "explicit_classifier_backed_free_boundary_wire_selection"
    geometry_fidelity_certified: bool = False


def sew_selected_native_boundaries(shape: TopoDS_Shape, evidence: NativeDefectReport,
                                   selected_wire_ids: tuple[int, ...],
                                   policy: KernelPolicy = KernelPolicy()) -> SelectedNativeSewingResult:
    """Sew an explicitly selected classifier-issued set of free-boundary wires.

    The classifier's local IDs are valid only for the exact source fingerprint.
    This intentionally refuses partial *open-boundary* selections: preserving
    unselected open faces while returning a kernel-accepted solid would require
    an additional, explicit topology-reconstruction contract.
    """
    before = audit_shape(shape, policy)
    fingerprint = _native_shape_fingerprint(shape)
    if evidence.source_fingerprint_sha256 != fingerprint:
        raise RepairRejected("Classifier evidence does not match the supplied native source")
    if evidence.audit != before:
        raise RepairRejected("Classifier evidence policy/audit does not match the supplied native source")
    if not selected_wire_ids:
        raise RepairRejected("An explicit nonempty classifier-backed selection is required")
    wires = {wire.wire_id: wire for wire in evidence.free_boundary_wires}
    if len(set(selected_wire_ids)) != len(selected_wire_ids):
        raise RepairRejected("Selected free-boundary wire IDs must be unique")
    selected = tuple(sorted(selected_wire_ids))
    if any(wire_id not in wires for wire_id in selected):
        raise RepairRejected("Selected free-boundary wire ID is absent from classifier evidence")
    selected_edges = tuple(sorted({edge_id for wire_id in selected for edge_id in wires[wire_id].edge_ids}))
    unselected_edges = tuple(sorted(set(before.free_edge_ids)-set(selected_edges)))
    if unselected_edges:
        raise RepairRejected(
            "Refusing partial sewing: every free-boundary wire must be explicitly selected "
            "before a kernel-accepted whole-shape candidate can be returned"
        )
    if before.unowned_edge_ids or before.unowned_vertex_ids:
        raise RepairRejected("Input contains unowned edges or vertices; refusing to discard them")
    if selected_edges != before.free_edge_ids:
        raise RepairRejected("Classifier wire evidence does not cover exactly the audited free boundaries")
    # Copy selected source faces into a private compound.  This is the only shape
    # passed to OCCT Sewing; no global proximity search or mate inference is used.
    source_faces = _shapes(shape, TopAbs_FACE)
    selected_face_ids = sorted({face_id for wire_id in selected for face_id in wires[wire_id].face_ids})
    selected_face_set = set(selected_face_ids)
    existing_solids = _shapes(shape, TopAbs_SOLID)
    owned_face_ids = {
        face_id for face_id, face in enumerate(source_faces)
        if any(_map(solid, TopAbs_FACE).Contains(face) for solid in existing_solids)
    }
    if selected_face_set & owned_face_ids:
        raise RepairRejected("Selected free-boundary wires overlap an existing solid; local sewing is ambiguous")
    if set(range(len(source_faces)))-selected_face_set-owned_face_ids:
        raise RepairRejected("Unselected faces are not owned by preserved solids; topology reconstruction is ambiguous")
    compound = TopoDS_Compound()
    builder = BRep_Builder()
    builder.MakeCompound(compound)
    for face_id in selected_face_ids:
        builder.Add(compound, BRepBuilderAPI_Copy(source_faces[face_id], True, False).Shape())
    sewing = BRepBuilderAPI_Sewing(policy.precision_mm, True, True, True, False)
    sewing.SetMaxTolerance(policy.maximum_tolerance_mm)
    sewing.Add(compound)
    sewing.Perform()
    sewed = sewing.SewedShape()
    if sewed.IsNull():
        raise RepairRejected("Selected native sewing produced no candidate shape")
    shells = _shapes(sewed, TopAbs_SHELL)
    if len(shells) != 1:
        raise RepairRejected("Selected sewing did not yield one unambiguous shell")
    shell = TopoDS.Shell_s(shells[0])
    if not BRep_Tool.IsClosed_s(shell):
        raise RepairRejected("Selected sewing leaves an open shell; no hole filling is authorized")
    shell_faces = _map(shell, TopAbs_FACE)
    if not all(shell_faces.Contains(face) for face in _shapes(sewed, TopAbs_FACE)):
        raise RepairRejected("Selected sewing left detached faces; refusing to discard them")
    maker = BRepBuilderAPI_MakeSolid(shell)
    if not maker.IsDone():
        raise RepairRejected("Selected closed-shell solid construction failed")
    selected_solid = maker.Solid()
    if not BRepLib.OrientClosedSolid_s(selected_solid):
        raise RepairRejected("Cannot establish a valid material orientation after selected sewing")
    candidate = TopoDS_Compound()
    builder = BRep_Builder()
    builder.MakeCompound(candidate)
    builder.Add(candidate, selected_solid)
    for solid in existing_solids:
        builder.Add(candidate, BRepBuilderAPI_Copy(solid, True, False).Shape())
    after = audit_shape(candidate, policy)
    if not policy.allow_face_count_change and after.face_count != before.face_count:
        raise RepairRejected("Selected sewing changed face count; explicit review is required")
    if before.surface_area_mm2 > 0:
        area_change = abs(after.surface_area_mm2/before.surface_area_mm2-1)
        if area_change > policy.max_relative_area_change:
            raise RepairRejected("Selected sewing exceeds surface-area policy (not a surface-distance proof)")
    if before.solid_count == after.solid_count and before.solid_volumes_mm3:
        volume_change = abs(sum(after.solid_volumes_mm3)/sum(before.solid_volumes_mm3)-1)
        if volume_change > policy.max_relative_volume_change:
            raise RepairRejected("Selected sewing exceeds volume-change policy")
    if not after.accepted_under_policy:
        raise RepairRejected("Selected sewing candidate failed kernel policy: " + "; ".join(after.acceptance_reasons))
    return SelectedNativeSewingResult(
        candidate, before, after, fingerprint, selected, selected_edges,
        ("BRepBuilderAPI_Sewing on explicitly selected classified free-boundary wires; "
         "nonmanifold mode disabled", "One closed shell converted to an oriented solid"),
    )


def repair_shape(shape: TopoDS_Shape, policy: KernelPolicy = KernelPolicy(),
                 *, on_event: Callable[[StageEvent], None] | None = None) -> NativeRepairResult:
    def event(stage: str, message: str) -> None:
        logger.info("%s: %s", stage, message)
        if on_event:
            on_event(StageEvent(stage, message))

    before = audit_shape(shape, policy)
    if before.unowned_edge_ids or before.unowned_vertex_ids:
        raise RepairRejected("Input contains unowned edges or vertices; refusing to discard them")
    # Copy native topology AND geometry before any mutating healing tool.
    candidate = BRepBuilderAPI_Copy(shape, True, False).Shape()
    if before.accepted_under_policy:
        return NativeRepairResult(candidate, before, audit_shape(candidate, policy), ("No repair needed",))
    event("shape_fix", "Applying bounded OCCT ShapeFix to a private copy")
    fixer = ShapeFix_Shape(candidate)
    fixer.SetPrecision(policy.precision_mm)
    fixer.SetMinTolerance(min(policy.precision_mm, 1e-7))
    fixer.SetMaxTolerance(policy.maximum_tolerance_mm)
    fixer.Perform()
    if fixer.Status(ShapeExtend_FAIL):
        raise RepairRejected("OCCT ShapeFix reported a repair failure")
    candidate = fixer.Shape()
    operations = ["ShapeFix_Shape on copied native geometry"]
    # Do not flatten an existing multi-shell solid: its inner shell may be a cavity.
    # A generic repair must never turn proximity into a guessed sewing selection.
    if not _shapes(candidate, TopAbs_SOLID):
        raise RepairRejected(
            "Native sewing requires an explicit classifier-backed selection; "
            "use classify_native_defects then sew_selected_native_boundaries"
        )
    after = audit_shape(candidate, policy)
    if not policy.allow_face_count_change and after.face_count != before.face_count:
        raise RepairRejected("Face count changed; explicit review is required")
    if before.surface_area_mm2 > 0:
        area_change = abs(after.surface_area_mm2/before.surface_area_mm2-1)
        if area_change > policy.max_relative_area_change:
            raise RepairRejected("Surface-area change exceeds policy (not a surface-distance proof)")
    if before.solid_volumes_mm3 and all(v > 0 for v in before.solid_volumes_mm3):
        volume_before = sum(before.solid_volumes_mm3)
        change = abs(sum(after.solid_volumes_mm3)/volume_before-1)
        if change > policy.max_relative_volume_change:
            raise RepairRejected("Volume change exceeds policy")
    if not after.accepted_under_policy:
        raise RepairRejected("Candidate failed kernel policy: " + "; ".join(after.acceptance_reasons))
    return NativeRepairResult(candidate, before, after, tuple(operations))


def _write_native(shape: TopoDS_Shape, path: Path) -> None:
    with _TRANSLATOR_LOCK:
        writer = STEPControl_Writer()
        model = writer.Model()
        model.SetLocalLengthUnit(1.0)
        model.SetWriteLengthUnit(1.0)
        if writer.Transfer(shape, STEPControl_AsIs) != IFSelect_RetDone:
            raise KernelOperationFailed("STEP writer could not transfer the shape")
        if writer.Write(str(path)) != IFSelect_RetDone or path.stat().st_size == 0:
            raise KernelOperationFailed("STEP writer failed to create a nonempty file")


@dataclass(frozen=True, slots=True)
class ExportReport:
    output: Path
    output_sha256: str
    before_serialization: KernelReport
    after_roundtrip: KernelReport
    label: str = "STEP_passed_configured_kernel_checks_not_engineering_certification"


def export_checked_step(shape: TopoDS_Shape, destination: str | Path,
                        policy: KernelPolicy = KernelPolicy(), *, overwrite: bool = False) -> ExportReport:
    """Audit -> temporary STEP -> read back -> audit -> atomic publish.

    No native export from tessellated arrays. No target is published on validation
    failure. The source and any prior destination are preserved by default.
    """
    target = Path(destination).expanduser().resolve()
    if target.suffix.lower() not in {".step", ".stp"}:
        raise ValueError("STEP destination needs .step or .stp extension")
    if not target.parent.is_dir():
        raise FileNotFoundError(target.parent)
    if target.exists() and not overwrite:
        raise FileExistsError(target)
    before = audit_shape(shape, policy)
    if not before.accepted_under_policy:
        raise ExportRejected("Export gate: " + "; ".join(before.acceptance_reasons))
    fd, temporary_name = tempfile.mkstemp(prefix=".cad-integrity-", suffix=".step", dir=target.parent)
    os.close(fd)
    temporary = Path(temporary_name)
    try:
        _write_native(shape, temporary)
        # Re-use the byte-budget check for the generated file as well.
        reread = read_step(temporary, max_bytes=policy.max_input_bytes)
        after = audit_shape(reread.shape, policy)
        if not after.accepted_under_policy:
            raise ExportRejected("STEP round trip failed: " + "; ".join(after.acceptance_reasons))
        if (before.solid_count != after.solid_count or before.face_count != after.face_count
                or before.surface_types != after.surface_types):
            raise ExportRejected("STEP round trip changed solid/face counts or analytic surface types")
        if not math.isclose(before.surface_area_mm2, after.surface_area_mm2, rel_tol=1e-7, abs_tol=1e-10):
            raise ExportRejected("STEP round trip changed measured surface area")
        if not math.isclose(sum(before.solid_volumes_mm3), sum(after.solid_volumes_mm3),
                            rel_tol=1e-7, abs_tol=1e-10):
            raise ExportRejected("STEP round trip changed measured solid volume")
        with temporary.open("rb") as stream:
            os.fsync(stream.fileno())
        if overwrite:
            os.replace(temporary, target)
        else:
            # Hard-link creation is atomic and refuses an existing destination, even
            # when another caller creates it after the initial exists() check.
            os.link(temporary, target)
            temporary.unlink()
        return ExportReport(target, reread.source_sha256, before, after)
    finally:
        temporary.unlink(missing_ok=True)


def run_step_pipeline(source: str | Path, destination: str | Path,
                      policy: KernelPolicy = KernelPolicy(), *, repair: bool = True,
                      on_event: Callable[[StageEvent], None] | None = None) -> dict[str, Any]:
    """Local STEP entry point; report sidecars are explicit caller-owned outputs."""
    if Path(source).resolve() == Path(destination).resolve():
        raise ValueError("Input and output must differ; this pipeline never overwrites the source")
    document = read_step(source, max_bytes=policy.max_input_bytes)
    if repair:
        candidate = repair_shape(document.shape, policy, on_event=on_event)
        exported = export_checked_step(candidate.candidate, destination, policy)
        before, operations = candidate.before, candidate.operations
    else:
        before = audit_shape(document.shape, policy)
        operations = ("Repair disabled",)
        exported = export_checked_step(document.shape, destination, policy)
    return {"schema_version": "1.0", "source_sha256": document.source_sha256,
            "source_unit_names": document.source_unit_names, "normalized_length_unit": "mm",
            "import_scope": document.import_scope, "policy": policy,
            "before": before, "operations": operations, "export": exported,
            "limitations": ("No manufacturing/structural certification", "No CAD feature-history reconstruction",
                            "No native Betti numbers inferred by treating trimmed faces as disks",
                            "Area/volume checks are not a continuous surface-fidelity bound")}


@dataclass(frozen=True, slots=True, eq=False)
class FaceTessellation:
    mesh: TriangleMesh
    triangle_face_ids: IntArray
    source_face_count: int
    missing_face_ids: tuple[int, ...] = ()
    scope: str = "display_only_vertices_are_duplicated_across_native_faces"


def tessellate_for_display(shape: TopoDS_Shape, *, linear_deflection_mm: float = 0.05,
                           angular_deflection: float = 0.3, max_triangles: int = 1_000_000,
                           max_vertices: int = 250_000, max_faces: int = 500_000
                           ) -> FaceTessellation:
    for limit in (max_triangles, max_vertices, max_faces):
        if type(limit) is not int or limit < 1:
            raise ValueError("Display limits must be positive integers")
    positive(linear_deflection_mm, "linear_deflection_mm")
    positive(angular_deflection, "angular_deflection")
    # Meshing caches triangulations on native shapes. Copy first to avoid mutation.
    copier = BRepBuilderAPI_Copy(shape, True, False)
    copy = copier.Shape()
    source_faces = _shapes(shape, TopAbs_FACE)
    if len(source_faces) > max_faces:
        raise ResourceLimitExceeded("Display face budget exceeded")
    copied_faces = _map(copy, TopAbs_FACE)
    # Resolve through copy history, never by matching traversal positions.
    mapped = [copier.ModifiedShape(face) for face in source_faces]
    mapped_ids = [copied_faces.FindIndex(face) for face in mapped]
    if (len(mapped_ids) != copied_faces.Extent()
            or set(mapped_ids) != set(range(1, copied_faces.Extent() + 1))):
        raise KernelOperationFailed("Display copy lost source face correspondence")
    mesher = BRepMesh_IncrementalMesh(copy, linear_deflection_mm, False, angular_deflection, False)
    if not mesher.IsDone():
        raise KernelOperationFailed("Native display tessellation failed")
    vertices: list[tuple[float, float, float]] = []
    triangles: list[tuple[int, int, int]] = []
    face_ids: list[int] = []
    missing: list[int] = []
    for face_id, copied_id in enumerate(mapped_ids):
        # Copy history identifies the face; the copied occurrence retains orientation.
        face_shape = copied_faces.FindKey(copied_id)
        face = TopoDS.Face_s(face_shape)
        location = TopLoc_Location()
        triangulation = BRep_Tool.Triangulation_s(face, location)
        if triangulation is None or triangulation.NbTriangles() == 0:
            missing.append(face_id)
            continue
        if len(triangles)+triangulation.NbTriangles() > max_triangles:
            raise ResourceLimitExceeded("Display tessellation exceeds the triangle budget")
        if len(vertices) + triangulation.NbNodes() > max_vertices:
            raise ResourceLimitExceeded("Display vertex budget exceeded")
        offset = len(vertices)
        transform = location.Transformation()
        for node in range(1, triangulation.NbNodes()+1):
            point = triangulation.Node(node).Transformed(transform)
            vertices.append((point.X(), point.Y(), point.Z()))
        for cell in range(1, triangulation.NbTriangles()+1):
            ids = [int(i)-1+offset for i in triangulation.Triangle(cell).Get()]
            if face.Orientation() == TopAbs_REVERSED:
                ids[1], ids[2] = ids[2], ids[1]
            triangles.append((ids[0], ids[1], ids[2]))
            face_ids.append(face_id)
    mesh = TriangleMesh(np.asarray(vertices, dtype=float).reshape(-1, 3),
                        np.asarray(triangles, dtype=np.int64).reshape(-1, 3), "mm")
    owners = np.frombuffer(np.asarray(face_ids, dtype=np.int64).tobytes(), dtype=np.int64)
    return FaceTessellation(mesh, owners, len(source_faces), tuple(missing))


def sample_edge_polylines(shape: TopoDS_Shape, edge_ids: tuple[int, ...], *, samples: int = 32
                          ) -> tuple[np.ndarray[Any, Any], ...]:
    """Local report edge IDs -> 3-D curve samples for defect overlays, not vertex IDs."""
    if samples < 2:
        raise ValueError("Need at least two samples per edge")
    edges = _map(shape, TopAbs_EDGE)
    lines = []
    for edge_id in edge_ids:
        if not 0 <= edge_id < edges.Extent():
            raise IndexError(edge_id)
        curve = BRepAdaptor_Curve(TopoDS.Edge_s(edges.FindKey(edge_id+1)))
        lo, hi = curve.FirstParameter(), curve.LastParameter()
        if not math.isfinite(lo) or not math.isfinite(hi):
            raise KernelOperationFailed("Cannot sample an unbounded native edge")
        points = [curve.Value(float(t)) for t in np.linspace(lo, hi, samples)]
        lines.append(np.array([(p.X(), p.Y(), p.Z()) for p in points], dtype=float))
    return tuple(lines)
