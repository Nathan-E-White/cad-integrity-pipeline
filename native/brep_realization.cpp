#include "brep_realization.hpp"
#include "surface_storage.hpp"
#include <algorithm>
#include <cmath>
#include <limits>
#include <map>
#include <numeric>
#include <set>

namespace cad::occt_adapter {
namespace {
using Pair = std::array<Id, 2>;
Pair pair(Id a, Id b) { return {std::min(a, b), std::max(a, b)}; }
struct Side {
  Id face, triangle, slot, direction;
};
struct Account {
  surface::SurfaceLimits limits;
  surface::Usage usage;
  void charge(std::uint64_t &n, std::uint64_t count, std::uint64_t width,
              std::uint64_t limit, surface::ErrorCode code) {
    if (n > limit || count > (limit - n) / width)
      throw RealizationError{code};
    n += count * width;
  }
  void work(std::uint64_t n = 1) {
    charge(usage.work_steps, n, 1, limits.max_work_steps,
           surface::ErrorCode::work_budget);
  }
};
void require(bool ok, RealizationDiagnostic d =
                          RealizationDiagnostic::invalid_evidence) {
  if (!ok)
    throw d;
}
} // namespace
class RealizationBuilder {
public:
  static RealizedSurface build(RealizationRequest &r, Account &a) {
    const auto n = r.nodes.size(), t = r.triangles.size();
    require(r.face_count > 0 && r.vertex_count >= 0 && n > 0 && t > 0 &&
            r.keys.size() == n && r.triangle_faces.size() == t &&
            std::isfinite(r.agreement_tolerance) && r.agreement_tolerance >= 0);
    require(n <= static_cast<std::size_t>(std::numeric_limits<Id>::max()) &&
            t <= static_cast<std::size_t>(std::numeric_limits<Id>::max()));
    auto out = std::make_shared<surface::SurfaceStorage>();
    out->source_face_count = r.face_count;
    out->native_faces = true;
    out->unit = cad::simplicial::LengthUnit::Millimeter;
    std::map<Triangle, Id> identity;
    std::vector<Id> remap(n), native_vertices;
    for (std::size_t i = 0; i < n; ++i) {
      a.work();
      const auto k = r.keys[i];
      require(k[2] >= 0 &&
              ((k[0] == 0 && k[1] >= 0 && k[1] < r.vertex_count && k[2] == 0) ||
               (k[0] == 1 && k[1] >= 0 &&
                std::cmp_less(k[1], r.edge_uses.size())) ||
               (k[0] == 2 && k[1] >= 0 && k[1] < r.face_count)));
      for (double x : r.nodes[i])
        require(std::isfinite(x));
      auto [it, inserted] =
          identity.emplace(k, static_cast<Id>(out->vertices.size()));
      remap[i] = it->second;
      if (inserted) {
        out->vertices.push_back(r.nodes[i]);
        native_vertices.push_back(k[0] == 0 ? k[1] : -1);
      } else {
        const auto p = out->vertices[it->second];
        const auto q = r.nodes[i];
        require(std::hypot(p[0] - q[0], p[1] - q[1], p[2] - q[2]) <=
                    r.agreement_tolerance,
                RealizationDiagnostic::coordinate_disagreement);
      }
    }
    std::set<Id> native_ids;
    for (auto id : native_vertices)
      if (id >= 0)
        native_ids.insert(id);
    require(native_ids.size() == static_cast<std::size_t>(r.vertex_count));
    std::map<Pair, std::vector<Side>> sides;
    std::vector<std::vector<Pair>> links(out->vertices.size());
    std::set<Triangle> unique;
    std::set<Id> faces;
    auto node = [&](Id id) {
      require(id >= 0 && std::cmp_less(id, n));
      return remap[id];
    };
    for (std::size_t i = 0; i < t; ++i) {
      a.work();
      const Id face = r.triangle_faces[i];
      require(face >= 0 && face < r.face_count);
      faces.insert(face);
      Triangle tri;
      for (int j = 0; j < 3; ++j) {
        const auto original = r.triangles[i][j];
        tri[j] = node(original);
        require(r.keys[original][0] != 2 || r.keys[original][1] == face);
      }
      auto sorted = tri;
      std::sort(sorted.begin(), sorted.end());
      require(sorted[0] != sorted[1] && sorted[1] != sorted[2] &&
                  unique.insert(sorted).second,
              RealizationDiagnostic::degenerate_triangle);
      Point u{}, v{};
      double scale = 0;
      for (int j = 0; j < 3; ++j) {
        u[j] = out->vertices[tri[1]][j] - out->vertices[tri[0]][j];
        v[j] = out->vertices[tri[2]][j] - out->vertices[tri[0]][j];
        require(std::isfinite(u[j]) && std::isfinite(v[j]));
        scale = std::max({scale, std::abs(u[j]), std::abs(v[j])});
      }
      require(scale > 0, RealizationDiagnostic::degenerate_triangle);
      for (int j = 0; j < 3; ++j) {
        u[j] /= scale;
        v[j] /= scale;
      }
      require(std::hypot(u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2],
                         u[0] * v[1] - u[1] * v[0]) > 1e-14,
              RealizationDiagnostic::degenerate_triangle);
      out->triangles.push_back(tri);
      out->triangle_edges.push_back({-1, -1, -1});
      for (int j = 0; j < 3; ++j) {
        Id x = tri[j], y = tri[(j + 1) % 3];
        sides[pair(x, y)].push_back(
            {face, static_cast<Id>(i), j, x < y ? 1 : -1});
        links[x].push_back(pair(y, tri[(j + 2) % 3]));
      }
    }
    require(faces.size() == static_cast<std::size_t>(r.face_count));
    struct Boundary {
      Id edge;
      std::vector<Id> faces;
    };
    std::map<Pair, Boundary> boundaries;
    std::set<Id> seen_edges;
    for (auto s : r.segments) {
      a.work();
      require(s[2] >= 0 && std::cmp_less(s[2], r.edge_uses.size()) &&
              s[3] >= 0 && s[3] < r.face_count);
      Pair p = pair(node(s[0]), node(s[1]));
      for (int j = 0; j < 2; ++j) {
        const auto key = r.keys[s[j]];
        require(key[0] == 0 || (key[0] == 1 && key[1] == s[2]),
                RealizationDiagnostic::edge_correspondence);
      }
      require(p[0] != p[1], RealizationDiagnostic::edge_correspondence);
      auto [it, inserted] = boundaries.emplace(p, Boundary{s[2], {}});
      require(inserted || it->second.edge == s[2],
              RealizationDiagnostic::edge_correspondence);
      it->second.faces.push_back(s[3]);
      seen_edges.insert(s[2]);
    }
    for (std::size_t i = 0; i < r.edge_uses.size(); ++i) {
      a.work();
      require(r.edge_uses[i] >= 0 && r.edge_uses[i] <= 2,
              RealizationDiagnostic::edge_correspondence);
      require((r.edge_uses[i] == 0) == !seen_edges.contains(static_cast<Id>(i)),
              RealizationDiagnostic::edge_correspondence);
    }
    std::set<Id> boundary_vertices;
    for (auto &[p, uses] : sides) {
      a.work();
      require(uses.size() <= 2, RealizationDiagnostic::edge_correspondence);
      if (uses.size() == 2)
        require(uses[0].direction != uses[1].direction,
                RealizationDiagnostic::orientation);
      auto found = boundaries.find(p);
      if (found == boundaries.end()) {
        require(uses.size() == 2 && uses[0].face == uses[1].face,
                RealizationDiagnostic::edge_correspondence);
      } else {
        auto &b = found->second;
        require(b.faces.size() == uses.size() &&
                    std::cmp_equal(uses.size(), r.edge_uses[b.edge]),
                RealizationDiagnostic::edge_correspondence);
        std::vector<Id> actual;
        for (auto u : uses) {
          actual.push_back(u.face);
          out->triangle_edges[u.triangle][u.slot] = b.edge;
        }
        std::sort(actual.begin(), actual.end());
        std::sort(b.faces.begin(), b.faces.end());
        require(actual == b.faces, RealizationDiagnostic::edge_correspondence);
        boundaries.erase(found);
      }
      if (uses.size() == 1) {
        boundary_vertices.insert(p[0]);
        boundary_vertices.insert(p[1]);
      }
    }
    require(boundaries.empty(), RealizationDiagnostic::edge_correspondence);
    // Each vertex link must be one path or cycle, including across periodic
    // seams.
    for (const auto &link : links) {
      require(!link.empty(), RealizationDiagnostic::nonmanifold_vertex);
      std::map<Id, std::vector<Id>> graph;
      for (auto p : link) {
        a.work();
        graph[p[0]].push_back(p[1]);
        graph[p[1]].push_back(p[0]);
      }
      int ends = 0;
      for (const auto &[id, neighbors] : graph) {
        (void)id;
        require(neighbors.size() <= 2,
                RealizationDiagnostic::nonmanifold_vertex);
        ends += neighbors.size() == 1;
      }
      require(ends == 0 || ends == 2,
              RealizationDiagnostic::nonmanifold_vertex);
      std::set<Id> visited;
      std::vector<Id> pending{graph.begin()->first};
      while (!pending.empty()) {
        a.work();
        auto id = pending.back();
        pending.pop_back();
        if (!visited.insert(id).second)
          continue;
        for (auto next : graph.at(id))
          if (!visited.contains(next))
            pending.push_back(next);
      }
      require(visited.size() == graph.size(),
              RealizationDiagnostic::nonmanifold_vertex);
    }
    out->source_vertices.resize(out->vertices.size());
    std::iota(out->source_vertices.begin(), out->source_vertices.end(), Id{0});
    out->selected_faces.assign(faces.begin(), faces.end());
    out->triangle_faces = std::move(r.triangle_faces);
    out->boundary_vertices.assign(boundary_vertices.begin(),
                                  boundary_vertices.end());
    out->usage = a.usage;
    return RealizedSurface(surface::Discretization(std::move(out)),
                           std::move(native_vertices));
  }
};
std::expected<RealizationAssessment, RealizationError>
realize(RealizationRequest r) {
  Account a{r.limits, {}};
  try {
    auto input = [&](std::size_t n, std::size_t width) {
      a.charge(a.usage.input_bytes, n, width, r.limits.max_input_bytes,
               surface::ErrorCode::input_budget);
    };
    input(r.nodes.size(), sizeof(Point));
    input(r.keys.size(), sizeof(Triangle));
    input(r.triangles.size(), sizeof(Triangle));
    input(r.triangle_faces.size(), sizeof(Id));
    input(r.segments.size(), sizeof(std::array<Id, 4>));
    input(r.edge_uses.size(), sizeof(Id));
    // Logical reservations include input, tree/map nodes and bounded per-item
    // scratch. Allocator metadata, capacity growth and OCCT allocations are
    // excluded.
    auto reserve = [&](std::size_t n, std::size_t width) {
      a.charge(a.usage.owned_bytes, n, width, r.limits.max_owned_bytes,
               surface::ErrorCode::storage_budget);
    };
    reserve(a.usage.input_bytes, 1);
    reserve(r.nodes.size(), 512);
    reserve(r.triangles.size(), 2048);
    reserve(r.segments.size(), 256);
    reserve(r.edge_uses.size(), 64);
    auto output = [&](std::size_t n, std::size_t width) {
      a.charge(a.usage.output_bytes, n, width, r.limits.max_output_bytes,
               surface::ErrorCode::output_budget);
    };
    output(r.nodes.size(), 48);
    output(r.triangles.size(), 56);
    output(r.triangles.size(), 8);
    auto admitted = RealizationBuilder::build(r, a);
    return RealizationAssessment{{}, std::move(admitted), a.usage};
  } catch (RealizationDiagnostic d) {
    return RealizationAssessment{{d}, std::nullopt, a.usage};
  } catch (RealizationError e) {
    return std::unexpected(e);
  }
}
} // namespace cad::occt_adapter
