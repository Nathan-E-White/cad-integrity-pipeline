#include "surface_preparation.hpp"
#include "surface_storage.hpp"
#include <algorithm>
#include <cmath>
#include <limits>
#include <map>
#include <numeric>
#include <set>

namespace cad::surface {
Discretization::Discretization(std::shared_ptr<const SurfaceStorage> owner)
    : owner_(std::move(owner)) {}
std::span<const Point> Discretization::vertices() const {
  return owner_->vertices;
}
std::span<const Triangle> Discretization::triangles() const {
  return owner_->triangles;
}
std::span<const Triangle> Discretization::triangle_edges() const {
  return owner_->triangle_edges;
}
std::span<const Id> Discretization::source_vertices() const {
  return owner_->source_vertices;
}
std::span<const Id> Discretization::selected_faces() const {
  return owner_->selected_faces;
}
std::span<const Id> Discretization::triangle_faces() const {
  return owner_->triangle_faces;
}
std::span<const Id> Discretization::boundary_vertices() const {
  return owner_->boundary_vertices;
}
bool Discretization::native_faces() const { return owner_->native_faces; }
Id Discretization::source_face_count() const {
  return owner_->source_face_count;
}
simplicial::LengthUnit Discretization::length_unit() const {
  return owner_->unit;
}
const Usage &Discretization::usage() const { return owner_->usage; }
namespace {
struct Accounting {
  SurfaceLimits limits;
  Operation operation;
  Usage usage;
  Id face = -1;
  [[noreturn]] void fail(ErrorCode code) const {
    throw SurfaceError{code, operation, face};
  }
  void charge(std::uint64_t &value, std::uint64_t count, std::uint64_t width,
              std::uint64_t limit, ErrorCode code) const {
    if (value > limit || count > (limit - value) / width)
      fail(code);
    value += count * width;
  }
  void work(std::uint64_t count = 1) {
    charge(usage.work_steps, count, 1, limits.max_work_steps,
           ErrorCode::work_budget);
  }
  void input(std::uint64_t count, std::uint64_t width) {
    charge(usage.input_bytes, count, width, limits.max_input_bytes,
           ErrorCode::input_budget);
  }
  void reserve(std::uint64_t count, std::uint64_t width) {
    charge(usage.owned_bytes, count, width, limits.max_owned_bytes,
           ErrorCode::storage_budget);
  }
  void output(std::uint64_t count, std::uint64_t width) {
    charge(usage.output_bytes, count, width, limits.max_output_bytes,
           ErrorCode::output_budget);
  }
};
Point sub(Point a, Point b, Accounting &bgt) {
  for (int k = 0; k < 3; ++k) {
    a[k] -= b[k];
    if (!std::isfinite(a[k]))
      bgt.fail(ErrorCode::numerical_range);
  }
  return a;
}
Point cross(Point a, Point b) {
  return {a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2],
          a[0] * b[1] - a[1] * b[0]};
}
double dot(Point a, Point b) { return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]; }
double norm(Point a) { return std::hypot(a[0], a[1], a[2]); }
using XY = std::array<double, 2>;
double cross2(XY a, XY b, XY c) {
  return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]);
}
std::vector<Triangle> triangulate(const std::vector<Point> &xyz,
                                  const std::vector<Id> &f, double tol,
                                  Accounting &bgt) {
  std::vector<Point> p;
  double scale = 0;
  for (auto v : f) {
    bgt.work();
    p.push_back(sub(xyz[v], xyz[f[0]], bgt));
    for (double x : p.back())
      scale = std::max(scale, std::abs(x));
  }
  if (scale == 0)
    bgt.fail(ErrorCode::invalid_geometry);
  double radius = 0;
  for (auto &q : p) {
    for (auto &x : q)
      x /= scale;
    radius = std::max(radius, norm(q));
  }
  for (auto &q : p)
    for (auto &x : q)
      x /= radius;
  Point normal{};
  for (std::size_t i = 0; i < p.size(); ++i) {
    auto c = cross(p[i], p[(i + 1) % p.size()]);
    for (int k = 0; k < 3; ++k)
      normal[k] += c[k];
  }
  if (!std::isfinite(norm(normal)))
    bgt.fail(ErrorCode::numerical_range);
  if (norm(normal) <= tol)
    bgt.fail(ErrorCode::invalid_geometry);
  int axis = 0;
  for (int k = 1; k < 3; ++k)
    if (std::abs(normal[k]) > std::abs(normal[axis]))
      axis = k;
  std::vector<XY> q;
  for (auto x : p) {
    XY v{};
    int k = 0;
    for (int j = 0; j < 3; ++j)
      if (j != axis)
        v[k++] = x[j];
    q.push_back(v);
  }
  double area = 0;
  for (std::size_t i = 0; i < q.size(); ++i)
    area +=
        q[i][0] * q[(i + 1) % q.size()][1] - q[i][1] * q[(i + 1) % q.size()][0];
  const double sign = area > 0 ? 1 : -1;
  auto on_segment = [tol](XY a, XY b, XY x) {
    return std::abs(cross2(a, b, x)) <= tol &&
           x[0] >= std::min(a[0], b[0]) - tol &&
           x[0] <= std::max(a[0], b[0]) + tol &&
           x[1] >= std::min(a[1], b[1]) - tol &&
           x[1] <= std::max(a[1], b[1]) + tol;
  };
  const auto n = q.size();
  for (std::size_t i = 0; i < n; ++i)
    for (std::size_t j = i + 1; j < n; ++j) {
      bgt.work();
      if (j == (i + 1) % n || (j + 1) % n == i)
        continue;
      auto a = q[i], b = q[(i + 1) % n], c = q[j], d = q[(j + 1) % n];
      if ((cross2(a, b, c) * cross2(a, b, d) < 0 &&
           cross2(c, d, a) * cross2(c, d, b) < 0) ||
          on_segment(a, b, c) || on_segment(a, b, d) || on_segment(c, d, a) ||
          on_segment(c, d, b))
        bgt.fail(ErrorCode::invalid_geometry);
    }
  if (n == 3)
    return {{f[0], f[1], f[2]}};
  if (n == 4) {
    for (const auto &pair : {std::array<Triangle, 2>{{{0, 1, 2}, {0, 2, 3}}},
                             std::array<Triangle, 2>{{{0, 1, 3}, {1, 2, 3}}}}) {
      bool valid = true;
      for (auto t : pair) {
        bgt.work();
        valid &= sign * cross2(q[t[0]], q[t[1]], q[t[2]]) > tol;
      }
      if (valid)
        return {{f[pair[0][0]], f[pair[0][1]], f[pair[0][2]]},
                {f[pair[1][0]], f[pair[1][1]], f[pair[1][2]]}};
    }
    bgt.fail(ErrorCode::invalid_geometry);
  }
  std::vector<std::size_t> remaining(n), order(n);
  std::iota(remaining.begin(), remaining.end(), 0);
  std::iota(order.begin(), order.end(), 0);
  std::stable_sort(order.begin(), order.end(), [&](auto a, auto b) {
    bgt.work();
    return xyz[f[a]] < xyz[f[b]];
  });
  std::vector<Triangle> out;
  while (remaining.size() > 3) {
    bool found = false;
    for (auto b : order) {
      bgt.work(remaining.size());
      auto pos = std::find(remaining.begin(), remaining.end(), b);
      if (pos == remaining.end())
        continue;
      auto k = static_cast<std::size_t>(pos - remaining.begin()),
           m = remaining.size();
      auto a = remaining[(k + m - 1) % m], c = remaining[(k + 1) % m];
      if (sign * cross2(q[a], q[b], q[c]) <= tol)
        continue;
      bool inside = false;
      for (auto x : remaining) {
        bgt.work();
        if (x == a || x == b || x == c)
          continue;
        if (std::min({sign * cross2(q[a], q[b], q[x]),
                      sign * cross2(q[b], q[c], q[x]),
                      sign * cross2(q[c], q[a], q[x])}) >= -tol) {
          inside = true;
          break;
        }
      }
      if (!inside) {
        out.push_back({f[a], f[b], f[c]});
        remaining.erase(pos);
        found = true;
        break;
      }
    }
    if (!found)
      bgt.fail(ErrorCode::invalid_geometry);
  }
  if (sign * cross2(q[remaining[0]], q[remaining[1]], q[remaining[2]]) <= tol)
    bgt.fail(ErrorCode::invalid_geometry);
  out.push_back({f[remaining[0]], f[remaining[1]], f[remaining[2]]});
  return out;
}
} // namespace
std::expected<Discretization, SurfaceError> prepare(PreparationRequest r) {
  Accounting b{r.limits, Operation::preparation, {}};
  try {
    const auto &in = r.input;
    b.input(in.vertices.size(), 24);
    b.input(in.edges.size(), 16);
    b.input(in.face_offsets.size(), 8);
    b.input(in.face_coedges.size(), 8);
    b.input(r.face_ids.size(), 8);
    // Conservative logical workspace reservation includes input, patch
    // assessment, incidence, maps, sorting and triangulation scratch. Not
    // allocator/RSS bytes.
    for (auto n : {in.vertices.size(), in.edges.size(), in.face_offsets.size(),
                   in.face_coedges.size(), r.face_ids.size()})
      b.reserve(n, 1024);
    b.reserve(1, 1024);
    for (auto n : {in.vertices.size(), in.edges.size(), in.face_offsets.size(),
                   in.face_coedges.size(), r.face_ids.size()})
      if (n > static_cast<std::uint64_t>(std::numeric_limits<Id>::max()))
        b.fail(ErrorCode::invalid_input);
    if (in.face_offsets.empty() || in.face_offsets[0] != 0 ||
        in.face_offsets.back() < 0 ||
        static_cast<std::size_t>(in.face_offsets.back()) !=
            in.face_coedges.size() ||
        r.face_ids.empty() || !std::isfinite(r.policy.relative_tolerance) ||
        r.policy.relative_tolerance < 0)
      b.fail(ErrorCode::invalid_input);
    for (std::size_t i = 1; i < in.face_offsets.size(); ++i) {
      b.work();
      if (in.face_offsets[i] < in.face_offsets[i - 1])
        b.fail(ErrorCode::invalid_input);
    }
    for (auto p : in.vertices) {
      b.work();
      for (auto x : p)
        if (!std::isfinite(x))
          b.fail(ErrorCode::invalid_input);
    }
    for (auto e : in.edges) {
      b.work();
      for (auto v : e)
        if (v < 0 || static_cast<std::size_t>(v) >= in.vertices.size())
          b.fail(ErrorCode::invalid_input);
    }
    for (auto t : in.face_coedges) {
      b.work();
      if (t == 0 || t == std::numeric_limits<Id>::min() ||
          static_cast<std::uint64_t>(std::abs(t)) > in.edges.size())
        b.fail(ErrorCode::invalid_input);
    }
    auto out = std::make_shared<SurfaceStorage>();
    out->unit = in.length_unit;
    out->source_face_count = static_cast<Id>(in.face_offsets.size() - 1);
    std::set<Id> selected, verts, edges;
    for (auto f : r.face_ids) {
      b.face = f;
      b.work();
      if (f < 0 || f >= out->source_face_count || !selected.insert(f).second)
        b.fail(ErrorCode::invalid_input);
      if (in.face_offsets[f + 1] - in.face_offsets[f] < 3)
        b.fail(ErrorCode::invalid_topology);
      for (auto k = in.face_offsets[f]; k < in.face_offsets[f + 1]; ++k) {
        b.work();
        auto e = std::abs(in.face_coedges[k]) - 1;
        edges.insert(e);
        verts.insert(in.edges[e][0]);
        verts.insert(in.edges[e][1]);
      }
    }
    b.face = -1;
    b.output(verts.size(), 32);
    b.output(r.face_ids.size(), 8);
    b.output(1, 48);
    out->source_vertices.assign(verts.begin(), verts.end());
    out->selected_faces = r.face_ids;
    simplicial::PolygonalInput patch;
    patch.length_unit = in.length_unit;
    patch.face_offsets = {0};
    std::map<Id, Id> vmap, emap;
    for (auto v : verts) {
      vmap[v] = static_cast<Id>(patch.vertices.size());
      patch.vertices.push_back(in.vertices[v]);
    }
    std::vector<Id> edge_sources;
    for (auto e : edges) {
      emap[e] = static_cast<Id>(patch.edges.size());
      patch.edges.push_back({vmap.at(in.edges[e][0]), vmap.at(in.edges[e][1])});
      edge_sources.push_back(e);
    }
    for (auto f : r.face_ids) {
      for (auto k = in.face_offsets[f]; k < in.face_offsets[f + 1]; ++k) {
        b.work();
        auto t = in.face_coedges[k];
        patch.face_coedges.push_back((t < 0 ? -1 : 1) *
                                     (emap.at(std::abs(t) - 1) + 1));
      }
      patch.face_offsets.push_back(static_cast<Id>(patch.face_coedges.size()));
    }
    auto assessment = simplicial::assess_polygonal(
        patch, {r.limits.max_input_bytes, r.limits.max_owned_bytes,
                r.limits.max_work_steps - b.usage.work_steps,
                r.limits.max_owned_bytes});
    if (!assessment) {
      using E = simplicial::PolygonalError;
      switch (assessment.error()) {
      case E::invalid_input:
        b.fail(ErrorCode::invalid_input);
      case E::work_budget:
        b.fail(ErrorCode::work_budget);
      case E::input_budget:
        b.fail(ErrorCode::input_budget);
      case E::storage_budget:
      case E::output_budget:
        b.fail(ErrorCode::storage_budget);
      }
    }
    b.work(assessment->usage().work_steps);
    const auto &facts = assessment->facts();
    if (!assessment->admitted_cells() ||
        !facts.inconsistent_orientation_edge_ids.empty()) {
      if (!facts.invalid_face_ids.empty())
        b.face = r.face_ids[facts.invalid_face_ids[0]];
      else if (!facts.duplicate_face_ids.empty())
        b.face = r.face_ids[facts.duplicate_face_ids[0]];
      b.fail(ErrorCode::invalid_topology);
    }
    std::set<Id> boundary;
    for (auto e : facts.boundary_edge_ids)
      for (auto v : patch.edges[e])
        boundary.insert(out->source_vertices[v]);
    b.output(boundary.size(), 8);
    out->boundary_vertices.assign(boundary.begin(), boundary.end());
    out->vertices = std::move(patch.vertices);
    for (std::size_t i = 0; i < r.face_ids.size(); ++i) {
      b.face = r.face_ids[i];
      std::vector<Id> loop;
      std::map<std::pair<Id, Id>, Id> original;
      for (auto k = patch.face_offsets[i]; k < patch.face_offsets[i + 1]; ++k) {
        auto t = patch.face_coedges[k], e = std::abs(t) - 1;
        auto pair = patch.edges[e];
        loop.push_back(pair[t < 0 ? 1 : 0]);
        original[std::minmax(pair[0], pair[1])] = edge_sources[e];
      }
      b.output(loop.size() - 2, 56); // triangles + side provenance + face ID
      auto tris =
          triangulate(out->vertices, loop, r.policy.relative_tolerance, b);
      for (auto t : tris) {
        Triangle side{-1, -1, -1};
        for (int k = 0; k < 3; ++k) {
          auto it = original.find(std::minmax(t[k], t[(k + 1) % 3]));
          if (it != original.end())
            side[k] = it->second;
        }
        out->triangles.push_back(t);
        out->triangle_edges.push_back(side);
        out->triangle_faces.push_back(b.face);
      }
    }
    b.face = -1;
    out->usage = b.usage;
    return Discretization(std::move(out));
  } catch (const SurfaceError &e) {
    return std::unexpected(e);
  }
}
std::expected<Operators, SurfaceError> assemble(Discretization surface,
                                                ConfidencePolicy confidence,
                                                SurfaceLimits limits) {
  Accounting b{limits, Operation::assembly, {}};
  try {
    b.input(confidence.face_weights.size(), 16);
    b.reserve(confidence.face_weights.size(), 128);
    b.reserve(surface.triangles().size(),
              768); // 12 triplets, sorted workspace and CSR
    b.reserve(surface.vertices().size() + 1, 16);
    std::map<Id, double> weights;
    for (auto [f, w] : confidence.face_weights) {
      b.face = f;
      b.work();
      if (f < 0 || f >= surface.source_face_count() || !std::isfinite(w) ||
          w < 0 || w > 1 || !weights.emplace(f, w).second)
        b.fail(ErrorCode::invalid_input);
    }
    confidence.face_weights.assign(weights.begin(), weights.end());
    struct Entry {
      Id row, col;
      double value;
    };
    std::vector<Entry> entries;
    for (std::size_t tid = 0; tid < surface.triangles().size(); ++tid) {
      b.work();
      b.face = surface.triangle_faces()[tid];
      auto it = weights.find(b.face);
      double c = it == weights.end() ? 1 : it->second;
      if (c == 0)
        continue;
      auto t = surface.triangles()[tid];
      std::array<Point, 3> q{};
      double scale = 0;
      for (int k = 0; k < 3; ++k) {
        q[k] = sub(surface.vertices()[t[k]], surface.vertices()[t[0]], b);
        for (auto x : q[k])
          scale = std::max(scale, std::abs(x));
      }
      if (scale == 0)
        b.fail(ErrorCode::invalid_geometry);
      for (auto &p : q)
        for (auto &x : p)
          x /= scale;
      auto longest =
          std::max({norm(q[1]), norm(q[2]), norm(sub(q[2], q[1], b))});
      for (auto &p : q)
        for (auto &x : p)
          x /= longest;
      double area = norm(cross(q[1], q[2]));
      if (!std::isfinite(area))
        b.fail(ErrorCode::numerical_range);
      if (area <= 1e-12)
        b.fail(ErrorCode::invalid_geometry);
      for (int k = 0; k < 3; ++k) {
        b.work();
        int i = (k + 1) % 3, j = (k + 2) % 3;
        double w = .5 * c * dot(sub(q[i], q[k], b), sub(q[j], q[k], b)) / area;
        if (!std::isfinite(w))
          b.fail(ErrorCode::numerical_range);
        entries.push_back({t[i], t[j], -w});
        entries.push_back({t[j], t[i], -w});
        entries.push_back({t[i], t[i], w});
        entries.push_back({t[j], t[j], w});
      }
    }
    b.face = -1;
    std::stable_sort(entries.begin(), entries.end(), [&](auto a, auto c) {
      b.work();
      return std::pair{a.row, a.col} < std::pair{c.row, c.col};
    });
    FloatingCSR matrix;
    matrix.dimension = static_cast<Id>(surface.vertices().size());
    b.output(surface.vertices().size() + 1, 8);
    b.output(confidence.face_weights.size(), 16);
    b.output(1, 40);
    matrix.offsets.resize(surface.vertices().size() + 1);
    for (std::size_t i = 0; i < entries.size();) {
      const auto row = entries[i].row, col = entries[i].col;
      double sum = 0;
      do {
        b.work();
        sum += entries[i++].value;
      } while (i < entries.size() && entries[i].row == row &&
               entries[i].col == col);
      if (!std::isfinite(sum))
        b.fail(ErrorCode::numerical_range);
      if (sum != 0) {
        b.output(1, 16);
        matrix.columns.push_back(col);
        matrix.values.push_back(sum);
        ++matrix.offsets[row + 1];
      }
    }
    std::partial_sum(matrix.offsets.begin(), matrix.offsets.end(),
                     matrix.offsets.begin());
    return Operators(std::move(surface), std::move(matrix),
                     std::move(confidence), b.usage);
  } catch (const SurfaceError &e) {
    return std::unexpected(e);
  }
}
std::expected<ChartAssessment, SurfaceError>
qualify_chart(Discretization surface, std::vector<UV> uv, ChartPolicy policy,
              SurfaceLimits limits) {
  Accounting b{limits, Operation::chart, {}};
  try {
    b.input(uv.size(), 16);
    b.reserve(uv.size(), 16);
    b.reserve(surface.triangles().size(), 16);
    b.reserve(1, 128);
    if (uv.size() != surface.vertices().size() ||
        (policy.orientation != 1 && policy.orientation != -1) ||
        !std::isfinite(policy.relative_tolerance) ||
        policy.relative_tolerance < 0)
      b.fail(ErrorCode::invalid_input);
    for (auto q : uv) {
      b.work();
      for (auto x : q)
        if (!std::isfinite(x))
          b.fail(ErrorCode::invalid_input);
    }
    ChartAssessment out;
    out.quality.triangle_count = surface.triangles().size();
    out.quality.minimum_signed_double_area =
        std::numeric_limits<double>::infinity();
    b.output(1, 56);
    for (std::size_t tid = 0; tid < surface.triangles().size(); ++tid) {
      b.work();
      b.face = surface.triangle_faces()[tid];
      auto t = surface.triangles()[tid];
      auto q0 = uv[t[0]], q1 = uv[t[1]], q2 = uv[t[2]];
      XY d1{q1[0] - q0[0], q1[1] - q0[1]}, d2{q2[0] - q0[0], q2[1] - q0[1]},
          d3{q2[0] - q1[0], q2[1] - q1[1]};
      double area = policy.orientation * (d1[0] * d2[1] - d1[1] * d2[0]);
      double scale2 = std::max({d1[0] * d1[0] + d1[1] * d1[1],
                                d2[0] * d2[0] + d2[1] * d2[1],
                                d3[0] * d3[0] + d3[1] * d3[1]});
      if (!std::isfinite(area) || !std::isfinite(scale2))
        b.fail(ErrorCode::numerical_range);
      out.quality.minimum_signed_double_area =
          std::min(out.quality.minimum_signed_double_area, area);
      if (scale2 == 0 || std::abs(area) <= policy.relative_tolerance * scale2) {
        b.output(1, 8);
        out.quality.degenerate_triangles.push_back(static_cast<Id>(tid));
        out.quality.maximum_conformal_distortion =
            std::numeric_limits<double>::infinity();
        continue;
      }
      if (area < 0) {
        b.output(1, 8);
        out.quality.flipped_triangles.push_back(static_cast<Id>(tid));
      }
      auto e1 = sub(surface.vertices()[t[1]], surface.vertices()[t[0]], b);
      auto e2 = sub(surface.vertices()[t[2]], surface.vertices()[t[0]], b);
      double x = std::sqrt(dot(e1, e1));
      if (!std::isfinite(x) || x == 0)
        b.fail(ErrorCode::numerical_range);
      Point tangent = e1;
      for (auto &v : tangent)
        v /= x;
      double y = dot(e2, tangent);
      Point perpendicular = e2;
      for (int k = 0; k < 3; ++k)
        perpendicular[k] -= y * tangent[k];
      double z = std::sqrt(dot(perpendicular, perpendicular));
      if (!std::isfinite(z) || z == 0)
        b.fail(ErrorCode::numerical_range);
      // Singular values of the 2x2 intrinsic-to-UV Jacobian, scaled before
      // squaring.
      double a = d1[0] / x, c = d1[1] / x, d = (d2[1] - y * c) / z,
             bb = (d2[0] - y * a) / z;
      for (auto v : {a, bb, c, d})
        if (!std::isfinite(v))
          b.fail(ErrorCode::numerical_range);
      double scale =
          std::max({std::abs(a), std::abs(bb), std::abs(c), std::abs(d)});
      if (scale == 0)
        b.fail(ErrorCode::numerical_range);
      a /= scale;
      bb /= scale;
      c /= scale;
      d /= scale;
      double largest =
          (std::hypot(a + d, c - bb) + std::hypot(a - d, c + bb)) / 2;
      double determinant = std::abs(a * d - bb * c);
      double distortion = largest * largest / determinant;
      if (!std::isfinite(distortion))
        b.fail(ErrorCode::numerical_range);
      out.quality.maximum_conformal_distortion =
          std::max(out.quality.maximum_conformal_distortion, distortion);
    }
    if (out.quality.flipped_triangles.empty() &&
        out.quality.degenerate_triangles.empty()) {
      b.output(uv.size(), 16);
      out.admitted = AdmittedChart(std::move(surface), std::move(uv));
    }
    out.usage = b.usage;
    return out;
  } catch (const SurfaceError &e) {
    return std::unexpected(e);
  }
}
} // namespace cad::surface
