#include "cad_mat/nurbs.hpp"

#include <algorithm>
#include <cmath>
#include <limits>
#include <vector>

namespace cad::nurbs {
namespace {

struct KnotDomain {
  std::uint32_t final_control_index;
  double first;
  double last;
};

[[nodiscard]] std::expected<KnotDomain, SurfaceError>
validate_knots(std::uint32_t degree, std::span<const double> knots) {
  if (degree > static_cast<std::uint32_t>(std::numeric_limits<int>::max())) {
    return std::unexpected(SurfaceError{SurfaceErrorCode::invalid_degree});
  }
  if (knots.size() > std::numeric_limits<std::uint32_t>::max()) {
    return std::unexpected(SurfaceError{SurfaceErrorCode::input_too_large});
  }
  const auto minimum_knot_count = 2 * (static_cast<std::size_t>(degree) + 1);
  if (knots.size() < minimum_knot_count) {
    return std::unexpected(SurfaceError{SurfaceErrorCode::invalid_knot_vector});
  }
  if (!std::ranges::all_of(knots,
                           [](double value) { return std::isfinite(value); }) ||
      !std::ranges::is_sorted(knots)) {
    return std::unexpected(SurfaceError{SurfaceErrorCode::invalid_knot_vector});
  }
  const auto final_control_index =
      static_cast<std::uint32_t>(knots.size() - degree - 2);
  if (final_control_index < degree ||
      knots[degree] >= knots[final_control_index + 1]) {
    return std::unexpected(SurfaceError{SurfaceErrorCode::invalid_knot_vector});
  }
  std::uint32_t multiplicity = 1;
  for (std::size_t index = 1; index < knots.size(); ++index) {
    multiplicity = knots[index] == knots[index - 1] ? multiplicity + 1 : 1;
    if (multiplicity > degree + 1) {
      return std::unexpected(
          SurfaceError{SurfaceErrorCode::invalid_knot_vector});
    }
  }
  return KnotDomain{final_control_index, knots[degree],
                    knots[final_control_index + 1]};
}

[[nodiscard]] double divide_or_zero(double numerator,
                                    double denominator) noexcept {
  return denominator == 0.0 ? 0.0 : numerator / denominator;
}

[[nodiscard]] Point3 add(Point3 left, Point3 right) noexcept {
  return {left.x + right.x, left.y + right.y, left.z + right.z};
}

[[nodiscard]] Point3 subtract(Point3 left, Point3 right) noexcept {
  return {left.x - right.x, left.y - right.y, left.z - right.z};
}

[[nodiscard]] Point3 scale(Point3 point, double scalar) noexcept {
  return {point.x * scalar, point.y * scalar, point.z * scalar};
}

[[nodiscard]] double dot(Point3 left, Point3 right) noexcept {
  return left.x * right.x + left.y * right.y + left.z * right.z;
}

[[nodiscard]] Point3 cross(Point3 left, Point3 right) noexcept {
  return {left.y * right.z - left.z * right.y,
          left.z * right.x - left.x * right.z,
          left.x * right.y - left.y * right.x};
}

[[nodiscard]] double norm(Point3 point) noexcept {
  return std::sqrt(dot(point, point));
}

[[nodiscard]] bool finite(Point3 point) noexcept {
  return std::isfinite(point.x) && std::isfinite(point.y) &&
         std::isfinite(point.z);
}

[[nodiscard]] Point3 xyz(HomogeneousPoint point) noexcept {
  return {point.xw, point.yw, point.zw};
}

[[nodiscard]] bool finite(HomogeneousPoint point) noexcept {
  return std::isfinite(point.xw) && std::isfinite(point.yw) &&
         std::isfinite(point.zw) && std::isfinite(point.w);
}

[[nodiscard]] std::expected<std::pair<KnotDomain, KnotDomain>, SurfaceError>
validate_surface(const SurfaceSpec &surface, const EvaluationRequest &request) {
  const auto u_domain = validate_knots(surface.degree_u, surface.knots_u);
  if (!u_domain.has_value()) {
    return std::unexpected(u_domain.error());
  }
  const auto v_domain = validate_knots(surface.degree_v, surface.knots_v);
  if (!v_domain.has_value()) {
    return std::unexpected(v_domain.error());
  }
  if (request.u.size() > std::numeric_limits<std::uint32_t>::max() ||
      request.v.size() > std::numeric_limits<std::uint32_t>::max()) {
    return std::unexpected(SurfaceError{SurfaceErrorCode::input_too_large});
  }
  if (surface.control_count_u != u_domain->final_control_index + 1 ||
      surface.control_count_v != v_domain->final_control_index + 1 ||
      surface.control_points.size() !=
          static_cast<std::size_t>(surface.control_count_u) *
              surface.control_count_v) {
    return std::unexpected(
        SurfaceError{SurfaceErrorCode::control_net_shape_mismatch});
  }
  for (const auto point : surface.control_points) {
    if (!finite(point)) {
      return std::unexpected(SurfaceError{SurfaceErrorCode::nonfinite_input});
    }
    if (point.w <= 0.0) {
      return std::unexpected(
          SurfaceError{SurfaceErrorCode::nonpositive_weight});
    }
  }
  if (!std::isfinite(request.regularity_tolerance) ||
      request.regularity_tolerance <= 0.0 ||
      request.regularity_tolerance >= 1.0) {
    return std::unexpected(
        SurfaceError{SurfaceErrorCode::invalid_regularity_tolerance});
  }
  return std::pair{*u_domain, *v_domain};
}

} // namespace

double
BasisDerivatives::derivative(std::uint32_t derivative_order,
                             std::uint32_t sample_index,
                             std::uint32_t local_basis_index) const noexcept {
  const auto local_count = degree_ + 1;
  return values_[(static_cast<std::size_t>(derivative_order) * sample_count_ +
                  sample_index) *
                     local_count +
                 local_basis_index];
}

std::expected<BasisDerivatives, SurfaceError>
basis_derivatives(std::uint32_t degree, std::span<const double> knots,
                  std::span<const double> parameters,
                  std::uint32_t max_derivative) {
  if (max_derivative >
      static_cast<std::uint32_t>(std::numeric_limits<int>::max())) {
    return std::unexpected(
        SurfaceError{SurfaceErrorCode::invalid_derivative_order});
  }
  if (parameters.size() > std::numeric_limits<std::uint32_t>::max()) {
    return std::unexpected(SurfaceError{SurfaceErrorCode::input_too_large});
  }
  const auto domain = validate_knots(degree, knots);
  if (!domain.has_value()) {
    return std::unexpected(domain.error());
  }
  for (std::size_t index = 0; index < parameters.size(); ++index) {
    if (!std::isfinite(parameters[index])) {
      return std::unexpected(SurfaceError{SurfaceErrorCode::nonfinite_input});
    }
    if (parameters[index] < domain->first || parameters[index] > domain->last) {
      return std::unexpected(
          SurfaceError{SurfaceErrorCode::parameter_out_of_domain});
    }
  }

  BasisDerivatives result;
  result.degree_ = degree;
  result.derivative_count_ = max_derivative + 1;
  result.sample_count_ = static_cast<std::uint32_t>(parameters.size());
  result.spans_.resize(parameters.size());
  const auto local_count = static_cast<std::size_t>(degree + 1);
  const auto derivative_count = static_cast<std::size_t>(max_derivative) + 1;
  if (parameters.size() >
          std::numeric_limits<std::size_t>::max() / derivative_count ||
      parameters.size() * derivative_count >
          std::numeric_limits<std::size_t>::max() / local_count) {
    return std::unexpected(SurfaceError{SurfaceErrorCode::input_too_large});
  }
  result.values_.assign(derivative_count * parameters.size() * local_count,
                        0.0);

  const auto supported_derivative = std::min(degree, max_derivative);
  for (std::uint32_t sample = 0; sample < result.sample_count_; ++sample) {
    const double parameter = parameters[sample];
    // Closed upper endpoint selects the last nonempty piece on its left.
    const auto upper = parameter == domain->last
        ? std::lower_bound(knots.begin(), knots.end(), parameter)
        : std::upper_bound(knots.begin(), knots.end(), parameter);
    const auto raw_span =
        static_cast<std::uint32_t>(std::distance(knots.begin(), upper) - 1);
    const auto span = std::clamp(raw_span, degree, domain->final_control_index);
    result.spans_[sample] = span;

    std::vector<double> ndu(local_count * local_count, 0.0);
    std::vector<double> left(local_count, 0.0);
    std::vector<double> right(local_count, 0.0);
    const auto ndu_at = [local_count, &ndu](std::uint32_t row,
                                            std::uint32_t column) -> double & {
      return ndu[static_cast<std::size_t>(row) * local_count + column];
    };
    ndu_at(0, 0) = 1.0;
    for (std::uint32_t column = 1; column <= degree; ++column) {
      left[column] = parameter - knots[span - column + 1];
      right[column] = knots[span + column] - parameter;
      double saved = 0.0;
      for (std::uint32_t row = 0; row < column; ++row) {
        ndu_at(column, row) = right[row + 1] + left[column - row];
        const auto temporary =
            divide_or_zero(ndu_at(row, column - 1), ndu_at(column, row));
        ndu_at(row, column) = saved + right[row + 1] * temporary;
        saved = left[column - row] * temporary;
      }
      ndu_at(column, column) = saved;
    }
    for (std::uint32_t local = 0; local <= degree; ++local) {
      result.values_[static_cast<std::size_t>(sample) * local_count + local] =
          ndu_at(local, degree);
    }

    for (std::uint32_t local = 0; local <= degree; ++local) {
      std::vector<double> a(2 * local_count, 0.0);
      const auto a_at = [local_count, &a](std::uint32_t row,
                                          std::uint32_t column) -> double & {
        return a[static_cast<std::size_t>(row) * local_count + column];
      };
      std::uint32_t first_row = 0;
      std::uint32_t second_row = 1;
      a_at(first_row, 0) = 1.0;
      for (std::uint32_t derivative = 1; derivative <= supported_derivative;
           ++derivative) {
        std::fill_n(a.begin() +
                        static_cast<std::ptrdiff_t>(second_row * local_count),
                    local_count, 0.0);
        double value = 0.0;
        const auto relative =
            static_cast<int>(local) - static_cast<int>(derivative);
        const auto remaining =
            static_cast<int>(degree) - static_cast<int>(derivative);
        if (relative >= 0) {
          a_at(second_row, 0) =
              divide_or_zero(a_at(first_row, 0),
                             ndu_at(static_cast<std::uint32_t>(remaining + 1),
                                    static_cast<std::uint32_t>(relative)));
          value = a_at(second_row, 0) *
                  ndu_at(static_cast<std::uint32_t>(relative),
                         static_cast<std::uint32_t>(remaining));
        }
        const auto start = relative >= -1 ? 1 : -relative;
        const auto end =
            static_cast<int>(local) - 1 <= remaining
                ? static_cast<int>(derivative) - 1
                : static_cast<int>(degree) - static_cast<int>(local);
        for (int term = start; term <= end; ++term) {
          const auto term_index = static_cast<std::uint32_t>(term);
          a_at(second_row, term_index) = divide_or_zero(
              a_at(first_row, term_index) - a_at(first_row, term_index - 1),
              ndu_at(static_cast<std::uint32_t>(remaining + 1),
                     static_cast<std::uint32_t>(relative + term)));
          value += a_at(second_row, term_index) *
                   ndu_at(static_cast<std::uint32_t>(relative + term),
                          static_cast<std::uint32_t>(remaining));
        }
        if (static_cast<int>(local) <= remaining) {
          a_at(second_row, derivative) = divide_or_zero(
              -a_at(first_row, derivative - 1),
              ndu_at(static_cast<std::uint32_t>(remaining + 1), local));
          value += a_at(second_row, derivative) *
                   ndu_at(local, static_cast<std::uint32_t>(remaining));
        }
        result.values_[(static_cast<std::size_t>(derivative) *
                            result.sample_count_ +
                        sample) *
                           local_count +
                       local] = value;
        std::swap(first_row, second_row);
      }
    }
  }

  double factor = static_cast<double>(degree);
  for (std::uint32_t derivative = 1; derivative <= supported_derivative;
       ++derivative) {
    for (std::uint32_t sample = 0; sample < result.sample_count_; ++sample) {
      for (std::uint32_t local = 0; local <= degree; ++local) {
        result.values_[(static_cast<std::size_t>(derivative) *
                            result.sample_count_ +
                        sample) *
                           local_count +
                       local] *= factor;
      }
    }
    factor *= degree - derivative;
  }
  return result;
}

std::expected<SurfaceGeometry, SurfaceError>
evaluate_surface(const SurfaceSpec &surface, const EvaluationRequest &request) {
  const auto domains = validate_surface(surface, request);
  if (!domains.has_value()) {
    return std::unexpected(domains.error());
  }
  const auto basis_u =
      basis_derivatives(surface.degree_u, surface.knots_u, request.u, 2);
  if (!basis_u.has_value()) {
    return std::unexpected(basis_u.error());
  }
  const auto basis_v =
      basis_derivatives(surface.degree_v, surface.knots_v, request.v, 2);
  if (!basis_v.has_value()) {
    return std::unexpected(basis_v.error());
  }

  std::vector<HomogeneousPoint> control_points = surface.control_points;
  double largest_weight = 0.0;
  for (const auto point : control_points) {
    largest_weight = std::max(largest_weight, point.w);
  }
  for (auto &point : control_points) {
    point.xw /= largest_weight;
    point.yw /= largest_weight;
    point.zw /= largest_weight;
    point.w /= largest_weight;
  }
  const Point3 origin =
      scale(xyz(control_points.front()), 1.0 / control_points.front().w);
  for (auto &point : control_points) {
    point.xw -= point.w * origin.x;
    point.yw -= point.w * origin.y;
    point.zw -= point.w * origin.z;
  }

  SurfaceGeometry result;
  result.u_count_ = static_cast<std::uint32_t>(request.u.size());
  result.v_count_ = static_cast<std::uint32_t>(request.v.size());
  const auto count = request.u.size() * request.v.size();
  const auto nan = std::numeric_limits<double>::quiet_NaN();
  result.points_.resize(count);
  result.normals_.assign(count, {});
  result.principal_max_.assign(count, nan);
  result.principal_min_.assign(count, nan);
  result.mean_.assign(count, nan);
  result.gaussian_.assign(count, nan);
  result.valid_mask_.assign(count, 0);

  const auto derivative = [&](std::uint32_t u_order, std::uint32_t v_order,
                              std::uint32_t u_sample, std::uint32_t v_sample) {
    HomogeneousPoint sum{};
    const auto u_span = basis_u->spans()[u_sample];
    const auto v_span = basis_v->spans()[v_sample];
    for (std::uint32_t u_local = 0; u_local <= surface.degree_u; ++u_local) {
      const auto u_control = u_span - surface.degree_u + u_local;
      const auto u_weight = basis_u->derivative(u_order, u_sample, u_local);
      for (std::uint32_t v_local = 0; v_local <= surface.degree_v; ++v_local) {
        const auto v_control = v_span - surface.degree_v + v_local;
        const auto weight =
            u_weight * basis_v->derivative(v_order, v_sample, v_local);
        const auto point = control_points[static_cast<std::size_t>(u_control) *
                                              surface.control_count_v +
                                          v_control];
        sum.xw += weight * point.xw;
        sum.yw += weight * point.yw;
        sum.zw += weight * point.zw;
        sum.w += weight * point.w;
      }
    }
    return sum;
  };

  bool singular = false;
  // Traversal is internal policy. Full output and basis tables are retained;
  // this operation does not promise bounded working memory.
  for (std::uint32_t u_sample = 0; u_sample < result.u_count_; ++u_sample) {
    for (std::uint32_t v_sample = 0; v_sample < result.v_count_; ++v_sample) {
      const auto index =
          static_cast<std::size_t>(u_sample) * result.v_count_ + v_sample;
      const auto homogeneous_position = derivative(0, 0, u_sample, v_sample);
      const auto homogeneous_u = derivative(1, 0, u_sample, v_sample);
      const auto homogeneous_v = derivative(0, 1, u_sample, v_sample);
      const auto homogeneous_uu = derivative(2, 0, u_sample, v_sample);
      const auto homogeneous_vv = derivative(0, 2, u_sample, v_sample);
      const auto homogeneous_uv = derivative(1, 1, u_sample, v_sample);
      if (!finite(homogeneous_position) || !finite(homogeneous_u) ||
          !finite(homogeneous_v) || !finite(homogeneous_uu) ||
          !finite(homogeneous_vv) || !finite(homogeneous_uv) ||
          homogeneous_position.w <= std::numeric_limits<double>::min()) {
        return std::unexpected(
            SurfaceError{SurfaceErrorCode::rational_denominator_underflow});
      }
      const auto point =
          scale(xyz(homogeneous_position), 1.0 / homogeneous_position.w);
      const auto u_tangent =
          scale(subtract(xyz(homogeneous_u), scale(point, homogeneous_u.w)),
                1.0 / homogeneous_position.w);
      const auto v_tangent =
          scale(subtract(xyz(homogeneous_v), scale(point, homogeneous_v.w)),
                1.0 / homogeneous_position.w);
      const auto uu =
          scale(subtract(subtract(xyz(homogeneous_uu),
                                  scale(u_tangent, 2.0 * homogeneous_u.w)),
                         scale(point, homogeneous_uu.w)),
                1.0 / homogeneous_position.w);
      const auto vv =
          scale(subtract(subtract(xyz(homogeneous_vv),
                                  scale(v_tangent, 2.0 * homogeneous_v.w)),
                         scale(point, homogeneous_vv.w)),
                1.0 / homogeneous_position.w);
      const auto uv =
          scale(subtract(subtract(subtract(xyz(homogeneous_uv),
                                           scale(v_tangent, homogeneous_u.w)),
                                  scale(u_tangent, homogeneous_v.w)),
                         scale(point, homogeneous_uv.w)),
                1.0 / homogeneous_position.w);
      if (!finite(point) || !finite(u_tangent) || !finite(v_tangent) ||
          !finite(uu) || !finite(vv) || !finite(uv)) {
        return std::unexpected(
            SurfaceError{SurfaceErrorCode::nonfinite_derivative});
      }

      const auto u_length = norm(u_tangent);
      const auto v_length = norm(v_tangent);
      const auto safe_u = u_length > 0.0 ? u_length : 1.0;
      const auto safe_v = v_length > 0.0 ? v_length : 1.0;
      const auto unit_u = scale(u_tangent, 1.0 / safe_u);
      const auto unit_v = scale(v_tangent, 1.0 / safe_v);
      const auto raw_normal = cross(unit_u, unit_v);
      const auto sine = norm(raw_normal);
      bool valid = u_length > 0.0 && v_length > 0.0 &&
                   sine > request.regularity_tolerance;
      auto normal = valid ? scale(raw_normal, 1.0 / sine) : Point3{};
      const auto cosine = dot(unit_u, unit_v);
      const auto b11 = dot(uu, normal) / safe_u / safe_u;
      const auto b12 = dot(uv, normal) / safe_u / safe_v;
      const auto b22 = dot(vv, normal) / safe_v / safe_v;
      const auto determinant = valid ? sine * sine : 1.0;
      const auto gaussian = (b11 * b22 - b12 * b12) / determinant;
      const auto mean = (b11 + b22 - 2.0 * cosine * b12) / (2.0 * determinant);
      const auto root = std::sqrt(std::max(0.0, mean * mean - gaussian));
      valid = valid && std::isfinite(mean) && std::isfinite(gaussian) &&
              std::isfinite(root);
      if (!valid) {
        normal = {};
        singular = true;
      }
      result.points_[index] = add(point, origin);
      result.normals_[index] = normal;
      result.valid_mask_[index] = valid ? 1 : 0;
      if (valid) {
        result.principal_max_[index] = mean + root;
        result.principal_min_[index] = mean - root;
        result.mean_[index] = mean;
        result.gaussian_[index] = gaussian;
      }
    }
  }
  if (singular && request.singular_policy == SingularPolicy::reject) {
    return std::unexpected(SurfaceError{SurfaceErrorCode::singular_surface});
  }
  return result;
}

} // namespace cad::nurbs
