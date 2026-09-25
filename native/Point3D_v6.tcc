#include <concepts>
#include <compare>
#include <cmath>
#include <iostream>
#include <format>
#include <utility>
#include <stdexcept>
#include <vector>
#include <array>
#include <limits>
#include <algorithm>
#include <string>

// ============================================================================
// CORE CONCEPTS & CORE LAYER
// ============================================================================

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

    constexpr Point3D() noexcept = default;
    constexpr Point3D(T x_val, T y_val, T z_val) noexcept
        : x(x_val), y(y_val), z(z_val) {}

    [[nodiscard]] constexpr T& operator[](std::size_t index) {
        switch (index) {
            case 0: return x;
            case 1: return y;
            case 2: return z;
            default: throw std::out_of_range("Point3D index out of range");
        }
    }

    [[nodiscard]] constexpr const T& operator[](std::size_t index) const {
        switch (index) {
            case 0: return x;
            case 1: return y;
            case 2: return z;
            default: throw std::out_of_range("Point3D index out of range");
        }
    }

    constexpr Point3D operator+() const noexcept { return *this; }
    constexpr Point3D operator-() const noexcept { return Point3D{-x, -y, -z}; }

    constexpr Point3D& operator+=(const Point3D& other) noexcept {
        x += other.x; y += other.y; z += other.z;
        return *this;
    }

    constexpr Point3D& operator-=(const Point3D& other) noexcept {
        x -= other.x; y -= other.y; z -= other.z;
        return *this;
    }

    constexpr Point3D& operator*=(T scalar) noexcept {
        x *= scalar; y *= scalar; z *= scalar;
        return *this;
    }

    constexpr Point3D& operator/=(T scalar) {
        if (scalar == T{0}) throw std::domain_error("Division by zero");
        x /= scalar; y /= scalar; z /= scalar;
        return *this;
    }

    [[nodiscard]] friend constexpr Point3D operator+(Point3D lhs, const Point3D& rhs) noexcept {
        lhs += rhs; return lhs;
    }

    [[nodiscard]] friend constexpr Point3D operator-(Point3D lhs, const Point3D& rhs) noexcept {
        lhs -= rhs; return lhs;
    }

    [[nodiscard]] friend constexpr Point3D operator*(Point3D pt, T scalar) noexcept {
        pt *= scalar; return pt;
    }

    [[nodiscard]] friend constexpr Point3D operator*(T scalar, Point3D pt) noexcept {
        pt *= scalar; return pt;
    }

    [[nodiscard]] friend constexpr Point3D operator/(Point3D pt, T scalar) {
        pt /= scalar; return pt;
    }

    [[nodiscard]] auto operator<=>(const Point3D&) const = default;

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

    [[nodiscard]] constexpr T length_squared() const noexcept { return this->dot(*this); }
    [[nodiscard]] auto length() const noexcept { return std::sqrt(length_squared()); }
    [[nodiscard]] auto distance(const Point3D& other) const noexcept { return (*this - other).length(); }

    [[nodiscard]] Point3D normalize() const {
        auto len = length();
        if (len == 0) throw std::domain_error("Cannot normalize zero vector");
        return *this / static_cast<T>(len);
    }

    template<std::size_t I> constexpr const T& get() const noexcept {
        static_assert(I < 3);
        if constexpr (I == 0) return x; else if constexpr (I == 1) return y; else return z;
    }

    template<std::size_t I> constexpr T& get() noexcept {
        static_assert(I < 3);
        if constexpr (I == 0) return x; else if constexpr (I == 1) return y; else return z;
    }
};

// ============================================================================
// SPATIAL PARTITIONING LAYER (BOUNDING VOLUME HIERARCHY TREE)
// ============================================================================

template<GeometricType T>
struct AABB3D {
    Point3D<T> min_pt{std::numeric_limits<T>::max(), std::numeric_limits<T>::max(), std::numeric_limits<T>::max()};
    Point3D<T> max_pt{std::numeric_limits<T>::lowest(), std::numeric_limits<T>::lowest(), std::numeric_limits<T>::lowest()};

    constexpr void grow(const Point3D<T>& p) noexcept {
        min_pt.x = std::min(min_pt.x, p.x);
        min_pt.y = std::min(min_pt.y, p.y);
        min_pt.z = std::min(min_pt.z, p.z);

        max_pt.x = std::max(max_pt.x, p.x);
        max_pt.y = std::max(max_pt.y, p.y);
        max_pt.z = std::max(max_pt.z, p.z);
    }

    static constexpr void grow(const Point3D<T>& p, const Point3D<T>& q) noexcept {
        min_pt.x = std::min(p.x, q.x);

    }
};

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

template<GeometricType T>
struct BVHNode {
    AABB3D<T> bbox;
    std::size_t left{0};
    std::size_t right{0};
    std::vector<std::size_t> face_indices;
    bool is_leaf() const noexcept { return face_indices.size() > 0; }
};

template<GeometricType T>
std::size_t build_bvh_recursive(
    const DiscreteMesh3D<T>& mesh,
    const std::vector<Point3D<T>>& positions,
    std::vector<std::size_t>& face_indices,
    std::size_t start,
    std::size_t end,
    std::vector<BVHNode<T>>& nodes)
{
    std::size_t node_idx = nodes.size();
    nodes.emplace_back();

    AABB3D<T> box;
    for (std::size_t i = start; i < end; ++i) {
        const auto& face = mesh.faces[face_indices[i]];
        box.grow(positions[face.v[0]]);
        box.grow(positions[face.v[1]]);
        box.grow(positions[face.v[2]]);
    }
    nodes[node_idx].bbox = box;

    std::size_t count = end - start;
    if (count <= 2) {
        for (std::size_t i = start; i < end; ++i) {
            nodes[node_idx].face_indices.push_back(face_indices[i]);
        }
        return node_idx;
    }

    T dx = box.max_pt.x - box.min_pt.x;
    T dy = box.max_pt.y - box.min_pt.y;
    T dz = box.max_pt.z - box.min_pt.z;

    int axis = 0;
    if (dy > dx && dy > dz) axis = 1;
    else if (dz > dx && dz > dy) axis = 2;

    std::sort(face_indices.begin() + start, face_indices.begin() + end, [&](std::size_t a, std::size_t b) {
        const auto& fA = mesh.faces[a];
        const auto& fB = mesh.faces[b];
        T cenA = (positions[fA.v[0]][axis] + positions[fA.v[1]][axis] + positions[fA.v[2]][axis]) / T{3};
        T cenB = (positions[fB.v[0]][axis] + positions[fB.v[1]][axis] + positions[fB.v[2]][axis]) / T{3};
        return cenA < cenB;
    });

    std::size_t mid = start + count / 2;
    std::size_t left_child = build_bvh_recursive(mesh, positions, face_indices, start, mid, nodes);
    std::size_t right_child = build_bvh_recursive(mesh, positions, face_indices, mid, end, nodes);

    nodes[node_idx].left = left_child;
    nodes[node_idx].right = right_child;
    return node_idx;
}

// ============================================================================
// REVERSE ENGINEERING & PRIMITIVE FITTING LAYER
// ============================================================================

template<GeometricType T>
struct Plane3D {
    Point3D<T> normal;
    T d{};
};

template<GeometricType T>
struct SymmetricMatrix3x3 {
    T m00{}, m01{}, m02{};
    T        m11{}, m12{};
    T                m22{};

    constexpr Point3D<T> multiply(const Point3D<T>& v) const noexcept {
        return Point3D<T>{
            m00 * v.x + m01 * v.y + m02 * v.z,
            m01 * v.x + m11 * v.y + m12 * v.z,
            m02 * v.x + m12 * v.y + m22 * v.z
        };
    }
};

template<GeometricType T>
[[nodiscard]] Plane3D<T> fit_plane_primitive(
    const std::vector<Point3D<T>>& positions,
    const std::vector<std::size_t>& patch_vertex_indices)
{
    if (patch_vertex_indices.size() < 3) {
        throw std::invalid_argument("At least 3 valid vertices are required.");
    }

    Point3D<T> centroid{0, 0, 0};
    for (auto idx : patch_vertex_indices) {
        centroid += positions[idx];
    }
    centroid /= static_cast<T>(patch_vertex_indices.size());

    SymmetricMatrix3x3<T> cov{};
    for (auto idx : patch_vertex_indices) {
        Point3D<T> diff = positions[idx] - centroid;
        cov.m00 += diff.x * diff.x; cov.m01 += diff.x * diff.y; cov.m02 += diff.x * diff.z;
        cov.m11 += diff.y * diff.y; cov.m12 += diff.y * diff.z;
        cov.m22 += diff.z * diff.z;
    }

    Point3D<T> v2{1, 1, 1};
    for (int iter = 0; iter < 12; ++iter) {
        Point3D<T> next_v = cov.multiply(v2);
        if (next_v.length_squared() > T{1e-12}) v2 = next_v.normalize();
    }
    T lambda2 = v2.dot(cov.multiply(v2));

    auto multiply_deflated = [&](const Point3D<T>& vec) noexcept {
        Point3D<T> Cvec = cov.multiply(vec);
        Point3D<T> projection = v2 * (v2.dot(vec));
        return Cvec - lambda2 * projection;
    };

    Point3D<T> v1 = (std::abs(v2.x) > T{0.6}) ? Point3D<T>{-v2.y, v2.x, T{0}} : Point3D<T>{T{0}, -v2.z, v2.y};
    v1 = v1.normalize();
    for (int iter = 0; iter < 12; ++iter) {
        Point3D<T> next_v = multiply_deflated(v1);
        if (next_v.length_squared() > T{1e-12}) v1 = next_v.normalize();
    }

    Point3D<T> fitted_normal = v2.cross(v1).normalize();
    T plane_offset = -fitted_normal.dot(centroid);

    return Plane3D<T>{fitted_normal, plane_offset};
}

// ============================================================================
// DATUM ALIGNMENT MATRIX LAYER
// ============================================================================

template<GeometricType T>
class Matrix4x4 {
public:
    T m[4][4]{};

    constexpr Matrix4x4() noexcept {
        m[0][0] = T{1}; m[1][1] = T{1}; m[2][2] = T{1}; m[3][3] = T{1};
    }

    constexpr Matrix4x4(T m00, T m01, T m02, T m03,
                        T m10, T m11, T m12, T m13,
                        T m20, T m21, T m22, T m23,
                        T m30, T m31, T m32, T m33) noexcept {
        m[0][0] = m00; m[0][1] = m01; m[0][2] = m02; m[0][3] = m03;
        m[1][0] = m10; m[1][1] = m11; m[1][2] = m12; m[1][3] = m13;
        m[2][0] = m20; m[2][1] = m21; m[2][2] = m22; m[2][3] = m23;
        m[3][0] = m30; m[3][1] = m31; m[3][2] = m32; m[3][3] = m33;
    }

    [[nodiscard]] static constexpr Matrix4x4 build_datum_alignment(
        const Point3D<T>& primary_normal,
        const Point3D<T>& secondary_direction,
        const Point3D<T>& origin) noexcept
    {
        Point3D<T> w = primary_normal.normalize();
        Point3D<T> u = (secondary_direction - w * secondary_direction.dot(w)).normalize();
        Point3D<T> v = w.cross(u).normalize();

        return Matrix4x4{
            u.x, u.y, u.z, -u.dot(origin),
            v.x, v.y, v.z, -v.dot(origin),
            w.x, w.y, w.z, -w.dot(origin),
            T{0}, T{0}, T{0}, T{1}
        };
    }
};

template<GeometricType T>
[[nodiscard]] constexpr Point3D<T> operator*(const Matrix4x4<T>& mat, const Point3D<T>& pt) noexcept {
    T tx = mat.m[0][0] * pt.x + mat.m[0][1] * pt.y + mat.m[0][2] * pt.z + mat.m[0][3];
    T ty = mat.m[1][0] * pt.x + mat.m[1][1] * pt.y + mat.m[1][2] * pt.z + mat.m[1][3];
    T tz = mat.m[2][0] * pt.x + mat.m[2][1] * pt.y + mat.m[2][2] * pt.z + mat.m[2][3];
    T tw = mat.m[3][0] * pt.x + mat.m[3][1] * pt.y + mat.m[3][2] * pt.z + mat.m[3][3];

    if (tw != T{1} && tw != T{0}) return Point3D<T>{tx / tw, ty / tw, tz / tw};
    return Point3D<T>{tx, ty, tz};
}

// ============================================================================
// GEOMETRIC DIMENSIONING & TOLERANCING (GD&T) MODIFIER LAYER
// ============================================================================

enum class MaterialModifier {
    RFS, // Regardless of Feature Size (Default behavior)
    MMC, // Maximum Material Condition (Ⓜ Modifier)
    LMC  // Least Material Condition (Ⓛ Modifier)
};

template<GeometricType T>
struct FeatureSizeSpec {
    T actual_size{};
    T mmc_size{};
    T lmc_size{};
    bool is_internal{true}; // true = internal hole, false = external shaft
};

template<GeometricType T>
struct GDTReport {
    std::string symbol;
    std::string modifier_symbol;
    T measured_deviation;
    T base_tolerance;
    T bonus_tolerance;
    T total_tolerance;
    bool passed;
};

template<GeometricType T>
class GDTInspector {
public:
    [[nodiscard]] static constexpr T
    calculate_bonus(MaterialModifier modifier, const FeatureSizeSpec<T>& size) noexcept {
        if (modifier == MaterialModifier::RFS) return T{0};

        T bonus = T{0};
        if (modifier == MaterialModifier::MMC) {
            if (size.is_internal) {
                bonus = size.actual_size - size.mmc_size; // Internal hole gets bonus as size increases
            } else {
                bonus = size.mmc_size - size.actual_size; // External shaft gets bonus as size decreases
            }
        } else if (modifier == MaterialModifier::LMC) {
            if (size.is_internal) {
                bonus = size.lmc_size - size.actual_size; // Internal hole gets bonus as size decreases
            } else {
                bonus = size.actual_size - size.lmc_size; // External shaft gets bonus as size increases
            }
        }
        return (bonus > T{0}) ? bonus : T{0};
    }

    [[nodiscard]] static constexpr std::string get_modifier_string(MaterialModifier modifier) noexcept {
        switch (modifier) {
            case MaterialModifier::MMC: return "[M]";
            case MaterialModifier::LMC: return "[L]";
            case MaterialModifier::RFS: default: return "";
        }
    }

    [[nodiscard]] static constexpr GDTReport<T> evaluate_parallelism(
        const Point3D<T>& feature_normal,
        const Point3D<T>& datum_normal,
        T base_tolerance,
        MaterialModifier modifier = MaterialModifier::RFS,
        FeatureSizeSpec<T> size_spec = {}) noexcept
    {
        Point3D<T> n_f = feature_normal.normalize();
        Point3D<T> n_d = datum_normal.normalize();

        T deviation = n_f.cross(n_d).length();
        T bonus = calculate_bonus(modifier, size_spec);
        T total_tolerance = base_tolerance + bonus;

        return GDTReport<T>{
            "Parallelism (||)",
            get_modifier_string(modifier),
            deviation,
            base_tolerance,
            bonus,
            total_tolerance,
            deviation <= total_tolerance
        };
    }

    [[nodiscard]] static constexpr GDTReport<T> evaluate_perpendicularity(
        const Point3D<T>& feature_normal,
        const Point3D<T>& datum_normal,
        T base_tolerance,
        MaterialModifier modifier = MaterialModifier::RFS,
        FeatureSizeSpec<T> size_spec = {}) noexcept
    {
        Point3D<T> n_f = feature_normal.normalize();
        Point3D<T> n_d = datum_normal.normalize();

        T deviation = std::abs(n_f.dot(n_d));
        T bonus = calculate_bonus(modifier, size_spec);
        T total_tolerance = base_tolerance + bonus;

        return GDTReport<T>{
            "Perpendicularity (|_|)",
            get_modifier_string(modifier),
            deviation,
            base_tolerance,
            bonus,
            total_tolerance,
            deviation <= total_tolerance
        };
    }
};

// ============================================================================
// PARSER AND FORMATTING LAYER
// ============================================================================

template<GeometricType T>
[[nodiscard]] DiscreteMesh3D<T> parse_indexed_triangle_mesh(
    const std::vector<Point3D<T>>& positions,
    const std::vector<std::array<std::size_t, 3>>& triangles)
{
    DiscreteMesh3D<T> mesh;
    mesh.vertices.reserve(positions.size());
    for (const auto& pos : positions) mesh.vertices.push_back({pos});

    auto get_or_register_edge = [&](std::size_t v0, std::size_t v1, int& side_sign) -> std::size_t {
        bool oriented_reverse = false;
        if (v0 > v1) { std::swap(v0, v1); oriented_reverse = true; }
        for (std::size_t i = 0; i < mesh.edges.size(); ++i) {
            if (mesh.edges[i].v0 == v0 && mesh.edges[i].v1 == v1) {
                side_sign = oriented_reverse ? -1 : 1; return i;
            }
        }
        T primal_len = (positions[v1] - positions[v0]).length();
        mesh.edges.push_back({v0, v1, primal_len, T{0.5} * primal_len});
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

template<GeometricType T>
struct std::formatter<Point3D<T>> : std::formatter<string_view> {
    auto format(const Point3D<T>& pt, format_context& ctx) const {
        return std::format_to(ctx.out(), "Point3D({:.4f}, {:.4f}, {:.4f})", pt.x, pt.y, pt.z);
    }
};

// ============================================================================
// MAIN METROLOGY PIPELINE TESTBED
// ============================================================================

int main() {
    std::cout << "=== Metrology Quality Pipeline & GD&T Modifiers ===\n\n";

    // 1. Simulating an incoming noisy AI-generated mechanical block geometry
    std::vector<Point3D<double>> positions = {
        { 0.001, -0.002,  1.002}, // Noisy Face Vertex (0)
        {-1.000, -1.000,  0.000}, // Base Floor (1)
        { 1.000, -1.000,  0.000}, // Base Floor (2)
        { 1.000,  1.000,  0.000}, // Base Floor (3)
        {-1.000,  1.000,  0.000}, // Base Floor (4)
        { 1.002,  0.001,  0.501}  // Side Feature Flange (5)
    };

    std::vector<std::array<std::size_t, 3>> triangles = {
        {0, 1, 2}, {0, 2, 3}, {0, 3, 4}, {0, 4, 1}, {2, 3, 5}
    };

    DiscreteMesh3D<double> mesh = parse_indexed_triangle_mesh(positions, triangles);

    // 2. Structural Partitioning Phase (BVH Tree Construction)
    std::vector<std::size_t> face_indices(mesh.faces.size());
    for (std::size_t i = 0; i < mesh.faces.size(); ++i) face_indices[i] = i;

    std::vector<BVHNode<double>> bvh_nodes;
    build_bvh_recursive(mesh, positions, face_indices, 0, mesh.faces.size(), bvh_nodes);

    // 3. Extracting Reference Datum Features via Local Analytical Fitting
    std::vector<std::size_t> primary_patch = {1, 2, 3, 4};
    Plane3D<double> datum_A_plane = fit_plane_primitive(positions, primary_patch);

    // 4. Automated GD&T Inspection Matrix with Material Modifiers
    std::cout << "=== Executing GD&T Metrology Inspection Matrix with Modifiers ===\n";

    Point3D<double> test_face_normal{0.005, 0.002, 0.999};
    double base_tolerance = 0.01; // 10 micron base specification limits

    // Define an internal hole size spec where departure from MMC yields a bonus tolerance
    // MMC hole size = 10.00, Actual measured produced size = 10.02 (larger hole)
    FeatureSizeSpec<double> hole_spec{
        .actual_size = 10.02,
        .mmc_size = 10.00,
        .lmc_size = 10.05,
        .is_internal = true
    };

    // Parallelism check under Maximum Material Condition (MMC)
    GDTReport<double> parallelism_report = GDTInspector<double>::evaluate_parallelism(
        test_face_normal, datum_A_plane.normal, base_tolerance, MaterialModifier::MMC, hole_spec
    );

    std::cout << std::format("  - Control: {} {}\n", parallelism_report.symbol, parallelism_report.modifier_symbol);
    std::cout << std::format("    Measured Deviation: {:.6f}\n", parallelism_report.measured_deviation);
    std::cout << std::format("    Base Tolerance:     {:.6f}\n", parallelism_report.base_tolerance);
    std::cout << std::format("    Bonus Tolerance:    {:.6f}\n", parallelism_report.bonus_tolerance);
    std::cout << std::format("    Total Allowed Limit: {:.6f}\n", parallelism_report.total_tolerance);
    std::cout << std::format("    Status:             {}\n", parallelism_report.passed ? "PASSED" : "FAILED");

    return 0;
}
