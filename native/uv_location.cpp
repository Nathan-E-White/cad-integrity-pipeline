// IMPLEMENTATION PENDING: intentionally excluded from active CMake targets.
#include "uv_location.hpp"

// Own an admitted chart and its 2D spatial index for repeated queries.
// Use conservative candidate bounds, barycentric tests and all-candidate XYZ comparison.
// Preserve query order; distinguish outside, unique, agreeing, ambiguous and exhausted.
// Budget exhaustion must never appear as outside or a successful first hit.
// Compare actual needs with FlatBVH before extracting shared private build machinery;
// nearest-ray termination is unsuitable for complete UV candidate collection.
// Reference integration/mesh_healing_extension/mesh_export.py UVSurfaceMap semantics.
// IndexRequest and QueryRequest must specify admission, tolerance and resource limits.

// No placeholder success, throwing stub, or algorithm definition is provided.
