#include "cad_mat/nurbs.hpp"

#include <cassert>
#include <cmath>
#include <limits>
#include <vector>

namespace {

void basis_derivatives_report_local_quadratic_values() {
  const std::vector<double> knots{0.0, 0.0, 0.0, 1.0, 1.0, 1.0};
  const std::vector<double> parameters{0.25};

  const auto result = cad::nurbs::basis_derivatives(2, knots, parameters, 2);

  assert(result.has_value());
  assert(result->spans().size() == 1);
  assert(result->spans()[0] == 2);
  assert(result->derivative(0, 0, 0) == 0.5625);
  assert(result->derivative(0, 0, 1) == 0.375);
  assert(result->derivative(0, 0, 2) == 0.0625);
  assert(result->derivative(1, 0, 0) == -1.5);
  assert(result->derivative(1, 0, 1) == 1.0);
  assert(result->derivative(1, 0, 2) == 0.5);
  assert(result->derivative(2, 0, 0) == 2.0);
  assert(result->derivative(2, 0, 1) == -4.0);
  assert(result->derivative(2, 0, 2) == 2.0);
}

void evaluates_a_planar_tensor_grid() {
  const cad::nurbs::SurfaceSpec surface{
      .degree_u = 1,
      .degree_v = 1,
      .knots_u = {0.0, 0.0, 1.0, 1.0},
      .knots_v = {0.0, 0.0, 1.0, 1.0},
      .control_points =
          {
              {0.0, 0.0, 0.0, 1.0},
              {0.0, 4.0, 0.0, 1.0},
              {3.0, 0.0, 0.0, 1.0},
              {3.0, 4.0, 0.0, 1.0},
          },
      .control_count_u = 2,
      .control_count_v = 2,
  };
  const std::vector<double> u{0.0, 0.5, 1.0};
  const std::vector<double> v{0.0, 0.25, 1.0};

  const auto result =
      cad::nurbs::evaluate_surface(surface, {.u = u, .v = v, .tile_side = 1});
  const auto untiled = cad::nurbs::evaluate_surface(surface, {.u = u, .v = v});

  assert(result.has_value());
  assert(untiled.has_value());
  assert(result->u_count() == 3);
  assert(result->v_count() == 3);
  assert(result->valid_mask().size() == 9);
  for (std::uint32_t u_index = 0; u_index < result->u_count(); ++u_index) {
    for (std::uint32_t v_index = 0; v_index < result->v_count(); ++v_index) {
      const auto index = u_index * result->v_count() + v_index;
      const auto point = result->points()[index];
      assert(std::abs(point.x - 3.0 * u[u_index]) < 1e-14);
      assert(std::abs(point.y - 4.0 * v[v_index]) < 1e-14);
      assert(std::abs(point.z) < 1e-14);
      assert(result->valid_mask()[index] == 1);
      assert(std::abs(result->normals()[index].z - 1.0) < 1e-14);
      assert(std::abs(result->principal_max()[index]) < 1e-14);
      assert(std::abs(result->principal_min()[index]) < 1e-14);
      assert(std::abs(untiled->points()[index].x - point.x) < 1e-14);
      assert(std::abs(untiled->points()[index].y - point.y) < 1e-14);
    }
  }
}

void evaluates_an_exact_rational_quarter_cylinder() {
  const double radius = 2.0;
  const double middle_weight = std::sqrt(0.5);
  const cad::nurbs::SurfaceSpec surface{
      .degree_u = 2,
      .degree_v = 1,
      .knots_u = {0.0, 0.0, 0.0, 1.0, 1.0, 1.0},
      .knots_v = {0.0, 0.0, 1.0, 1.0},
      .control_points =
          {
              {radius, 0.0, 0.0, 1.0},
              {radius, 0.0, 3.0, 1.0},
              {radius * middle_weight, radius * middle_weight, 0.0,
               middle_weight},
              {radius * middle_weight, radius * middle_weight,
               3.0 * middle_weight, middle_weight},
              {0.0, radius, 0.0, 1.0},
              {0.0, radius, 3.0, 1.0},
          },
      .control_count_u = 3,
      .control_count_v = 2,
  };
  const std::vector<double> u{0.0, 0.5, 1.0};
  const std::vector<double> v{0.0, 1.0};

  const auto result = cad::nurbs::evaluate_surface(surface, {.u = u, .v = v});
  auto uniformly_rescaled = surface;
  for (auto &point : uniformly_rescaled.control_points) {
    point.xw *= 1e100;
    point.yw *= 1e100;
    point.zw *= 1e100;
    point.w *= 1e100;
  }
  const auto rescaled =
      cad::nurbs::evaluate_surface(uniformly_rescaled, {.u = u, .v = v});

  assert(result.has_value());
  assert(rescaled.has_value());
  for (std::size_t index = 0; index < result->points().size(); ++index) {
    const auto point = result->points()[index];
    assert(std::abs(std::hypot(point.x, point.y) - radius) < 1e-12);
    assert(std::abs(result->principal_max()[index]) < 1e-11);
    assert(std::abs(result->principal_min()[index] + 1.0 / radius) < 1e-11);
    assert(std::abs(result->normals()[index].x - point.x / radius) < 1e-11);
    assert(std::abs(result->normals()[index].y - point.y / radius) < 1e-11);
    assert(std::abs(rescaled->points()[index].x - point.x) < 1e-12);
    assert(std::abs(rescaled->points()[index].y - point.y) < 1e-12);
    assert(std::abs(rescaled->points()[index].z - point.z) < 1e-12);
  }
}

void does_not_invent_curvature_after_large_translation() {
  const double x = 1e10;
  const cad::nurbs::SurfaceSpec surface{
      .degree_u = 1,
      .degree_v = 1,
      .knots_u = {0.0, 0.0, 1.0, 1.0},
      .knots_v = {0.0, 0.0, 1.0, 1.0},
      .control_points =
          {
              {x, -2.0 * x, x, 1.0},
              {x, -2.0 * x + 4.0, x, 1.0},
              {x + 3.0, -2.0 * x, x, 1.0},
              {x + 3.0, -2.0 * x + 4.0, x, 1.0},
          },
      .control_count_u = 2,
      .control_count_v = 2,
  };
  const std::vector<double> parameter{0.0, 0.5, 1.0};

  const auto result =
      cad::nurbs::evaluate_surface(surface, {.u = parameter, .v = parameter});

  assert(result.has_value());
  for (std::size_t index = 0; index < result->mean().size(); ++index) {
    assert(std::abs(result->mean()[index]) < 1e-15);
    assert(std::abs(result->normals()[index].z - 1.0) < 1e-15);
  }
}

void masks_or_rejects_a_singular_parameterization() {
  const cad::nurbs::SurfaceSpec surface{
      .degree_u = 1,
      .degree_v = 1,
      .knots_u = {0.0, 0.0, 1.0, 1.0},
      .knots_v = {0.0, 0.0, 1.0, 1.0},
      .control_points = {{0.0, 0.0, 0.0, 1.0},
                         {0.0, 0.0, 0.0, 1.0},
                         {0.0, 0.0, 0.0, 1.0},
                         {0.0, 0.0, 0.0, 1.0}},
      .control_count_u = 2,
      .control_count_v = 2,
  };
  const std::vector<double> u{0.25, 0.75};
  const std::vector<double> v{0.5};

  const auto masked = cad::nurbs::evaluate_surface(surface, {.u = u, .v = v});
  const auto rejected = cad::nurbs::evaluate_surface(
      surface,
      {.u = u, .v = v, .singular_policy = cad::nurbs::SingularPolicy::reject});

  assert(masked.has_value());
  for (std::size_t index = 0; index < masked->valid_mask().size(); ++index) {
    assert(masked->valid_mask()[index] == 0);
    assert(std::isnan(masked->principal_max()[index]));
    assert(masked->normals()[index].x == 0.0);
    assert(masked->normals()[index].y == 0.0);
    assert(masked->normals()[index].z == 0.0);
  }
  assert(!rejected.has_value());
  assert(rejected.error().code ==
         cad::nurbs::SurfaceErrorCode::singular_surface);
}

void preserves_endpoint_and_zeroes_unsupported_derivatives() {
  const std::vector<double> knots{0.0, 0.0, 1.0, 1.0};
  const std::vector<double> parameters{1.0};

  const auto result = cad::nurbs::basis_derivatives(1, knots, parameters, 3);

  assert(result.has_value());
  assert(result->spans()[0] == 1);
  assert(result->derivative(0, 0, 0) == 0.0);
  assert(result->derivative(0, 0, 1) == 1.0);
  assert(result->derivative(2, 0, 0) == 0.0);
  assert(result->derivative(3, 0, 1) == 0.0);
}

void selects_the_right_hand_piece_at_an_interior_repeated_knot() {
  const std::vector<double> knots{0.0, 0.0, 0.5, 0.5, 1.0, 1.0};
  const std::vector<double> parameters{0.5};

  const auto result = cad::nurbs::basis_derivatives(1, knots, parameters, 1);

  assert(result.has_value());
  assert(result->spans()[0] == 3);
  assert(result->derivative(0, 0, 0) == 1.0);
  assert(result->derivative(0, 0, 1) == 0.0);
  assert(result->derivative(1, 0, 0) == -2.0);
  assert(result->derivative(1, 0, 1) == 2.0);
}

void rejects_an_unrepresentable_derivative_order() {
  const std::vector<double> knots{0.0, 0.0, 1.0, 1.0};
  const std::vector<double> parameters{0.5};

  const auto result = cad::nurbs::basis_derivatives(
      1, knots, parameters,
      static_cast<std::uint32_t>(std::numeric_limits<int>::max()) + 1);

  assert(!result.has_value());
  assert(result.error().code ==
         cad::nurbs::SurfaceErrorCode::invalid_derivative_order);
}

void rejects_a_degree_beyond_the_signed_recurrence_range() {
  const auto result = cad::nurbs::basis_derivatives(
      static_cast<std::uint32_t>(std::numeric_limits<int>::max()) + 1, {}, {},
      0);

  assert(!result.has_value());
  assert(result.error().code == cad::nurbs::SurfaceErrorCode::invalid_degree);
}

} // namespace

int main() {
  basis_derivatives_report_local_quadratic_values();
  evaluates_a_planar_tensor_grid();
  evaluates_an_exact_rational_quarter_cylinder();
  does_not_invent_curvature_after_large_translation();
  masks_or_rejects_a_singular_parameterization();
  preserves_endpoint_and_zeroes_unsupported_derivatives();
  selects_the_right_hand_piece_at_an_interior_repeated_knot();
  rejects_an_unrepresentable_derivative_order();
  rejects_a_degree_beyond_the_signed_recurrence_range();
}
