#pragma once

#include <array>
#include <compare>
#include <cstddef>
#include <cstdint>
#include <expected>
#include <limits>
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
  Point3 inv_direction;
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
  // std::invalid_argument. The query mesh must be the unchanged build mesh.
  [[nodiscard]] static FlatBVH build(const TriangleMesh &mesh);
  // Appends primitive-box overlap candidates, not exact triangle-box
  // intersections.
  void query_box(const AABB &bounds, std::vector<std::size_t> &triangles) const;
  [[nodiscard]] IntersectionResult intersect_ray(const TriangleMesh &mesh,
                                                 const Ray &ray) const;
  [[nodiscard]] std::vector<IntersectionResult>
  parallel_intersect_rays(const TriangleMesh &mesh,
                          const std::vector<Ray> &rays) const;
  [[nodiscard]] std::size_t node_count() const noexcept { return nodes.size(); }

private:
  std::size_t build_recursive(const TriangleMesh &mesh, std::size_t start,
                              std::size_t end);
  std::vector<FlatBVHNode> nodes;
  std::vector<std::size_t> primitive_indices;
};

} // namespace cad::simplicial
