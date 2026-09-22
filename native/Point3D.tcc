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
        : x(x_val), y(y_val), z(z_val) {
    }

    // Element Access via index
    [[nodiscard]] constexpr T &operator[](std::size_t index) {
        switch (index) {
            case 0: return x;
            case 1: return y;
            case 2: return z;
            default: throw std::out_of_range("Point3D index out of range (must be 0, 1, or 2)");
        }
    }

    [[nodiscard]] constexpr const T &operator[](std::size_t index) const {
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
    constexpr Point3D &operator+=(const Point3D &other) noexcept {
        x += other.x;
        y += other.y;
        z += other.z;
        return *this;
    }

    constexpr Point3D &operator-=(const Point3D &other) noexcept {
        x -= other.x;
        y -= other.y;
        z -= other.z;
        return *this;
    }

    constexpr Point3D &operator*=(T scalar) noexcept {
        x *= scalar;
        y *= scalar;
        z *= scalar;
        return *this;
    }

    constexpr Point3D &operator/=(T scalar) {
        if (scalar == T{0}) {
            throw std::domain_error("Division by zero in Point3D operation");
        }
        x /= scalar;
        y /= scalar;
        z /= scalar;
        return *this;
    }

    // Binary Vector Arithmetic
    [[nodiscard]] friend constexpr Point3D operator+(Point3D lhs, const Point3D &rhs) noexcept {
        lhs += rhs;
        return lhs;
    }

    [[nodiscard]] friend constexpr Point3D operator-(Point3D lhs, const Point3D &rhs) noexcept {
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
    [[nodiscard]] auto operator<=>(const Point3D &) const = default;

    // Geometric Functions
    [[nodiscard]] constexpr T dot(const Point3D &other) const noexcept {
        return x * other.x + y * other.y + z * other.z;
    }

    [[nodiscard]] constexpr Point3D cross(const Point3D &other) const noexcept {
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

    [[nodiscard]] auto distance(const Point3D &other) const noexcept {
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
    constexpr const T &get() const noexcept {
        static_assert(I < 3, "Point3D structured binding index out of bounds");
        if constexpr (I == 0) return x;
        else if constexpr (I == 1) return y;
        else return z;
    }

    template<std::size_t I>
    constexpr T &get() noexcept {
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
        : yz(yz_val), zx(zx_val), xy(xy_val) {
    }

    [[nodiscard]] auto operator<=>(const Bivector3D &) const = default;

    constexpr Bivector3D &operator*=(T scalar) noexcept {
        yz *= scalar;
        zx *= scalar;
        xy *= scalar;
        return *this;
    }
};

// Explicit representation of a 3-form (Trivector / Volume Form) in 3D Euclidean space
template<GeometricType T>
class Trivector3D {
public:
    T xyz{}; // Coefficient for dx ∧ dy ∧ dz

    constexpr Trivector3D() noexcept = default;

    constexpr Trivector3D(T xyz_val) noexcept : xyz(xyz_val) {
    }

    [[nodiscard]] auto operator<=>(const Trivector3D &) const = default;
};

// Wedge Product Overloads (∧ Shorthand via operator^)
template<GeometricType T>
[[nodiscard]] constexpr Bivector3D<T> operator^(const Point3D<T> &lhs, const Point3D<T> &rhs) noexcept {
    return Bivector3D<T>{
        lhs.y * rhs.z - lhs.z * rhs.y,
        lhs.z * rhs.x - lhs.x * rhs.z,
        lhs.x * rhs.y - lhs.y * rhs.x
    };
}

template<GeometricType T>
[[nodiscard]] constexpr Trivector3D<T> operator^(const Point3D<T> &lhs, const Bivector3D<T> &rhs) noexcept {
    return Trivector3D<T>{lhs.x * rhs.yz + lhs.y * rhs.zx + lhs.z * rhs.xy};
}

template<GeometricType T>
[[nodiscard]] constexpr Trivector3D<T> operator^(const Bivector3D<T> &lhs, const Point3D<T> &rhs) noexcept {
    return Trivector3D<T>{lhs.yz * rhs.x + lhs.zx * rhs.y + lhs.xy * rhs.z};
}

// Hodge Star Operations (Dualization Framework)
template<GeometricType T>
[[nodiscard]] constexpr Trivector3D<T> hodge_star(T scalar) noexcept { return Trivector3D<T>{scalar}; }

template<GeometricType T>
[[nodiscard]] constexpr Bivector3D<T> hodge_star(const Point3D<T> &dynamic_form) noexcept {
    return Bivector3D<T>{dynamic_form.x, dynamic_form.y, dynamic_form.z};
}

template<GeometricType T>
[[nodiscard]] constexpr Point3D<T> hodge_star(const Bivector3D<T> &surface_form) noexcept {
    return Point3D<T>{surface_form.yz, surface_form.zx, surface_form.xy};
}

template<GeometricType T>
[[nodiscard]] constexpr T hodge_star(const Trivector3D<T> &volume_form) noexcept { return volume_form.xyz; }

template<GeometricType T>
[[nodiscard]] constexpr Bivector3D<T> operator~(const Point3D<T> &p) noexcept { return hodge_star(p); }

template<GeometricType T>
[[nodiscard]] constexpr Point3D<T> operator~(const Bivector3D<T> &b) noexcept { return hodge_star(b); }

template<GeometricType T>
[[nodiscard]] constexpr T operator~(const Trivector3D<T> &t) noexcept { return hodge_star(t); }

// ============================================================================
// DISCRETE EXTERIOR CALCULUS LAYER (DEC / COCHAIN CALCULUS)
// ============================================================================

template<GeometricType T>
struct DiscreteMesh3D {
    struct Vertex {
        Point3D<T> pos;
    };

    struct Edge {
        std::size_t v0;
        std::size_t v1;
        T primal_length;
        T dual_length;
    };

    struct Face {
        std::size_t e0;
        std::size_t e1;
        std::size_t e2;
        int sign0;
        int sign1;
        int sign2;
    };

    std::vector<Vertex> vertices;
    std::vector<Edge> edges;
    std::vector<Face> faces;
};

// Discrete k-forms modeled as structural linear vector cochains
template<GeometricType T>
struct Discrete0Form {
    std::vector<T> values;
};

template<GeometricType T>
struct Discrete1Form {
    std::vector<T> values;
};

template<GeometricType T>
struct Discrete2Form {
    std::vector<T> values;
};

// Discrete Exterior Derivative d0 (Maps 0-forms to 1-forms along edges)
template<GeometricType T>
[[nodiscard]] constexpr Discrete1Form<T> discrete_d(const DiscreteMesh3D<T> &mesh, const Discrete0Form<T> &f0) {
    Discrete1Form<T> f1;
    f1.values.resize(mesh.edges.size());
    for (std::size_t i = 0; i < mesh.edges.size(); ++i) {
        const auto &edge = mesh.edges[i];
        f1.values[i] = f0.values[edge.v1] - f0.values[edge.v0];
    }
    return f1;
}

// Discrete Exterior Derivative d1 (Maps 1-forms to 2-forms over faces)
template<GeometricType T>
[[nodiscard]] constexpr Discrete2Form<T> discrete_d(const DiscreteMesh3D<T> &mesh, const Discrete1Form<T> &f1) {
    Discrete2Form<T> f2;
    f2.values.resize(mesh.faces.size());
    for (std::size_t i = 0; i < mesh.faces.size(); ++i) {
        const auto &face = mesh.faces[i];
        f2.values[i] = face.sign0 * f1.values[face.e0] +
                       face.sign1 * f1.values[face.e1] +
                       face.sign2 * f1.values[face.e2];
    }
    return f2;
}

// Discrete Diagonal Hodge Star for 1-forms (*1: Primal 1-form -> Dual 2-form)
template<GeometricType T>
[[nodiscard]] constexpr Discrete1Form<T> discrete_hodge_star_1(const DiscreteMesh3D<T> &mesh,
                                                               const Discrete1Form<T> &f1) {
    Discrete1Form<T> dual_f1;
    dual_f1.values.resize(mesh.edges.size());
    for (std::size_t i = 0; i < mesh.edges.size(); ++i) {
        dual_f1.values[i] = (mesh.edges[i].dual_length / mesh.edges[i].primal_length) * f1.values[i];
    }
    return dual_f1;
}

// Discrete Inner Coderivative delta (δ = - * d * on primal 1-forms in 3D Euclidean manifolds)
// Maps a 1-form to a 0-form (acting as a discrete divergence operator)
template<GeometricType T>
[[nodiscard]] constexpr Discrete0Form<T> discrete_coderivative(const DiscreteMesh3D<T> &mesh,
                                                               const Discrete1Form<T> &f1,
                                                               const std::vector<T> &vertex_dual_volumes) {
    Discrete0Form<T> delta_f1;
    delta_f1.values.assign(mesh.vertices.size(), T{0});

    // 1. Transform primal 1-form into its dual representation via Hodge Star
    Discrete1Form<T> dual_f1 = discrete_hodge_star_1(mesh, f1);

    // 2. Apply adjoint boundary derivative operator via topological accumulation
    for (std::size_t i = 0; i < mesh.edges.size(); ++i) {
        const auto &edge = mesh.edges[i];
        T flux = dual_f1.values[i];
        delta_f1.values[edge.v0] -= flux;
        delta_f1.values[edge.v1] += flux;
    }

    // 3. Complete boundary equation scaling by applying the vertex-wise 0-form Hodge Star inverse
    for (std::size_t i = 0; i < mesh.vertices.size(); ++i) {
        if (vertex_dual_volumes[i] > T{0}) {
            delta_f1.values[i] = -delta_f1.values[i] / vertex_dual_volumes[i];
        }
    }
    return delta_f1;
}

// Discrete Laplace-Beltrami Operator (Δ = δd)
// Maps a Discrete 0-Form directly to a Discrete 0-Form
template<GeometricType T>
[[nodiscard]] constexpr Discrete0Form<T> discrete_laplace_beltrami(const DiscreteMesh3D<T> &mesh,
                                                                   const Discrete0Form<T> &f0,
                                                                   const std::vector<T> &vertex_dual_volumes) {
    // Δf = δ(df)
    Discrete1Form<T> df = discrete_d(mesh, f0);
    return discrete_coderivative(mesh, df, vertex_dual_volumes);
}

// ============================================================================
// INDEXED TRIANGLE MESH PARSER / BUILDER
// ============================================================================

template<GeometricType T>
[[nodiscard]] DiscreteMesh3D<T> parse_indexed_triangle_mesh(
    const std::vector<Point3D<T> > &positions,
    const std::vector<std::array<std::size_t, 3> > &triangles) {
    DiscreteMesh3D<T> mesh;

    // 1. Parse Positions into Primal Vertices
    mesh.vertices.reserve(positions.size());
    for (const auto &pos: positions) {
        mesh.vertices.push_back({pos});
    }

    // Helper map/search abstraction to generate unique undirected tracking edges
    auto get_or_register_edge = [&](std::size_t v0, std::size_t v1, int &side_sign) -> std::size_t {
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

        // Compute edge metrics
        T primal_len = (positions[v1] - positions[v0]).length();
        // Fallback robust dual computation metric (Voronoi/Primal scaling balance)
        T dual_len = T{0.5} * primal_len;

        mesh.edges.push_back({v0, v1, primal_len, dual_len});
        side_sign = oriented_reverse ? -1 : 1;
        return mesh.edges.size() - 1;
    };

    // 2. Build Mesh Faces and Topological Sign Signatures
    mesh.faces.reserve(triangles.size());
    for (const auto &tri: triangles) {
        int s0, s1, s2;
        std::size_t e0 = get_or_register_edge(tri[0], tri[1], s0);
        std::size_t e1 = get_or_register_edge(tri[1], tri[2], s1);
        std::size_t e2 = get_or_register_edge(tri[2], tri[0], s2);

        mesh.faces.push_back({e0, e1, e2, s0, s1, s2});
    }

    return mesh;
}

// ============================================================================
// TRANSFORMATION LAYER
// ============================================================================

template<GeometricType T>
class Matrix4x4 {
public:
    T m[4][4]{};

    constexpr Matrix4x4() noexcept {
        m[0][0] = T{1};
        m[1][1] = T{1};
        m[2][2] = T{1};
        m[3][3] = T{1};
    }

    constexpr Matrix4x4(T m00, T m01, T m02, T m03,
                        T m10, T m11, T m12, T m13,
                        T m20, T m21, T m22, T m23,
                        T m30, T m31, T m32, T m33) noexcept {
        m[0][0] = m00;
        m[0][1] = m01;
        m[0][2] = m02;
        m[0][3] = m03;
        m[1][0] = m10;
        m[1][1] = m11;
        m[1][2] = m12;
        m[1][3] = m13;
        m[2][0] = m20;
        m[2][1] = m21;
        m[2][2] = m22;
        m[2][3] = m23;
        m[3][0] = m30;
        m[3][1] = m31;
        m[3][2] = m32;
        m[3][3] = m33;
    }

    [[nodiscard]] friend constexpr Matrix4x4 operator*(const Matrix4x4 &lhs, const Matrix4x4 &rhs) noexcept {
        Matrix4x4 result;
        for (std::size_t r = 0; r < 4; ++r) {
            for (std::size_t c = 0; c < 4; ++c) {
                result.m[r][c] = lhs.m[r][0] * rhs.m[0][c] +
                                 lhs.m[r][1] * rhs.m[1][c] +
                                 lhs.m[r][2] * rhs.m[2][c] +
                                 lhs.m[r][3] * rhs.m[3][c];
            }
        }
        return result;
    }

    [[nodiscard]] static constexpr Matrix4x4 translation(T x, T y, T z) noexcept {
        return Matrix4x4{
            T{1}, T{0}, T{0}, x,
            T{0}, T{1}, T{0}, y,
            T{0}, T{0}, T{1}, z,
            T{0}, T{0}, T{0}, T{1}
        };
    }

    [[nodiscard]] static constexpr Matrix4x4 scaling(T x, T y, T z) noexcept {
        return Matrix4x4{
            x, T{0}, T{0}, T{0},
            T{0}, y, T{0}, T{0},
            T{0}, T{0}, z, T{0},
            T{0}, T{0}, T{0}, T{1}
        };
    }
};

template<GeometricType T>
[[nodiscard]] constexpr Point3D<T> operator*(const Matrix4x4<T> &mat, const Point3D<T> &pt) noexcept {
    T tx = mat.m[0][0] * pt.x + mat.m[0][1] * pt.y + mat.m[0][2] * pt.z + mat.m[0][3];
    T ty = mat.m[1][0] * pt.x + mat.m[1][1] * pt.y + mat.m[1][2] * pt.z + mat.m[1][3];
    T tz = mat.m[2][0] * pt.x + mat.m[2][1] * pt.y + mat.m[2][2] * pt.z + mat.m[2][3];
    T tw = mat.m[3][0] * pt.x + mat.m[3][1] * pt.y + mat.m[3][2] * pt.z + mat.m[3][3];

    if (tw != T{1} && tw != T{0}) {
        return Point3D<T>{tx / tw, ty / tw, tz / tw};
    }
    return Point3D<T>{tx, ty, tz};
}

// ============================================================================
// SYSTEM FORMATTERS & PACKAGING
// ============================================================================

template<GeometricType T>
struct std::formatter<Point3D<T> > : std::formatter<string_view> {
    auto format(const Point3D<T> &pt, format_context &ctx) const {
        return std::format_to(ctx.out(), "Point3D({:.4f}, {:.4f}, {:.4f})", pt.x, pt.y, pt.z);
    }
};

namespace std {
    template<GeometricType T>
    struct tuple_size<Point3D<T> > : std::integral_constant<std::size_t, 3> {
    };

    template<std::size_t I, GeometricType T>
    struct tuple_element<I, Point3D<T> > {
        static_assert(I < 3, "Point3D structured binding index out of bounds");
        using type = T;
    };
}

template<std::size_t I, GeometricType T>
constexpr decltype(auto) get(Point3D<T> &pt) noexcept { return pt.template get<I>(); }

template<std::size_t I, GeometricType T>
constexpr decltype(auto) get(const Point3D<T> &pt) noexcept { return pt.template get<I>(); }


// ============================================================================
// DRIVER TESTBED
// ============================================================================

int main() {
    // 1. Exterior Calculus Operations Verification
    std::cout << "=== Continuous Exterior Calculus Verification ===\n";
    constexpr Point3D<double> u{1.0, 0.0, 0.0};
    constexpr Point3D<double> v{0.0, 2.0, 0.0};
    constexpr Bivector3D<double> wedge_2form = u ^ v;
    std::cout << std::format("u ∧ v (Bivector 2-form): {}\n\n", wedge_2form);

    // 2. Discrete Exterior Calculus (DEC) Operations Verification
    std::cout << "=== Discrete Exterior Calculus Validation ===\n";

    // Construct a minimal topology: 2 vertices connected by 1 edge
    DiscreteMesh3D<double> mesh;
    mesh.vertices = {{{0.0, 0.0, 0.0}}, {{2.0, 0.0, 0.0}}};
    mesh.edges = {{0, 1, 2.0, 0.5}}; // v0 to v1, primal len = 2.0, dual len = 0.5

    // Set 0-form field data values at the vertices
    Discrete0Form<double> f0;
    f0.values = {10.0, 25.0}; // f(v0) = 10, f(v1) = 25

    // Compute discrete derivative: d0 (Calculates differences across edges)
    Discrete1Form<double> df = discrete_d(mesh, f0);
    std::cout << std::format("Discrete d0 output value on Edge 0: {:.1f} (Expected: 15.0)\n", df.values[0]);

    // Compute inner coderivative: delta (Calculates discrete divergence)
    std::vector<double> dual_vertex_volumes = {1.0, 1.0};
    Discrete0Form<double> div_df = discrete_coderivative(mesh, df, dual_vertex_volumes);
    std::cout << std::format("Discrete Coderivative δ on Vertex 0: {:.4f}\n", div_df.values[0]);
    std::cout << std::format("Discrete Coderivative δ on Vertex 1: {:.4f}\n", div_df.values[1]);


    std::cout << "=== Parser & Discrete Laplace-Beltrami Integration Test ===\n\n";

    // 1. Simulating an Indexed Face Mesh input sequence
    // A symmetrical 3D pyramid (5 vertices, 4 triangular faces)
    const std::vector<Point3D<double> > vertex_positions = {
        {0.0, 0.0, 1.5}, // Top Vertex (0)
        {-1.0, -1.0, 0.0}, // Base Corner (1)
        {1.0, -1.0, 0.0}, // Base Corner (2)
        {1.0, 1.0, 0.0}, // Base Corner (3)
        {-1.0, 1.0, 0.0} // Base Corner (4)
    };

    const std::vector<std::array<std::size_t, 3> > triangle_indices = {
        {0, 1, 2}, // Face 0
        {0, 2, 3}, // Face 1
        {0, 3, 4}, // Face 2
        {0, 4, 1} // Face 3
    };

    // Execute the parser transformation pipeline
    std::cout << "Parsing Indexed Triangle Mesh...\n";
    DiscreteMesh3D<double> mesh2 = parse_indexed_triangle_mesh(vertex_positions, triangle_indices);
    std::cout << std::format("Successfully generated Topology: {} Vertices, {} Edges, {} Faces.\n\n",
                             mesh2.vertices.size(), mesh2.edges.size(), mesh2.faces.size());

    // 2. Construct a test scalar field mapping data to the 0-form
    // Example: A parabolic heat signature concentrated on the apex point
    Discrete0Form<double> heat_field;
    heat_field.values = {100.0, 20.0, 20.0, 20.0, 20.0};

    std::cout << "Initial 0-Form Data Matrix (Heat Profile):\n";
    for (std::size_t i = 0; i < mesh2.vertices.size(); ++i) {
        std::cout << std::format("  Vertex {}: Value = {:.1f}\n", i, heat_field.values[i]);
    }
    std::cout << "\n";

    // Define diagonal hodge metric capacities for dual vertices (lumped surface mass)
    std::vector<double> vertex_dual_volumes = {1.2, 1.0, 1.0, 1.0, 1.0};

    // 3. Compute the Discrete Laplace-Beltrami Operation
    std::cout << "Evaluating Discrete Laplace-Beltrami (Δ = δd)...\n";
    Discrete0Form<double> laplacian_output = discrete_laplace_beltrami(mesh, heat_field, vertex_dual_volumes);

    std::cout << "Resulting Laplace-Beltrami Divergence Signatures:\n";
    for (std::size_t i = 0; i < laplacian_output.values.size(); ++i) {
        std::cout << std::format("  Δf(Vertex {}): Spatial Curvature = {:.4f}\n", i, laplacian_output.values[i]);
    }

    return 0;


    return 0;
}
