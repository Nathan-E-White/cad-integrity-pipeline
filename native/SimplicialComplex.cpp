#include "SimplicialComplex.hpp"

#include <algorithm>
#include <bit>
#include <cmath>
#include <future>
#include <numeric>
#include <map>
#include <deque>
#include <set>
#include <stdexcept>
#include <thread>
#include <utility>

namespace cad::simplicial {
namespace {

bool valid_unit(LengthUnit unit) noexcept {
  switch (unit) {
  case LengthUnit::Millimeter:
  case LengthUnit::Centimeter:
  case LengthUnit::Meter:
  case LengthUnit::Inch:
    return true;
  }
  return false;
}
bool finite_point(const Point3 &point) noexcept {
  return std::all_of(point.begin(), point.end(),
                     [](float x) { return std::isfinite(x); });
}
bool valid_layout(const PolyhedralBRep &model) noexcept {
  if (model.face_offsets.empty())
    return model.face_coedges.empty();
  return model.face_offsets.front() == 0 &&
         model.face_offsets.back() == model.face_coedges.size() &&
         std::is_sorted(model.face_offsets.begin(), model.face_offsets.end());
}
std::expected<void, TopologyStatus>
validate_vertices(std::span<const Point3> vertices, LengthUnit unit) {
  if (!valid_unit(unit))
    return std::unexpected(TopologyStatus::UnsupportedUnit);
  if (vertices.size() >
      static_cast<std::size_t>(std::numeric_limits<int>::max()))
    return std::unexpected(TopologyStatus::InputTooLarge);
  for (const auto &point : vertices)
    if (!finite_point(point))
      return std::unexpected(TopologyStatus::NonfiniteInput);
  return {};
}

using WorkPoint = std::array<double, 3>;
WorkPoint widen(const Point3 &p) noexcept { return {p[0], p[1], p[2]}; }
WorkPoint vec_sub(const WorkPoint &a, const WorkPoint &b) noexcept {
  return {a[0] - b[0], a[1] - b[1], a[2] - b[2]};
}
double vec_dot(const WorkPoint &a, const WorkPoint &b) noexcept {
  return a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
}
WorkPoint vec_cross(const WorkPoint &a, const WorkPoint &b) noexcept {
  return {a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2],
          a[0] * b[1] - a[1] * b[0]};
}
double vec_norm(const WorkPoint &a) noexcept {
  return std::hypot(a[0], a[1], a[2]);
}

IntersectionResult ray_triangle_intersect(const Ray &ray, const Point3 &v0,
                                          const Point3 &v1, const Point3 &v2,
                                          std::size_t tri_idx) noexcept {
  const auto edge1 = vec_sub(widen(v1), widen(v0));
  const auto edge2 = vec_sub(widen(v2), widen(v0));
  const auto direction = widen(ray.direction);
  const auto h = vec_cross(direction, edge2);
  const auto determinant = vec_dot(edge1, h);
  const auto threshold = 32 * std::numeric_limits<double>::epsilon() *
                         vec_norm(edge1) * vec_norm(edge2) *
                         vec_norm(direction);
  if (std::abs(determinant) <= threshold)
    return {};
  const auto offset = vec_sub(widen(ray.origin), widen(v0));
  const auto u = vec_dot(offset, h) / determinant;
  if (u < 0 || u > 1)
    return {};
  const auto q = vec_cross(offset, edge1);
  const auto v = vec_dot(direction, q) / determinant;
  if (v < 0 || u + v > 1)
    return {};
  const auto distance = vec_dot(edge2, q) / determinant;
  if (distance <= 0)
    return {};
  return {true, distance, u, v, tri_idx};
}
} // namespace

Ray Ray::create(Point3 orig, Point3 dir) {
  if (!finite_point(orig) || !finite_point(dir))
    throw std::invalid_argument("ray requires finite coordinates");
  const auto length = std::hypot(static_cast<double>(dir[0]), dir[1], dir[2]);
  if (length == 0)
    throw std::invalid_argument("ray requires a nonzero direction");
  for (auto &x : dir)
    x = static_cast<float>(x / length);
  return {orig, dir};
}

void AABB::grow(const Point3 &pt) noexcept {
  min_pt[0] = std::min(min_pt[0], pt[0]);
  min_pt[1] = std::min(min_pt[1], pt[1]);
  min_pt[2] = std::min(min_pt[2], pt[2]);
  max_pt[0] = std::max(max_pt[0], pt[0]);
  max_pt[1] = std::max(max_pt[1], pt[1]);
  max_pt[2] = std::max(max_pt[2], pt[2]);
}

void AABB::grow(const AABB &other) noexcept {
  min_pt[0] = std::min(min_pt[0], other.min_pt[0]);
  min_pt[1] = std::min(min_pt[1], other.min_pt[1]);
  min_pt[2] = std::min(min_pt[2], other.min_pt[2]);
  max_pt[0] = std::max(max_pt[0], other.max_pt[0]);
  max_pt[1] = std::max(max_pt[1], other.max_pt[1]);
  max_pt[2] = std::max(max_pt[2], other.max_pt[2]);
}

bool AABB::intersects(const AABB &other) const noexcept {
  return (min_pt[0] <= other.max_pt[0] && max_pt[0] >= other.min_pt[0]) &&
         (min_pt[1] <= other.max_pt[1] && max_pt[1] >= other.min_pt[1]) &&
         (min_pt[2] <= other.max_pt[2] && max_pt[2] >= other.min_pt[2]);
}

bool AABB::intersects_ray(const Ray &ray, double &t_min_out) const noexcept {
  double lower = 0, upper = std::numeric_limits<double>::infinity();
  for (std::size_t axis = 0; axis < 3; ++axis) {
    if (ray.direction[axis] == 0) {
      if (ray.origin[axis] < min_pt[axis] || ray.origin[axis] > max_pt[axis])
        return false;
      continue;
    }
    auto a = (static_cast<double>(min_pt[axis]) - ray.origin[axis]) /
             ray.direction[axis];
    auto b = (static_cast<double>(max_pt[axis]) - ray.origin[axis]) /
             ray.direction[axis];
    if (a > b)
      std::swap(a, b);
    lower = std::max(lower, a);
    upper = std::min(upper, b);
    if (lower > upper)
      return false;
  }
  t_min_out = lower;
  return true;
}

std::size_t Simplex::dim() const noexcept {
  return vertices.empty() ? 0 : vertices.size() - 1;
}

FlatBVH FlatBVH::build(const TriangleMesh &mesh) {
  if (!validate_vertices(mesh.vertices, mesh.length_unit))
    throw std::invalid_argument(
        "BVH requires finite mesh vertices and a supported unit");
  for (const auto &triangle : mesh.triangles)
    for (auto index : triangle)
      if (index < 0 || static_cast<std::size_t>(index) >= mesh.vertices.size())
        throw std::invalid_argument("BVH triangle index out of range");
  if (mesh.triangles.size() > std::numeric_limits<std::size_t>::max() / 2)
    throw std::length_error("BVH node count is not representable");

  if (!mesh.polygonal_face_ids.empty() &&
      mesh.polygonal_face_ids.size() != mesh.triangles.size())
    throw std::invalid_argument(
        "polygonal face IDs must match the triangle count");
  FlatBVH bvh;
  bvh.mesh_ = mesh;
  if (mesh.triangles.empty())
    return bvh;

  std::size_t num_tris = mesh.triangles.size();
  bvh.primitive_indices.resize(num_tris);
  std::iota(bvh.primitive_indices.begin(), bvh.primitive_indices.end(), 0);

  bvh.nodes.reserve(2 * num_tris - 1);
  bvh.build_recursive(mesh, 0, num_tris);
  return bvh;
}

void FlatBVH::query_box(const AABB &query_bounds,
                        std::vector<std::size_t> &out_triangles) const {
  if (nodes.empty())
    return;

  std::size_t idx = 0;
  while (idx < nodes.size()) {
    const auto &node = nodes[idx];
    if (node.bounds.intersects(query_bounds)) {
      if (node.primitive_count > 0) {
        for (std::size_t i = 0; i < node.primitive_count; ++i) {
          out_triangles.push_back(primitive_indices[node.primitive_offset + i]);
        }
        idx++;
      } else {
        idx++;
      }
    } else {
      if (node.primitive_count > 0) {
        idx++;
      } else {
        idx = node.second_child_offset;
      }
    }
  }
}

IntersectionResult FlatBVH::intersect_ray(const Ray &ray) const {
  return intersect_normalized_ray(Ray::create(ray.origin, ray.direction));
}

IntersectionResult FlatBVH::intersect_normalized_ray(const Ray &ray) const {
  const auto &mesh = mesh_;
  IntersectionResult closest_hit;
  if (nodes.empty())
    return closest_hit;

  std::size_t idx = 0;
  double t_dummy = 0;

  while (idx < nodes.size()) {
    const auto &node = nodes[idx];

    if (node.bounds.intersects_ray(ray, t_dummy) && t_dummy < closest_hit.t) {
      if (node.primitive_count > 0) {
        for (std::size_t i = 0; i < node.primitive_count; ++i) {
          std::size_t tri_idx = primitive_indices[node.primitive_offset + i];
          const auto &tri = mesh.triangles[tri_idx];

          auto hit = ray_triangle_intersect(ray, mesh.vertices[tri[0]],
                                            mesh.vertices[tri[1]],
                                            mesh.vertices[tri[2]], tri_idx);
          if (hit.hit && hit.t < closest_hit.t) {
            closest_hit = hit;
            if (!mesh.polygonal_face_ids.empty())
              closest_hit.polygonal_face_id = mesh.polygonal_face_ids[tri_idx];
          }
        }
        idx++;
      } else {
        idx++;
      }
    } else {
      if (node.primitive_count > 0) {
        idx++;
      } else {
        idx = node.second_child_offset;
      }
    }
  }
  return closest_hit;
}

std::vector<IntersectionResult>
FlatBVH::parallel_intersect_rays(const std::vector<Ray> &rays) const {
  std::vector<Ray> normalized;
  normalized.reserve(rays.size());
  for (const auto &ray : rays)
    normalized.push_back(Ray::create(ray.origin, ray.direction));
  std::vector<IntersectionResult> global_results(rays.size());
  if (rays.empty())
    return global_results;

  unsigned int hardware_threads = std::thread::hardware_concurrency();
  std::size_t num_workers = std::max<std::size_t>(
      1, std::min<std::size_t>(hardware_threads, rays.size() / 16));

  std::vector<std::future<void>> futures;
  std::size_t chunk_size = rays.size() / num_workers;

  for (std::size_t w = 0; w < num_workers; ++w) {
    std::size_t start_idx = w * chunk_size;
    std::size_t end_idx =
        (w == num_workers - 1) ? rays.size() : start_idx + chunk_size;

    futures.push_back(
        std::async(std::launch::async, [this, &normalized, &global_results,
                                        start_idx, end_idx]() {
          for (std::size_t i = start_idx; i < end_idx; ++i) {
            global_results[i] = this->intersect_normalized_ray(normalized[i]);
          }
        }));
  }

  for (auto &f : futures) {
    f.get();
  }

  return global_results;
}

std::size_t FlatBVH::build_recursive(const TriangleMesh &mesh,
                                     std::size_t start, std::size_t end) {
  std::size_t node_idx = nodes.size();
  nodes.emplace_back();

  AABB node_bounds;
  AABB centroid_bounds;
  for (std::size_t i = start; i < end; ++i) {
    std::size_t tri_idx = primitive_indices[i];
    const auto &tri = mesh.triangles[tri_idx];

    AABB tri_box;
    tri_box.grow(mesh.vertices[tri[0]]);
    tri_box.grow(mesh.vertices[tri[1]]);
    tri_box.grow(mesh.vertices[tri[2]]);
    node_bounds.grow(tri_box);

    std::array<float, 3> centroid = {
        static_cast<float>((static_cast<double>(mesh.vertices[tri[0]][0]) +
                            mesh.vertices[tri[1]][0] +
                            mesh.vertices[tri[2]][0]) /
                           3.0),
        static_cast<float>((static_cast<double>(mesh.vertices[tri[0]][1]) +
                            mesh.vertices[tri[1]][1] +
                            mesh.vertices[tri[2]][1]) /
                           3.0),
        static_cast<float>((static_cast<double>(mesh.vertices[tri[0]][2]) +
                            mesh.vertices[tri[1]][2] +
                            mesh.vertices[tri[2]][2]) /
                           3.0)};
    centroid_bounds.grow(centroid);
  }

  nodes[node_idx].bounds = node_bounds;
  std::size_t count = end - start;

  if (count <= 1) {
    nodes[node_idx].primitive_offset = static_cast<std::size_t>(start);
    nodes[node_idx].primitive_count = static_cast<std::size_t>(count);
    return node_idx;
  }

  int axis = 0;
  float ext0 = centroid_bounds.max_pt[0] - centroid_bounds.min_pt[0];
  float ext1 = centroid_bounds.max_pt[1] - centroid_bounds.min_pt[1];
  float ext2 = centroid_bounds.max_pt[2] - centroid_bounds.min_pt[2];
  if (ext1 > ext0)
    axis = 1;
  if (ext2 > std::max(ext0, ext1))
    axis = 2;

  const auto mid = start + count / 2;
  const auto centroid = [&](std::size_t index) {
    const auto &t = mesh.triangles[index];
    return (static_cast<double>(mesh.vertices[t[0]][axis]) +
            mesh.vertices[t[1]][axis] + mesh.vertices[t[2]][axis]) /
           3;
  };
  std::nth_element(primitive_indices.begin() + start,
                   primitive_indices.begin() + mid,
                   primitive_indices.begin() + end, [&](auto a, auto b) {
                     const auto ca = centroid(a), cb = centroid(b);
                     return ca < cb || (ca == cb && a < b);
                   });

  build_recursive(mesh, start, mid);
  std::size_t right_child_idx = build_recursive(mesh, mid, end);
  nodes[node_idx].second_child_offset =
      static_cast<std::size_t>(right_child_idx);

  return node_idx;
}

std::size_t PolyhedralBRep::face_count() const noexcept {
  return face_offsets.empty() ? 0 : face_offsets.size() - 1;
}

std::span<const int>
PolyhedralBRep::face_loop(std::size_t face_id) const noexcept {
  if (face_id >= face_count())
    return {};
  const auto begin = face_offsets[face_id], end = face_offsets[face_id + 1];
  if (begin > end || end > face_coedges.size())
    return {};
  return std::span<const int>(face_coedges).subspan(begin, end - begin);
}

std::expected<PolyhedralBRep, TopologyStatus>
PolyhedralBRep::from_polygons(std::vector<Point3> vertices,
                              const std::vector<std::vector<int>> &polygons,
                              LengthUnit unit, bool share_edges) {
  const auto admission = validate_vertices(vertices, unit);
  if (!admission)
    return std::unexpected(admission.error());

  std::vector<std::array<int, 2>> edges;

  struct EdgeKey {
    int u, v;
    auto operator<=>(const EdgeKey &) const = default;
  };
  std::vector<std::pair<EdgeKey, int>> lookup;

  std::vector<std::size_t> face_offsets = {0};
  std::vector<int> face_coedges;
  const int num_verts = static_cast<int>(vertices.size());

  for (const auto &polygon : polygons) {
    if (polygon.size() < 3)
      return std::unexpected(TopologyStatus::DegenerateTriangle);

    std::vector<int> uniq = polygon;
    std::sort(uniq.begin(), uniq.end());
    if (std::adjacent_find(uniq.begin(), uniq.end()) != uniq.end()) {
      return std::unexpected(TopologyStatus::DuplicateVertices);
    }
    for (int v : polygon) {
      if (v < 0 || v >= num_verts)
        return std::unexpected(TopologyStatus::IndexOutOfBounds);
    }

    std::size_t n = polygon.size();
    for (std::size_t i = 0; i < n; ++i) {
      int u = polygon[i];
      int v = polygon[(i + 1) % n];
      EdgeKey key{std::min(u, v), std::max(u, v)};

      int edge_id = -1;
      auto it = std::lower_bound(
          lookup.begin(), lookup.end(), key,
          [](const auto &pair, const EdgeKey &k) { return pair.first < k; });

      if (!share_edges || it == lookup.end() || it->first != key) {
        if (edges.size() >=
            static_cast<std::size_t>(std::numeric_limits<int>::max()))
          return std::unexpected(TopologyStatus::InputTooLarge);
        edge_id = static_cast<int>(edges.size());
        edges.push_back({key.u, key.v});
        if (share_edges) {
          lookup.insert(it, {key, edge_id});
        }
      } else {
        edge_id = it->second;
      }

      int token = edge_id + 1;
      face_coedges.push_back(u < v ? token : -token);
    }
    face_offsets.push_back(face_coedges.size());
  }

  return PolyhedralBRep{.vertices = std::move(vertices),
                        .edges = std::move(edges),
                        .face_offsets = std::move(face_offsets),
                        .face_coedges = std::move(face_coedges),
                        .length_unit = unit};
}

namespace {
std::expected<std::vector<int>, TopologyStatus>
validated_face_vertices(const PolyhedralBRep &model, std::size_t face_id) {
  auto tokens = model.face_loop(face_id);
  if (tokens.empty())
    return std::unexpected(TopologyStatus::IndexOutOfBounds);

  std::vector<std::array<int, 2>> endpoints;
  endpoints.reserve(tokens.size());

  for (int t : tokens) {
    if (t == 0 || t == std::numeric_limits<int>::min())
      return std::unexpected(TopologyStatus::IndexOutOfBounds);
    const auto edge_idx = static_cast<std::size_t>(t < 0 ? -t : t) - 1;
    if (edge_idx >= model.edges.size()) {
      return std::unexpected(TopologyStatus::IndexOutOfBounds);
    }
    auto edge = model.edges[edge_idx];
    for (auto vertex : edge)
      if (vertex < 0 ||
          static_cast<std::size_t>(vertex) >= model.vertices.size())
        return std::unexpected(TopologyStatus::IndexOutOfBounds);
    if (t < 0)
      std::swap(edge[0], edge[1]);
    endpoints.push_back(edge);
  }

  std::size_t n = endpoints.size();
  for (std::size_t i = 0; i < n; ++i) {
    if (endpoints[i][1] != endpoints[(i + 1) % n][0]) {
      return std::unexpected(TopologyStatus::DisconnectedLoop);
    }
  }

  std::vector<int> face_verts;
  face_verts.reserve(n);
  for (std::size_t i = 0; i < n; ++i) {
    face_verts.push_back(endpoints[i][0]);
  }

  return face_verts;
}
} // namespace
std::expected<std::vector<int>, TopologyStatus>
PolyhedralBRep::face_vertices(std::size_t face_id) const {
  if (!valid_layout(*this))
    return std::unexpected(TopologyStatus::InvalidLayout);
  return validated_face_vertices(*this, face_id);
}

namespace {
// Project along the dominant normal coordinate. Near-collinear decisions are
// conservative and independent of the caller's plane-distance tolerance.
using PlanePoint = std::array<double, 2>;
int side(const PlanePoint &a, const PlanePoint &b,
         const PlanePoint &c) noexcept {
  const auto x = b[0] - a[0], y = b[1] - a[1];
  const auto u = c[0] - a[0], v = c[1] - a[1];
  const auto area = x * v - y * u;
  const auto uncertainty = 32 * std::numeric_limits<double>::epsilon() *
                           std::hypot(x, y) * std::hypot(u, v);
  return area > uncertainty ? 1 : (area < -uncertainty ? -1 : 0);
}
bool on_segment(const PlanePoint &a, const PlanePoint &b,
                const PlanePoint &p) noexcept {
  return p[0] >= std::min(a[0], b[0]) && p[0] <= std::max(a[0], b[0]) &&
         p[1] >= std::min(a[1], b[1]) && p[1] <= std::max(a[1], b[1]);
}
bool segments_meet(const PlanePoint &a, const PlanePoint &b,
                   const PlanePoint &c, const PlanePoint &d) noexcept {
  const auto ab_c = side(a, b, c), ab_d = side(a, b, d);
  const auto cd_a = side(c, d, a), cd_b = side(c, d, b);
  return (ab_c * ab_d < 0 && cd_a * cd_b < 0) ||
         (ab_c == 0 && on_segment(a, b, c)) ||
         (ab_d == 0 && on_segment(a, b, d)) ||
         (cd_a == 0 && on_segment(c, d, a)) ||
         (cd_b == 0 && on_segment(c, d, b));
}

std::expected<std::vector<std::array<int, 3>>, TopologyStatus>
validated_triangulate_face(const PolyhedralBRep &model, std::size_t face_id,
                           float planarity_tolerance) {
  auto verts_res = validated_face_vertices(model, face_id);
  if (!verts_res)
    return std::unexpected(verts_res.error());
  const auto &ids = *verts_res;

  auto distinct = ids;
  std::sort(distinct.begin(), distinct.end());
  if (std::adjacent_find(distinct.begin(), distinct.end()) != distinct.end())
    return std::unexpected(TopologyStatus::DuplicateVertices);
  if (ids.size() < 3)
    return std::unexpected(TopologyStatus::DegenerateTriangle);

  std::vector<WorkPoint> xyz;
  xyz.reserve(ids.size());
  for (int id : ids)
    xyz.push_back(widen(model.vertices[id]));

  auto r1 = vec_sub(xyz[1], xyz[0]);
  auto r2 = vec_sub(xyz[2], xyz[0]);
  auto normal = vec_cross(r1, r2);
  double n_norm = vec_norm(normal);

  if (!std::isfinite(n_norm))
    return std::unexpected(TopologyStatus::NonfiniteInput);
  if (n_norm == 0.0f)
    return std::unexpected(TopologyStatus::DegenerateTriangle);
  normal = {normal[0] / n_norm, normal[1] / n_norm, normal[2] / n_norm};

  for (const auto &pt : xyz) {
    auto rel = vec_sub(pt, xyz[0]);
    const auto distance = vec_dot(rel, normal);
    if (!std::isfinite(distance))
      return std::unexpected(TopologyStatus::NonfiniteInput);
    if (std::abs(distance) > planarity_tolerance) {
      return std::unexpected(TopologyStatus::NonPlanarFace);
    }
  }

  std::size_t drop = 0;
  for (std::size_t axis = 1; axis < 3; ++axis)
    if (std::abs(normal[axis]) > std::abs(normal[drop]))
      drop = axis;
  std::vector<PlanePoint> projected;
  projected.reserve(xyz.size());
  for (const auto &p : xyz)
    projected.push_back({p[(drop + 1) % 3], p[(drop + 2) % 3]});
  for (std::size_t i = 0; i < ids.size(); ++i) {
    for (std::size_t j = i + 1; j < ids.size(); ++j) {
      const auto ni = (i + 1) % ids.size(), nj = (j + 1) % ids.size();
      if (ni == j || nj == i)
        continue;
      if (segments_meet(projected[i], projected[ni], projected[j],
                        projected[nj]))
        return std::unexpected(TopologyStatus::NonConvexFace);
    }
  }

  for (std::size_t k = 0; k < ids.size(); ++k) {
    auto edge = vec_sub(xyz[(k + 1) % ids.size()], xyz[k]);
    double edge_len = vec_norm(edge);
    if (!std::isfinite(edge_len))
      return std::unexpected(TopologyStatus::NonfiniteInput);
    if (edge_len == 0)
      return std::unexpected(TopologyStatus::DegenerateTriangle);

    for (std::size_t m = 0; m < ids.size(); ++m) {
      auto diff = vec_sub(xyz[m], xyz[k]);
      auto cross_side = vec_cross(edge, diff);
      double orientation = vec_dot(cross_side, normal);
      if (!std::isfinite(orientation))
        return std::unexpected(TopologyStatus::NonfiniteInput);
      const auto uncertainty = 32 * std::numeric_limits<double>::epsilon() *
                               edge_len * vec_norm(diff);
      if (orientation < -uncertainty) {
        return std::unexpected(TopologyStatus::NonConvexFace);
      }
    }
  }

  std::vector<std::array<int, 3>> face_tris;
  face_tris.reserve(ids.size() - 2);
  for (std::size_t i = 1; i < ids.size() - 1; ++i) {
    const auto a = vec_sub(xyz[i], xyz[0]), b = vec_sub(xyz[i + 1], xyz[0]);
    if (vec_norm(vec_cross(a, b)) <=
        32 * std::numeric_limits<double>::epsilon() * vec_norm(a) * vec_norm(b))
      return std::unexpected(TopologyStatus::DegenerateTriangle);
    face_tris.push_back({ids[0], ids[i], ids[i + 1]});
  }
  return face_tris;
}
} // namespace
std::expected<std::vector<std::array<int, 3>>, TopologyStatus>
PolyhedralBRep::triangulate_face(std::size_t face_id,
                                 float planarity_tolerance) const {
  if (!std::isfinite(planarity_tolerance) || planarity_tolerance < 0)
    return std::unexpected(TopologyStatus::InvalidTolerance);
  if (!valid_layout(*this))
    return std::unexpected(TopologyStatus::InvalidLayout);
  const auto admission = validate_vertices(vertices, length_unit);
  if (!admission)
    return std::unexpected(admission.error());
  return validated_triangulate_face(*this, face_id, planarity_tolerance);
}

std::expected<TriangleMesh, TopologyStatus>
PolyhedralBRep::triangulate_convex_faces(float planarity_tolerance) const {
  if (!std::isfinite(planarity_tolerance) || planarity_tolerance < 0)
    return std::unexpected(TopologyStatus::InvalidTolerance);
  if (!valid_layout(*this))
    return std::unexpected(TopologyStatus::InvalidLayout);
  const auto admission = validate_vertices(vertices, length_unit);
  if (!admission)
    return std::unexpected(admission.error());

  std::vector<std::array<int, 3>> global_triangles;
  std::vector<std::size_t> face_ids;
  for (std::size_t f = 0; f < face_count(); ++f) {
    auto tris_res = validated_triangulate_face(*this, f, planarity_tolerance);
    if (!tris_res)
      return std::unexpected(tris_res.error());
    face_ids.insert(face_ids.end(), tris_res->size(), f);
    global_triangles.insert(global_triangles.end(), tris_res->begin(),
                            tris_res->end());
  }
  return TriangleMesh{.vertices = this->vertices,
                      .triangles = std::move(global_triangles),
                      .length_unit = this->length_unit,
                      .polygonal_face_ids = std::move(face_ids)};
}

int SimplicialComplex::compare_skipped_face(std::span<const int> lower,
                                            std::span<const int> upper,
                                            std::size_t skip_idx) noexcept {
  std::size_t l_idx = 0;
  for (std::size_t u_idx = 0; u_idx < upper.size(); ++u_idx) {
    if (u_idx == skip_idx) [[unlikely]]
      continue;
    if (l_idx >= lower.size())
      return -1;

    if (lower[l_idx] < upper[u_idx])
      return -1;
    if (lower[l_idx] > upper[u_idx])
      return 1;
    l_idx++;
  }
  return (l_idx < lower.size()) ? 1 : 0;
}

std::size_t
SimplicialComplex::find_face_index(std::span<const Simplex> lower_tier,
                                   const Simplex &upper,
                                   std::size_t skip_idx) noexcept {
  std::size_t low = 0, high = lower_tier.size();
  while (low < high) {
    const auto mid = low + (high - low) / 2;
    const auto comparison = compare_skipped_face(lower_tier[mid].vertices,
                                                 upper.vertices, skip_idx);
    if (comparison == 0)
      return mid;
    if (comparison < 0)
      low = mid + 1;
    else
      high = mid;
  }
  return std::numeric_limits<std::size_t>::max();
}

std::expected<SimplicialComplex, TopologyStatus>
SimplicialComplex::build_from_mesh_engine(const TriangleMesh &mesh,
                                          std::size_t simplex_budget) {
  if (mesh.vertices.size() >
      static_cast<std::size_t>(std::numeric_limits<int>::max()))
    return std::unexpected(TopologyStatus::InputTooLarge);
  if (mesh.vertices.size() > simplex_budget ||
      mesh.triangles.size() > simplex_budget)
    return std::unexpected(TopologyStatus::BudgetExceeded);
  std::set<std::array<int, 3>> triangles;
  std::vector<std::vector<int>> facets;
  for (auto triangle : mesh.triangles) {
    for (auto index : triangle)
      if (index < 0 || static_cast<std::size_t>(index) >= mesh.vertices.size())
        return std::unexpected(TopologyStatus::IndexOutOfBounds);
    std::sort(triangle.begin(), triangle.end());
    if (triangle[0] == triangle[1] || triangle[1] == triangle[2])
      return std::unexpected(TopologyStatus::DegenerateTriangle);
    if (!triangles.insert(triangle).second)
      return std::unexpected(TopologyStatus::DuplicateTriangles);
    facets.emplace_back(triangle.begin(), triangle.end());
  }
  for (std::size_t i = 0; i < mesh.vertices.size(); ++i)
    facets.push_back({static_cast<int>(i)});
  auto result = build(facets, simplex_budget);
  if (!result)
    return result;
  result->spatial_tiers_.resize(3);
  result->max_dim_ = 2;
  return result;
}

std::span<const Simplex>
SimplicialComplex::get_tier(std::size_t d) const noexcept {
  return (d < spatial_tiers_.size()) ? spatial_tiers_[d]
                                     : std::span<const Simplex>{};
}

std::expected<SparseCSR, TopologyStatus>
SimplicialComplex::boundary_operator(std::size_t d) const {
  if (d == 0 || d > max_dim_)
    return std::unexpected(TopologyStatus::InvalidDimension);

  auto current_cols = get_tier(d);
  auto lower_rows = get_tier(d - 1);

  SparseCSR csr;
  csr.num_rows = lower_rows.size();
  csr.num_cols = current_cols.size();
  csr.row_ptr.assign(csr.num_rows + 1, 0);

  if (current_cols.empty())
    return csr;

  for (std::size_t j = 0; j < current_cols.size(); ++j) {
    const auto &upper_simplex = current_cols[j];
    for (std::size_t k = 0; k < upper_simplex.vertices.size(); ++k) {
      std::size_t i = find_face_index(lower_rows, upper_simplex, k);
      if (i != std::numeric_limits<std::size_t>::max()) {
        csr.row_ptr[i + 1]++;
      }
    }
  }

  for (std::size_t i = 0; i < csr.num_rows; ++i) {
    csr.row_ptr[i + 1] += csr.row_ptr[i];
  }

  std::size_t total_nnz = csr.row_ptr.back();
  csr.col_ind.resize(total_nnz);
  csr.values.resize(total_nnz);

  std::vector<std::size_t> write_cursors = csr.row_ptr;

  for (std::size_t j = 0; j < current_cols.size(); ++j) {
    const auto &upper_simplex = current_cols[j];
    for (std::size_t k = 0; k < upper_simplex.vertices.size(); ++k) {
      std::size_t i = find_face_index(lower_rows, upper_simplex, k);
      if (i != std::numeric_limits<std::size_t>::max()) {
        std::size_t write_pos = write_cursors[i]++;
        csr.col_ind[write_pos] = j;
        csr.values[write_pos] = (k % 2 == 0) ? 1 : -1;
      }
    }
  }

  return csr;
}

SimplicialComplex::SimplicialComplex(std::vector<std::vector<Simplex>> tiers,
                                     std::size_t max_dim)
    : spatial_tiers_(std::move(tiers)), max_dim_(max_dim) {}

std::expected<SimplicialComplex, TopologyStatus>
TriangleMesh::to_simplicial_complex(std::size_t max_simplices) const {
  return SimplicialComplex::build_from_mesh_engine(*this, max_simplices);
}

std::expected<SimplicialComplex, TopologyStatus>
SimplicialComplex::build(const std::vector<std::vector<int>> &facets,
                         std::size_t simplex_budget) {
  std::vector<std::set<Simplex>> unique_tiers;
  std::size_t total = 0;
  for (const auto &input : facets) {
    if (input.empty())
      continue;
    // A single facet requires all its nonempty subsets. Reject before shifting
    // or allocating its closure; retained storage never exceeds the budget.
    if (input.size() >= std::numeric_limits<std::size_t>::digits)
      return std::unexpected(TopologyStatus::InputTooLarge);
    const auto subsets = (std::size_t{1} << input.size()) - 1;
    if (subsets > simplex_budget)
      return std::unexpected(TopologyStatus::BudgetExceeded);
    auto facet = input;
    std::sort(facet.begin(), facet.end());
    if (std::adjacent_find(facet.begin(), facet.end()) != facet.end())
      return std::unexpected(TopologyStatus::DuplicateVertices);
    unique_tiers.resize(std::max(unique_tiers.size(), facet.size()));
    for (std::size_t mask = 1; mask <= subsets; ++mask) {
      Simplex face;
      face.vertices.reserve(std::popcount(mask));
      for (std::size_t i = 0; i < facet.size(); ++i)
        if ((mask >> i) & 1)
          face.vertices.push_back(facet[i]);
      auto &tier = unique_tiers[face.dim()];
      if (tier.contains(face))
        continue;
      if (total == simplex_budget)
        return std::unexpected(TopologyStatus::BudgetExceeded);
      tier.insert(std::move(face));
      ++total;
    }
  }
  std::vector<std::vector<Simplex>> tiers(unique_tiers.size());
  for (std::size_t d = 0; d < tiers.size(); ++d) {
    tiers[d].reserve(unique_tiers[d].size());
    while (!unique_tiers[d].empty()) {
      auto node = unique_tiers[d].extract(unique_tiers[d].begin());
      tiers[d].push_back(std::move(node.value()));
    }
  }
  const auto dimension = tiers.empty() ? 0 : tiers.size() - 1;
  return SimplicialComplex(std::move(tiers), dimension);
}

} // namespace cad::simplicial

namespace cad::simplicial {
struct PolygonalStorage {
  PolygonalInput input;
  PolygonalFacts facts;
  PolygonalOrientation orientation;
  PolygonalUsage usage;
  SparseCSR d1, d2;
};
AdmittedPolygonalCells::AdmittedPolygonalCells(std::shared_ptr<const PolygonalStorage> owner)
    : owner_(std::move(owner)) {}
const SparseCSR& AdmittedPolygonalCells::boundary(std::size_t degree) const {
  if (degree == 1) return owner_->d1;
  if (degree == 2) return owner_->d2;
  throw std::out_of_range("Polygonal incidence has degrees 1 and 2");
}
PolygonalAssessment::PolygonalAssessment(std::shared_ptr<const PolygonalStorage> owner, bool admitted)
    : owner_(std::move(owner)) {
  if (admitted) admitted_ = AdmittedPolygonalCells(owner_);
}
const PolygonalInput& PolygonalAssessment::input() const noexcept { return owner_->input; }
const PolygonalFacts& PolygonalAssessment::facts() const noexcept { return owner_->facts; }
const PolygonalOrientation& PolygonalAssessment::orientation() const noexcept { return owner_->orientation; }
const PolygonalUsage& PolygonalAssessment::usage() const noexcept { return owner_->usage; }
const std::optional<AdmittedPolygonalCells>& PolygonalAssessment::admitted_cells() const noexcept { return admitted_; }
namespace {
struct PolygonalStop { PolygonalError error; };
void charge(std::uint64_t& used, std::uint64_t count, std::uint64_t width,
            std::uint64_t limit, PolygonalError error) {
  if (used > limit || count > (limit-used)/width) throw PolygonalStop{error};
  used += count*width;
}
struct WorkMeter {
  PolygonalUsage& usage;
  const PolygonalLimits& limits;
  void step(std::size_t count = 1) {
    charge(usage.work_steps, count, 1, limits.max_work_steps, PolygonalError::work_budget);
  }
};
using CellId = std::int64_t;
using FaceUse = std::pair<CellId, CellId>;
std::size_t token_edge(CellId token) {
  // Called only after rejecting INT64_MIN, zero and out-of-range tokens.
  return static_cast<std::size_t>((token < 0 ? -token : token) - 1);
}
bool polygonal_layout(const PolygonalInput& input, WorkMeter& work) {
  if (!valid_unit(input.length_unit) || input.face_offsets.empty() ||
      input.face_offsets.front() != 0 || input.face_offsets.back() < 0 ||
      static_cast<std::uint64_t>(input.face_offsets.back()) != input.face_coedges.size()) return false;
  work.step(input.face_offsets.size());
  work.step(input.vertices.size()); work.step(input.edges.size()); work.step(input.face_coedges.size());
  for (std::size_t i = 1; i < input.face_offsets.size(); ++i)
    if (input.face_offsets[i] < 0 || input.face_offsets[i-1] > input.face_offsets[i] ||
        input.face_offsets[i] - input.face_offsets[i-1] < 3) return false;
  for (const auto& point : input.vertices)
    for (const auto x : point) if (!std::isfinite(x)) return false;
  for (const auto& edge : input.edges)
    for (const auto v : edge)
      if (v < 0 || static_cast<std::uint64_t>(v) >= input.vertices.size()) return false;
  for (const auto token : input.face_coedges)
    if (token == 0 || token == std::numeric_limits<CellId>::min() ||
        token_edge(token) >= input.edges.size()) return false;
  return true;
}
std::vector<CellId> canonical_cycle(std::vector<CellId> vertices) {
  std::rotate(vertices.begin(), std::min_element(vertices.begin(), vertices.end()), vertices.end());
  auto reversed = vertices;
  std::reverse(reversed.begin() + 1, reversed.end());
  return std::min(vertices, reversed);
}
void classify_faces(PolygonalStorage& storage, WorkMeter& work) {
  const auto& raw = storage.input;
  auto& facts = storage.facts;
  std::set<std::vector<CellId>> seen_faces;
  std::vector<std::vector<std::pair<std::size_t, std::size_t>>> links(raw.vertices.size());
  for (std::size_t face = 0; face + 1 < raw.face_offsets.size(); ++face) {
    work.step();
    const auto start = static_cast<std::size_t>(raw.face_offsets[face]);
    const auto stop = static_cast<std::size_t>(raw.face_offsets[face+1]);
    std::vector<CellId> vertices;
    std::set<CellId> unique;
    bool valid = true;
    for (auto i = start; i < stop; ++i) {
      work.step();
      const auto token = raw.face_coedges[i];
      const auto next = raw.face_coedges[i+1 == stop ? start : i+1];
      const auto& edge = raw.edges[token_edge(token)];
      const auto& other = raw.edges[token_edge(next)];
      const auto vertex = edge[token > 0 ? 0 : 1];
      valid &= edge[token > 0 ? 1 : 0] == other[next > 0 ? 0 : 1];
      valid &= unique.insert(vertex).second;
      vertices.push_back(vertex);
    }
    if (!valid) { facts.invalid_face_ids.push_back(static_cast<CellId>(face)); continue; }
    work.step(vertices.size());
    if (!seen_faces.insert(canonical_cycle(vertices)).second)
      facts.duplicate_face_ids.push_back(static_cast<CellId>(face));
    for (auto i = start; i < stop; ++i)
      links[static_cast<std::size_t>(vertices[i-start])].emplace_back(
          token_edge(raw.face_coedges[i == start ? stop-1 : i-1]), token_edge(raw.face_coedges[i]));
  }
  for (std::size_t vertex = 0; vertex < links.size(); ++vertex) {
    work.step();
    if (links[vertex].empty()) continue;
    std::map<std::size_t, std::vector<std::size_t>> neighbors;
    for (const auto& [a,b] : links[vertex]) { work.step(); neighbors[a].push_back(b); neighbors[b].push_back(a); }
    std::size_t degree_one = 0;
    bool path_or_cycle = true;
    for (const auto& [edge, adjacent] : neighbors) {
      work.step();
      (void)edge;
      degree_one += adjacent.size() == 1;
      path_or_cycle &= adjacent.size() == 1 || adjacent.size() == 2;
    }
    path_or_cycle &= degree_one == 0 || degree_one == 2;
    std::set<std::size_t> seen{neighbors.begin()->first};
    std::vector<std::size_t> pending{neighbors.begin()->first};
    while (!pending.empty()) {
      const auto edge = pending.back(); pending.pop_back();
      for (const auto other : neighbors.at(edge)) {
        work.step();
        if (seen.insert(other).second) pending.push_back(other);
      }
    }
    if (!path_or_cycle || seen.size() != neighbors.size())
      facts.nonmanifold_vertex_ids.push_back(static_cast<CellId>(vertex));
  }
}
void orient_cells(PolygonalStorage& storage, const std::vector<std::vector<FaceUse>>& uses, WorkMeter& work) {
  auto& result = storage.orientation;
  struct Neighbor { std::size_t face; CellId relation, edge; };
  std::vector<std::vector<Neighbor>> adjacent(storage.input.face_offsets.size()-1);
  // First-use edge order matches the host's deterministic insertion/traversal order.
  for (const auto edge : storage.facts.edge_order) {
    work.step();
    const auto& incidents = uses[static_cast<std::size_t>(edge)];
    if (incidents.size() > 2) { result.nonmanifold_edge = edge; return; }
    if (incidents.size() != 2) continue;
    const auto [f,s] = incidents[0]; const auto [g,t] = incidents[1];
    adjacent[static_cast<std::size_t>(f)].push_back({static_cast<std::size_t>(g), -s*t, edge});
    adjacent[static_cast<std::size_t>(g)].push_back({static_cast<std::size_t>(f), -s*t, edge});
  }
  result.multipliers.resize(adjacent.size(), 0);
  std::set<CellId> conflicts;
  for (std::size_t seed = 0; seed < adjacent.size(); ++seed) {
    work.step();
    if (result.multipliers[seed]) continue;
    result.multipliers[seed] = 1;
    std::deque<std::size_t> pending{seed};
    while (!pending.empty()) {
      const auto face = pending.front(); pending.pop_front();
      for (const auto& other : adjacent[face]) {
        work.step();
        const auto expected = result.multipliers[face] * other.relation;
        if (!result.multipliers[other.face]) {
          result.multipliers[other.face] = expected; pending.push_back(other.face);
        } else if (result.multipliers[other.face] != expected) conflicts.insert(other.edge);
      }
    }
  }
  result.conflicting_edge_ids.assign(conflicts.begin(), conflicts.end());
}
void cellular_incidence(PolygonalStorage& storage, WorkMeter& work) {
  work.step(storage.input.vertices.size());
  work.step(storage.input.edges.size()); work.step(storage.input.edges.size());
  work.step(storage.input.face_coedges.size());
  const auto& input = storage.input;
  const auto& facts = storage.facts;
  auto& d1 = storage.d1;
  auto& d2 = storage.d2;
  d1.num_rows = input.vertices.size(); d1.num_cols = input.edges.size();
  d1.row_ptr.resize(d1.num_rows + 1);
  for (const auto& edge : input.edges)
    for (const auto vertex : edge) ++d1.row_ptr[static_cast<std::size_t>(vertex) + 1];
  std::partial_sum(d1.row_ptr.begin(), d1.row_ptr.end(), d1.row_ptr.begin());
  d1.col_ind.resize(input.edges.size() * 2); d1.values.resize(d1.col_ind.size());
  auto next = d1.row_ptr;
  for (std::size_t edge = 0; edge < input.edges.size(); ++edge)
    for (std::size_t end = 0; end < 2; ++end) {
      const auto index = next[static_cast<std::size_t>(input.edges[edge][end])]++;
      d1.col_ind[index] = edge; d1.values[index] = end == 0 ? -1 : 1;
    }
  d2.num_rows = input.edges.size(); d2.num_cols = input.face_offsets.size() - 1;
  d2.row_ptr.assign(facts.edge_offsets.begin(), facts.edge_offsets.end());
  d2.col_ind.assign(facts.edge_faces.begin(), facts.edge_faces.end());
  d2.values.assign(facts.edge_signs.begin(), facts.edge_signs.end());
}
}
std::expected<PolygonalAssessment, PolygonalError>
assess_polygonal(PolygonalInput input, const PolygonalLimits& limits) {
  try {
  PolygonalUsage usage;
  for (const auto count : {input.vertices.size(), input.edges.size(), input.face_offsets.size(), input.face_coedges.size()})
    if (count > static_cast<std::uint64_t>(std::numeric_limits<CellId>::max()))
      return std::unexpected(PolygonalError::invalid_input);
  auto input_charge = [&](std::size_t count, std::uint64_t width) {
    charge(usage.input_bytes, count, width, limits.max_input_bytes, PolygonalError::input_budget);
  };
  input_charge(input.vertices.size(), 24); input_charge(input.edges.size(), 16);
  input_charge(input.face_offsets.size(), 8); input_charge(input.face_coedges.size(), 8);
  WorkMeter admission_work{usage, limits};
  if (!polygonal_layout(input, admission_work)) return std::unexpected(PolygonalError::invalid_input);
  // Conservative logical workspace reservation, not allocator or RSS accounting.
  charge(usage.owned_bytes, usage.input_bytes, 1, limits.max_owned_bytes, PolygonalError::storage_budget);
  for (const auto count : {input.vertices.size(), input.edges.size(), input.face_coedges.size()})
    charge(usage.owned_bytes, count, 256, limits.max_owned_bytes, PolygonalError::storage_budget);
  charge(usage.owned_bytes, input.face_offsets.size()-1, 128, limits.max_owned_bytes, PolygonalError::storage_budget);
  charge(usage.owned_bytes, 1, 64, limits.max_owned_bytes, PolygonalError::storage_budget);
  // All subsequent vector dimensions are bounded by the reservation above.
  if (usage.owned_bytes > std::numeric_limits<std::size_t>::max())
    return std::unexpected(PolygonalError::storage_budget);
  auto storage = std::make_shared<PolygonalStorage>();
  storage->input = std::move(input);
  storage->usage = usage;
  WorkMeter work{storage->usage, limits};
  const auto& raw = storage->input;
  auto& facts = storage->facts;
  std::vector<std::vector<FaceUse>> uses(raw.edges.size());
  for (std::size_t face = 0; face + 1 < raw.face_offsets.size(); ++face)
    for (auto i = raw.face_offsets[face]; i < raw.face_offsets[face+1]; ++i) {
      work.step();
      const auto token = raw.face_coedges[static_cast<std::size_t>(i)];
      const auto edge = token_edge(token);
      if (uses[edge].empty()) facts.edge_order.push_back(static_cast<CellId>(edge));
      uses[edge].emplace_back(static_cast<CellId>(face), token > 0 ? 1 : -1);
    }
  std::vector<bool> active(raw.vertices.size(), false);
  facts.edge_offsets.push_back(0);
  for (std::size_t edge = 0; edge < uses.size(); ++edge) {
    work.step();
    if (uses[edge].size() == 1) facts.boundary_edge_ids.push_back(static_cast<CellId>(edge));
    if (uses[edge].empty()) facts.unused_edge_ids.push_back(static_cast<CellId>(edge));
    else for (const auto v : raw.edges[edge]) active[static_cast<std::size_t>(v)] = true;
    if (uses[edge].size() > 2) facts.nonmanifold_edge_ids.push_back(static_cast<CellId>(edge));
    if (uses[edge].size() == 2 && uses[edge][0].second == uses[edge][1].second)
      facts.inconsistent_orientation_edge_ids.push_back(static_cast<CellId>(edge));
    const auto& ends = raw.edges[edge];
    if (ends[0] == ends[1] || raw.vertices[static_cast<std::size_t>(ends[0])] ==
                            raw.vertices[static_cast<std::size_t>(ends[1])])
      facts.collapsed_edge_ids.push_back(static_cast<CellId>(edge));
    for (const auto& [face, sign] : uses[edge]) {
      work.step();
      facts.edge_faces.push_back(face); facts.edge_signs.push_back(sign);
    }
    facts.edge_offsets.push_back(static_cast<CellId>(facts.edge_faces.size()));
  }
  for (std::size_t v = 0; v < active.size(); ++v)
    if (!active[v]) facts.unused_vertex_ids.push_back(static_cast<CellId>(v));
  work.step(active.size());
  classify_faces(*storage, work);
  orient_cells(*storage, uses, work);
  const bool admitted = raw.face_offsets.size() > 1 && facts.invalid_face_ids.empty() &&
      facts.duplicate_face_ids.empty() && facts.collapsed_edge_ids.empty() &&
      facts.nonmanifold_edge_ids.empty() && facts.nonmanifold_vertex_ids.empty() &&
      facts.unused_vertex_ids.empty() && facts.unused_edge_ids.empty();
  // Charge packed int64 outputs before incidence or binding output allocation.
  auto output = [&](std::size_t count) {
    charge(storage->usage.output_bytes, count, 8, limits.max_output_bytes, PolygonalError::output_budget);
  };
  for (const auto* values : {&facts.boundary_edge_ids, &facts.nonmanifold_edge_ids,
      &facts.inconsistent_orientation_edge_ids, &facts.nonmanifold_vertex_ids,
      &facts.unused_vertex_ids, &facts.unused_edge_ids, &facts.invalid_face_ids,
      &facts.duplicate_face_ids, &facts.collapsed_edge_ids, &facts.edge_offsets,
      &facts.edge_faces, &facts.edge_signs, &facts.edge_order,
      &storage->orientation.multipliers, &storage->orientation.conflicting_edge_ids}) output(values->size());
  if (admitted) {
    output(raw.vertices.size()+1); output(raw.edges.size()+1);
    for (int i = 0; i < 4; ++i) output(raw.edges.size());
    output(raw.face_coedges.size()); output(raw.face_coedges.size());
    output(4); // Two matrix shapes.
    cellular_incidence(*storage, work);
  }
  return PolygonalAssessment(std::move(storage), admitted);
  } catch (const PolygonalStop& stop) { return std::unexpected(stop.error); }
}
}
