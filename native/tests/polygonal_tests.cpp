#include "SimplicialComplex.hpp"
#include <cassert>
#include <algorithm>
#include <iostream>
#include <type_traits>
#include <limits>
using namespace cad::simplicial;

PolygonalInput disk() {
  return {{{0,0,0},{1,0,0},{1,1,0},{0,1,0}},
          {{0,1},{1,2},{2,3},{0,3}}, {0,4}, {1,2,3,-4}};
}
PolygonalInput from_faces(std::size_t vertex_count, const std::vector<std::vector<int>>& faces) {
  std::vector<Point3> points;
  for (std::size_t i = 0; i < vertex_count; ++i) points.push_back({static_cast<float>(i),0,0});
  auto raw = PolyhedralBRep::from_polygons(points, faces);
  assert(raw);
  PolygonalInput input;
  for (const auto& p : raw->vertices) input.vertices.push_back({p[0],p[1],p[2]});
  for (const auto& e : raw->edges) input.edges.push_back({e[0],e[1]});
  input.face_offsets.assign(raw->face_offsets.begin(), raw->face_offsets.end());
  input.face_coedges.assign(raw->face_coedges.begin(), raw->face_coedges.end());
  return input;
}
void check_closed_chain(const PolygonalInput& raw, std::size_t expected_edges) {
  auto result = assess_polygonal(raw);
  assert(result && result->admitted_cells());
  assert(result->facts().boundary_edge_ids.empty());
  assert(result->facts().nonmanifold_vertex_ids.empty());
  const auto& a = result->admitted_cells()->boundary(1);
  const auto& b = result->admitted_cells()->boundary(2);
  assert(a.num_rows == raw.vertices.size() && a.num_cols == expected_edges);
  assert(b.num_rows == expected_edges && b.num_cols == raw.face_offsets.size()-1);
  for (std::size_t vertex = 0; vertex < a.num_rows; ++vertex) {
    std::vector<int> product(b.num_cols, 0);
    for (auto i = a.row_ptr[vertex]; i < a.row_ptr[vertex+1]; ++i) {
      const auto edge = a.col_ind[i];
      for (auto j = b.row_ptr[edge]; j < b.row_ptr[edge+1]; ++j)
        product[b.col_ind[j]] += a.values[i]*b.values[j];
    }
    for (auto value : product) assert(value == 0);
  }
}
std::vector<int> dense(const SparseCSR& matrix) {
  std::vector<int> values(matrix.num_rows*matrix.num_cols, 0);
  for (std::size_t r = 0; r < matrix.num_rows; ++r)
    for (auto k = matrix.row_ptr[r]; k < matrix.row_ptr[r+1]; ++k)
      values[r*matrix.num_cols+matrix.col_ind[k]] = matrix.values[k];
  return values;
}
void check_renumbering(PolygonalInput raw) {
  const auto before = assess_polygonal(raw);
  assert(before && before->admitted_cells());
  const auto nv = raw.vertices.size(), ne = raw.edges.size(), nf = raw.face_offsets.size()-1;
  PolygonalInput changed;
  changed.vertices = raw.vertices;
  std::reverse(changed.vertices.begin(), changed.vertices.end());
  changed.edges.resize(ne);
  auto edge_sign = [](std::size_t old) { return old%2 ? -1 : 1; };
  for (std::size_t old = 0; old < ne; ++old) {
    auto edge = raw.edges[old];
    for (auto& v : edge) v = static_cast<std::int64_t>(nv-1)-v;
    if (edge_sign(old) < 0) std::swap(edge[0],edge[1]);
    changed.edges[ne-1-old] = edge;
  }
  changed.face_offsets = {0};
  for (std::size_t face = nf; face-- > 0;) {
    std::vector<std::int64_t> loop;
    for (auto k = raw.face_offsets[face]; k < raw.face_offsets[face+1]; ++k) {
      auto token = raw.face_coedges[static_cast<std::size_t>(k)];
      const auto old_edge = static_cast<std::size_t>((token < 0 ? -token : token)-1);
      loop.push_back((token < 0 ? -1 : 1)*edge_sign(old_edge)*static_cast<std::int64_t>(ne-old_edge));
    }
    std::rotate(loop.begin(),loop.begin()+1,loop.end());
    changed.face_coedges.insert(changed.face_coedges.end(),loop.begin(),loop.end());
    changed.face_offsets.push_back(static_cast<std::int64_t>(changed.face_coedges.size()));
  }
  const auto after = assess_polygonal(std::move(changed));
  assert(after && after->admitted_cells());
  const auto d1 = dense(before->admitted_cells()->boundary(1));
  const auto d2 = dense(before->admitted_cells()->boundary(2));
  const auto new_d1 = dense(after->admitted_cells()->boundary(1));
  const auto new_d2 = dense(after->admitted_cells()->boundary(2));
  for (std::size_t v = 0; v < nv; ++v) for (std::size_t e = 0; e < ne; ++e)
    assert(new_d1[(nv-1-v)*ne+(ne-1-e)] == d1[v*ne+e]*edge_sign(e));
  for (std::size_t e = 0; e < ne; ++e) for (std::size_t f = 0; f < nf; ++f)
    assert(new_d2[(ne-1-e)*nf+(nf-1-f)] == d2[e*nf+f]*edge_sign(e));
}
int main() {
  auto assessment = assess_polygonal(disk(), {});
  assert(assessment);
  assert(assessment->facts().boundary_edge_ids == std::vector<std::int64_t>({0,1,2,3}));
  assert(assessment->admitted_cells());
  const auto& cells = *assessment->admitted_cells();
  const auto& d1 = cells.boundary(1);
  const auto& d2 = cells.boundary(2);
  assert(d1.num_rows == 4 && d1.num_cols == 4);
  assert(d2.num_rows == 4 && d2.num_cols == 1);
  assert(d2.values == std::vector<std::int8_t>({1,1,1,-1}));
  auto broken = disk();
  broken.face_coedges[1] *= -1;
  auto invalid = assess_polygonal(broken);
  assert(invalid && !invalid->admitted_cells());
  assert(invalid->facts().invalid_face_ids == std::vector<std::int64_t>({0}));
  auto duplicate = disk();
  duplicate.face_offsets.push_back(8);
  duplicate.face_coedges.insert(duplicate.face_coedges.end(), {4,-3,-2,-1});
  auto repeated = assess_polygonal(duplicate);
  assert(repeated && !repeated->admitted_cells());
  assert(repeated->facts().duplicate_face_ids == std::vector<std::int64_t>({1}));
  auto adjacent = disk();
  adjacent.vertices.push_back({2,0,0});
  adjacent.vertices.push_back({2,1,0});
  adjacent.edges.insert(adjacent.edges.end(), {{1,4},{4,5},{2,5}});
  adjacent.face_offsets.push_back(8);
  // Second face is reversed relative to the coherently oriented patch.
  adjacent.face_coedges.insert(adjacent.face_coedges.end(), {2,7,-6,-5});
  auto oriented = assess_polygonal(adjacent);
  assert(oriented && oriented->admitted_cells());
  assert(oriented->orientation().multipliers == std::vector<std::int64_t>({1,-1}));
  assert(oriented->facts().inconsistent_orientation_edge_ids == std::vector<std::int64_t>({1}));
  auto limited = PolygonalLimits{};
  limited.max_input_bytes = 207;
  auto exhausted = assess_polygonal(disk(), limited);
  assert(!exhausted && exhausted.error() == PolygonalError::input_budget);
  static_assert(!std::is_default_constructible_v<AdmittedPolygonalCells>);
  const auto saved = [] { return *assess_polygonal(disk())->admitted_cells(); }();
  assert(saved.boundary(2).values == std::vector<std::int8_t>({1,1,1,-1}));
  auto output_copy = saved.boundary(2);
  output_copy.values[0] = 0;
  assert(saved.boundary(2).values[0] == 1);
  const auto usage = assessment->usage();
  limited = {usage.input_bytes, usage.owned_bytes, usage.work_steps, usage.output_bytes};
  assert(assess_polygonal(disk(), limited));
  const std::array errors{PolygonalError::input_budget, PolygonalError::storage_budget,
                          PolygonalError::work_budget, PolygonalError::output_budget};
  for (std::size_t i = 0; i < errors.size(); ++i) {
    auto budget = limited;
    const std::array fields{&budget.max_input_bytes, &budget.max_owned_bytes,
                            &budget.max_work_steps, &budget.max_output_bytes};
    --*fields[i];
    const auto failed = assess_polygonal(disk(), budget);
    assert(!failed && failed.error() == errors[i]);
  }
  for (const auto token : {std::int64_t(0), std::numeric_limits<std::int64_t>::min(),
                           std::numeric_limits<std::int64_t>::max()}) {
    auto malformed = disk(); malformed.face_coedges[0] = token;
    auto failure = assess_polygonal(std::move(malformed));
    assert(!failure && failure.error() == PolygonalError::invalid_input);
  }
  auto unused = disk(); unused.vertices.push_back({2,2,2}); unused.edges.push_back({0,4});
  auto extra = assess_polygonal(unused);
  assert(extra && !extra->admitted_cells());
  assert(extra->facts().unused_vertex_ids == std::vector<std::int64_t>({4}));
  assert(extra->facts().unused_edge_ids == std::vector<std::int64_t>({4}));
  auto collapsed = disk(); collapsed.vertices[1] = collapsed.vertices[0];
  auto collapse = assess_polygonal(collapsed);
  assert(collapse && !collapse->admitted_cells());
  assert(collapse->facts().collapsed_edge_ids == std::vector<std::int64_t>({0}));
  auto triple = duplicate;
  triple.face_offsets.push_back(12);
  triple.face_coedges.insert(triple.face_coedges.end(), {1,2,3,-4});
  auto many = assess_polygonal(triple);
  assert(many && !many->admitted_cells());
  assert(many->facts().nonmanifold_edge_ids == std::vector<std::int64_t>({0,1,2,3}));
  assert(many->facts().nonmanifold_vertex_ids == std::vector<std::int64_t>({0,1,2,3}));
  assert(many->orientation().nonmanifold_edge == 0);
  PolygonalInput empty; empty.face_offsets = {0};
  auto nothing = assess_polygonal(empty);
  assert(nothing && !nothing->admitted_cells() && nothing->orientation().multipliers.empty());
  // Literal disk D1 oracle, in row-major order.
  const std::vector<int> expected_d1{-1,0,0,-1, 1,-1,0,0, 0,1,-1,0, 0,0,1,1};
  std::vector<int> actual(16, 0);
  for (std::size_t row = 0; row < 4; ++row)
    for (auto k = d1.row_ptr[row]; k < d1.row_ptr[row+1]; ++k)
      actual[row*4+d1.col_ind[k]] = d1.values[k];
  assert(actual == expected_d1);
  for (std::size_t row = 0; row < 4; ++row) {
    int product = 0;
    for (std::size_t col = 0; col < 4; ++col) product += actual[row*4+col]*d2.values[col];
    assert(product == 0);
  }
  const std::vector<std::vector<int>> cube_faces{
      {0,3,2,1},{4,5,6,7},{0,1,5,4},{1,2,6,5},{2,3,7,6},{3,0,4,7}};
  check_closed_chain(from_faces(8,cube_faces),12);
  check_renumbering(from_faces(8,cube_faces));
  std::vector<std::vector<int>> torus_faces;
  for (int i = 0; i < 4; ++i) for (int j = 0; j < 4; ++j)
    torus_faces.push_back({i*4+j, ((i+1)%4)*4+j, ((i+1)%4)*4+(j+1)%4, i*4+(j+1)%4});
  check_closed_chain(from_faces(16,torus_faces),32);
  auto double_cube = cube_faces;
  for (auto face : cube_faces) { for (auto& vertex : face) vertex += 8; double_cube.push_back(face); }
  check_closed_chain(from_faces(16,double_cube),24);
  auto pinched = assess_polygonal(from_faces(7, {{0,2,1},{0,1,3},{1,2,3},{2,0,3},
                                                {0,5,4},{0,4,6},{4,5,6},{5,0,6}}));
  assert(pinched && !pinched->admitted_cells());
  assert(pinched->facts().nonmanifold_edge_ids.empty());
  assert(pinched->facts().nonmanifold_vertex_ids == std::vector<std::int64_t>({0}));
  // Three-quad twisted strip: orientation conflicts do not refuse cellular admission.
  auto mobius = assess_polygonal(from_faces(6, {{0,2,3,1},{2,4,5,3},{4,1,0,5}}));
  assert(mobius && mobius->admitted_cells());
  assert(!mobius->orientation().conflicting_edge_ids.empty());
  std::cout << "Polygonal contracts passed\n";
}
