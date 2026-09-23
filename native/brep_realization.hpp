#pragma once
#include "surface_preparation.hpp"

namespace cad::occt_adapter {
using surface::Id;
using surface::Point;
using surface::Triangle;
// Owned evidence from the same-runtime OCCT extractor. No foreign kernel
// handles. Keys: (0,native vertex,0), (1,native edge,sample ordinal),
//       (2,native face,local node ordinal). Coordinates never imply identity.
struct RealizationRequest {
  std::vector<Point> nodes;
  std::vector<Triangle> keys, triangles;
  std::vector<Id> triangle_faces;
  // Local node pair, native edge, native face: one record per coedge segment.
  std::vector<std::array<Id, 4>> segments;
  std::vector<Id> edge_uses; // 0 for degenerate edges; otherwise 1 or 2
  Id face_count = 0, vertex_count = 0;
  double agreement_tolerance = 1e-7;
  surface::SurfaceLimits limits;
};
enum class RealizationDiagnostic {
  invalid_evidence,
  coordinate_disagreement,
  degenerate_triangle,
  edge_correspondence,
  orientation,
  nonmanifold_vertex
};
struct RealizationError {
  surface::ErrorCode code;
};
class RealizedSurface {
public:
  [[nodiscard]] const surface::Discretization &surface() const {
    return surface_;
  }
  [[nodiscard]] std::span<const Id> native_vertex_ids() const {
    return vertex_ids_;
  }

private:
  RealizedSurface(surface::Discretization s, std::vector<Id> v)
      : surface_(std::move(s)), vertex_ids_(std::move(v)) {}
  surface::Discretization surface_;
  std::vector<Id> vertex_ids_;
  friend class RealizationBuilder;
};
struct RealizationAssessment {
  std::vector<RealizationDiagnostic> diagnostics;
  std::optional<RealizedSurface> admitted;
  surface::Usage usage;
};
[[nodiscard]] std::expected<RealizationAssessment, RealizationError>
realize(RealizationRequest request);
} // namespace cad::occt_adapter
