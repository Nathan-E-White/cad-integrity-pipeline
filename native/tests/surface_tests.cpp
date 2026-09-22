#include "surface_preparation.hpp"
#include <cassert>
#include <cmath>
#include <limits>
using namespace cad::surface;
int main() {
  cad::simplicial::PolygonalInput raw{
      {{0, 0, 0}, {2, 0, 0}, {1, 0.5, 0}, {0, 2, 0}},
      {{0, 1}, {1, 2}, {2, 3}, {3, 0}},
      {0, 4},
      {1, 2, 3, 4}};
  auto result = prepare({raw, {0}, {}, {}});
  assert(result);
  assert(result->triangles().size() == 2);
  assert(result->triangle_faces()[0] == 0);
  assert(result->source_vertices().size() == 4);
  raw.vertices[0][0] = 100;
  assert(result->vertices()[0][0] == 0);
  cad::simplicial::PolygonalInput right{{{0, 0, 0}, {1, 0, 0}, {0, 1, 0}},
                                        {{0, 1}, {1, 2}, {2, 0}},
                                        {0, 3},
                                        {1, 2, 3}};
  auto triangle = prepare({right, {0}, {}, {}});
  assert(triangle);
  auto op = assemble(*triangle, {}, {});
  assert(op);
  const auto &l = op->stiffness();
  assert(l.offsets == std::vector<Id>({0, 3, 5, 7}));
  assert(l.values == std::vector<double>({1, -.5, -.5, -.5, .5, -.5, .5}));
  auto chart = qualify_chart(*triangle, {{0, 0}, {1, 0}, {0, 1}}, {}, {});
  assert(chart && chart->admitted);
  assert(chart->quality.maximum_conformal_distortion == 1);
  auto flip = qualify_chart(*triangle, {{0, 0}, {0, 1}, {1, 0}}, {}, {});
  assert(flip && !flip->admitted);
  assert(flip->quality.flipped_triangles == std::vector<Id>{0});

  for (int kind = 0; kind < 4; ++kind) {
    SurfaceLimits limits;
    if (kind == 0)
      limits.max_input_bytes = 0;
    if (kind == 1)
      limits.max_owned_bytes = 0;
    if (kind == 2)
      limits.max_work_steps = 0;
    if (kind == 3)
      limits.max_output_bytes = 0;
    assert(!prepare({right, {0}, {}, limits}));
    assert(!assemble(*triangle, {{{0, .5}}}, limits));
    assert(!qualify_chart(*triangle, {{0, 0}, {1, 0}, {0, 1}}, {}, limits));
  }
  auto tiny = right;
  for (auto &p : tiny.vertices)
    for (auto &x : p)
      x *= 1e-200;
  auto small = prepare({tiny, {0}, {}, {}});
  assert(small);
  assert(assemble(*small)->stiffness().values == l.values);
  auto malformed = right;
  malformed.face_coedges[0] = std::numeric_limits<Id>::min();
  assert(!prepare({malformed, {0}, {}, {}}));
  assert(!prepare({right, {0, 0}, {}, {}}));
  auto collapse = qualify_chart(*triangle, {{0, 0}, {1, 0}, {2, 0}});
  assert(collapse && !collapse->admitted &&
         collapse->quality.degenerate_triangles == std::vector<Id>{0});
  assert(!qualify_chart(*triangle, {{0, 0}, {1e200, 0}, {0, 1e200}}));
  auto retained = chart->admitted;
  triangle = std::unexpected(
      SurfaceError{ErrorCode::invalid_input, Operation::preparation});
  assert(retained->surface().vertices().size() == 3);
  assert(retained->uv()[1][0] == 1);
}
