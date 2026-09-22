#include <concepts>
#include <compare>
#include <cmath>
#include <iostream>
#include <format>
#include <utility>
#include <stdexcept>
#include <vector>
#include <array>

// ============================================================================
// CORE CONCEPTS & CORE LAYER
// ============================================================================

// Concept to restrict the template to numeric types (integrals or floating-points)
template<typename T>
concept GeometricType = std::integral<T> || std::floating_point<T>;

template<GeometricType T>
class Matrix4x4;

template<GeometricType T>
class Bivector3D;

template<GeometricType T>
class Trivector3D;

template<GeometricType T>
class Point3D {
public:
    using value_type = T;

    T x{};
    T y{};
    T z{};

    // Constructors
    constexpr Point3D() noexcept = default;
    constexpr Point3D(T x_val, T y_val, T z_val) noexcept
        : x(x_val), y(y_val), z(z_val) {}

    // Element Access via index
    [[nodiscard]] constexpr T& operator[](std::size_t index) {
        switch (index) {
            case 0: return x;
            case 1: return y;
            case 2: return z;
            default: throw std::out_of_range("Point3D index out of range (must be 0, 1, or 2)");
        }
    }

    [[nodiscard]] constexpr const T& operator[](std::size_t index) const {
        switch (index) {
            case 0: return x;
            case 1: return y;
            case 2: return z;
            default: throw std::out_of_range("Point3D index out of range (must be 0, 1, or 2)");
        }
    }

    // Unary Operators
    constexpr Point3D operator+() const noexcept { return *this; }
    constexpr Point3D operator-() const noexcept { return Point3D{-x, -y, -z}; }

    // Compound Assignment Operators
    constexpr Point3D& operator+=(const Point3D& other) noexcept {
        x += other.x;
        y += other.y;
        z += other.z;
        return *this;
    }

    constexpr Point3D& operator-=(const Point3D& other) noexcept {
        x -= other.x;
        y -= other.y;
        z -= other.z;
        return *this;
    }

    constexpr Point3D& operator*=(T scalar) noexcept {
        x *= scalar;
        y *= scalar;
        z *= scalar;
        return *this;
    }

    constexpr Point3D& operator/=(T scalar) {
        if (scalar == T{0}) {
            throw std::domain_error("Division by zero in Point3D operation");
        }
        x /= scalar;
        y /= scalar;
        z /= scalar;
        return *this;
    }

    // Binary Vector Arithmetic
    [[nodiscard]] friend constexpr Point3D operator+(Point3D lhs, const Point3D& rhs) noexcept {
        lhs += rhs;
        return lhs;
    }

    [[nodiscard]] friend constexpr Point3D operator-(Point3D lhs, const Point3D& rhs) noexcept {
        lhs -= rhs;
        return lhs;
    }

    [[nodiscard]] friend constexpr Point3D operator*(Point3D pt, T scalar) noexcept {
        pt *= scalar;
        return pt;
    }

    [[nodiscard]] friend constexpr Point3D operator*(T scalar, Point3D pt) noexcept {
        pt *= scalar;
        return pt;
    }

    [[nodiscard]] friend constexpr Point3D operator/(Point3D pt, T scalar) {
        pt /= scalar;
        return pt;
    }

    // Comparison Operators (C++20 Defaulted Spaceship Operator)
    [[nodiscard]] auto operator<=>(const Point3D&) const = default;

    // Geometric Functions
    [[nodiscard]] constexpr T dot(const Point3D& other) const noexcept {
        return x * other.x + y * other.y + z * other.z;
    }

    [[nodiscard]] constexpr Point3D cross(const Point3D& other) const noexcept {
        return Point3D{
            y * other.z - z * other.y,
            z * other.x - x * other.z,
            x * other.y - y * other.x
        };
    }

    [[nodiscard]] constexpr T length_squared() const noexcept {
        return this->dot(*this);
    }

    [[nodiscard]] auto length() const noexcept {
        return std::sqrt(length_squared());
    }

    [[nodiscard]] auto distance(const Point3D& other) const noexcept {
        return (*this - other).length();
    }

    [[nodiscard]] Point3D normalize() const {
        auto len = length();
        if (len == 0) {
            throw std::domain_error("Cannot normalize a zero-length Point3D");
        }
        return *this / static_cast<T>(len);
    }

    // Compile-time structured binding position getters
    template<std::size_t I>
    constexpr const T& get() const noexcept {
        static_assert(I < 3, "Point3D structured binding index out of bounds");
        if constexpr (I == 0) return x;
        else if constexpr (I == 1) return y;
        else return z;
    }

    template<std::size_t I>
    constexpr T& get() noexcept {
        static_assert(I < 3, "Point3D structured binding index out of bounds");
        if constexpr (I == 0) return x;
        else if constexpr (I == 1) return y;
        else return z;
    }
};

// ============================================================================
// CONTINUOUS EXTERIOR CALCULUS LAYER (DIFFERENTIAL FORMS)
// ============================================================================

// Explicit representation of a 2-form (Bivector) in 3D Euclidean space
template<GeometricType T>
class Bivector3D {
public:
    T yz{}; // Coefficient for dy ∧ dz
    T zx{}; // Coefficient for dz ∧ dx
    T xy{}; // Coefficient for dx ∧ dy

    constexpr Bivector3D() noexcept = default;
    constexpr Bivector3D(T yz_val, T zx_val, T xy_val) noexcept
        : yz(yz_val), zx(zx_val), xy(xy_val) {}

    [[nodiscard]] auto operator<=>(const Bivector3D&) const = default;

    constexpr Bivector3D& operator*=(T scalar) noexcept {
        yz *= scalar; zx *= scalar; xy *= scalar;
        return *this;
    }
};

// Explicit representation of a 3-form (Trivector / Volume Form) in 3D Euclidean space
template<GeometricType T>
class Trivector3D {
public:
    T xyz{}; // Coefficient for dx ∧ dy ∧ dz

    constexpr Trivector3D() noexcept = default;
    constexpr Trivector3D(T xyz_val) noexcept : xyz(xyz_val) {}

    [[nodiscard]] auto operator<=>(const Trivector3D&) const = default;
};

// Wedge Product Overloads (∧ Shorthand via operator^)
template<GeometricType T>
[[nodiscard]] constexpr Bivector3D<T> operator^(const Point3D<T>& lhs, const Point3D<T>& rhs) noexcept {
    return Bivector3D<T>{
        lhs.y * rhs.z - lhs.z * rhs.y,
        lhs.z * rhs.x - lhs.x * rhs.z,
        lhs.x * rhs.y - lhs.y * rhs.x
    };
}

template<GeometricType T>
[[nodiscard]] constexpr Trivector3D<T> operator^(const Point3D<T>& lhs, const Bivector3D<T>& rhs) noexcept {
    return Trivector3D<T>{ lhs.x * rhs.yz + lhs.y * rhs.zx + lhs.z * rhs.xy };
}

template<GeometricType T>
[[nodiscard]] constexpr Trivector3D<T> operator^(const Bivector3D<T>& lhs, const Point3D<T>& rhs) noexcept {
    return Trivector3D<T>{ lhs.yz * rhs.x + lhs.zx * rhs.y + lhs.xy * rhs.z };
}

// Hodge Star Operations (Dualization Framework)
template<GeometricType T>
[[nodiscard]] constexpr Trivector3D<T> hodge_star(T scalar) noexcept { return Trivector3D<T>{scalar}; }

template<GeometricType T>
[[nodiscard]] constexpr Bivector3D<T> hodge_star(const Point3D<T>& dynamic_form) noexcept {
    return Bivector3D<T>{dynamic_form.x, dynamic_form.y, dynamic_form.z};
}

template<GeometricType T>
[[nodiscard]] constexpr Point3D<T> hodge_star(const Bivector3D<T>& surface_form) noexcept {
    return Point3D<T>{surface_form.yz, surface_form.zx, surface_form.xy};
}

template<GeometricType T>
[[nodiscard]] constexpr T hodge_star(const Trivector3D<T>& volume_form) noexcept { return volume_form.xyz; }

template<GeometricType T>
[[nodiscard]] constexpr Bivector3D<T> operator~(const Point3D<T>& p) noexcept { return hodge_star(p); }
template<GeometricType T>
[[nodiscard]] constexpr Point3D<T> operator~(const Bivector3D<T>& b) noexcept { return hodge_star(b); }
template<GeometricType T>
[[nodiscard]] constexpr T operator~(const Trivector3D<T>& t) noexcept { return hodge_star(t); }

// ============================================================================
// DISCRETE EXTERIOR CALCULUS LAYER (DEC / COCHAIN CALCULUS)
// ============================================================================

template<GeometricType T>
struct DiscreteMesh3D {
    struct Vertex { Point3D<T> pos; };
    struct Edge { std::size_t v0; std::size_t v1; T primal_length; T dual_length; };
    struct Face {
        std::size_t e0; std::size_t e1; std::size_t e2;
        int sign0; int sign1; int sign2;
        std::array<std::size_t, 3> v;
    };

    std::vector<Vertex> vertices;
    std::vector<Edge> edges;
    std::vector<Face> faces;
};

// Discrete k-forms modeled as structural linear vector cochains
template<GeometricType T>
struct Discrete0Form { std::vector<T> values; };

template<GeometricType T>
struct Discrete1Form { std::vector<T> values; };

template<GeometricType T>
struct Discrete2Form { std::vector<T> values; };

// Discrete Exterior Derivative d0 (Maps 0-forms to 1-forms along edges)
template<GeometricType T>
[[nodiscard]] constexpr Discrete1Form<T> discrete_d(const DiscreteMesh3D<T>& mesh, const Discrete0Form<T>& f0) {
    Discrete1Form<T> f1;
    f1.values.resize(mesh.edges.size());
    for (std::size_t i = 0; i < mesh.edges.size(); ++i) {
        const auto& edge = mesh.edges[i];
        f1.values[i] = f0.values[edge.v1] - f0.values[edge.v0];
    }
    return f1;
}

// Discrete Exterior Derivative d1 (Maps 1-forms to 2-forms over faces)
template<GeometricType T>
[[nodiscard]] constexpr Discrete2Form<T> discrete_d(const DiscreteMesh3D<T>& mesh, const Discrete1Form<T>& f1) {
    Discrete2Form<T> f2;
    f2.values.resize(mesh.faces.size());
    for (std::size_t i = 0; i < mesh.faces.size(); ++i) {
        const auto& face = mesh.faces[i];
        f2.values[i] = face.sign0 * f1.values[face.e0] +
                       face.sign1 * f1.values[face.e1] +
                       face.sign2 * f1.values[face.e2];
    }
    return f2;
}

// Discrete Diagonal Hodge Star for 1-forms (*1: Primal 1-form -> Dual 2-form)
template<GeometricType T>
[[nodiscard]] constexpr Discrete1Form<T> discrete_hodge_star_1(const DiscreteMesh3D<T>& mesh, const Discrete1Form<T>& f1) {
    Discrete1Form<T> dual_f1;
    dual_f1.values.resize(mesh.edges.size());
    for (std::size_t i = 0; i < mesh.edges.size(); ++i) {
        dual_f1.values[i] = (mesh.edges[i].dual_length / mesh.edges[i].primal_length) * f1.values[i];
    }
    return dual_f1;
}

// Discrete Inner Coderivative delta (δ = - * d * on primal 1-forms in 3D Euclidean manifolds)
template<GeometricType T>
[[nodiscard]] constexpr Discrete0Form<T> discrete_coderivative(const DiscreteMesh3D<T>& mesh, const Discrete1Form<T>& f1, const std::vector<T>& vertex_dual_volumes) {
    Discrete0Form<T> delta_f1;
    delta_f1.values.assign(mesh.vertices.size(), T{0});

    Discrete1Form<T> dual_f1 = discrete_hodge_star_1(mesh, f1);

    for (std::size_t i = 0; i < mesh.edges.size(); ++i) {
        const auto& edge = mesh.edges[i];
        T flux = dual_f1.values[i];
        delta_f1.values[edge.v0] -= flux;
        delta_f1.values[edge.v1] += flux;
    }

    for (std::size_t i = 0; i < mesh.vertices.size(); ++i) {
        if (vertex_dual_volumes[i] > T{0}) {
            delta_f1.values[i] = -delta_f1.values[i] / vertex_dual_volumes[i];
        }
    }
    return delta_f1;
}

// Discrete Laplace-Beltrami Operator (Δ = δd)
template<GeometricType T>
[[nodiscard]] constexpr Discrete0Form<T> discrete_laplace_beltrami(const DiscreteMesh3D<T>& mesh, const Discrete0Form<T>& f0, const std::vector<T>& vertex_dual_volumes) {
    Discrete1Form<T> df = discrete_d(mesh, f0);
    return discrete_coderivative(mesh, df, vertex_dual_volumes);
}

// ============================================================================
// CLEAN & DECOUPLED GEOMETRIC MESH PROCESSING LAYER (SMOOTHING Engine)
// ============================================================================

// Standalone function to calculate cotangent weights for all unique mesh edges.
// This function avoids expensive math library evaluations by computing cotangents directly via dot/cross vector calculations.
template<GeometricType T>
[[nodiscard]] std::vector<T> compute_cotangent_weights(const DiscreteMesh3D<T>& mesh, const std::vector<Point3D<T>>& positions) {
    std::vector<T> weights(mesh.edges.size(), T{0});

    for (const auto& face : mesh.faces) {
        // Evaluate the internal corner angles for each of the three face vertices
        for (std::size_t i = 0; i < 3; ++i) {
            std::size_t v_curr = face.v[i];
            std::size_t v_next = face.v[(i + 1) % 3];
            std::size_t v_opp  = face.v[(i + 2) % 3];

            // Formulate vectors spanning from the opposite corner vertex
            Point3D<T> d1 = positions[v_curr] - positions[v_opp];
            Point3D<T> d2 = positions[v_next] - positions[v_opp];

            T dot_val = d1.dot(d2);
            T cross_len = d1.cross(d2).length();

            T cot_alpha = T{0};
            if (cross_len > T{1e-10}) {
                cot_alpha = dot_val / cross_len;
            }

            // Resolve which undirected edge matching description tracks the current vertex pairs
            std::size_t match_edge = face.e0;
            if ((mesh.edges[face.e1].v0 == v_curr && mesh.edges[face.e1].v1 == v_next) ||
                (mesh.edges[face.e1].v0 == v_next && mesh.edges[face.e1].v1 == v_curr)) {
                match_edge = face.e1;
            } else if ((mesh.edges[face.e2].v0 == v_curr && mesh.edges[face.e2].v1 == v_next) ||
                       (mesh.edges[face.e2].v0 == v_next && mesh.edges[face.e2].v1 == v_curr)) {
                match_edge = face.e2;
            }

            // Accumulate half-cotangent contribution (0.5 * cot(alpha)) into the undirected edge weight slot
            weights[match_edge] += T{0.5} * cot_alpha;
        }
    }
    return weights;
}

// Clean and flexible explicit mesh smoothing algorithm interface.
// It accepts any arbitrary edge weight set, decoupling execution from monolithic operators or matrices.
template<GeometricType T>
void apply_mesh_smoothing(std::vector<Point3D<T>>& positions, const DiscreteMesh3D<T>& mesh, const std::vector<T>& edge_weights, T lambda) {
    std::vector<Point3D<T>> total_displacement(positions.size(), Point3D<T>{0, 0, 0});
    std::vector<T> total_weight(positions.size(), T{0});

    // Accumulate geometric spatial adjustments by iterating flat across undirected edge links
    for (std::size_t e = 0; e < mesh.edges.size(); ++e) {
        std::size_t v0 = mesh.edges[e].v0;
        std::size_t v1 = mesh.edges[e].v1;
        T w = edge_weights[e];

        // Ensure safety by eliminating negative weights from obtuse boundary geometric folds
        if (w < T{0}) w = T{0};

        total_displacement[v0] += w * (positions[v1] - positions[v0]);
        total_weight[v0] += w;

        total_displacement[v1] += w * (positions[v0] - positions[v1]);
        total_weight[v1] += w;
    }

    // Apply the spatial translation update steps safely using local normalized scaling parameters
    for (std::size_t i = 0; i < positions.size(); ++i) {
        if (total_weight[i] > T{1e-10}) {
            positions[i] += lambda * (total_displacement[i] / total_weight[i]);
        }
    }
}

// ============================================================================
// INDEXED TRIANGLE MESH PARSER / BUILDER
// ============================================================================

template<GeometricType T>
[[nodiscard]] DiscreteMesh3D<T> parse_indexed_triangle_mesh(
    const std::vector<Point3D<T>>& positions,
    const std::vector<std::array<std::size_t, 3>>& triangles)
{
    DiscreteMesh3D<T> mesh;

    mesh.vertices.reserve(positions.size());
    for (const auto& pos : positions) {
        mesh.vertices.push_back({pos});
    }

    auto get_or_register_edge = [&](std::size_t v0, std::size_t v1, int& side_sign) -> std::size_t {
        bool oriented_reverse = false;
        if (v0 > v1) {
            std::swap(v0, v1);
            oriented_reverse = true;
        }

        for (std::size_t i = 0; i < mesh.edges.size(); ++i) {
            if (mesh.edges[i].v0 == v0 && mesh.edges[i].v1 == v1) {
                side_sign = oriented_reverse ? -1 : 1;
                return i;
            }
        }

        T primal_len = (positions[v1] - positions[v0]).length();
        T dual_len = T{0.5} * primal_len;

        mesh.edges.push_back({v0, v1, primal_len, dual_len});
        side_sign = oriented_reverse ? -1 : 1;
        return mesh.edges.size() - 1;
    };

    mesh.faces.reserve(triangles.size());
    for (const auto& tri : triangles) {
        int s0, s1, s2;
        std::size_t e0 = get_or_register_edge(tri[0], tri[1], s0);
        std::size_t e1 = get_or_register_edge(tri[1], tri[2], s1);
        std::size_t e2 = get_or_register_edge(tri[2], tri[0], s2);

        mesh.faces.push_back({e0, e1, e2, s0, s1, s2, tri});
    }

    return mesh;
}

// ============================================================================
// SYSTEM FORMATTERS & PACKAGING
// ============================================================================

template<GeometricType T>
struct std::formatter<Point3D<T>> : std::formatter<string_view> {
    auto format(const Point3D<T>& pt, format_context& ctx) const {
        return std::format_to(ctx.out(), "Point3D({:.4f}, {:.4f}, {:.4f})", pt.x, pt.y, pt.z);
    }
};

namespace std {
    template<GeometricType T>
    struct tuple_size<Point3D<T>> : std::integral_constant<std::size_t, 3> {};

    template<std::size_t I, GeometricType T>
    struct tuple_element<I, Point3D<T>> {
        static_assert(I < 3, "Point3D structured binding index out of bounds");
        using type = T;
    };
}

template<std::size_t I, GeometricType T>
constexpr decltype(auto) get(Point3D<T>& pt) noexcept { return pt.template get<I>(); }
template<std::size_t I, GeometricType T>
constexpr decltype(auto) get(const Point3D<T>& pt) noexcept { return pt.template get<I>(); }

// ============================================================================
// DRIVER TESTBED
// ============================================================================

int main() {
    std::cout << "=== Clean & Decoupled Cotangent Mesh Smoothing Pipeline ===\n\n";

    // 1. Initialize an indexed face mesh with a sharp feature point (apex at z=2.0)
    std::vector<Point3D<double>> positions = {
        { 0.0,  0.0,  2.0}, // Sharp Apex Vertex (0)
        {-1.0, -1.0,  0.0}, // Base Corner (1)
        { 1.0, -1.0,  0.0}, // Base Corner (2)
        { 1.0,  1.0,  0.0}, // Base Corner (3)
        {-1.0,  1.0,  0.0}  // Base Corner (4)
    };

    std::vector<std::array<std::size_t, 3>> triangles = {
        {0, 1, 2}, {0, 2, 3}, {0, 3, 4}, {0, 4, 1}
    };

    // Parse connectivity topology mapping layout
    DiscreteMesh3D<double> mesh = parse_indexed_triangle_mesh(positions, triangles);

    std::cout << "Initial Sharp Apex Position: " << std::format("{}\n", positions[0]);

    // 2. Compute Cotangent Weights independently using the decoupled engine
    std::vector<double> cot_weights = compute_cotangent_weights(mesh, positions);
    std::cout << "Decoupled Cotangent Weights derived successfully across edges.\n";

    // 3. Execute the explicit geometric smoothing pass using the decoupled weight data matrix
    double lambda = 0.5; // Update step damping factor ratio
    apply_mesh_smoothing(positions, mesh, cot_weights, lambda);

    std::cout << "Smoothed Apex Position (After 1 Iteration): " << std::format("{}\n", positions[0]);

    return 0;
}
