#include "uv_location.hpp"
#include <cassert>
#include <cmath>
#include <limits>
using namespace cad::surface;
int main() {
  cad::simplicial::PolygonalInput raw{{{0, 0, 0}, {1, 0, 0}, {0, 1, 0}},
                                      {{0, 1}, {1, 2}, {2, 0}},
                                      {0, 3},
                                      {1, 2, 3}};
  auto surface = prepare({raw, {0}, {}, {}});
  assert(surface);
  auto chart = qualify_chart(*surface, {{0, 0}, {1, 0}, {0, 1}});
  assert(chart && chart->admitted);
  auto locator = cad::uv::Locator::create({*chart->admitted, {}, {}});
  assert(locator);
  const std::vector<UV> queries{{.25, .25}, {10, 10}, {0, 0}};
  auto result = locator->locate({queries, {}});
  assert(result);
  assert(result->records()[0].status == cad::uv::Status::unique);
  assert(result->records()[1].status == cad::uv::Status::outside);
  assert(result->records()[2].status == cad::uv::Status::unique);
  assert(result->candidates()[0].xyz == Point({.25, .25, 0}));
  assert(result->offsets() == std::vector<std::uint64_t>({0, 1, 1, 2}));
  auto stacked = raw;
  stacked.vertices.insert(stacked.vertices.end(),
                          {{0, 0, 1}, {1, 0, 1}, {0, 1, 1}});
  stacked.edges.insert(stacked.edges.end(), {{3, 4}, {4, 5}, {5, 3}});
  stacked.face_offsets = {0, 3, 6};
  stacked.face_coedges = {1, 2, 3, 4, 5, 6};
  auto sheets = prepare({stacked, {0, 1}, {}, {}});
  assert(sheets);
  auto overlap =
      qualify_chart(*sheets, {{0, 0}, {1, 0}, {0, 1}, {0, 0}, {1, 0}, {0, 1}});
  assert(overlap && overlap->admitted);
  auto both = cad::uv::Locator::create({*overlap->admitted, {}, {}});
  assert(both);
  auto hits = both->locate({queries, {}});
  assert(hits && hits->records()[0].status == cad::uv::Status::ambiguous);
  assert(!hits->records()[0].resolved);
  assert(hits->offsets()[1] == 2);
  assert(hits->candidates()[1].source_face == 1);

  cad::uv::Limits cap;
  cap.max_candidates_per_query = 1;
  auto stopped = both->locate({queries, cap});
  assert(stopped && stopped->exhaustion());
  assert(stopped->records()[0].status == cad::uv::Status::budget_exceeded);
  assert(stopped->candidates().empty());
  assert(stopped->records()[2].status == cad::uv::Status::budget_exceeded);
  cap.max_input_bytes = 0;
  assert(!both->locate({queries, cap}));
  auto invalid = queries;
  invalid.back()[0] = std::numeric_limits<double>::quiet_NaN();
  assert(!both->locate({invalid, {}}));
  cad::uv::Limits short_search;
  short_search.max_work_steps = 2;
  const std::vector<UV> distant{{1e100, 1e100}};
  auto pruned = both->locate({distant, short_search});
  assert(pruned && pruned->records()[0].status == cad::uv::Status::outside);

  for (int kind = 0; kind < 4; ++kind) {
    cad::uv::Limits limits;
    if (kind == 0)
      limits.max_input_bytes = 0;
    if (kind == 1)
      limits.max_owned_bytes = 0;
    if (kind == 2)
      limits.max_work_steps = 0;
    if (kind == 3)
      limits.max_output_bytes = 0;
    auto refused = cad::uv::Locator::create({*chart->admitted, {}, limits});
    assert(!refused);
  }
  const std::vector<UV> edge{{-5e-10, .5}, {-2e-9, .5}};
  auto near = locator->locate({edge, {}});
  assert(near && near->records()[0].status == cad::uv::Status::unique);
  assert(near->records()[1].status == cad::uv::Status::outside);
  const std::vector<UV> repeated{{.2, .2}, {.3, .3}};
  auto complete = locator->locate({repeated, {}});
  assert(complete);
  cad::uv::Limits output;
  output.max_output_bytes =
      complete->usage().output_bytes - sizeof(cad::uv::Candidate);
  auto prefix = locator->locate({repeated, output});
  assert(prefix && prefix->exhaustion());
  assert(prefix->records()[0].resolved);
  assert(!prefix->records()[1].resolved);
  assert(prefix->candidates().size() == 1);
  assert(prefix->exhaustion()->code == cad::uv::ErrorCode::output_budget);
  locator = std::unexpected(cad::uv::LocationError{
      cad::uv::ErrorCode::invalid_input, cad::uv::Operation::index});
  assert(prefix->chart().surface().vertices()[1][0] == 1);
  for (double scale : {1e-100, 1e100}) {
    auto scaled = qualify_chart(*surface, {{0, 0}, {scale, 0}, {0, scale}});
    assert(scaled && scaled->admitted);
    auto index = cad::uv::Locator::create({*scaled->admitted, {}, {}});
    assert(index);
    const std::vector<UV> point{{.25 * scale, .25 * scale}};
    auto located = index->locate({point, {}});
    assert(located && located->records()[0].resolved);
    assert(std::abs((*located->records()[0].resolved)[0] - .25) < 1e-14);
  }

  cad::simplicial::PolygonalInput many;
  many.face_offsets = {0};
  std::vector<Id> selected;
  std::vector<UV> many_uv;
  for (Id i = 0; i < 31; ++i) {
    const Id v = 3 * i;
    many.vertices.insert(
        many.vertices.end(),
        {{0, 0, double(i)}, {1, 0, double(i)}, {0, 1, double(i)}});
    many.edges.insert(many.edges.end(),
                      {{v, v + 1}, {v + 1, v + 2}, {v + 2, v}});
    many.face_coedges.insert(many.face_coedges.end(), {v + 1, v + 2, v + 3});
    many.face_offsets.push_back(v + 3);
    selected.push_back(i);
    many_uv.insert(many_uv.end(), {{0, 0}, {1, 0}, {0, 1}});
  }
  auto many_surface = prepare({many, selected, {}, {}});
  assert(many_surface);
  auto many_chart = qualify_chart(*many_surface, many_uv);
  assert(many_chart && many_chart->admitted);
  auto many_index = cad::uv::Locator::create({*many_chart->admitted, {}, {}});
  assert(many_index &&
         many_index->usage().owned_bytes > many_index->usage().output_bytes);
  cad::uv::Limits no_scratch;
  no_scratch.max_owned_bytes = many_index->usage().output_bytes;
  assert(!cad::uv::Locator::create({*many_chart->admitted, {}, no_scratch}));
  auto all = many_index->locate({repeated, {}});
  assert(all && all->records()[0].status == cad::uv::Status::ambiguous);
  assert(all->candidates().size() == 62);
  for (Id i = 0; i < 31; ++i)
    assert(all->candidates()[i].triangle == i);
}
