#pragma once

#include <expected>
#include <span>
#include <vector>
#include <numeric>
#include <valarray>

namespace cad::nurbs {
    enum class SurfaceErrorCode {
        invalid_degree,
        invalid_knot_vector,
        parameter_out_of_domain,
        nonfinite_input,
        invalid_derivative_order,
        input_too_large,
        control_net_shape_mismatch,
        nonpositive_weight,
        invalid_regularity_tolerance,
        rational_denominator_underflow,
        nonfinite_derivative,
        singular_surface,
    };

    template<typename T>
    concept FloatingPoint = std::is_floating_point_v<T>;


    struct Point3 {
        double x;
        double y;
        double z;
    };

    /// Homogeneous control point stored as ``(x*w, y*w, z*w, w)``.
    struct HomogeneousPoint {
        double xw;
        double yw;
        double zw;
        double w;
    };

    /// Value-owned rational tensor-product surface input with u-major control-point
    /// order.
    struct SurfaceSpec {
        std::uint32_t degree_u;
        std::uint32_t degree_v;
        std::vector<double> knots_u;
        std::vector<double> knots_v;
        std::vector<HomogeneousPoint> control_points;
        std::uint32_t control_count_u;
        std::uint32_t control_count_v;
    };

    enum class SingularPolicy { mask, reject };

    struct EvaluationRequest {
        std::span<const double> u;
        std::span<const double> v;
        double regularity_tolerance = 1e-10;
        SingularPolicy singular_policy = SingularPolicy::mask;
        std::uint32_t tile_side = 64;
    };


    struct SurfaceError {
        SurfaceErrorCode code;
    };

    /// Local B-spline basis derivatives for independent one-dimensional samples.
    class BasisDerivatives {
    public:
        [[nodiscard]] std::span<const std::uint32_t> spans() const noexcept {
            return spans_;
        }

        /// Access ``derivative_order, sample_index, local_basis_index``.
        [[nodiscard]] double
        derivative(std::uint32_t derivative_order, std::uint32_t sample_index,
                   std::uint32_t local_basis_index) const noexcept;

    private:
        std::uint32_t degree_ = 0;
        std::uint32_t derivative_count_ = 0;
        std::uint32_t sample_count_ = 0;
        std::vector<std::uint32_t> spans_;
        std::vector<double> values_;

        friend std::expected<BasisDerivatives, SurfaceError>
        basis_derivatives(std::uint32_t degree, std::span<const double> knots,
                          std::span<const double> parameters,
                          std::uint32_t max_derivative);
    };

    /// Evaluate local B-spline basis terms and their derivatives.
    [[nodiscard]] std::expected<BasisDerivatives, SurfaceError>
    basis_derivatives(std::uint32_t degree, std::span<const double> knots,
                      std::span<const double> parameters,
                      std::uint32_t max_derivative);

    /// Value-owned tensor-grid surface results in u-major flattened order.
    template <FloatingPoint Fp>
    class SurfaceGeometry {
    public:
        [[nodiscard]] std::uint32_t u_count() const noexcept { return u_count_; }
        [[nodiscard]] std::uint32_t v_count() const noexcept { return v_count_; }

        [[nodiscard]] std::span<const Point3> points() const noexcept {
            return points_;
        }

        [[nodiscard]] std::span<const Point3> normals() const noexcept {
            return normals_;
        }

        [[nodiscard]] std::span<const double> principal_max() const noexcept {
            return principal_max_;
        }

        [[nodiscard]] std::span<const double> principal_min() const noexcept {
            return principal_min_;
        }

        [[nodiscard]] std::span<const double> mean() const noexcept { return mean_; }

        [[nodiscard]] std::span<const double> gaussian() const noexcept {
            return gaussian_;
        }

        [[nodiscard]] std::span<const std::uint8_t> valid_mask() const noexcept {
            return valid_mask_;
        }

    private:
        std::uint32_t u_count_ = 0;
        std::uint32_t v_count_ = 0;
        std::vector<Point3> points_;
        std::vector<Point3> normals_;
        std::vector<Fp> principal_max_;
        std::vector<Fp> principal_min_;
        std::vector<Fp> mean_;
        std::vector<Fp> gaussian_;
        std::vector<std::uint8_t> valid_mask_;

        friend std::expected<SurfaceGeometry, SurfaceError>
        evaluate_surface(const SurfaceSpec &surface,
                         const EvaluationRequest &request);
    };

    /// Evaluate positions, oriented normals, and curvature over the u-v Cartesian
    /// product.
    ///
    [[nodiscard]] std::expected<SurfaceGeometry<float>, SurfaceError>
    evaluate_surface(const SurfaceSpec &surface, const EvaluationRequest &request);
} // namespace cad::nurbs
