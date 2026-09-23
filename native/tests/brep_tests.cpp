#include "brep_realization.hpp"
#include <cassert>
#include <cmath>
using namespace cad::occt_adapter;
RealizationRequest square() {
  return {{{0, 0, 0}, {1, 0, 0}, {1, 1, 0}, {0, 0, 0}, {1, 1, 0}, {0, 1, 0}},
          {{0, 0, 0}, {0, 1, 0}, {0, 2, 0}, {0, 0, 0}, {0, 2, 0}, {0, 3, 0}},
          {{0, 1, 2}, {3, 4, 5}},
          {0, 1},
          {{0, 1, 0, 0},
           {1, 2, 1, 0},
           {2, 0, 2, 0},
           {3, 4, 2, 1},
           {4, 5, 3, 1},
           {5, 3, 4, 1}},
          {1, 1, 2, 1, 1},
          2,
          4,
          1e-7,
          {}};
}
int main() {
  auto request = square();
  auto result = realize(request);
  assert(result && result->admitted && result->diagnostics.empty());
  auto retained = result->admitted->surface();
  assert(retained.native_faces() && retained.vertices().size() == 4 &&
         retained.triangles().size() == 2);
  assert(retained.triangle_faces()[1] == 1 &&
         retained.triangle_edges()[0][2] == 2);
  assert(retained.boundary_vertices().size() == 4);
  request.nodes[0] = {99, 99, 99};
  result = RealizationAssessment{};
  assert(retained.vertices()[0][0] == 0);
  auto operators = cad::surface::assemble(retained);
  assert(operators);
  auto mismatch = square();
  mismatch.nodes[3][0] = 0.01;
  auto bad = realize(mismatch);
  assert(bad && !bad->admitted &&
         bad->diagnostics[0] == RealizationDiagnostic::coordinate_disagreement);
  auto incomplete = square();
  incomplete.segments.pop_back();
  bad = realize(incomplete);
  assert(bad && !bad->admitted);
  auto reversed = square();
  reversed.triangles[1] = {3, 5, 4};
  bad = realize(reversed);
  assert(bad && !bad->admitted &&
         bad->diagnostics[0] == RealizationDiagnostic::orientation);
  auto orphan = square();
  orphan.vertex_count = 5;
  bad = realize(orphan);
  assert(bad && !bad->admitted);
  auto nan = square();
  nan.nodes[0][0] = NAN;
  bad = realize(nan);
  assert(bad && !bad->admitted);
  auto bad_index = square();
  bad_index.triangles[0][0] = -1;
  bad = realize(bad_index);
  assert(bad && !bad->admitted);
  for (int budget = 0; budget < 4; ++budget) {
    auto limited = square();
    if (budget == 0)
      limited.limits.max_input_bytes = 0;
    if (budget == 1)
      limited.limits.max_owned_bytes = 0;
    if (budget == 2)
      limited.limits.max_work_steps = 0;
    if (budget == 3)
      limited.limits.max_output_bytes = 0;
    assert(!realize(limited));
  }
}
