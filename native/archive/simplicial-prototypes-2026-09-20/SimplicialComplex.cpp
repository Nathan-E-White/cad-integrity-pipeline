#include <iostream>
#include <vector>
#include <algorithm>

#include <expected>
#include <string>
#include <span>
#include <cstdint>

#include <valarray>
#include <compare>
#include "SimplicialComplex.hpp"

// Unifying error tracking using modern lightweight value types
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

static std::string to_string(const TopologyStatus status) {
    switch (status) {
        case TopologyStatus::Success:
            return "Success";
        case TopologyStatus::DuplicateVertices:
            return "Topology error: Duplicate vertices found within a facet.";
        case TopologyStatus::BudgetExceeded:
            return "Resource constraint: Complex size crossed allocation limits.";
        case TopologyStatus::InvalidDimension:
            return "Boundary operator error: Requested dimension out of bounds.";
        case TopologyStatus::IndexOutOfBounds:
            return "Geometry error: Entity index references non-existent layout point.";
        case TopologyStatus::DuplicateTriangles:
            return "Geometry error: Duplicate triangles detected within topology maps.";
        case TopologyStatus::DegenerateTriangle:
            return "Geometry error: Face structure contains zero area or collapsed lines.";
        case TopologyStatus::NonPlanarFace:
            return "Geometric error: Polygon vertices violate face planarity constraints.";
        case TopologyStatus::NonConvexFace:
            return "Geometric error: Polygon contains nonconvex or self-intersecting bounds.";
        case TopologyStatus::DisconnectedLoop:
            return "Structural error: Face coedges fail to form a continuous closed circuit.";
        case TopologyStatus::UnsupportedUnit:
            return "Configuration error: Unsupported length unit specified.";
    }
    return "Unknown state.";
}

// Explicit physical type system for length units instead of standard runtime string fields
enum class LengthUnit : uint8_t {
    Millimeter,
    Centimeter,
    Meter,
    Inch
};

[[nodiscard, maybe_unused]]
static std::string to_string(const LengthUnit unit) {
    switch (unit) {
        case LengthUnit::Millimeter: return "mm";
        case LengthUnit::Centimeter: return "cm";
        case LengthUnit::Meter: return "m";
        case LengthUnit::Inch: return "in";
    }
    return "unknown";
}

// Some inlined vector operations
[[maybe_unused, nodiscard]]
static std::array<float, 3>
vec_sub(const std::array<float, 3> &a, const std::array<float, 3> &b) noexcept {
    return std::array{a[0] - b[0], a[1] - b[1], a[2] - b[2]};
}

[[maybe_unused, nodiscard]]
static std::array<double, 3>
vec_sub(const std::array<double, 3> &a, const std::array<double, 3> &b) noexcept {
    return std::array{a[0] - b[0], a[1] - b[1], a[2] - b[2]};
}

[[maybe_unused, nodiscard]]
static float vec_dot(const std::array<float, 3> &a, const std::array<float, 3> &b) noexcept {
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
}

[[maybe_unused, nodiscard]]
static double vec_dot(const std::array<double, 3> &a, const std::array<double, 3> &b) noexcept {
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
}

[[maybe_unused, nodiscard]]
static std::array<float, 3>
vec_cross(const std::array<float, 3> &a, const std::array<float, 3> &b) noexcept {
    return {
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0]
    };
}

[[maybe_unused, nodiscard]]
static std::array<double, 3>
vec_cross(const std::array<double, 3> &a, const std::array<double, 3> &b) noexcept {
    return {
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0]
    };
}

[[maybe_unused, nodiscard]]
static float
vec_norm(const std::array<float, 3> &a) noexcept {
    return std::sqrt(vec_dot(a, a));
}

[[maybe_unused, nodiscard]]
static double
vec_norm(const std::array<double, 3> &a) noexcept {
    return std::sqrt(vec_dot(a, a));
}

// Flat, un-fragmented representation of a simplex using an explicitly managed contiguous block
struct Simplex {
    std::vector<int> vertices;

    [[maybe_unused, nodiscard]]
    std::size_t dim() const noexcept;

    auto operator<=>(const Simplex &) const = default;
};

// Custom Compressed Sparse Row (CSR) implementation optimized for topological operators.
// Since boundary entries are exclusively +1 or -1, we store coefficients using int8_t,
// saving 87.5% memory overhead on numerical values relative to double-precision layouts.
struct OksSparseCSR {
    std::vector<size_t> row_ptr;
    std::vector<size_t> col_ind;
    std::vector<int8_t> values;
    size_t num_rows = 0;
    size_t num_cols = 0;

    void print() const noexcept {
        std::cout << "Optimized CSR Matrix [" << num_rows << " x " << num_cols << "] (" << values.size() << " NNZ):\n";
        std::cout << "  row_ptr: "; for (const auto p : row_ptr) std::cout << p << " ";
        std::cout << "\n  col_ind: "; for (const auto c : col_ind) std::cout << c << " ";
        std::cout << "\n  values:  "; for (const auto v : values) std::cout << static_cast<int>(v) << " ";
        std::cout << "\n\n";
    }
};

// Forward decl
class SimplicialComplex;


// C++ structurally safe geometric layout container replacing Python idioms
struct TriangleMesh {
    std::vector<std::array<float, 3> > vertices;
    std::vector<std::array<int, 3> > triangles;
    LengthUnit length_unit = LengthUnit::Millimeter;

    [[nodiscard]]
    std::expected<SimplicialComplex, TopologyStatus> to_simplicial_complex(size_t max_simplicial = 50000) const noexcept;
};

struct PolyhedralBRep {
    std::vector<std::array<float, 3> > vertices;
    std::vector<std::array<int, 2> > edges;
    std::vector<std::size_t> face_offsets;
    std::vector<int> face_coedges;

    LengthUnit length_unit = LengthUnit::Millimeter;

    [[nodiscard]]
    std::size_t face_count() const noexcept;

    [[nodiscard]]
    std::span<const int> face_loop(const size_t face_id) const noexcept {
        if (face_id >= face_count()) return {};
        return {
            face_coedges.data() + face_offsets[face_id],
            face_coedges.data() + face_offsets[face_id + 1]
        };
    }

        // Modern factory method processing polygonal paths down into canonical shared BRep components
    [[maybe_unused, nodiscard]]
    static std::expected<PolyhedralBRep, TopologyStatus> from_polygons(
        std::vector<std::array<float, 3>> vertices,
        const std::vector<std::vector<int>>& polygons,
        const LengthUnit unit = LengthUnit::Millimeter,
        const bool share_edges = true) noexcept
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

            // Check bounding ranges and verify internal polygon uniqueness constraints
            std::vector<int> uniq = polygon;
            std::ranges::sort(uniq);
            if (std::ranges::adjacent_find(uniq) != uniq.end()) {
                return std::unexpected(TopologyStatus::DuplicateVertices);
            }
            for (const int v : polygon) {
                if (v < 0 || v >= num_verts) return std::unexpected(TopologyStatus::IndexOutOfBounds);
            }

            const auto n = polygon.size();
            for (size_t i = 0; i < n; ++i) {
                int u = polygon[i];
                int v = polygon[(i + 1) % n];
                EdgeKey key{ .u = std::min(u, v), .v = std::max(u, v) };

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


    // Extracts ordered vertex loops cleanly without allocations or string modifications
    [[maybe_unused, nodiscard]]
    std::expected<std::vector<int>, TopologyStatus>
    face_vertices(const size_t face_id) const noexcept {
        const auto tokens = face_loop(face_id);
        if (tokens.empty()) return std::unexpected(TopologyStatus::IndexOutOfBounds);

        std::vector<std::array<int, 2>> endpoints;
        endpoints.reserve(tokens.size());

        for (const auto t : tokens) {
            const auto edge_idx = std::abs(t) - 1;
            if (edge_idx < 0 || edge_idx >= static_cast<int>(edges.size())) {
                return std::unexpected(TopologyStatus::IndexOutOfBounds);
            }
            auto edge = edges[edge_idx];
            if (t < 0) std::swap(edge[0], edge[1]);
            endpoints.push_back(edge);
        }

        // Structural loop tracking step verification
        const auto n = endpoints.size();
        for (auto i = 0; i < n; ++i) {
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



    // Unrolls high-speed fan triangulations over validated planar/convex boundaries
    [[maybe_unused, nodiscard]]
    std::expected<std::vector<std::array<int, 3>>, TopologyStatus>
    triangulate_face(
        const std::size_t face_id,
        const float planarity_tolerance = 1e-6f) const noexcept
    {
        auto verts_res = face_vertices(face_id);
        if (!verts_res) return std::unexpected(verts_res.error());
        const auto& ids = *verts_res;

        if (ids.size() < 3) return std::unexpected(TopologyStatus::DegenerateTriangle);

        std::vector<std::array<float, 3>> xyz;
        xyz.reserve(ids.size());
        for (const auto id : ids) xyz.push_back(vertices[id]);

        const auto r1 = vec_sub(xyz[1], xyz[0]);
        const auto r2 = vec_sub(xyz[2], xyz[0]);
        auto normal = vec_cross(r1, r2);
        const float n_norm = vec_norm(normal);

        if (n_norm == 0.0f) return std::unexpected(TopologyStatus::DegenerateTriangle);
        normal = { normal[0] / n_norm, normal[1] / n_norm, normal[2] / n_norm };

        // Planarity Verification Stage
        for (const auto& pt : xyz) {
            if (auto rel = vec_sub(pt, xyz[0]); std::abs(vec_dot(rel, normal)) > planarity_tolerance) {
                return std::unexpected(TopologyStatus::NonPlanarFace);
            }
        }

        // Convexity Verification Step
        for (size_t k = 0; k < ids.size(); ++k) {
            auto edge = vec_sub(xyz[(k + 1) % ids.size()], xyz[k]);
            float edge_len = vec_norm(edge);

            for (size_t m = 0; m < ids.size(); ++m) {
                auto diff = vec_sub(xyz[m], xyz[k]);
                auto cross_side = vec_cross(edge, diff);
                if (const float orientation = vec_dot(cross_side, normal); orientation < -planarity_tolerance * std::max(1.0f, edge_len)) {
                    return std::unexpected(TopologyStatus::NonConvexFace);
                }
            }
        }

        // Output fast fan triangulation blocks directly
        std::vector<std::array<int, 3>> face_tris;
        face_tris.reserve(ids.size() - 2);
        for (size_t i = 1; i < ids.size() - 1; ++i) {
            face_tris.push_back({ ids[0], ids[i], ids[i + 1] });
        }
        return face_tris;
    }

    [[maybe_unused, nodiscard]]
    std::expected<TriangleMesh, TopologyStatus>
    triangulate_convex_faces(const float planarity_tolerance = 1e-6f) const noexcept {
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
    // Memory Layout: A flat vector of dimensions, where each dimension holds a flat,
    // contiguous, lexicographically sorted vector of Simplices. This guarantees
    // maximum hardware prefetcher efficiency and cache-line saturation.
    std::vector<std::vector<Simplex> > spatial_tiers_;
    size_t max_dim_ = 0;

    // Micro-optimized zero-allocation comparator. Compares a lower-dimensional simplex
    // against an upper-dimensional simplex *as if* the upper simplex had its k-th vertex removed.
    // This allows complete binary search logic across spans without copying or allocating memory.
    static int compare_skipped_face(
        const std::span<const int> lower,
        const std::span<const int> upper, const size_t skip_idx) noexcept {
        size_t l_idx = 0;
        for (size_t u_idx = 0; u_idx < upper.size(); ++u_idx) {
            if (u_idx == skip_idx) [[unlikely]] continue;
            if (l_idx >= lower.size()) return -1;

            if (lower[l_idx] < upper[u_idx]) return -1;
            if (lower[l_idx] > upper[u_idx]) return 1;

            l_idx++;
        }
        return l_idx < lower.size() ? 1 : 0;
    }

    // Binary search engine implementing the zero-allocation comparison routine
    static size_t find_face_index(
        const std::span<const Simplex> lower_tier,
        const Simplex &upper,
        const size_t skip_idx
        ) noexcept {
        long long low = 0;
        long long high = static_cast<long long>(lower_tier.size()) - 1;

        while (low <= high) {
            const long long mid = low + (high - low) / 2;
            const int comparison = compare_skipped_face(lower_tier[mid].vertices, upper.vertices, skip_idx);

            if (comparison == 0) return mid;
            if (comparison < 0) low = mid + 1;
            else high = mid - 1;
        }
        return std::string::npos;
    }

public:
    explicit SimplicialComplex(
        std::vector<std::vector<Simplex> > tiers, const size_t max_dim)
        : spatial_tiers_(std::move(tiers)), max_dim_(max_dim) {
    }


    static std::expected<SimplicialComplex, TopologyStatus> build_from_mesh_engine(
        const TriangleMesh &mesh,
        const std::size_t simplex_budget) noexcept {

        // 1. Structural Validations via high-speed cache-local linear sweeps
        const int num_verts = static_cast<int>(mesh.vertices.size());
        std::vector<std::array<int, 3> > canonical_triangles;
        canonical_triangles.reserve(mesh.triangles.size());

        for (auto t: mesh.triangles) {
            // Index Out of Bounds protection verification
            if (t[0] < 0 || t[0] >= num_verts ||
                t[1] < 0 || t[1] >= num_verts ||
                t[2] < 0 || t[2] >= num_verts) [[unlikely]] {
                return std::unexpected(TopologyStatus::IndexOutOfBounds);
            }

            // Reject degenerate repeated vertices inside single triangle
            if (t[0] == t[1] || t[1] == t[2] || t[0] == t[2]) [[unlikely]] {
                return std::unexpected(TopologyStatus::DegenerateTriangle);
            }

            // Standardize canonical ordering layout inline to prepare for geometric uniqueness sort checks
            std::ranges::sort(t);
            canonical_triangles.push_back(t);
        }

        // Sort unique check mimicking Python's unique rows check
        std::ranges::sort(canonical_triangles);
        if (std::ranges::adjacent_find(canonical_triangles) != canonical_triangles.end()) {
            return std::unexpected(TopologyStatus::DuplicateTriangles);
        }

        // 2. Allocate staging arrays (Max tracking dimension for standard structural triangle mesh is 2)
        std::vector<std::vector<Simplex> > staging_tiers(3);

        // Natively seed isolated and active vertices as explicitly tracked 0-simplices
        staging_tiers[0].reserve(mesh.vertices.size());
        for (int i = 0; i < num_verts; ++i) {
            staging_tiers[0].push_back(Simplex{.vertices = {i}});
        }

        // Populate geometric boundaries inline directly from canonical configurations
        for (const auto &t: canonical_triangles) {
            // Generating underlying 1-simplices (Edges)
            staging_tiers[1].push_back(Simplex{.vertices = {t[0], t[1]}});
            staging_tiers[1].push_back(Simplex{.vertices = {t[1], t[2]}});
            staging_tiers[1].push_back(Simplex{.vertices = {t[0], t[2]}});

            // Generating ultimate 2-simplices (Triangles)
            staging_tiers[2].push_back(Simplex{.vertices = {t[0], t[1], t[2]}});
        }

        // 3. Deduplicate elements sequentially via linear Sort-Unique passes
        auto total_allocated = staging_tiers[0].size();

        // TODO(Shouldn't this below just be unrolled?)
        for (size_t d = 1; d <= 2; ++d) {
            std::ranges::sort(staging_tiers[d]);
            auto unique_range = std::ranges::unique(staging_tiers[d]).begin();
            staging_tiers[d].erase(unique_range, staging_tiers[d].end());
            total_allocated += staging_tiers[d].size();

            if (total_allocated > simplex_budget) [[unlikely]] {
                return std::unexpected(TopologyStatus::BudgetExceeded);
            }
        }

        return SimplicialComplex(std::move(staging_tiers), 2);
    }

    [[maybe_unused, nodiscard]]
    std::span<const Simplex>
    get_tier(const size_t d) const noexcept {
        return d < spatial_tiers_.size() ? spatial_tiers_[d] : std::span<const Simplex>{};
    }

    // Blazing-fast factory using the Vector Sort-Unique pattern instead of tree-balanced std::sets.
    // Drastically lowers heap allocations by accumulating in flat staging arrays before deduplication.
    [[nodiscard, maybe_unused]]
    static std::expected<SimplicialComplex, TopologyStatus> build(
        const std::vector<std::vector<int> > &facets,
        const size_t simplex_budget = 100'000) {

        if (facets.empty()) return SimplicialComplex({}, 0);

        // Determine ultimate dimension limits to scale out initial tracking buffers safely
        size_t calculated_max_dim = 0;
        for (const auto &f: facets) {
            if (!f.empty()) calculated_max_dim = std::max(calculated_max_dim, f.size() - 1);
        }

        std::vector<std::vector<Simplex> > staging_tiers(calculated_max_dim + 1);
        size_t total_allocated = 0;

        for (auto facet: facets) {
            if (facet.empty()) continue;

            std::ranges::sort(facet);
            if (std::ranges::adjacent_find(facet) != facet.end()) {
                return std::unexpected(TopologyStatus::DuplicateVertices);
            }

            const size_t n = facet.size();
            const uint64_t subfaces = (1ULL << n) - 1;

            // Compute subface properties inline via bitmask permutations
            for (uint64_t mask = 1; mask <= subfaces; ++mask) {
                std::vector<int> face_vertices;
                face_vertices.reserve(std::popcount(mask));

                for (size_t i = 0; i < n; ++i) {
                    if ((mask >> i) & 1) {
                        face_vertices.push_back(facet[i]);
                    }
                }

                const auto d = face_vertices.size() - 1;
                staging_tiers[d].push_back(Simplex{.vertices = std::move(face_vertices)});
            }
        }

        // Deduplicate staging tiers sequentially via sorting and unique-filtering contiguous spans
        for (auto &tier: staging_tiers) {
            std::ranges::sort(tier);
            auto unique_range = std::ranges::unique(tier).begin();
            tier.erase(unique_range, tier.end());
            total_allocated += tier.size();

            if (total_allocated > simplex_budget) [[unlikely]] {
                return std::unexpected(TopologyStatus::BudgetExceeded);
            }
        }

        return SimplicialComplex(std::move(staging_tiers), calculated_max_dim);
    }


    // High-Performance Two-Pass Zero-Sort CSR Assembly Engine.
    // Appending items in a sequential column-index execution sweep means column keys
    // are automatically sorted inside each row by default. Eliminates triplet sorting arrays entirely.
    [[nodiscard, maybe_unused]] std::expected<OksSparseCSR, TopologyStatus>
    boundary_operator(const size_t d) const noexcept {
        if (d == 0 || d > max_dim_) return std::unexpected(TopologyStatus::InvalidDimension);

        const auto current_cols = get_tier(d);
        const auto lower_rows = get_tier(d - 1);

        OksSparseCSR csr;
        csr.num_rows = lower_rows.size();
        csr.num_cols = current_cols.size();
        csr.row_ptr.assign(csr.num_rows + 1, 0);

        if (current_cols.empty()) return csr;

        // Pass 1: Scan structural hierarchies to calculate exact non-zero distributions per row
        for (const auto & upper_simplex : current_cols) {
            for (auto k = 0; k < upper_simplex.vertices.size(); ++k) {
                if (const auto i = find_face_index(lower_rows, upper_simplex, k); i != std::string::npos) {
                    csr.row_ptr[i + 1]++; // Track offsets shifted by one position
                }
            }
        }

        // Generate cumulative row offset tracking pointers using a fast running prefix sum

        for (auto i = 0; i < csr.num_rows; ++i) {
            csr.row_ptr[i + 1] += csr.row_ptr[i];
        }

        // Sizing the tracking buffers to perfectly match calculated non-zero targets
        const auto total_nnz = csr.row_ptr.back();
        csr.col_ind.resize(total_nnz);
        csr.values.resize(total_nnz);

        // Mirror active offset blocks to safely trace localized cursor coordinates
        std::vector<size_t> write_cursors = csr.row_ptr;

        // Pass 2: Fill internal tracking buffers. Processing columns sequentially from
        // 0 to num_cols-1 automatically orders column indices within row blocks.
        for (size_t j = 0; j < current_cols.size(); ++j) {
            const auto &upper_simplex = current_cols[j];
            for (size_t k = 0; k < upper_simplex.vertices.size(); ++k) {
                if (const auto i = find_face_index(lower_rows, upper_simplex, k); i != std::string::npos) {
                    const auto write_pos = write_cursors[i]++;
                    csr.col_ind[write_pos] = j;
                    csr.values[write_pos] = k % 2 == 0 ? 1 : -1;
                }
            }
        }

        return csr;
    }
};

std::size_t Simplex::dim() const noexcept {
    return vertices.empty() ? 0 : vertices.size() - 1;
}

// Implement structured mesh redirection mechanics natively
std::expected<SimplicialComplex, TopologyStatus>
TriangleMesh::to_simplicial_complex(const size_t max_simplicial) const noexcept {
    return SimplicialComplex::build_from_mesh_engine(*this, max_simplicial);
}

std::size_t PolyhedralBRep::face_count() const noexcept {
    return face_offsets.empty() ? 0 : face_offsets.size() - 1;
}

int main() {
    // Generate a flat square composed of a single 4-sided polygon (a quad boundary)
    std::vector<std::array<float, 3>> pts = {
        {0.0f, 0.0f, 0.0f}, // 0
        {1.0f, 0.0f, 0.0f}, // 1
        {1.0f, 1.0f, 0.0f}, // 2
        {0.0f, 1.0f, 0.0f}  // 3
    };
    std::vector<std::vector<int>> polys = { {0, 1, 2, 3} };

    std::cout << "Step 1: Building PolyhedralBRep from raw polygon tracks...\n";
    auto brep_res = PolyhedralBRep::from_polygons(pts, polys, LengthUnit::Millimeter, true);
    if (!brep_res) {
        std::cerr << "BRep generation aborted: " << to_string(brep_res.error()) << "\n";
        return 1;
    }
    const auto& brep = *brep_res;
    std::cout << "  Faces loaded: " << brep.face_count() << ", Edges generated: " << brep.edges.size() << "\n\n";

    std::cout << "Step 2: Launching geometric planarity and convexity validation sweeps for fan triangulation...\n";
    auto mesh_res = brep.triangulate_convex_faces();
    if (!mesh_res) {
        std::cerr << "Triangulation failed: " << to_string(mesh_res.error()) << "\n";
        return 1;
    }
    const auto& mesh = *mesh_res;
    std::cout << "  Mesh Output: Triangles mapped: " << mesh.triangles.size() << "\n\n";

    std::cout << "Step 3: Downward closure mapping to create the final SimplicialComplex...\n";
    auto complex_res = mesh.to_simplicial_complex();
    if (!complex_res) {
        std::cerr << "Complex assembly aborted: " << to_string(complex_res.error()) << "\n";
        return 1;
    }
    const auto& complex = *complex_res;
    std::cout << "  Simplicial Complex structural distributions:\n";
    std::cout << "    0-Simplices (Vertices): " << complex.get_tier(0).size() << "\n";
    std::cout << "    1-Simplices (Edges):    " << complex.get_tier(1).size() << "\n";
    std::cout << "    2-Simplices (Faces):    " << complex.get_tier(2).size() << "\n\n";

    std::cout << "Step 4: Compiling sparse boundary operators across 2-simplices...\n";
    if (auto boundary_op_2 = complex.boundary_operator(2)) {
        boundary_op_2->print();
    }

    return 0;
}
