#include "quad_tracing.hpp"
#include <algorithm>
#include <cassert>
#include <type_traits>
static_assert(!std::is_convertible_v<cad::trace::EdgeId, cad::trace::VertexId>);
static_assert(!std::is_convertible_v<cad::trace::VertexId, cad::trace::SeedId>);
using namespace cad::trace;
cad::simplicial::PolygonalInput grid() {
  using namespace cad::simplicial;
  std::vector<Point3> vertices;
  std::vector<std::vector<int>> faces;
  for (int y = 0; y < 5; ++y)
    for (int x = 0; x < 5; ++x)
      vertices.push_back({float(x), float(y), 0});
  for (int y = 0; y < 4; ++y)
    for (int x = 0; x < 4; ++x) {
      int v = 5 * y + x;
      faces.push_back({v, v + 1, v + 6, v + 5});
    }
  auto mesh = PolyhedralBRep::from_polygons(vertices, faces);
  assert(mesh);
  PolygonalInput p;
  for (auto v : mesh->vertices)
    p.vertices.push_back({v[0], v[1], v[2]});
  for (auto e : mesh->edges)
    p.edges.push_back({e[0], e[1]});
  p.face_offsets.assign(mesh->face_offsets.begin(), mesh->face_offsets.end());
  p.face_coedges.assign(mesh->face_coedges.begin(), mesh->face_coedges.end());
  return p;
}
Id edge(const cad::simplicial::PolygonalInput &p, Id a, Id b) {
  for (std::size_t e = 0; e < p.edges.size(); ++e)
    if (p.edges[e] == std::array<Id, 2>{a, b} ||
        p.edges[e] == std::array<Id, 2>{b, a})
      return static_cast<Id>(e);
  assert(false);
  return -1;
}
int main() {
  cad::simplicial::PolygonalInput raw{
      {{0, 0, 0}, {1, 0, 0}, {1, 1, 0}, {0, 1, 0}},
      {{0, 1}, {1, 2}, {2, 3}, {3, 0}},
      {0, 4},
      {1, 2, 3, 4}};
  auto assessment = cad::simplicial::assess_polygonal(raw);
  assert(assessment);
  auto patch = AdmittedQuadPatch::create(*assessment);
  assert(patch && patch->canonical_seeds().empty());
  auto result = trace_quads(*patch, patch->canonical_seeds());
  assert(result && result->stop == Stop::none && result->segments.empty());
  assert(result->patch.boundary_edges().size() == 4);
  auto g = grid();
  auto a = cad::simplicial::assess_polygonal(g);
  auto q = AdmittedQuadPatch::create(*a);
  assert(q);
  std::vector<Seed> seeds{{10, 11, edge(g, 11, 12)}, {20, 7, edge(g, 7, 12)}};
  auto t = trace_quads(*q, seeds);
  assert(t && !t->canonical && t->stop == Stop::none);
  assert(t->segments.size() == 4 && t->unfinished.empty());
  assert(t->events[0].reason == Reason::right_hand && t->events[0].seed == 10);
  assert(t->events[1].reason == Reason::advance && t->events[1].seed == 20);
  assert(t->events.back().reason == Reason::boundary &&
         t->events.back().time2 == 6);

  // Opposing edge travel meets at half a step, never at the far vertices.
  seeds = {{1, 11, edge(g, 11, 12)}, {2, 12, edge(g, 11, 12)}};
  t = trace_quads(*q, seeds);
  assert(t && t->segments.size() == 2 && t->events[0].time2 == 1);
  for (auto e : t->events)
    assert(e.reason == Reason::opposing && e.vertex == -1);
  Limits tiny;
  tiny.max_events = 1;
  t = trace_quads(*q, seeds, tiny);
  assert(t && t->stop == Stop::event_budget && t->events.empty() &&
         t->unfinished.size() == 2);
  // An already deposited vertex remains a barrier after its depositor stops.
  seeds = {{10, 11, edge(g, 11, 12)},
           {20, 7, edge(g, 7, 12)},
           {30, 14, edge(g, 14, 13)}};
  t = trace_quads(*q, seeds);
  assert(t);
  auto hit = std::ranges::find_if(
      t->events, [](auto e) { return e.seed == 30 && e.time2 == 4; });
  assert(hit != t->events.end() && hit->reason == Reason::deposited_track &&
         hit->deposited_time2 == 2);
  auto before_permutation = t->events;
  std::reverse(seeds.begin(), seeds.end());
  t = trace_quads(*q, seeds);
  assert(t && t->events.size() == before_permutation.size());
  for (std::size_t i = 0; i < before_permutation.size(); ++i) {
    assert(t->events[i].seed == before_permutation[i].seed &&
           t->events[i].reason == before_permutation[i].reason);
  }
  // Three and four simultaneous arrivals stop as a group.
  seeds = {{1, 11, edge(g, 11, 12)},
           {2, 7, edge(g, 7, 12)},
           {3, 13, edge(g, 13, 12)},
           {4, 17, edge(g, 17, 12)}};
  for (std::size_t count : {3, 4}) {
    t = trace_quads(*q, std::span(seeds).first(count));
    assert(t && t->segments.size() == count);
    for (auto e : t->events)
      assert(e.reason == Reason::simultaneous && e.time2 == 2);
  }
  // Failure is not budget-stopped success. Duplicate launches and bad
  // references refuse.
  seeds = {{1, 11, edge(g, 11, 12)}, {2, 11, edge(g, 11, 12)}};
  assert(!trace_quads(*q, seeds));
  seeds = {{1, 99, 0}};
  assert(!trace_quads(*q, seeds));
  auto reversed = g;
  for (std::size_t f = 0; f + 1 < g.face_offsets.size(); ++f) {
    auto b = reversed.face_coedges.begin() + g.face_offsets[f];
    auto e = reversed.face_coedges.begin() + g.face_offsets[f + 1];
    std::reverse(b, e);
    for (auto it = b; it != e; ++it)
      *it = -*it;
  }
  auto ar = cad::simplicial::assess_polygonal(reversed);
  auto qr = AdmittedQuadPatch::create(*ar);
  seeds = {{10, 11, edge(g, 11, 12)}, {20, 7, edge(g, 7, 12)}};
  t = trace_quads(*qr, seeds);
  assert(t && t->events[0].reason == Reason::advance &&
         t->events[1].reason == Reason::right_hand);
  auto broken = g;
  std::reverse(broken.face_coedges.begin(), broken.face_coedges.begin() + 4);
  for (std::size_t i = 0; i < 4; ++i)
    broken.face_coedges[i] = -broken.face_coedges[i];
  auto ab = cad::simplicial::assess_polygonal(broken);
  assert(ab && !AdmittedQuadPatch::create(*ab));
  tiny = Limits{};
  tiny.max_owned_bytes = 0;
  assert(!AdmittedQuadPatch::create(*a, tiny));
  tiny = Limits{};
  tiny.max_work_steps = 0;
  assert(!AdmittedQuadPatch::create(*a, tiny));
}
