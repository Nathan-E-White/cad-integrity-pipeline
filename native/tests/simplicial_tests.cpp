#include "SimplicialComplex.hpp"

#include <cstdlib>
#include <iostream>
#include <numeric>

#define CHECK(...)                                                             \
  do {                                                                         \
    if (!(__VA_ARGS__)) {                                                      \
      std::cerr << __FILE__ << ':' << __LINE__ << ": " << #__VA_ARGS__         \
                << '\n';                                                       \
      std::exit(1);                                                            \
    }                                                                          \
  } while (false)

using namespace cad::simplicial;

void general_facets_retain_all_dimensions() {
  auto result = SimplicialComplex::build({{3, 1, 0, 2}});
  CHECK(result);
  CHECK(result->get_tier(0).size() == 4);
  CHECK(result->get_tier(1).size() == 6);
  CHECK(result->get_tier(2).size() == 4);
  CHECK(result->get_tier(3).size() == 1);
  auto incidence = result->boundary_operator(3);
  CHECK(incidence);
  CHECK(incidence->num_rows == 4 && incidence->num_cols == 1);
  CHECK(incidence->values == std::vector<std::int8_t>({-1, 1, -1, 1}));
}

void closure_budget_and_incidence_are_checked() {
  CHECK(!SimplicialComplex::build({{1, 1}}));
  auto exact = SimplicialComplex::build({{0, 1, 2}, {2, 0, 1}}, 7);
  CHECK(exact);
  CHECK(!SimplicialComplex::build({{0, 1, 2}}, 6));
  std::vector<int> huge(64);
  std::iota(huge.begin(), huge.end(), 0);
  CHECK(!SimplicialComplex::build({huge}, 10));
  auto tetra = SimplicialComplex::build({{0, 1, 2, 3}});
  for (std::size_t d = 2; d <= 3; ++d) {
    auto a = tetra->boundary_operator(d - 1), b = tetra->boundary_operator(d);
    CHECK(a && b);
    for (std::size_t r = 0; r < a->num_rows; ++r) {
      for (std::size_t c = 0; c < b->num_cols; ++c) {
        int sum = 0;
        for (auto i = a->row_ptr[r]; i < a->row_ptr[r + 1]; ++i) {
          auto k = a->col_ind[i];
          for (auto j = b->row_ptr[k]; j < b->row_ptr[k + 1]; ++j)
            if (b->col_ind[j] == c)
              sum += a->values[i] * b->values[j];
        }
        CHECK(sum == 0);
      }
    }
  }
  TriangleMesh mesh{{{0, 0, 0}, {1, 0, 0}, {0, 1, 0}, {9, 9, 9}}, {{0, 1, 2}}};
  auto complex = mesh.to_simplicial_complex(8);
  CHECK(complex && complex->get_tier(0).size() == 4);
  CHECK(!mesh.to_simplicial_complex(7));
  mesh.triangles.push_back({2, 1, 0});
  CHECK(mesh.to_simplicial_complex().error() ==
        TopologyStatus::DuplicateTriangles);
}

void polygon_conversion_rejects_malformed_input() {
  auto polygon = PolyhedralBRep::from_polygons(
      {{0, 0, 0}, {2, 0, 0}, {2, 2, 0}, {0, 2, 0}}, {{0, 1, 2, 3}});
  CHECK(polygon);
  auto mesh = polygon->triangulate_convex_faces();
  CHECK(mesh && mesh->triangles.size() == 2);
  CHECK(mesh->triangles[0] == std::array<int, 3>({0, 1, 2}));
  CHECK(mesh->triangles[1] == std::array<int, 3>({0, 2, 3}));
  CHECK(!polygon->triangulate_face(0, -1));
  CHECK(!polygon->triangulate_face(0, std::numeric_limits<float>::quiet_NaN()));
  polygon->face_coedges[0] = std::numeric_limits<int>::min();
  CHECK(!polygon->face_vertices(0));
  polygon->face_offsets.back() = 999;
  CHECK(polygon->face_loop(0).empty());
  CHECK(!polygon->triangulate_convex_faces());
  CHECK(!PolyhedralBRep::from_polygons({{0, 0, 0}}, {{0, 1, 2}}));
  CHECK(!PolyhedralBRep::from_polygons({}, {}, static_cast<LengthUnit>(255)));
  auto nonplanar = PolyhedralBRep::from_polygons(
      {{0, 0, 0}, {2, 0, 0}, {2, 2, 0}, {0, 2, 1}}, {{0, 1, 2, 3}});
  CHECK(nonplanar && !nonplanar->triangulate_convex_faces());
  auto concave = PolyhedralBRep::from_polygons(
      {{0, 0, 0}, {2, 0, 0}, {1, 0.5f, 0}, {2, 2, 0}, {0, 2, 0}},
      {{0, 1, 2, 3, 4}});
  CHECK(concave && !concave->triangulate_convex_faces());
}

void spatial_queries_retain_box_and_ray_behavior() {
  TriangleMesh mesh{
      {{0, 0, 0}, {1, 0, 0}, {0, 1, 0}, {0, 0, -2}, {1, 0, -2}, {0, 1, -2}},
      {{0, 1, 2}, {3, 4, 5}}};
  const auto bvh = FlatBVH::build(mesh);
  CHECK(bvh.node_count() == 3);
  AABB box;
  box.grow(Point3{0, 0, -0.1f});
  box.grow(Point3{1, 1, 0.1f});
  std::vector<std::size_t> candidates;
  bvh.query_box(box, candidates);
  CHECK(candidates == std::vector<std::size_t>{0});
  std::vector<Ray> rays;
  for (int i = 0; i < 64; ++i)
    rays.push_back(Ray::create({0.25f, 0.25f, 1}, {0, 0, -2}));
  rays.push_back(Ray::create({3, 3, 1}, {0, 0, -1}));
  auto batch = bvh.parallel_intersect_rays(rays);
  for (std::size_t i = 0; i < rays.size(); ++i) {
    auto scalar = bvh.intersect_ray(rays[i]);
    CHECK(scalar.hit == batch[i].hit);
    CHECK(scalar.triangle_index == batch[i].triangle_index);
    CHECK(scalar.t == batch[i].t);
    CHECK(scalar.hit == (i < 64));
    if (scalar.hit) {
      CHECK(scalar.triangle_index == 0);
      CHECK(scalar.t == 1);
    }
  }
  // Origin lies exactly on a slab plane; no zero-times-infinity arithmetic.
  auto edge = bvh.intersect_ray(Ray::create({0, 0.25f, 1}, {0, 0, -1}));
  CHECK(edge.hit && edge.t == 1);
  bool rejected = false;
  try {
    (void)Ray::create({0, 0, 0}, {0, 0, 0});
  } catch (const std::invalid_argument &) {
    rejected = true;
  }
  CHECK(rejected);
  mesh.triangles[0][0] = -1;
  rejected = false;
  try {
    (void)FlatBVH::build(mesh);
  } catch (const std::invalid_argument &) {
    rejected = true;
  }
  CHECK(rejected);
}

void finite_geometry_uses_scale_aware_ray_arithmetic() {
  for (float scale : {1e-4f, 1.0f, 1e20f}) {
    TriangleMesh mesh{{{0, 0, 0}, {scale, 0, 0}, {0, scale, 0}}, {{0, 1, 2}}};
    auto bvh = FlatBVH::build(mesh);
    auto ray = Ray::create({scale / 4, scale / 4, 1}, {0, 0, -1});
    auto hit = bvh.intersect_ray(ray);
    CHECK(hit.hit && hit.t == 1);
    auto hits = bvh.parallel_intersect_rays(std::vector<Ray>(64, ray));
    for (const auto &result : hits)
      CHECK(result.hit && result.t == 1);
  }
}

void spatial_snapshot_owns_geometry_and_face_identity() {
  auto polygon = PolyhedralBRep::from_polygons({{0, 0, 0},
                                                {2, 0, 0},
                                                {2, 2, 0},
                                                {0, 2, 0},
                                                {4, 0, 0},
                                                {5, 0, 0},
                                                {4, 1, 0}},
                                               {{0, 1, 2, 3}, {4, 5, 6}});
  CHECK(polygon);
  auto mesh = polygon->triangulate_convex_faces();
  CHECK(mesh &&
        mesh->polygonal_face_ids == std::vector<std::size_t>({0, 0, 1}));
  auto bvh = FlatBVH::build(*mesh);
  mesh->vertices.clear();
  mesh->triangles.clear();
  mesh->polygonal_face_ids.clear();
  const auto hit = bvh.intersect_ray(Ray::create({4.2f, 0.2f, 1}, {0, 0, -1}));
  CHECK(hit.hit && hit.polygonal_face_id == 1);
  auto copied = bvh;
  CHECK(copied.intersect_ray(Ray::create({0.2f, 0.2f, 1}, {0, 0, -1}))
            .polygonal_face_id == 0);
  TriangleMesh direct{{{0, 0, 0}, {1, 0, 0}, {0, 1, 0}}, {{0, 1, 2}}};
  auto direct_hit = FlatBVH::build(direct).intersect_ray(
      Ray::create({0.2f, 0.2f, 1}, {0, 0, -1}));
  CHECK(direct_hit.hit && !direct_hit.polygonal_face_id);
  direct.polygonal_face_ids = {0, 1};
  bool rejected = false;
  try {
    (void)FlatBVH::build(direct);
  } catch (const std::invalid_argument &) {
    rejected = true;
  }
  CHECK(rejected);
}

void polygon_admission_is_independent_of_planarity_tolerance() {
  for (float scale : {1e-4f, 1.0f, 1e20f}) {
    auto bowtie = PolyhedralBRep::from_polygons(
        {{0, 0, 0}, {scale, scale, 0}, {0, scale, 0}, {scale, 0, 0}},
        {{0, 1, 2, 3}});
    CHECK(bowtie);
    CHECK(!bowtie->triangulate_convex_faces());
    auto concave = PolyhedralBRep::from_polygons({{0, 0, 0},
                                                  {scale, 0, 0},
                                                  {scale / 2, scale / 4, 0},
                                                  {scale, scale, 0},
                                                  {0, scale, 0}},
                                                 {{0, 1, 2, 3, 4}});
    CHECK(concave && !concave->triangulate_convex_faces(1000));
    auto square = PolyhedralBRep::from_polygons(
        {{0, 0, 0}, {scale, 0, 0}, {scale, scale, 0}, {0, scale, 0}},
        {{0, 1, 2, 3}});
    CHECK(square && square->triangulate_convex_faces());
  }
  auto collapsed_fan = PolyhedralBRep::from_polygons(
      {{0, 0, 0}, {1, 0, 0}, {1, 1, 0}, {0, 1, 0}, {0, 0.5f, 0}},
      {{0, 1, 2, 3, 4}});
  CHECK(collapsed_fan && !collapsed_fan->triangulate_convex_faces());
}

int main() {
  general_facets_retain_all_dimensions();
  closure_budget_and_incidence_are_checked();
  polygon_conversion_rejects_malformed_input();
  spatial_queries_retain_box_and_ray_behavior();
  finite_geometry_uses_scale_aware_ray_arithmetic();
  spatial_snapshot_owns_geometry_and_face_identity();
  polygon_admission_is_independent_of_planarity_tolerance();
  std::cout << "simplicial checks passed\n";
}
