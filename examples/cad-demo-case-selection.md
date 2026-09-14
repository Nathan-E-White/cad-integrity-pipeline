# Six cases for the CAD Integrity Lab demonstration

Four additional author-published GenCAD image/mesh pairs, plus two deliberately constructed pathological controls. Names below describe the reference image, not a verified reconstruction of that image. The pairings, repository file sizes and input images were inspected; the generated GLBs have not been audited in this environment. No pathological meshes have been generated yet.

## Published pairs

| ID | Category | Reference shape | Input | First published output | GLB bytes |
| --- | --- | --- | --- | --- | ---: |
| V1 | Vanilla | Round base with a cylindrical boss | [Image](https://gencad.github.io/static/images/sample_diversity_2.png) | [GLB](https://gencad.github.io/static/mesh/sample_diversity_2_1.glb) | 12,304 |
| V2 | Vanilla | Hexagonal spacer with a central bore | [Image](https://gencad.github.io/static/images/sample_diversity_1.png) | [GLB](https://gencad.github.io/static/mesh/sample_diversity_1_1.glb) | 4,500 |
| N1 | Neat | Slotted annular part with a thin flange | [Image](https://gencad.github.io/static/images/386.png) | [GLB](https://gencad.github.io/static/mesh/386.glb) | 18,224 |
| N2 | Neat | Two-hole link with a raised boss at one end | [Image](https://gencad.github.io/static/images/390.png) | [GLB](https://gencad.github.io/static/mesh/390.glb) | 14,384 |

The four primary GLBs total **49,412 bytes**, excluding input images and documentation. They are visualization meshes, not native STEP models or proven raw inference outputs. Their file sizes do not establish audit or browser-rendering latency.

### V1: Round boss — baseline preservation

Use this as the least visually complicated entry. Audit the published result first; do not assume it is a single solid merely because the reference image looks that way. On a baseline that passes the chosen checks, exercise a no-op repair and verify that no unnecessary vertex movement, smoothing, or feature changes occur.

The desired demonstration is restraint: already acceptable geometry should not be modified merely to produce an animated before/after comparison.

### V2: Hex spacer — preserve the bore and planar silhouette

Use the contrast between flat external faces and the circular-looking bore. Show that topological integrity and resemblance to the source are different questions. In particular, do not infer a through-bore, rather than a blind bore, from a single rendered image alone.

For an independently verified, closed, single-through-bore reference, the boundary surface has torus topology and Betti numbers (1, 2, 1) over F2. That is a mathematical reference, not a measured result for this published GLB. Nonzero b1 is not itself a leak.

### N1: Slotted flange — a visible opening need not be a mesh defect

This C-shaped reference has a radial slot, a central opening, and a thin outer flange. It is useful for testing feature preservation under a weld tolerance: an intentional slot must not be zipped shut. A solid with such a slot can still possess a completely closed boundary surface because the slot has walls.

Let visitors inspect the slot and thin flange while changing a bounded tolerance. A candidate should be rejected rather than accepted solely because a coarse topological metric improves. The input image helps explain the intended feature; it is not a dimensional specification.

### N2: Two-hole link — multiple features and reconstruction fidelity

This reference combines an elongated body, two bore openings, rounded ends, and a raised boss. Inspect bore connectivity, orientation around concave surfaces, and preservation of small features. Whether either bore passes completely through must be established from the actual geometry or a supplied specification.

For a deliberately specified closed reference with two independent through-bores and no other topology, the boundary is genus two, with (b0, b1, b2) = (1, 4, 1) over F2. Again, this is not an audited value for the published output.

## Pathological controls to construct

Both controls should retain the original image and published mesh as provenance, but the interface must explicitly distinguish the modified test mesh from the author's output. Audit and document any conversion from rendering vertices to analysis topology before injecting a defect.

### P1: Detached and reversed surface patch

**Parent:** V1, after obtaining an independently audited closed, coherently oriented working mesh.

Choose a disk-like patch, duplicate its boundary vertex indices to disconnect it, translate the entire patch outward a small distance, and reverse its triangle winding. Save the exact face IDs, vertex mappings, displacement, and baseline hash. A starting displacement of 0.001 times the bounding-box diagonal is a proposed experiment, not a physical tolerance; reduce it further when local features demand it.

**Expected result:** boundary/disconnection diagnostics detect the detached patch. Candidate welding/sewing and orientation correction are evaluated under explicit geometric and displacement limits. Acceptance is conditional on the audit; it is not guaranteed. The patch still exists, so this tests reattachment rather than invented missing-surface reconstruction.

**Label:** “Synthetic seam and orientation defect; introduced after generation.”

### P2: Two closed shapes sharing exactly one vertex

**Parent:** an audited closed manifold V1 working mesh.

Choose a vertex p that uniquely maximizes n dot x for a direction n. Create a second copy using x' = 2p - x, reverse the copied triangle winding, and identify only the two copies of p as one vertex. The unique supporting-plane condition puts the two copies on opposite sides of a plane so they meet only at p. Record the transform and the one explicit topological identification.

**Expected result:** every edge retains two incident faces, but the shared vertex has a disconnected link. The combined surface is not a two-manifold. A stitcher must not report success simply because there are no free edges. An explicit decision is required between two separate bodies and a physically connected body.

Splitting the shared topological vertex creates separate combinatorial sheets but leaves the geometric point contact in place; that distinction belongs in the report.

**Label:** “Synthetic nonmanifold junction; not an original GenCAD output.”

## Additional generated alternatives

The website publishes three outputs for each vanilla input. Preserve them as alternative generations, not alleged successive repairs:

- Hex spacer: [sample 2](https://gencad.github.io/static/mesh/sample_diversity_1_2.glb), [sample 3](https://gencad.github.io/static/mesh/sample_diversity_1_3.glb).
- Round boss: [sample 2](https://gencad.github.io/static/mesh/sample_diversity_2_2.glb), [sample 3](https://gencad.github.io/static/mesh/sample_diversity_2_3.glb).

With these alternatives, eight GLBs total 79,116 bytes, excluding images and documentation.

## Fetching the existing examples

Use the companion standard-library script:

```bash
python fetch_gencad_demo_cases.py --list
python fetch_gencad_demo_cases.py --out ./examples/gencad --include-alternates
```

It pins the upstream commit, validates GLB sizes and Git blob hashes, records SHA-256 provenance, and refuses to overwrite different existing files. It does not download weights, run a model, audit a mesh, modify geometry, or create the pathological fixtures. The fixture recipes are saved as plans. Local header/hash/output-protection smoke checks passed; end-to-end network download was not executable in the preparation environment.

## Sources and reuse

GenCAD: Md Ferdous Alam and Faez Ahmed. [Project website](https://gencad.github.io/). [Source page showing the image-to-mesh pairings](https://github.com/gencad/gencad.github.io/blob/cc789e32e0831df4e15ff271fb0a0ffcfb54ef03/index.html). [Asset directory](https://github.com/gencad/gencad.github.io/tree/cc789e32e0831df4e15ff271fb0a0ffcfb54ef03/static/mesh).

Pinned website commit: `cc789e32e0831df4e15ff271fb0a0ffcfb54ef03`.

The upstream [README](https://github.com/gencad/gencad.github.io/blob/cc789e32e0831df4e15ff271fb0a0ffcfb54ef03/README.md) declares a CC BY-SA 4.0 website license. Preserve that attribution and notice, identify modifications, and confirm that its scope covers the downloadable assets before public redistribution. This selection does not provide additional permissions or imply author endorsement.

For the geometric/combinatorial distinction in P2, see [CGAL's mesh-repair manual](https://doc.cgal.org/latest/PMP_Mesh_repair/index.html). For separation of rendering attributes from topology analysis, see the [Khronos glTF specification](https://registry.khronos.org/glTF/specs/2.0/glTF-2.0.html).
