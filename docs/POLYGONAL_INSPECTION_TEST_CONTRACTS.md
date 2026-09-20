# Polygonal inspection — test contracts

Status: design recipes retained alongside the implemented public seams. Companion
to the [case catalogue](POLYGONAL_INSPECTION_TDD_CASES.md).

Implemented Python APIs are authoritative in `src/cad_integrity/inspection.py`: 
`InspectionGeometryInput`, `MeshScope`, `CategoryMembership`, `DisplayIssue`,
`DisplayGeometry`, `MeshInspection`, `InspectionSnapshot`, `ProjectionLimits`,
`triangulate_for_inspection`, `project_polygonal_inspection`, and `encode_inspection`.
The recipes below use illustrative names, not importable stubs. `DisplayIssue` uses
`face_id` within its owning mesh; targets gain mesh/revision scope in the adapter.
The V2 wire uses snake_case fields and lossless gzip delivery through a Gradio-managed file envelope.
Browser contracts live in `frontend/src/core/{inspection,state,wire}.ts`.
See [implementation evidence](evidence/polygonal-inspection/IMPLEMENTATION.md) for
executed coverage and measured capacity, separately from these recipes.

## Backend signatures

This Python notation defines public responsibilities, not production import stubs.
`FrozenArray` means owned storage with no publicly reachable writable alias,
including through NumPy write flags or buffer access. Choose its representation
with capacity measurements; tuples of boxed numbers are not mandated.

```python
Stage = Literal["original", "candidate"]
EntityKind = Literal["vertex", "edge", "polygonal_face"]
CategoryId = Literal[
    "nonmanifold_vertices", "unused_vertices", "boundary_edges",
    "nonmanifold_edges", "winding_conflicts", "unused_edges",
    "collapsed_edges", "invalid_faces", "duplicate_faces",
]

@dataclass(frozen=True)
class MeshScope:
    mesh_id: str
    revision: str

@dataclass(frozen=True)
class EntityRef:
    scope: MeshScope
    kind: EntityKind
    entity_id: int

@dataclass(frozen=True)
class CategoryMembership:
    category: CategoryId
    kind: EntityKind
    entity_ids: tuple[int, ...]

@dataclass(frozen=True)
class DisplayIssue:
    entity: EntityRef
    code: str
    detail: str

@dataclass(frozen=True)
class DisplayGeometry:
    triangles: FrozenArray             # integer Nx3 vertex references
    triangle_source_faces: FrozenArray # owner for each emitted triangle
    boundary_segments: FrozenArray     # resolvable endpoint pairs
    boundary_source_faces: FrozenArray # owner per segment; no guessed closure
    issues: tuple[DisplayIssue, ...]

@dataclass(frozen=True)
class MeshInspection:
    stage: Stage
    scope: MeshScope
    frame_id: str
    length_unit: Literal["mm", "cm", "m", "in"]
    vertices: FrozenArray
    edges: FrozenArray
    face_offsets: FrozenArray
    face_coedges: FrozenArray
    categories: tuple[CategoryMembership, ...]
    display: DisplayGeometry

@dataclass(frozen=True)
class InspectionSnapshot:
    original: MeshInspection
    candidate: MeshInspection | None

@dataclass(frozen=True)
class ProjectionContext:
    original_scope: MeshScope
    candidate_scope: MeshScope | None
    frame_id: str

@dataclass(frozen=True)
class ProjectionLimits:
    max_vertices: int
    max_edges: int
    max_faces: int
    max_display_triangles: int
    max_payload_bytes: int

def triangulate_for_inspection(
    brep: PolyhedralBRep, *, scope: MeshScope, limits: ProjectionLimits,
) -> DisplayGeometry: ...

def project_polygonal_inspection(
    result: RepairResult, *, context: ProjectionContext, limits: ProjectionLimits,
) -> InspectionSnapshot: ...

def encode_inspection(snapshot: InspectionSnapshot) -> InspectionPayloadV2: ...
```

Add `inspection: InspectionSnapshot | None = None` after the required fields in
`WorkbenchOutcome`. Keep publication/exposure policy outside the projector. No
analyzer, renderer, filesystem store or lazy backend callback is a projection
parameter. Use supplied reports and the caller's already-computed result.

Limits guard allocations; they do not authorize reduced upload admission.
Production limits must support admitted workloads before switching. Smaller test
limits enable boundary cases. Unrepresentable/oversized counts raise the existing
`ResourceLimitExceeded` family; unsupported faces return local issues. Agree exact
issue codes, revision policy and wire encoding before asserting those literals.

### Carrier gap found during review

`PolyhedralBRep.__post_init__` rejects out-of-range edge vertex references, invalid
coedge tokens and invalid offsets. P19/P20 must not fabricate an impossible public
`RepairResult` by altering private object state. Broken but in-range wires are
available negative fixtures through the present carrier.

Resolved with `InspectionGeometryInput`, a bounded display-only owned carrier.
Its offsets remain valid records while unresolved connectivity produces local
issues and only resolvable segments. Numerical `PolyhedralBRep` admission remains
unchanged; no impossible `RepairResult` is fabricated in tests.

## Frontend signatures

```typescript
type EntityKindV2 = "vertex" | "edge" | "polygonal_face";
type ScopedV2 = { meshId: string; revision: string };
type TargetV2 = ScopedV2 & (
  | { type: "entity"; kind: EntityKindV2; entityId: number }
  | { type: "category"; categoryId: CategoryId }
);
type ResolvedTargetV2 = {
  entities: readonly EntityRefV2[];
  displayTriangleIds: readonly number[];
  pointIds: readonly number[];
  segmentIds: readonly number[];
};
type ValidationResult<T> =
  | { ok: true; value: T }
  | { ok: false; issues: readonly PayloadIssue[] };

declare function validateInspectionPayload(
  input: unknown,
): ValidationResult<InspectionPayloadV2>;
declare function resolveInspectionTarget(
  mesh: MeshInspectionV2, target: TargetV2 | null,
): ResolvedTargetV2 | null;
declare function targetFromDisplayTriangle(
  mesh: MeshInspectionV2, triangleId: number,
): TargetV2 | null;
```

These interfaces support contract tests without Three.js or private selection
stores. Invalid scope/kind/ID never falls back to another entity. Emitted mappings
are authoritative. Keep V2 separate from the existing V1 `face` target, which
currently means a display triangle. Browser state is separate from payloads;
test workspace actions through rendered controls. A public reducer is optional,
not a new requirement solely to facilitate tests.

## Executable test recipes

These bodies become runnable as interfaces are confirmed and implemented. They
are not currently collected tests. Do not install permanently skipped tests or
import-failing skeletons into normal suites. Fixtures refer to catalogue oracles.

### M02 — snapshot does not alias source vertices (pytest)

```python
def test_snapshot_does_not_alias_source_vertices(repair_result, context, limits):
    snapshot = project_polygonal_inspection(
        repair_result, context=context, limits=limits,
    )
    source = repair_result.original.vertices  # existing public NumPy array
    source.setflags(write=True)
    source[0] = (99.0, 98.0, 97.0)
    assert tuple(snapshot.original.vertices[0]) == (0.0, 0.0, 0.0)
```

If the source carrier later becomes strongly immutable, use mutable input at the
confirmed snapshot construction boundary instead; do not weaken the carrier.
M05/M06 separately check mutation through snapshot accessors and write flags.

### P01 — supplied memberships survive (pytest)

```python
@pytest.mark.parametrize("category,kind,expected_ids", [
    ("nonmanifold_vertices", "vertex", (1,)),
    ("unused_vertices", "vertex", (8,)),
    ("boundary_edges", "edge", (0, 2)),
    ("nonmanifold_edges", "edge", (3,)),
    ("winding_conflicts", "edge", (2,)),
    ("unused_edges", "edge", (7,)),
    ("collapsed_edges", "edge", (9,)),
    ("invalid_faces", "polygonal_face", (1,)),
    ("duplicate_faces", "polygonal_face", (2,)),
])
def test_projects_supplied_membership(
    category, kind, expected_ids, supplied_result, context, limits,
):
    snapshot = project_polygonal_inspection(
        supplied_result, context=context, limits=limits,
    )
    membership = next(c for c in snapshot.original.categories
                      if c.category == category)
    assert (membership.kind, membership.entity_ids) == (kind, expected_ids)
```

The fixture has sufficient entities and literal report fields; it never runs an
analyzer to derive expected results. It is a projection oracle, not a claim of a
physically realizable audit. Add parameters in successive red → green cycles.

### P11 — mixed polygon provenance (pytest)

```python
def test_mixed_faces_emit_source_provenance(g1, original_scope, limits):
    display = triangulate_for_inspection(g1, scope=original_scope, limits=limits)
    assert Counter(display.triangle_source_faces) == {0: 1, 1: 2, 2: 3}
    expected_vertices = {0: {0, 1, 2}, 1: {3, 4, 5, 6},
                         2: {7, 8, 9, 10, 11}}
    assert len(display.triangles) == len(display.triangle_source_faces) == 6
    for triangle, face_id in zip(display.triangles, display.triangle_source_faces):
        assert set(triangle) <= expected_vertices[face_id]
```

P12 separately checks worked areas/coverage; repeated or degenerate triangles
cannot satisfy the entire contract merely by having correct owners.

### A06 — triangle picks select their source face (Node test)

```typescript
test("each square triangle selects the whole source face", () => {
  const parsed = validateInspectionPayload(backendG1Fixture);
  assert.equal(parsed.ok, true);
  if (!parsed.ok) throw new Error("invalid backend fixture");
  const mesh = parsed.value.original;
  const squareTriangles = mesh.triangleSourceFaces
    .flatMap((face, triangle) => face === 1 ? [triangle] : []);
  assert.equal(squareTriangles.length, 2); // independent G1 fact
  for (const triangle of squareTriangles) {
    const target = targetFromDisplayTriangle(mesh, triangle);
    assert.deepEqual(target, {
      meshId: mesh.id, revision: mesh.revision,
      type: "entity", kind: "polygonal_face", entityId: 1,
    });
    const selected = resolveInspectionTarget(mesh, target);
    assert.ok(selected);
    assert.deepEqual(selected.displayTriangleIds.toSorted(), squareTriangles.toSorted());
  }
});
```

P11 independently tests mapping production. A06 tests consumption without guessing
triangle order. The proposed camelCase wire fields need confirmation.

### W27 — hover restores pinned selection (Playwright recipe)

Confirm accessible labels with the workspace. Use fixed viewport/device scale and
reviewed browser-specific screenshots alongside the source identity assertion.

```typescript
test("leaving a row restores the pinned entity", async ({ page }) => {
  await openInstalledParentWithB1(page);
  const original = page.getByRole("region", { name: "Original" });
  const entities = page.getByRole("table", { name: "Original entities" });
  await entities.getByRole("row", { name: "Face 0", exact: true }).click();
  await entities.getByRole("row", { name: "Face 1", exact: true }).hover();
  await expect(original.getByRole("status", { name: "Selection" }))
    .toHaveText("Face 0");
  await expect(original).toHaveScreenshot("face-1-hover-face-0-pinned.png");
  await page.getByRole("heading", { name: "Mesh Lab", exact: true }).hover();
  await expect(original).toHaveScreenshot("face-0-pinned.png");
});
```

## Automation inventory

| Cases | Execution form | Oracle / limitation |
| --- | --- | --- |
| M01–M14 | Python public-value/controller tests; M14 also browser | Literal fields, mutation isolation, unchanged numerical/release results |
| P01–P08, P11–P27, P29–P30 | Python projection/triangulation tests | Independent reports/geometry; P19/P20 await the raw-carrier contract |
| P09–P10 | Projection tests plus constrained process/system observation | Supplied facts authoritative; no file/network effects |
| P28 | Preflight tests plus bounded process-memory instrumentation | Failure before material allocation; no deliberate host OOM |
| A01–A13 | Python fixtures consumed by TypeScript contract tests | V2 validation, identity, legacy meaning |
| A14 | Browser runtime test plus ownership review | No orphan resources; review establishes overlay ownership |
| W01–W13, W15–W33, W36 | Installed-parent Playwright tests | Real controls/rows, rendering and network events |
| W14, W35 | Automated value/presence checks plus visual/content review | DOM counts alone cannot establish emphasis/readability |
| W34 | Browser test plus GPU/platform instrumentation | Geometry uploads and state stay stable |
| I01–I12, I26–I27 | Controller tests; I01–I07/I26 also installed-parent browser | Actual retained files, checks and snapshot |
| I13–I24 | Session-boundary integration plus browser tests | Deterministic barriers; no arbitrary sleeps |
| I25, I28 | Installed-package browser and initialization-failure tests | Built assets, explicit error, preserved outcome facts |
| D01–D03 | Conditional controller/browser tests after D-001 | Only selected visibility/lifetime policy becomes required |
| Q01–Q13 | Target-machine browser benchmark/failure harness | Measured agreed bounds; machine-specific evidence |
| Q14–Q16 | Switch checklist backed by regression and capacity runs | Release decision, not a unit assertion that a flag is true |

## Evidence record per executed case

```text
case_id:
seam_and_contract_revision:
fixture_and_independent_oracle:
test_file_and_test_name:
red_command_and_behavioral_failure:
green_command_and_executed_count:
runtime_and_artifact_paths:
limitations_or_blocked_decision:
```

No records are populated by writing this catalogue. Use existing Pixi Python tasks
and inspector scripts when implementation begins. Register workspace tests in its
actual package scripts once placement is settled; today's inspector scripts do
not already test the placeholder workspace. Keep numerical/controller, frontend
contract, installed-parent browser and target-machine capacity results separate.
A skipped or uncollected test is not a passing qualification case.
