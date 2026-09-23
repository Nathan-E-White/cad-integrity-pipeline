#pragma once

#include <cstdint>
#include <array>
#include <compare>
#include <cstddef>
#include <expected>
#include <limits>
#include <optional>
#include <memory>
#include <span>
#include <vector>

namespace cad::simplicial {

// Domain errors are values. Allocation and executor failures propagate as
// exceptions.
enum class TopologyStatus : std::uint8_t {
  Success,
  DuplicateVertices,
  BudgetExceeded,
  InvalidDimension,
  IndexOutOfBounds,
  DuplicateTriangles,
  DegenerateTriangle,
  NonPlanarFace,
  NonConvexFace,
  DisconnectedLoop,
  UnsupportedUnit,
  NonfiniteInput,
  InvalidTolerance,
  InputTooLarge,
  InvalidLayout
};
enum class LengthUnit : std::uint8_t { Millimeter, Centimeter, Meter, Inch };
using Point3 = std::array<float, 3>;

struct Simplex {
  std::vector<int> vertices;
  [[nodiscard]] std::size_t dim() const noexcept;
  auto operator<=>(const Simplex &) const = default;
};

// Signed integer incidence, not a reduced homology matrix.
struct SparseCSR {
  std::vector<std::size_t> row_ptr;
  std::vector<std::size_t> col_ind;
  std::vector<std::int8_t> values;
  std::size_t num_rows = 0;
  std::size_t num_cols = 0;
};

// Owned host-precision input. The legacy float/int polygon model stays unchanged.
struct PolygonalInput {
  std::vector<std::array<double, 3>> vertices;
  std::vector<std::array<std::int64_t, 2>> edges;
  std::vector<std::int64_t> face_offsets;
  std::vector<std::int64_t> face_coedges;
  LengthUnit length_unit = LengthUnit::Millimeter;
};
struct PolygonalLimits {
  std::uint64_t max_input_bytes = 256000000;
  std::uint64_t max_owned_bytes = 512000000;
  std::uint64_t max_work_steps = 50000000;
  std::uint64_t max_output_bytes = 256000000;
};
enum class PolygonalError : std::uint8_t {
  invalid_input, input_budget, storage_budget, work_budget, output_budget
};
struct PolygonalUsage {
  std::uint64_t input_bytes = 0, owned_bytes = 0, work_steps = 0, output_bytes = 0;
};
struct PolygonalFacts {
  std::vector<std::int64_t> boundary_edge_ids, nonmanifold_edge_ids;
  std::vector<std::int64_t> inconsistent_orientation_edge_ids, nonmanifold_vertex_ids;
  std::vector<std::int64_t> unused_vertex_ids, unused_edge_ids, invalid_face_ids;
  std::vector<std::int64_t> duplicate_face_ids, collapsed_edge_ids;
  // Signed face uses grouped by edge; order is first encountered edge order.
  std::vector<std::int64_t> edge_offsets, edge_faces, edge_signs, edge_order;
};
struct PolygonalOrientation {
  std::vector<std::int64_t> multipliers, conflicting_edge_ids;
  std::optional<std::int64_t> nonmanifold_edge;
};
struct PolygonalStorage;
class PolygonalAssessment;
class AdmittedPolygonalCells {
public:
  // Degrees 1 and 2 only. References live as long as this owner.
  [[nodiscard]] const SparseCSR& boundary(std::size_t degree) const;
private:
  explicit AdmittedPolygonalCells(std::shared_ptr<const PolygonalStorage> owner);
  std::shared_ptr<const PolygonalStorage> owner_;
  friend class PolygonalAssessment;
};
class PolygonalAssessment {
public:
  [[nodiscard]] const PolygonalInput& input() const noexcept;
  [[nodiscard]] const PolygonalFacts& facts() const noexcept;
  [[nodiscard]] const PolygonalOrientation& orientation() const noexcept;
  [[nodiscard]] const PolygonalUsage& usage() const noexcept;
  [[nodiscard]] const std::optional<AdmittedPolygonalCells>& admitted_cells() const noexcept;
private:
  PolygonalAssessment(std::shared_ptr<const PolygonalStorage> owner, bool admitted);
  std::shared_ptr<const PolygonalStorage> owner_;
  std::optional<AdmittedPolygonalCells> admitted_;
  friend std::expected<PolygonalAssessment, PolygonalError>
  assess_polygonal(PolygonalInput, const PolygonalLimits&);
};
[[nodiscard]] std::expected<PolygonalAssessment, PolygonalError>
assess_polygonal(PolygonalInput input, const PolygonalLimits& limits = {});

struct TriangleMesh;
class SimplicialComplex {
public:
  // Canonical downward closure of arbitrary facets. Empty facets are ignored;
  // repeated facets are idempotent. Vertex labels need not be contiguous.
  // Budget limits retained unique simplices, checked before insertion; it is
  // not a byte or time limit. Allocation failures remain exceptions.
  [[nodiscard]] static std::expected<SimplicialComplex, TopologyStatus>
  build(const std::vector<std::vector<int>> &facets,
        std::size_t simplex_budget = 100000);
  // Triangle indices address mesh vertices; isolated vertices are retained.
  [[nodiscard]] static std::expected<SimplicialComplex, TopologyStatus>
  build_from_mesh_engine(const TriangleMesh &mesh, std::size_t simplex_budget);
  [[nodiscard]] std::span<const Simplex> get_tier(std::size_t d) const noexcept;
  [[nodiscard]] std::expected<SparseCSR, TopologyStatus>
  boundary_operator(std::size_t d) const;

private:
  SimplicialComplex(std::vector<std::vector<Simplex>> tiers,
                    std::size_t max_dim);
  static int compare_skipped_face(std::span<const int> lower,
                                  std::span<const int> upper,
                                  std::size_t skip_idx) noexcept;
  static std::size_t find_face_index(std::span<const Simplex> lower_tier,
                                     const Simplex &upper,
                                     std::size_t skip_idx) noexcept;
  std::vector<std::vector<Simplex>> spatial_tiers_;
  std::size_t max_dim_ = 0;
};

struct TriangleMesh {
  std::vector<Point3> vertices;
  std::vector<std::array<int, 3>> triangles;
  LengthUnit length_unit = LengthUnit::Millimeter;
  // Empty means unavailable. Otherwise one local polygonal face ID per display
  // triangle. IDs address the source polygon model snapshot, not a global
  // revision.
  std::vector<std::size_t> polygonal_face_ids = {};
  [[nodiscard]] std::expected<SimplicialComplex, TopologyStatus>
  to_simplicial_complex(std::size_t max_simplices = 50000) const;
};

// Planar convex polygon loops with signed, one-based coedge tokens.
// This is a polygonal representation, not an OCCT B-Rep.
struct PolyhedralBRep {
  std::vector<Point3> vertices;
  std::vector<std::array<int, 2>> edges;
  std::vector<std::size_t> face_offsets;
  std::vector<int> face_coedges;
  LengthUnit length_unit = LengthUnit::Millimeter;
  [[nodiscard]] std::size_t face_count() const noexcept;
  // Invalid face/offset layouts produce an empty span;
  // construction/triangulation return a typed error for malformed input.
  [[nodiscard]] std::span<const int>
  face_loop(std::size_t face_id) const noexcept;
  [[nodiscard]] static std::expected<PolyhedralBRep, TopologyStatus>
  from_polygons(std::vector<Point3> vertices,
                const std::vector<std::vector<int>> &polygons,
                LengthUnit unit = LengthUnit::Millimeter,
                bool share_edges = true);
  [[nodiscard]] std::expected<std::vector<int>, TopologyStatus>
  face_vertices(std::size_t face_id) const;
  [[nodiscard]] std::expected<std::vector<std::array<int, 3>>, TopologyStatus>
  triangulate_face(std::size_t face_id,
                   float planarity_tolerance = 1e-6f) const;
  [[nodiscard]] std::expected<TriangleMesh, TopologyStatus>
  triangulate_convex_faces(float planarity_tolerance = 1e-6f) const;
};

struct Ray {
  Point3 origin;
  Point3 direction;
  // Finite origin and nonzero finite direction required; invalid input throws
  // std::invalid_argument. Queries normalize direction, so t is distance.
  [[nodiscard]] static Ray create(Point3 orig, Point3 dir);
};
struct IntersectionResult {
  bool hit = false;
  double t = std::numeric_limits<double>::infinity();
  double u = 0;
  double v = 0;
  std::size_t triangle_index = std::numeric_limits<std::size_t>::max();
  std::optional<std::size_t> polygonal_face_id = std::nullopt;
};
struct AABB {
  Point3 min_pt = {INFINITY_VALUE, INFINITY_VALUE, INFINITY_VALUE};
  Point3 max_pt = {-INFINITY_VALUE, -INFINITY_VALUE, -INFINITY_VALUE};
  void grow(const Point3 &pt) noexcept;
  void grow(const AABB &other) noexcept;
  [[nodiscard]] bool intersects(const AABB &other) const noexcept;
  [[nodiscard]] bool intersects_ray(const Ray &ray,
                                    double &t_min_out) const noexcept;

private:
  static constexpr float INFINITY_VALUE =
      std::numeric_limits<float>::infinity();
};

struct FlatBVHNode {
  AABB bounds;
  std::size_t primitive_offset = 0;
  std::size_t primitive_count = 0;
  std::size_t second_child_offset = 0;
};
class FlatBVH {
public:
  // Mesh indices and finite coordinates are checked; malformed meshes throw
  // std::invalid_argument. The BVH owns a copy of the admitted mesh snapshot.
  [[nodiscard]] static FlatBVH build(const TriangleMesh &mesh);
  // Appends primitive-box overlap candidates, not exact triangle-box
  // intersections.
  void query_box(const AABB &bounds, std::vector<std::size_t> &triangles) const;
  [[nodiscard]] IntersectionResult intersect_ray(const Ray &ray) const;
  [[nodiscard]] std::vector<IntersectionResult>
  parallel_intersect_rays(const std::vector<Ray> &rays) const;
  [[nodiscard]] std::size_t node_count() const noexcept { return nodes.size(); }

private:
  [[nodiscard]] IntersectionResult
  intersect_normalized_ray(const Ray &ray) const;
  TriangleMesh mesh_;
  std::size_t build_recursive(const TriangleMesh &mesh, std::size_t start,
                              std::size_t end);
  std::vector<FlatBVHNode> nodes;
  std::vector<std::size_t> primitive_indices;
};

} // namespace cad::simplicial
