//
// Created by Nathan White on 9/20/26.
//

#include "SimpComp3.hpp"

#include <iostream>
#include <vector>
#include <array>
#include <algorithm>
#include <concepts>
#include <expected>
#include <string>
#include <span>
#include <cstdint>
#include <numeric>
#include <cmath>
#include <limits>
#include <thread>
#include <future>

// Unifying topological and geometric error tracing states
enum class TopologyStatus : uint8_t {
    Success,
    DuplicateVertices,
    BudgetExceeded,
    InvalidDimension,
    IndexOutOfBounds,
    DuplicateTriangles,
    DegenerateTriangle,
    NonPlanarFace,
    NonConvexFace,
    DisconnectedLoop,
    UnsupportedUnit
};

inline std::string to_string(TopologyStatus status) {
    switch (status) {
        case TopologyStatus::Success:            return "Success";
        case TopologyStatus::DuplicateVertices:  return "Topology error: Duplicate vertices found within a facet.";
        case TopologyStatus::BudgetExceeded:     return "Resource constraint: Complex size crossed allocation limits.";
        case TopologyStatus::InvalidDimension:   return "Boundary operator error: Requested dimension out of bounds.";
        case TopologyStatus::IndexOutOfBounds:   return "Geometry error: Entity index references non-existent layout point.";
        case TopologyStatus::DuplicateTriangles: return "Geometry error: Duplicate triangles detected within topology maps.";
        case TopologyStatus::DegenerateTriangle: return "Geometry error: Face structure contains zero area or collapsed lines.";
        case TopologyStatus::NonPlanarFace:      return "Geometric error: Polygon vertices violate face planarity constraints.";
        case TopologyStatus::NonConvexFace:      return "Geometric error: Polygon contains nonconvex or self-intersecting bounds.";
        case TopologyStatus::DisconnectedLoop:    return "Structural error: Face coedges fail to form a continuous closed circuit.";
        case TopologyStatus::UnsupportedUnit:    return "Configuration error: Unsupported length unit specified.";
    }
    return "Unknown state.";
}

// Physical measurement scale tracking properties
enum class LengthUnit : uint8_t {
    Millimeter,
    Centimeter,
    Meter,
    Inch
};

inline std::string to_string(LengthUnit unit) {
    switch (unit) {
        case LengthUnit::Millimeter: return "mm";
        case LengthUnit::Centimeter: return "cm";
        case LengthUnit::Meter:      return "m";
        case LengthUnit::Inch:       return "in";
    }
    return "unknown";
}

// Inlined Vector math operations mapping contiguous float structures natively
inline std::array<float, 3> vec_sub(const std::array<float, 3>& a, const std::array<float, 3>& b) noexcept {
    return { a[0] - b[0], a[1] - b[1], a[2] - b[2] };
}

inline float vec_dot(const std::array<float, 3>& a, const std::array<float, 3>& b) noexcept {
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
}

inline std::array<float, 3> vec_cross(const std::array<float, 3>& a, const std::array<float, 3>& b) noexcept {
    return {
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0]
    };
}

inline float vec_norm(const std::array<float, 3>& a) noexcept {
    return std::sqrt(vec_dot(a, a));
}

// Geometric structure tracking an exact ray parameter layout
struct Ray {
    std::array<float, 3> origin;
    std::array<float, 3> direction; // Assumed to be normalized for exact t parameter tracking
    std::array<float, 3> inv_direction; // Precomputed for rapid AABB intersection tests

    static Ray create(std::array<float, 3> orig, std::array<float, 3> dir) noexcept {
        float len = vec_norm(dir);
        if (len > 0.0f) {
            dir = { dir[0] / len, dir[1] / len, dir[2] / len };
        }
        return Ray{
            .origin = orig,
            .direction = dir,
            .inv_direction = {
                dir[0] == 0.0f ? std::numeric_limits<float>::infinity() : 1.0f / dir[0],
                dir[1] == 0.0f ? std::numeric_limits<float>::infinity() : 1.0f / dir[1],
                dir[2] == 0.0f ? std::numeric_limits<float>::infinity() : 1.0f / dir[2]
            }
        };
    }
};

// Hit specification recording detailed geometric ray parameters
struct IntersectionResult {
    bool hit = false;
    float t = std::numeric_limits<float>::infinity();
    float u = 0.0f;
    float v = 0.0f;
    size_t triangle_index = std::numeric_limits<size_t>::max();
};

// Axis-Aligned Bounding Box (AABB) supporting fast spatial partitioning calculations
struct AABB {
    std::array<float, 3> min_pt = { std::numeric_limits<float>::infinity(), std::numeric_limits<float>::infinity(), std::numeric_limits<float>::infinity() };
    std::array<float, 3> max_pt = { -std::numeric_limits<float>::infinity(), -std::numeric_limits<float>::infinity(), -std::numeric_limits<float>::infinity() };

    void grow(const std::array<float, 3>& pt) noexcept {
        min_pt[0] = std::min(min_pt[0], pt[0]);
        min_pt[1] = std::min(min_pt[1], pt[1]);
        min_pt[2] = std::min(min_pt[2], pt[2]);
        max_pt[0] = std::max(max_pt[0], pt[0]);
        max_pt[1] = std::max(max_pt[1], pt[1]);
        max_pt[2] = std::max(max_pt[2], pt[2]);
    }

    void grow(const AABB& other) noexcept {
        min_pt[0] = std::min(min_pt[0], other.min_pt[0]);
        min_pt[1] = std::min(min_pt[1], other.min_pt[1]);
        min_pt[2] = std::min(min_pt[2], other.min_pt[2]);
        max_pt[0] = std::max(max_pt[0], other.max_pt[0]);
        max_pt[1] = std::max(max_pt[1], other.max_pt[1]);
        max_pt[2] = std::max(max_pt[2], other.max_pt[2]);
    }

    bool intersects(const AABB& other) const noexcept {
        return (min_pt[0] <= other.max_pt[0] && max_pt[0] >= other.min_pt[0]) &&
               (min_pt[1] <= other.max_pt[1] && max_pt[1] >= other.min_pt[1]) &&
               (min_pt[2] <= other.max_pt[2] && max_pt[2] >= other.min_pt[2]);
    }

    // High-speed slab intersection check for inline ray tracing traversal optimization
    bool intersects_ray(const Ray& ray, float& t_min_out) const noexcept {
        float t1 = (min_pt[0] - ray.origin[0]) * ray.inv_direction[0];
        float t2 = (max_pt[0] - ray.origin[0]) * ray.inv_direction[0];
        float t_min = std::min(t1, t2);
        float t_max = std::max(t1, t2);

        for (int i = 1; i < 3; ++i) {
            t1 = (min_pt[i] - ray.origin[i]) * ray.inv_direction[i];
            t2 = (max_pt[i] - ray.origin[i]) * ray.inv_direction[i];
            t_min = std::max(t_min, std::min(t1, t2));
            t_max = std::min(t_max, std::max(t1, t2));
        }

        t_min_out = t_min;
        return t_max >= std::max(0.0f, t_min);
    }
};

// High-speed allocation-free Möller-Trumbore ray-triangle intersection implementation
inline IntersectionResult ray_triangle_intersect(const Ray& ray, const std::array<float, 3>& v0, const std::array<float, 3>& v1, const std::array<float, 3>& v2, size_t tri_idx) noexcept {
    IntersectionResult result;
    constexpr float kEpsilon = 1e-7f;

    std::array<float, 3> edge1 = vec_sub(v1, v0);
    std::array<float, 3> edge2 = vec_sub(v2, v0);
    std::array<float, 3> h = vec_cross(ray.direction, edge2);
    float a = vec_dot(edge1, h);

    if (a > -kEpsilon && a < kEpsilon) return result; // Ray is parallel to this triangle plane

    float f = 1.0f / a;
    std::array<float, 3> s = vec_sub(ray.origin, v0);
    result.u = f * vec_dot(s, h);

    if (result.u < 0.0f || result.u > 1.0f) return result;

    std::array<float, 3> q = vec_cross(s, edge1);
    result.v = f * vec_dot(ray.direction, q);

    if (result.v < 0.0f || result.u + result.v > 1.0f) return result;

    float t = f * vec_dot(edge2, q);
    if (t > kEpsilon) { // Valid non-backfacing or non-occluded ray segment intersection
        result.hit = true;
        result.t = t;
        result.triangle_index = tri_idx;
    }

    return result;
}

// Flat tokenization components representing standalone geometric simplex structures
struct Simplex {
    std::vector<int> vertices;

    size_t dim() const noexcept {
        return vertices.empty() ? 0 : vertices.size() - 1;
    }

    auto operator<=>(const Simplex&) const = default;
};

// Custom Compressed Sparse Row representation tracking matrix properties
struct OksSparseCSR {
    std::vector<size_t> row_ptr;
    std::vector<size_t> col_ind;
    std::vector<int8_t> values;
    size_t num_rows = 0;
    size_t num_cols = 0;

    void print() const noexcept {
        std::cout << "Optimized CSR Matrix [" << num_rows << " x " << num_cols << "] (" << values.size() << " NNZ):\n";
        std::cout << "  row_ptr: "; for (auto p : row_ptr) std::cout << p << " ";
        std::cout << "\n  col_ind: "; for (auto c : col_ind) std::cout << c << " ";
        std::cout << "\n  values:  "; for (auto v : values) std::cout << static_cast<int>(v) << " ";
        std::cout << "\n\n";
    }
};

class SimplicialComplex;

// Intermediary optimized TriangleMesh layer linking BRep outputs to Topology engines
struct TriangleMesh {
    std::vector<std::array<float, 3>> vertices;
    std::vector<std::array<int, 3>> triangles;
    LengthUnit length_unit = LengthUnit::Millimeter;

    std::expected<SimplicialComplex, TopologyStatus> to_simplicial_complex(size_t max_simplices = 50000) const noexcept;
};

// Layout node optimized for a stackless flat BVH layout representation
struct FlatBVHNode {
    AABB bounds;
    uint32_t primitive_offset = 0;
    uint32_t primitive_count = 0;
    uint32_t second_child_offset = 0;
};

// Allocation-Optimized Flat Bounding Volume Hierarchy Container with parallel partitioning
class FlatBVH {
public:
    std::vector<FlatBVHNode> nodes;
    std::vector<size_t> primitive_indices;

    static FlatBVH build(const TriangleMesh& mesh) noexcept {
        FlatBVH bvh;
        if (mesh.triangles.empty()) return bvh;

        size_t num_tris = mesh.triangles.size();
        bvh.primitive_indices.resize(num_tris);
        std::iota(bvh.primitive_indices.begin(), bvh.primitive_indices.end(), 0);

        bvh.nodes.reserve(2 * num_tris - 1);
        bvh.build_recursive(mesh, 0, num_tris);
        return bvh;
    }

    // High-speed stackless spatial window search query
    void query_box(const AABB& query_bounds, std::vector<size_t>& out_triangles) const noexcept {
        if (nodes.empty()) return;

        size_t idx = 0;
        while (idx < nodes.size()) {
            const auto& node = nodes[idx];
            if (node.bounds.intersects(query_bounds)) {
                if (node.primitive_count > 0) {
                    for (uint32_t i = 0; i < node.primitive_count; ++i) {
                        out_triangles.push_back(primitive_indices[node.primitive_offset + i]);
                    }
                    idx++;
                } else {
                    idx++;
                }
            } else {
                if (node.primitive_count > 0) {
                    idx++;
                } else {
                    idx = node.second_child_offset;
                }
            }
        }
    }

    // Single-ray optimization path using a stackless flat tree traversal loop
    IntersectionResult intersect_ray(const TriangleMesh& mesh, const Ray& ray) const noexcept {
        IntersectionResult closest_hit;
        if (nodes.empty()) return closest_hit;

        size_t idx = 0;
        float t_dummy = 0.0f;

        while (idx < nodes.size()) {
            const auto& node = nodes[idx];

            // Optimization: Skip traversal if ray completely misses AABB bounds or if an active hit is closer
            if (node.bounds.intersects_ray(ray, t_dummy) && t_dummy < closest_hit.t) {
                if (node.primitive_count > 0) {
                    for (uint32_t i = 0; i < node.primitive_count; ++i) {
                        size_t tri_idx = primitive_indices[node.primitive_offset + i];
                        const auto& tri = mesh.triangles[tri_idx];

                        auto hit = ray_triangle_intersect(ray, mesh.vertices[tri[0]], mesh.vertices[tri[1]], mesh.vertices[tri[2]], tri_idx);
                        if (hit.hit && hit.t < closest_hit.t) {
                            closest_hit = hit;
                        }
                    }
                    idx++;
                } else {
                    idx++; // Step clean into the left child node
                }
            } else {
                if (node.primitive_count > 0) {
                    idx++;
                } else {
                    idx = node.second_child_offset; // Jump across left branch bypass shortcut
                }
            }
        }
        return closest_hit;
    }

    // Multi-threaded task partitioning query driving parallel processing loops across bounds
    std::vector<IntersectionResult> parallel_intersect_rays(const TriangleMesh& mesh, const std::vector<Ray>& rays) const noexcept {
        std::vector<IntersectionResult> global_results(rays.size());
        if (rays.empty()) return global_results;

        unsigned int hardware_threads = std::thread::hardware_concurrency();
        size_t num_workers = std::max(1u, std::min(hardware_threads, static_cast<unsigned int>(rays.size() / 16))); // Prevent over-partitioning trivial sizes

        std::vector<std::future<void>> futures;
        size_t chunk_size = rays.size() / num_workers;

        for (size_t w = 0; w < num_workers; ++w) {
            size_t start_idx = w * chunk_size;
            size_t end_idx = (w == num_workers - 1) ? rays.size() : start_idx + chunk_size;

            futures.push_back(std::async(std::launch::async, [this, &mesh, &rays, &global_results, start_idx, end_idx]() {
                for (size_t i = start_idx; i < end_idx; ++i) {
                    global_results[i] = this->intersect_ray(mesh, rays[i]);
                }
            }));
        }

        for (auto& f : futures) {
            f.wait();
        }

        return global_results;
    }

private:
    size_t build_recursive(const TriangleMesh& mesh, size_t start, size_t end) noexcept {
        size_t node_idx = nodes.size();
        nodes.emplace_back();

        AABB node_bounds;
        AABB centroid_bounds;
        for (size_t i = start; i < end; ++i) {
            size_t tri_idx = primitive_indices[i];
            const auto& tri = mesh.triangles[tri_idx];

            AABB tri_box;
            tri_box.grow(mesh.vertices[tri[0]]);
            tri_box.grow(mesh.vertices[tri[1]]);
            tri_box.grow(mesh.vertices[tri[2]]);
            node_bounds.grow(tri_box);

            std::array<float, 3> centroid = {
                (mesh.vertices[tri[0]][0] + mesh.vertices[tri[1]][0] + mesh.vertices[tri[2]][0]) / 3.0f,
                (mesh.vertices[tri[0]][1] + mesh.vertices[tri[1]][1] + mesh.vertices[tri[2]][1]) / 3.0f,
                (mesh.vertices[tri[0]][2] + mesh.vertices[tri[1]][2] + mesh.vertices[tri[2]][2]) / 3.0f
            };
            centroid_bounds.grow(centroid);
        }

        nodes[node_idx].bounds = node_bounds;
        size_t count = end - start;

        if (count <= 1) {
            nodes[node_idx].primitive_offset = static_cast<uint32_t>(start);
            nodes[node_idx].primitive_count = static_cast<uint32_t>(count);
            return node_idx;
        }

        int axis = 0;
        float ext0 = centroid_bounds.max_pt[0] - centroid_bounds.min_pt[0];
        float ext1 = centroid_bounds.max_pt[1] - centroid_bounds.min_pt[1];
        float ext2 = centroid_bounds.max_pt[2] - centroid_bounds.min_pt[2];
        if (ext1 > ext0) axis = 1;
        if (ext2 > std::max(ext0, ext1)) axis = 2;

        float split_coord = 0.5f * (centroid_bounds.min_pt[axis] + centroid_bounds.max_pt[axis]);

        size_t mid = start;
        for (size_t i = start; i < end; ++i) {
            size_t tri_idx = primitive_indices[i];
            const auto& tri = mesh.triangles[tri_idx];
            float c = (mesh.vertices[tri[0]][axis] + mesh.vertices[tri[1]][axis] + mesh.vertices[tri[2]][axis]) / 3.0f;
            if (c < split_coord) {
                std::swap(primitive_indices[i], primitive_indices[mid]);
                mid++;
            }
        }

        if (mid == start || mid == end) {
            mid = start + count / 2;
        }

        build_recursive(mesh, start, mid);
        size_t right_child_idx = build_recursive(mesh, mid, end);
        nodes[node_idx].second_child_offset = static_cast<uint32_t>(right_child_idx);

        return node_idx;
    }
};

// High-Performance Boundary Representation Model mapping arbitrary polygonal boundaries
struct PolyhedralBRep {
    std::vector<std::array<float, 3>> vertices;
    std::vector<std::array<int, 2>> edges;
    std::vector<size_t> face_offsets;
    std::vector<int> face_coedges;
    LengthUnit length_unit = LengthUnit::Millimeter;

    size_t face_count() const noexcept {
        return face_offsets.empty() ? 0 : face_offsets.size() - 1;
    }

    std::span<const int> face_loop(size_t face_id) const noexcept {
        if (face_id >= face_count()) return {};
        return std::span<const int>(face_coedges.data() + face_offsets[face_id],
                                     face_coedges.data() + face_offsets[face_id + 1]);
    }

    static std::expected<PolyhedralBRep, TopologyStatus> from_polygons(
        std::vector<std::array<float, 3>> vertices,
        const std::vector<std::vector<int>>& polygons,
        LengthUnit unit = LengthUnit::Millimeter,
        bool share_edges = true) noexcept
    {
        std::vector<std::array<int, 2>> edges;

        struct EdgeKey {
            int u, v;
            auto operator<=>(const EdgeKey&) const = default;
        };
        std::vector<std::pair<EdgeKey, int>> lookup;

        std::vector<size_t> face_offsets = {0};
        std::vector<int> face_coedges;
        const int num_verts = static_cast<int>(vertices.size());

        for (const auto& polygon : polygons) {
            if (polygon.size() < 3) return std::unexpected(TopologyStatus::DegenerateTriangle);

            std::vector<int> uniq = polygon;
            std::sort(uniq.begin(), uniq.end());
            if (std::adjacent_find(uniq.begin(), uniq.end()) != uniq.end()) {
                return std::unexpected(TopologyStatus::DuplicateVertices);
            }
            for (int v : polygon) {
                if (v < 0 || v >= num_verts) return std::unexpected(TopologyStatus::IndexOutOfBounds);
            }

            size_t n = polygon.size();
            for (size_t i = 0; i < n; ++i) {
                int u = polygon[i];
                int v = polygon[(i + 1) % n];
                EdgeKey key{ std::min(u, v), std::max(u, v) };

                int edge_id = -1;
                auto it = std::lower_bound(lookup.begin(), lookup.end(), key, [](const auto& pair, const EdgeKey& k) {
                    return pair.first < k;
                });

                if (!share_edges || it == lookup.end() || it->first != key) {
                    edge_id = static_cast<int>(edges.size());
                    edges.push_back({ key.u, key.v });
                    if (share_edges) {
                        lookup.insert(it, { key, edge_id });
                    }
                } else {
                    edge_id = it->second;
                }

                int token = edge_id + 1;
                face_coedges.push_back(u < v ? token : -token);
            }
            face_offsets.push_back(face_coedges.size());
        }

        return PolyhedralBRep{
            .vertices = std::move(vertices),
            .edges = std::move(edges),
            .face_offsets = std::move(face_offsets),
            .face_coedges = std::move(face_coedges),
            .length_unit = unit
        };
    }

    std::expected<std::vector<int>, TopologyStatus> face_vertices(size_t face_id) const noexcept {
        auto tokens = face_loop(face_id);
        if (tokens.empty()) return std::unexpected(TopologyStatus::IndexOutOfBounds);

        std::vector<std::array<int, 2>> endpoints;
        endpoints.reserve(tokens.size());

        for (int t : tokens) {
            int edge_idx = std::abs(t) - 1;
            if (edge_idx < 0 || edge_idx >= static_cast<int>(edges.size())) {
                return std::unexpected(TopologyStatus::IndexOutOfBounds);
            }
            auto edge = edges[edge_idx];
            if (t < 0) std::swap(edge[0], edge[1]);
            endpoints.push_back(edge);
        }

        size_t n = endpoints.size();
        for (size_t i = 0; i < n; ++i) {
            if (endpoints[i][1] != endpoints[(i + 1) % n][0]) {
                return std::unexpected(TopologyStatus::DisconnectedLoop);
            }
        }

        std::vector<int> face_verts;
        face_verts.reserve(n);
        for (size_t i = 0; i < n; ++i) {
            face_verts.push_back(endpoints[i][0]);
        }

        return face_verts;
    }

    std::expected<std::vector<std::array<int, 3>>, TopologyStatus> triangulate_face(
        size_t face_id,
        float planarity_tolerance = 1e-6f) const noexcept
    {
        auto verts_res = face_vertices(face_id);
        if (!verts_res) return std::unexpected(verts_res.error());
        const auto& ids = *verts_res;

        if (ids.size() < 3) return std::unexpected(TopologyStatus::DegenerateTriangle);

        std::vector<std::array<float, 3>> xyz;
        xyz.reserve(ids.size());
        for (int id : ids) xyz.push_back(vertices[id]);

        auto r1 = vec_sub(xyz[1], xyz[0]);
        auto r2 = vec_sub(xyz[2], xyz[0]);
        auto normal = vec_cross(r1, r2);
        float n_norm = vec_norm(normal);

        if (n_norm == 0.0f) return std::unexpected(TopologyStatus::DegenerateTriangle);
        normal = { normal[0] / n_norm, normal[1] / n_norm, normal[2] / n_norm };

        for (const auto& pt : xyz) {
            auto rel = vec_sub(pt, xyz[0]);
            if (std::abs(vec_dot(rel, normal)) > planarity_tolerance) {
                return std::unexpected(TopologyStatus::NonPlanarFace);
            }
        }

        for (size_t k = 0; k < ids.size(); ++k) {
            auto edge = vec_sub(xyz[(k + 1) % ids.size()], xyz[k]);
            float edge_len = vec_norm(edge);

            for (size_t m = 0; m < ids.size(); ++m) {
                auto diff = vec_sub(xyz[m], xyz[k]);
                auto cross_side = vec_cross(edge, diff);
                float orientation = vec_dot(cross_side, normal);
                if (orientation < -planarity_tolerance * std::max(1.0f, edge_len)) {
                    return std::unexpected(TopologyStatus::NonConvexFace);
                }
            }
        }

        std::vector<std::array<int, 3>> face_tris;
        face_tris.reserve(ids.size() - 2);
        for (size_t i = 1; i < ids.size() - 1; ++i) {
            face_tris.push_back({ ids[0], ids[i], ids[i + 1] });
        }
        return face_tris;
    }

    std::expected<TriangleMesh, TopologyStatus> triangulate_convex_faces(float planarity_tolerance = 1e-6f) const noexcept {
        std::vector<std::array<int, 3>> global_triangles;
        for (size_t f = 0; f < face_count(); ++f) {
            auto tris_res = triangulate_face(f, planarity_tolerance);
            if (!tris_res) return std::unexpected(tris_res.error());
            global_triangles.insert(global_triangles.end(), tris_res->begin(), tris_res->end());
        }
        return TriangleMesh{
            .vertices = this->vertices,
            .triangles = std::move(global_triangles),
            .length_unit = this->length_unit
        };
    }
};

class SimplicialComplex {
private:
    std::vector<std::vector<Simplex>> spatial_tiers_;
    size_t max_dim_ = 0;

    static int compare_skipped_face(std::span<const int> lower, std::span<const int> upper, size_t skip_idx) noexcept {
        size_t l_idx = 0;
        for (size_t u_idx = 0; u_idx < upper.size(); ++u_idx) {
            if (u_idx == skip_idx) [[unlikely]] continue;
            if (l_idx >= lower.size()) return -1;

            if (lower[l_idx] < upper[u_idx]) return -1;
            if (lower[l_idx] > upper[u_idx]) return 1;
            l_idx++;
        }
        return (l_idx < lower.size()) ? 1 : 0;
    }

    static size_t find_face_index(std::span<const Simplex> lower_tier, const Simplex& upper, size_t skip_idx) noexcept {
        long long low = 0;
        long long high = static_cast<long long>(lower_tier.size()) - 1;

        while (low <= high) {
            long long mid = low + (high - low) / 2;
            int comparison = compare_skipped_face(lower_tier[mid].vertices, upper.vertices, skip_idx);

            if (comparison == 0) return static_cast<size_t>(mid);
            if (comparison < 0) low = mid + 1;
            else high = mid - 1;
        }
        return std::string::npos;
    }

public:
    explicit SimplicialComplex(std::vector<std::vector<Simplex>> tiers, size_t max_dim)
        : spatial_tiers_(std::move(tiers)), max_dim_(max_dim) {}

    static std::expected<SimplicialComplex, TopologyStatus> build_from_mesh_engine(
        const TriangleMesh& mesh,
        size_t simplex_budget) noexcept
    {
        const int num_verts = static_cast<int>(mesh.vertices.size());
        std::vector<std::array<int, 3>> canonical_triangles;
        canonical_triangles.reserve(mesh.triangles.size());

        for (auto t : mesh.triangles) {
            if (t[0] < 0 || t[0] >= num_verts || t[1] < 0 || t[1] >= num_verts || t[2] < 0 || t[2] >= num_verts) [[unlikely]] {
                return std::unexpected(TopologyStatus::IndexOutOfBounds);
            }
            if (t[0] == t[1] || t[1] == t[2] || t[0] == t[2]) [[unlikely]] {
                return std::unexpected(TopologyStatus::DegenerateTriangle);
            }
            std::sort(t.begin(), t.end());
            canonical_triangles.push_back(t);
        }

        std::sort(canonical_triangles.begin(), canonical_triangles.end());
        if (std::adjacent_find(canonical_triangles.begin(), canonical_triangles.end()) != canonical_triangles.end()) {
            return std::unexpected(TopologyStatus::DuplicateTriangles);
        }

        std::vector<std::vector<Simplex>> staging_tiers(3);
        staging_tiers[0].reserve(mesh.vertices.size());
        for (int i = 0; i < num_verts; ++i) {
            staging_tiers[0].push_back(Simplex{ .vertices = {i} });
        }

        for (const auto& t : canonical_triangles) {
            staging_tiers[1].push_back(Simplex{ .vertices = {t[0], t[1]} });
            staging_tiers[1].push_back(Simplex{ .vertices = {t[1], t[2]} });
            staging_tiers[1].push_back(Simplex{ .vertices = {t[0], t[2]} });
            staging_tiers[2].push_back(Simplex{ .vertices = {t[0], t[1], t[2]} });
        }

        size_t total_allocated = staging_tiers[0].size();
        for (size_t d = 1; d <= 2; ++d) {
            std::sort(staging_tiers[d].begin(), staging_tiers[d].end());
            auto unique_range = std::unique(staging_tiers[d].begin(), staging_tiers[d].end());
            staging_tiers[d].erase(unique_range, staging_tiers[d].end());
            total_allocated += staging_tiers[d].size();

            if (total_allocated > simplex_budget) [[unlikely]] {
                return std::unexpected(TopologyStatus::BudgetExceeded);
            }
        }

        return SimplicialComplex(std::move(staging_tiers), 2);
    }

    std::span<const Simplex> get_tier(size_t d) const noexcept {
        return (d < spatial_tiers_.size()) ? spatial_tiers_[d] : std::span<const Simplex>{};
    }

    std::expected<OksSparseCSR, TopologyStatus> boundary_operator(size_t d) const noexcept {
        if (d == 0 || d > max_dim_) return std::unexpected(TopologyStatus::InvalidDimension);

        auto current_cols = get_tier(d);
        auto lower_rows   = get_tier(d - 1);

        OksSparseCSR csr;
        csr.num_rows = lower_rows.size();
        csr.num_cols = current_cols.size();
        csr.row_ptr.assign(csr.num_rows + 1, 0);

        if (current_cols.empty()) return csr;

        for (size_t j = 0; j < current_cols.size(); ++j) {
            const auto& upper_simplex = current_cols[j];
            for (size_t k = 0; k < upper_simplex.vertices.size(); ++k) {
                size_t i = find_face_index(lower_rows, upper_simplex, k);
                if (i != std::string::npos) {
                    csr.row_ptr[i + 1]++;
                }
            }
        }

        for (size_t i = 0; i < csr.num_rows; ++i) {
            csr.row_ptr[i + 1] += csr.row_ptr[i];
        }

        size_t total_nnz = csr.row_ptr.back();
        csr.col_ind.resize(total_nnz);
        csr.values.resize(total_nnz);

        std::vector<size_t> write_cursors = csr.row_ptr;

        for (size_t j = 0; j < current_cols.size(); ++j) {
            const auto& upper_simplex = current_cols[j];
            for (size_t k = 0; k < upper_simplex.vertices.size(); ++k) {
                size_t i = find_face_index(lower_rows, upper_simplex, k);
                if (i != std::string::npos) {
                    size_t write_pos = write_cursors[i]++;
                    csr.col_ind[write_pos] = j;
                    csr.values[write_pos]  = (k % 2 == 0) ? 1 : -1;
                }
            }
        }

        return csr;
    }
};

std::expected<SimplicialComplex, TopologyStatus> TriangleMesh::to_simplicial_complex(size_t max_simplices) const noexcept {
    return SimplicialComplex::build_from_mesh_engine(*this, max_simplices);
}

int main() {
    // Instantiate geometry for a bounded quad patch mapping two triangles
    std::vector<std::array<float, 3>> pts = {
        {0.0f, 0.0f, 0.0f}, // 0
        {2.0f, 0.0f, 0.0f}, // 1
        {2.0f, 2.0f, 0.0f}, // 2
        {0.0f, 2.0f, 0.0f}  // 3
    };
    std::vector<std::vector<int>> polys = { {0, 1, 2, 3} };

    std::cout << "Step 1: Instantiating PolyhedralBRep...\n";
    auto brep_res = PolyhedralBRep::from_polygons(pts, polys, LengthUnit::Millimeter, true);
    if (!brep_res) return 1;

    std::cout << "Step 2: Triangulating planar face models...\n";
    auto mesh_res = brep_res->triangulate_convex_faces();
    if (!mesh_res) return 1;
    const auto& mesh = *mesh_res;

    std::cout << "Step 3: Compiling flat stackless BVH architecture...\n";
    FlatBVH bvh = FlatBVH::build(mesh);

    std::cout << "Step 4: Launching multi-threaded partitioned batch ray intersection checks...\n";
    // Construct a test suite of distinct query ray targets
    std::vector<Ray> batch_rays = {
        Ray::create({0.5f, 0.5f,  1.0f}, {0.0f, 0.0f, -1.0f}), // Positive intersection hit (Tri 0)
        Ray::create({1.5f, 1.5f,  1.0f}, {0.0f, 0.0f, -1.0f}), // Positive intersection hit (Tri 1)
        Ray::create({5.0f, 5.0f,  5.0f}, {0.0f, 0.0f, -1.0f}), // Clear boundary out-of-bounds miss
        Ray::create({1.0f, 1.0f, -1.0f}, {0.0f, 0.0f,  1.0f})  // Opposite tracking approach hit vector
    };

    auto results = bvh.parallel_intersect_rays(mesh, batch_rays);

    for (size_t i = 0; i < results.size(); ++i) {
        std::cout << "  Ray [" << i << "]: ";
        if (results[i].hit) {
            std::cout << "HIT located at distance t = " << results[i].t
                      << " on Triangle Primitive Index ID: " << results[i].triangle_index
                      << " (u: " << results[i].u << ", v: " << results[i].v << ")\n";
        } else {
            std::cout << "MISS recorded outside spatial boundaries.\n";
        }
    }

    std::cout << "\nStep 5: Compiling topological matrix state closure confirmation...\n";
    auto complex_res = mesh.to_simplicial_complex();
    if (complex_res) {
        std::cout << "  Simplicial complex mapped successfully with "
                  << complex_res->get_tier(2).size() << " 2-simplex facets.\n";
    }

    return 0;
}
