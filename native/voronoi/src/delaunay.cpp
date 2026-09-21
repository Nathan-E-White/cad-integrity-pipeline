// IMPLEMENTATION PENDING: intentionally excluded from active CMake targets.
#include "cad_mat/delaunay.hpp"

// Build the existing DelaunaySnapshot for extract_finite_voronoi_dual.
// Reuse cad::mat Point3, SampleId, cell types and sentinel contracts.
// Construction owns robust predicates, circumcenters, degeneracy policy and bounded work.
// Retain original-sample correspondence after deduplication; range-check cell IDs.
// Keep the construction dependency private. Preserve independent snapshot extractor tests.
// Python/OCP retains shape-relative verification; finite dual output is not a certified MAT.
// ConstructionRequest includes owned/admitted samples, policy and explicit limits.

// No placeholder success, throwing stub, or algorithm definition is provided.
