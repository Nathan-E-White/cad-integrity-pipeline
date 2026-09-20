# Data structures for large mesh workflows

Research date: 2026-09-20. Sources are project documentation and original research. Recommendations and byte estimates below are engineering synthesis, not measurements of this repository.

Large meshes do not have a face count at which a transactional database becomes compulsory. Three separate questions govern the design: how algorithms traverse topology, how the active working set fits memory, and how persistent assets are queried and coordinated. The first two often call for compact arrays, partitioning, and external storage. The third can justify a database even for small meshes.

## Choose the representation for the operation

| Workload | Starting representation | Reason to add another structure |
| --- | --- | --- |
| Import, rendering, sequential geometry checks | Packed vertex coordinates and face indices | Repeated neighborhood queries |
| Polygonal incidence and read-heavy topology | Offsets plus flat incidence arrays, in CSR style | Frequent local connectivity edits |
| Surface editing, remeshing, oriented traversal | Index-based halfedge structure | General nonmanifold incidence requires a broader model |
| Intersection, distance, picking | BVH/AABB tree over geometric primitives | It supplements connectivity; it does not encode it |
| Mixed or volume cells, numerical simulation | Cell-complex incidence with partition ownership | Distributed computation needs overlap and communication |
| Large archives and workflow history | Binary mesh assets plus a searchable catalog | Transactional and concurrent lifecycle requirements |

This table is a design recommendation; it is not a claim that every listed representation is implemented here.

### Packed arrays and incidence

An immutable surface snapshot can start with `positions[V,3]` and `triangles[F,3]`. General polygons use `face_offsets[F+1]` and a flat `face_vertices[K]`, where `K` is total corners. Reverse incidence, such as vertex-to-face or edge-to-face, can use the same layout. SciPy documents the underlying CSR convention: row `i` occupies `indices[indptr[i]:indptr[i+1]]`. Numeric sparse matrices additionally carry values; pure incidence need not store a redundant array of ones. [SciPy CSR](https://docs.scipy.org/doc/scipy/reference/generated/scipy.sparse.csr_array.html)

Recommendation: build only the reverse relations that measured algorithms reuse. Use a construction phase followed by a compact traversal phase; arbitrary insertion into compressed topology is a poor default. SciPy explicitly identifies sparsity-structure changes as expensive for CSR. [SciPy CSR mutation costs](https://docs.scipy.org/doc/scipy/reference/generated/scipy.sparse.csr_matrix.html)

Keep element identity distinct from its current array position. A persisted identifier should survive reordering through an explicit mapping or a new snapshot identity. Also distinguish index widths: an entity ID may fit in 32 bits while an offset into the total incidence stream requires 64 bits. Check both bounds before allocation or narrowing. These are representation design requirements, not guarantees supplied by CSR itself.

### Halfedges without object-per-element overhead

Halfedges are useful when traversal and local mutation dominate. They need not be heap objects linked by pointers. CGAL's `Surface_mesh` uses integer descriptors and property arrays, with paired opposite halfedges stored consecutively. Deleted elements remain marked until garbage collection. This illustrates both compact representation and the need to handle compaction deliberately. [CGAL Surface Mesh](https://doc.cgal.org/latest/Surface_mesh/index.html)

A conventional oriented manifold halfedge model assumes two sides per edge. That assumption is unsuitable as the sole input carrier when the task is to diagnose edges shared by three or more faces. Geometry Central distinguishes its manifold representation from a general surface mesh: the latter traverses incident halfedges through a sibling cycle and supports broader incidence. Its documentation also cautions that individual algorithms may still require manifold or triangular input. [Geometry Central mesh variants](https://geometry-central.net/surface/surface_mesh/basics/)

Recommendation: preserve arbitrary input incidence first; construct a specialized manifold editing view only after its preconditions are established. A more restrictive data structure should not erase the defect being inspected. Geometry Central's internal design demonstrates that array storage and mutation can coexist; general meshes require additional connectivity arrays rather than a universal two-halfedge encoding. [Geometry Central internals](https://geometry-central.net/surface/surface_mesh/internals/)

### Spatial indexes and algebra solve different problems

An AABB tree accelerates geometric intersection and nearest-point queries. CGAL describes a static hierarchy and an optional secondary accelerator for distance queries. It also warns that degenerate primitives can cause undefined behavior with relevant traits. Thus validation precedes index construction, and geometry changes require an explicit index-validity policy. [CGAL AABB tree](https://doc.cgal.org/latest/AABB_tree/index.html)

Recommendation: budget the spatial index separately from connectivity and tie it to the mesh revision. Geometric proximity does not establish topological adjacency. Likewise, a sparse boundary operator is an algebraic view of incidence, not a substitute for geometry or provenance. Under F2 column reduction, symmetric differences can enlarge columns; a small input matrix therefore does not bound the reduction workspace. Record peak nonzeros, retained pivots, and operation counts, with explicit failure budgets. This last point follows from the reduction operation itself, not from a performance benchmark.

## Quantify the working set before selecting storage

The following is arithmetic for a hypothetical large, closed triangular surface with `V` approximately `F/2`. It excludes properties, boundaries, provenance, allocator overhead, spare capacity, temporary arrays, and indexes. Values are decimal GB; none is a measured application peak.

| Faces | float64 XYZ + uint32 triangles: `24V + 12F` bytes | float64 XYZ + uint64 triangles: `24V + 24F` bytes |
| ---: | ---: | ---: |
| 1 million | 0.024 GB | 0.036 GB |
| 10 million | 0.24 GB | 0.36 GB |
| 100 million | 2.4 GB | 3.6 GB |
| 1 billion | 24 GB | 36 GB |

For the same assumed mesh, a custom vertex-to-face incidence relation adds `3F` IDs plus `V+1` offsets: roughly `16F` bytes with 32-bit IDs and 64-bit offsets. A hypothetical halfedge layout with three 32-bit fields per interior halfedge plus one halfedge reference per vertex and face adds about `42F` bytes, excluding geometry. Actual library layouts differ. At one billion faces, a 32-bit halfedge index space would require especially careful validation of conventions, reserved values, and additional entities.

An operational memory model is:

`peak = input + retained topology + derived indexes + algorithm workspace + output buffers + copies + concurrent jobs`

Measure each stage against the budget available to this process. If that peak cannot fit, first bound copies and intermediates, then use streaming, memory mapping, or partitions. A storage change alone cannot make a whole-mesh algorithm operate within a bounded working set.

## Distributed meshes are not database queries

PETSc DMPlex represents mesh entities as points in a DAG of covering relations, separating topology from field layout. This supports dimension-independent mesh operations and separately associated numerical values. [DMPlex topology and fields](https://petsc.org/main/manual/dmplex/)

Its distribution interface partitions a mesh across processes and accepts an overlap depth; the returned point mapping is part of communicating distributed data. This is the relevant family of tools when computation needs ownership and neighboring cells across process boundaries. [DMPlexDistribute](https://petsc.org/release/manualpages/DMPlex/DMPlexDistribute/)

MOAB is another scientific mesh data library covering structured and unstructured meshes, including polygons and polyhedra. Its name expands to Mesh-Oriented datABase, but that should not be mistaken for a recommendation to place every cell in a SQL or graph server. Its documented lazy construction of some adjacencies and internal entities reinforces the value of materializing topology on demand. Historical mesh-size examples in its FAQ are project-reported demonstrations, not capacity promises for this application. [MOAB overview](https://sigma.mcs.anl.gov/moab-library/), [MOAB FAQ](https://sigma.mcs.anl.gov/moab/faq-moab/)

Recommendation: adopt partitioned mesh infrastructure when sustained computation exceeds one process and can exploit domain decomposition. Persist ownership, global-to-local mappings, boundary relationships, and revision identity explicitly. A database can catalog these partitions, but it does not supply the numerical algorithm's halo exchange or establish correctness of partitioned topology checks.

## Storage and database decision

The following is an engineering recommendation derived from the documented mechanisms, not a benchmark or an implemented migration.

| Requirement | First candidate | What it does not solve |
|---|---|---|
| One immutable mesh, sequential processing | Contiguous typed arrays and files | Concurrent revision management |
| Arrays larger than the working memory budget | Memory mapping or chunked HDF5/Zarr, with bounded algorithms | Global random access, unbounded temporary arrays, reduction fill-in |
| Persistent local run history and indexed metadata | SQLite catalogue plus array artifacts | Many simultaneous independent writers |
| Shared mutable catalogue across machines | PostgreSQL service plus immutable array artifacts | Partitioning mesh computations or supplying GPU memory |
| Distributed numerical computation | Partitioned mesh, local IDs, global correspondence and ghost exchange | Product catalogue and revision transactions |

NumPy memory mapping accesses file segments without reading the entire file first; `open_memmap` specifically provides this for `.npy` arrays. Mapping storage does not bound allocations made by sorting, advanced indexing, or derived topology. A viable out-of-core path must budget those operations too. [NumPy memmap](https://numpy.org/doc/stable/reference/generated/numpy.memmap.html), [open_memmap](https://numpy.org/doc/stable/reference/generated/numpy.lib.format.open_memmap.html).

HDF5 chunking permits partial I/O and compression, but accessing a subset can require reading and decompressing a whole chunk. Select chunk shape using actual access patterns: spatial block, cell range, field component or time slice. Merely changing the file extension does not make an algorithm out-of-core. [HDF5 chunking](https://portal.hdfgroup.org/documentation/hdf5/latest/hdf5_chunking.html).

Zarr sharding packs multiple chunks into one storage object, reducing object/file counts while preserving small independently readable chunks. Read granularity and efficient write granularity differ; plan writer ownership at the shard level when applicable. Choose it for a demonstrated storage/access requirement, not simply because data are large. [Zarr performance](https://zarr.readthedocs.io/en/stable/user-guide/performance/).

HDF5 SWMR is specifically single-writer/multiple-reader; h5py documents flush/refresh coordination and restrictions on creating new groups/datasets after entering SWMR. This is not a general multi-writer transaction catalogue. [h5py SWMR](https://docs.h5py.org/en/stable/swmr.html).

### When a database becomes necessary

There is no face-count threshold. A database becomes the practical default when the application must maintain durable shared facts under failures and concurrent updates, or provide indexed cross-run queries within a required latency. Examples: one accepted head per branch, unique publication of a run attempt, revision ancestry, resumable job state, and results tied to exact input/settings/tool versions. Files plus locks and journals can implement these requirements; at that point the project is taking responsibility for database machinery itself.

SQLite is appropriate for a local catalogue with short write transactions. Many readers and occasional queued writers do not automatically require PostgreSQL. Move to a server database when independently concurrent writers cannot meet latency requirements by serializing, or when multiple machines must directly access a shared transactional service. SQLite's own guidance makes writer concurrency and deployment topology central to this choice. [SQLite appropriate uses](https://www.sqlite.org/whentouse.html).

SQLite WAL allows readers alongside a writer, but still only one writer at a time and requires processes sharing the WAL database to be on one host. An application server can expose that local database to remote users; placing its WAL files on a shared network filesystem is a different arrangement. [SQLite WAL](https://www.sqlite.org/wal.html).

A server database does not automatically prevent every lost update. Specify unique/foreign-key constraints, revision comparisons, transaction boundaries and retries. PostgreSQL documents that serializable transactions can abort and require retry of the entire transaction. [PostgreSQL constraints](https://www.postgresql.org/docs/current/ddl-constraints.html), [transaction isolation](https://www.postgresql.org/docs/current/transaction-iso.html).

### Proposed division of responsibility

Store bulk positions, incidence, field arrays and display blocks in immutable artifacts. Store mesh revision identity, parent relations, artifact digests/locations, run state, parameters, tool version, diagnostic summaries and annotations in the catalogue. Suggested tables: `mesh_revision`, `revision_parent`, `artifact`, `revision_artifact`, `run`, `run_input`, `run_output`, `diagnostic_summary`, `annotation`.

Use `(revision_id, entity_kind, entity_id)` for annotations and selections. Compaction/remeshing needs explicit correspondence; an array index must not silently become an identity across revisions. Keep display-triangle-to-polygonal-face mappings. Source B-Rep entities require their own provenance mapping.

Do not assume SQL transactions cover external artifact files. A proposed publication protocol is: write a unique immutable artifact; close and make it durable using the storage system's contract; verify its digest; then commit catalogue references and publication state. Failed catalogue commits can leave unreferenced artifacts for reconciliation. Garbage collection must respect retention and active publication. Incomplete runs remain explicitly incomplete. This is a design proposal, not a claim about existing release atomicity.

A graph database may suit application-level dependency exploration. It is not required just because mesh incidence forms a graph. For kernels scanning almost every edge, contiguous adjacency is the relevant starting point. Per-vertex SQL rows or graph objects need a measured query advantage to justify replacing array traversal; small editable datasets or selective entity queries can be exceptions.

## Mapping to the current CAD Integrity checkout

Read-only inspection on 2026-09-20 found an actively modified worktree. These observations describe the current local files, including uncommitted work; they do not establish released capability or a tested capacity.

- [models.py](../../src/cad_integrity/models.py) already defines `TriangleMesh` arrays and `PolyhedralBRep` structure-of-arrays with `face_offsets` and signed `face_coedges`. Preserve its orientation and restricted polygonal contract rather than replacing it with database entities.
- [arrays.py](../../src/cad_integrity/arrays.py) normalizes to float64/int64 with defensive copies. Mapping an array from disk and then passing through these constructors still copies it. A future mapped/chunked reader needs an explicit ownership/lifetime contract.
- [inspection.py](../../src/cad_integrity/inspection.py) owns inspection arrays and `encode_inspection` emits Python lists for browser delivery. Its defaults include 250,000 vertices, 500,000 polygonal faces and 1,000,000 display triangles. These are admission policies, not measured hardware limits or database thresholds. Profile copies, serialization, transport, browser heap and GPU buffers independently.
- [f2_reduction.py](../../src/cad_integrity/f2_reduction.py) has separate work/storage budgets and retains reduction traces. Mesh residency does not establish that the homology reduction or its evidence fits. Preserve fail-closed budgets while measuring retained traces, pivots and intermediate fill-in.
- [workbench_results.py](../../src/cad_integrity/workbench_results.py) explicitly describes `ArtifactStore` as bounded local request storage, with a default one-hour retention. A durable catalogue would require a separate durable artifact/retention contract; indexing expiring paths is insufficient.

Recommended sequence: (1) measure peak resident memory and elapsed time per stage on representative meshes; (2) preserve compact topology and remove avoidable copies under an explicit ownership contract; (3) deliver bounded display blocks with entity correspondence and independent view budgets; (4) introduce mapped/chunked arrays when measured working sets demand them; (5) add SQLite when persistent history/search is needed; (6) adopt a server catalogue when measured concurrency and deployment require it. Steps 4 and 5 are independent: a tiny multi-user mesh application may need transactions before a huge batch mesh does.

Record vertex/edge/face/incidence counts, index widths, attribute/time-step counts, peak RAM including temporaries and evidence, bytes read versus useful bytes, cold/warm latency, browser memory, and catalogue write queue/lock/retry latency. Select workload-specific limits from these measurements. No universal RAM multiplier, chunk size, or triangle-count migration threshold is established by this research.
