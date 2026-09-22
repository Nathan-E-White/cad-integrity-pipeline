#pragma once
#include "SimplicialComplex.hpp"
#include <expected>
#include <memory>
#include <span>

namespace cad::surface {
using Id = std::int64_t;
using Point = std::array<double, 3>;
using Triangle = std::array<Id, 3>;
struct SurfaceLimits {
  std::uint64_t max_input_bytes = 256000000;
  std::uint64_t max_owned_bytes = 512000000;
  std::uint64_t max_work_steps = 50000000;
  std::uint64_t max_output_bytes = 256000000;
};
struct Usage {
  std::uint64_t input_bytes = 0, owned_bytes = 0, work_steps = 0,
                output_bytes = 0;
};
enum class Operation { preparation, assembly, chart };
enum class ErrorCode {
  invalid_input,
  invalid_topology,
  invalid_geometry,
  numerical_range,
  input_budget,
  storage_budget,
  work_budget,
  output_budget
};
struct SurfaceError {
  ErrorCode code;
  Operation operation;
  Id source_face = -1;
};
struct TriangulationPolicy {
  double relative_tolerance = 1e-12;
};
struct PreparationRequest {
  simplicial::PolygonalInput input;
  std::vector<Id> face_ids;
  TriangulationPolicy policy;
  SurfaceLimits limits;
};
struct SurfaceStorage;
class Discretization {
public:
  [[nodiscard]] std::span<const Point> vertices() const;
  [[nodiscard]] std::span<const Triangle> triangles() const;
  [[nodiscard]] std::span<const Id> source_vertices() const;
  [[nodiscard]] std::span<const Id> selected_faces() const;
  [[nodiscard]] std::span<const Id> triangle_faces() const;
  // Per triangle side: original source edge ID, or -1 for an inserted diagonal.
  [[nodiscard]] std::span<const Triangle> triangle_edges() const;
  [[nodiscard]] std::span<const Id> boundary_vertices() const; // source IDs
  [[nodiscard]] Id source_face_count() const;
  [[nodiscard]] simplicial::LengthUnit length_unit() const;
  [[nodiscard]] const Usage &usage() const;

private:
  explicit Discretization(std::shared_ptr<const SurfaceStorage> owner);
  std::shared_ptr<const SurfaceStorage> owner_;
  friend std::expected<Discretization, SurfaceError>
      prepare(PreparationRequest);
};
[[nodiscard]] std::expected<Discretization, SurfaceError>
prepare(PreparationRequest request);
struct FloatingCSR {
  std::vector<Id> offsets, columns;
  std::vector<double> values;
  Id dimension = 0;
};
struct ConfidencePolicy {
  std::vector<std::pair<Id, double>> face_weights;
};
class Operators {
public:
  [[nodiscard]] const FloatingCSR &stiffness() const { return stiffness_; }
  [[nodiscard]] const Discretization &surface() const { return surface_; }
  [[nodiscard]] const ConfidencePolicy &confidence() const {
    return confidence_;
  }
  [[nodiscard]] const Usage &usage() const { return usage_; }

private:
  Operators(Discretization s, FloatingCSR l, ConfidencePolicy c, Usage u)
      : surface_(std::move(s)), stiffness_(std::move(l)),
        confidence_(std::move(c)), usage_(u) {}
  Discretization surface_;
  FloatingCSR stiffness_;
  ConfidencePolicy confidence_;
  Usage usage_;
  friend std::expected<Operators, SurfaceError>
      assemble(Discretization, ConfidencePolicy, SurfaceLimits);
};
[[nodiscard]] std::expected<Operators, SurfaceError>
assemble(Discretization surface, ConfidencePolicy confidence = {},
         SurfaceLimits limits = {});
using UV = std::array<double, 2>;
struct ChartPolicy {
  int orientation = 1;
  double relative_tolerance = 1e-12;
};
struct ChartQuality {
  std::uint64_t triangle_count = 0;
  std::vector<Id> flipped_triangles, degenerate_triangles;
  double minimum_signed_double_area = 0;
  double maximum_conformal_distortion = 0;
};
struct ChartAssessment;
class AdmittedChart {
public:
  [[nodiscard]] const Discretization &surface() const { return surface_; }
  [[nodiscard]] std::span<const UV> uv() const { return *uv_; }

private:
  AdmittedChart(Discretization s, std::vector<UV> uv)
      : surface_(std::move(s)),
        uv_(std::make_shared<const std::vector<UV>>(std::move(uv))) {}
  Discretization surface_;
  std::shared_ptr<const std::vector<UV>> uv_;
  friend std::expected<ChartAssessment, SurfaceError>
      qualify_chart(Discretization, std::vector<UV>, ChartPolicy,
                    SurfaceLimits);
};
struct ChartAssessment {
  ChartQuality quality;
  std::optional<AdmittedChart> admitted;
  Usage usage;
};
[[nodiscard]] std::expected<ChartAssessment, SurfaceError>
qualify_chart(Discretization surface, std::vector<UV> uv,
              ChartPolicy policy = {}, SurfaceLimits limits = {});
} // namespace cad::surface
