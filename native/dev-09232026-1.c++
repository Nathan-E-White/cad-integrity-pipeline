#include <iostream>
#include <vector>
#include <array>
#include <cmath>
#include <algorithm>
#include <unordered_map>
#include <cstdint>
#include <map>
#include <execution>

// User-provided snippet for a 3D coordinate point
template <typename T>
struct Pnt3D {
    std::array<T, 3> data;
};

// Internal representation for a triangular face
struct Face {
    uint32_t v0, v1, v2;
};

// Sparse Matrix Triplet representation
struct SparseEntry {
    uint32_t row;
    uint32_t col;
    double value;
};

using SparseMatrix = std::vector<SparseEntry>;

struct OrientedEdge {
    uint32_t v0;
    uint32_t v1;

    bool operator<(const OrientedEdge& o) const {
        if (v0 != o.v0) return v0 < o.v0;
        return v1 < o.v1;
    }
};

// Vector math utilities for Pnt3D
template <typename T>
Pnt3D<T> sub(const Pnt3D<T>& a, const Pnt3D<T>& b) {
    return {a.data[0] - b.data[0], a.data[1] - b.data[1], a.data[2] - b.data[2]};
}

template <typename T>
T dot(const Pnt3D<T>& a, const Pnt3D<T>& b) {
    return a.data[0] * b.data[0] + a.data[1] * b.data[1] + a.data[2] * b.data[2];
}

template <typename T>
Pnt3D<T> cross(const Pnt3D<T>& a, const Pnt3D<T>& b) {
    return {
        a.data[1] * b.data[2] - a.data[2] * b.data[1],
        a.data[2] * b.data[0] - a.data[0] * b.data[2],
        a.data[0] * b.data[1] - a.data[1] * b.data[0]
    };
}

template <typename T>
T norm(const Pnt3D<T>& a) {
    return std::sqrt(dot(a, a));
}

// Morton 3D bits dilation mechanics
inline uint64_t dilate_bits(uint64_t x) {
    x &= 0x1fffff;
    x = (x | (x << 32)) & 0x1f00000000ffff;
    x = (x | (x << 16)) & 0x1f0000ff0000ff;
    x = (x | (x << 8))  & 0x100f00f00f00f00f;
    x = (x | (x << 4))  & 0x10c30c30c30c30c3;
    x = (x | (x << 2))  & 0x1249249249249249;
    return x;
}

inline uint64_t encode_morton3d(uint32_t x, uint32_t y, uint32_t z) {
    return dilate_bits(x) | (dilate_bits(y) << 1) | (dilate_bits(z) << 2);
}

// O(N) duplicate vertex deduplication
template <typename T>
void deduplicate_vertices(const std::vector<Pnt3D<T>>& src_vertices,
                          const std::vector<Face>& src_faces,
                          std::vector<Pnt3D<T>>& out_vertices,
                          std::vector<Face>& out_faces,
                          T tolerance)
{
    struct GridKey {
        int64_t x, y, z;
        bool operator==(const GridKey& o) const { return x == o.x && y == o.y && z == o.z; }
    };
    struct GridKeyHash {
        std::size_t operator()(const GridKey& k) const {
            return (k.x * 73856093) ^ (k.y * 19349663) ^ (k.z * 83492791);
        }
    };

    std::unordered_map<GridKey, std::vector<uint32_t>, GridKeyHash> grid;
    std::vector<uint32_t> remap_table(src_vertices.size());
    out_vertices.clear();
    out_faces.clear();

    T cell_size = tolerance;

    for (size_t i = 0; i < src_vertices.size(); ++i) {
        const auto& v = src_vertices[i];
        GridKey key{
            static_cast<int64_t>(std::floor(v.data[0] / cell_size)),
            static_cast<int64_t>(std::floor(v.data[1] / cell_size)),
            static_cast<int64_t>(std::floor(v.data[2] / cell_size))
        };

        bool found = false;
        uint32_t target_idx = 0;

        for (int dx = -1; dx <= 1 && !found; ++dx) {
            for (int dy = -1; dy <= 1 && !found; ++dy) {
                for (int dz = -1; dz <= 1 && !found; ++dz) {
                    GridKey neighbor{key.x + dx, key.y + dy, key.z + dz};
                    auto it = grid.find(neighbor);
                    if (it != grid.end()) {
                        for (uint32_t existing_idx : it->second) {
                            const auto& ev = out_vertices[existing_idx];
                            if (norm(sub(v, ev)) <= tolerance) {
                                found = true;
                                target_idx = existing_idx;
                                break;
                            }
                        }
                    }
                }
            }
        }

        if (!found) {
            target_idx = static_cast<uint32_t>(out_vertices.size());
            out_vertices.push_back(v);
            grid[key].push_back(target_idx);
        }
        remap_table[i] = target_idx;
    }

    for (const auto& f : src_faces) {
        uint32_t v0 = remap_table[f.v0];
        uint32_t v1 = remap_table[f.v1];
        uint32_t v2 = remap_table[f.v2];
        if (v0 != v1 && v1 != v2 && v2 != v0) {
            out_faces.push_back({v0, v1, v2});
        }
    }
}

// Parallelized Spatial Sorting Framework
template <typename T>
void parallel_spatial_sort(std::vector<Pnt3D<T>>& vertices, std::vector<Face>& faces) {
    if (vertices.empty()) return;

    Pnt3D<T> min_b = vertices[0], max_b = vertices[0];
    for (const auto& v : vertices) {
        for (int d = 0; d < 3; ++d) {
            min_b.data[d] = std::min(min_b.data[d], v.data[d]);
            max_b.data[d] = std::max(max_b.data[d], v.data[d]);
        }
    }

    std::vector<std::pair<uint64_t, uint32_t>> morton_pairs(vertices.size());
    uint32_t max_val = (1u << 21) - 1;

    for (uint32_t i = 0; i < vertices.size(); ++i) {
        uint32_t ix = 0, iy = 0, iz = 0;
        if (max_b.data[0] > min_b.data[0]) ix = static_cast<uint32_t>(((vertices[i].data[0] - min_b.data[0]) / (max_b.data[0] - min_b.data[0])) * max_val);
        if (max_b.data[1] > min_b.data[1]) iy = static_cast<uint32_t>(((vertices[i].data[1] - min_b.data[1]) / (max_b.data[1] - min_b.data[1])) * max_val);
        if (max_b.data[2] > min_b.data[2]) iz = static_cast<uint32_t>(((vertices[i].data[2] - min_b.data[2]) / (max_b.data[2] - min_b.data[2])) * max_val);

        morton_pairs[i] = { encode_morton3d(ix, iy, iz), i };
    }

    std::sort(std::execution::par, morton_pairs.begin(), morton_pairs.end());

    std::vector<Pnt3D<T>> sorted_vertices(vertices.size());
    std::vector<uint32_t> forward_map(vertices.size());
    for (uint32_t i = 0; i < morton_pairs.size(); ++i) {
        uint32_t original_idx = morton_pairs[i].second;
        sorted_vertices[i] = vertices[original_idx];
        forward_map[original_idx] = i;
    }
    vertices = std::move(sorted_vertices);

    for (auto& f : faces) {
        f.v0 = forward_map[f.v0];
        f.v1 = forward_map[f.v1];
        f.v2 = forward_map[f.v2];
    }
}

// =====================================
// Boundary Chain Operator extraction
// =====================================
// Discrete Boundary Chain Matrix Formations (\(\partial_1, \partial_2\))
// 1. compute_boundary_operators collects a unique set of edge entities,
//    enforcing standard canonical direction rules (\(v_0 < v_1\)) to
//    index 1-chains systematically.
// 2. Matrix \[\partial _{1}\] (\(V \times E\)) assigns boundary nodes
//    weights of \[-1\] (tail origin) and \[+1\] (head target).
// 3. Matrix \[\partial _{2}\] (\(E \times F\)) tracks face boundary paths,
//    matching orientation alignments to generate sign configurations
//    (\[+1\] for forward cycles, \[-1\] for reversed paths).
//
void compute_boundary_operators(const std::vector<Face>& faces,
                                std::vector<OrientedEdge>& out_edges,
                                SparseMatrix& out_d1,
                                SparseMatrix& out_d2)
{
    std::map<OrientedEdge, uint32_t> edge_to_index;
    out_edges.clear();

    for (const auto& f : faces) {
        std::array<std::pair<uint32_t, uint32_t>, 3> segments = {{{f.v0, f.v1}, {f.v1, f.v2}, {f.v2, f.v0}}};
        for (const auto& seg : segments) {
            uint32_t u = std::min(seg.first, seg.second);
            uint32_t v = std::max(seg.first, seg.second);
            OrientedEdge canonical{u, v};
            if (edge_to_index.find(canonical) == edge_to_index.end()) {
                edge_to_index[canonical] = static_cast<uint32_t>(out_edges.size());
                out_edges.push_back(canonical);
            }
        }
    }

    for (uint32_t e_idx = 0; e_idx < out_edges.size(); ++e_idx) {
        const auto& edge = out_edges[e_idx];
        out_d1.push_back({edge.v0, e_idx, -1.0});
        out_d1.push_back({edge.v1, e_idx, 1.0});
    }

    for (uint32_t f_idx = 0; f_idx < faces.size(); ++f_idx) {
        const auto& f = faces[f_idx];
        std::array<std::pair<uint32_t, uint32_t>, 3> segments = {{{f.v0, f.v1}, {f.v1, f.v2}, {f.v2, f.v0}}};
        for (const auto& seg : segments) {
            uint32_t u = std::min(seg.first, seg.second);
            uint32_t v = std::max(seg.first, seg.second);
            OrientedEdge canonical{u, v};
            uint32_t e_idx = edge_to_index[canonical];
            double orientation_sign = (seg.first < seg.second) ? 1.0 : -1.0;
            out_d2.push_back({e_idx, f_idx, orientation_sign});
        }
    }
}

// ==========================================================
// NEW EXTENSION: DISCRETE EXTERIOR CALCULUS HODGE STAR OPERATORS
// ==========================================================
// Mathematical & Algorithmic Summary
// Discrete Exterior Calculus Hodge Stars:
// \[\star _{0}\] (0-Forms): Computes the primal-to-dual structural
// mapping, mapping 0-cells to dual 2-cells. It maps each vertex to
// its corresponding localized diagonal Voronoi boundary field.
// \[\star _{1}\] (1-Forms): Calculates the geometric ratios between
// dual edge lengths and primal edge lengths using cotangent
// configurations (\(\frac{1}{2}(\cot \alpha + \cot \beta)\)),
// optimizing physical field translations across structural paths.
// \[\star _{2}\] (2-Forms):
// Computes inverse surface area scales (\(1 / \text{Area}(f)\)),
// which converts primal triangles directly into dual point representations.
template <typename T>
void compute_dec_hodge_stars(const std::vector<Pnt3D<T>>& vertices,
                             const std::vector<Face>& faces,
                             const std::vector<OrientedEdge>& edges,
                             std::vector<double>& out_star0,
                             std::vector<double>& out_star1,
                             std::vector<double>& out_star2)
{
    out_star0.assign(vertices.size(), 0.0);
    out_star1.assign(edges.size(), 0.0);
    out_star2.assign(faces.size(), 0.0);

    // Track structural mappings to update dual edge cotangent variables safely
    std::map<OrientedEdge, uint32_t> edge_to_idx;
    for (uint32_t i = 0; i < edges.size(); ++i) {
        edge_to_idx[edges[i]] = i;
    }

    // 1. Compute Face Dual Space metrics (Hodge Star 2-Forms: 1 / Area)
    // 2. Accumulate Primal Vertex Voronoi cells (Hodge Star 0-Forms)
    for (uint32_t f_idx = 0; f_idx < faces.size(); ++f_idx) {
        const auto& f = faces[f_idx];
        Pnt3D<T> v0 = vertices[f.v0];
        Pnt3D<T> v1 = vertices[f.v1];
        Pnt3D<T> v2 = vertices[f.v2];

        T area = norm(cross(sub(v1, v0), sub(v2, v0))) * 0.5;
        out_star2[f_idx] = (area > 1e-9) ? (1.0 / area) : 0.0;

        // Distribute stable localized barycentric dual cellular areas to 0-cells
        double barycentric_contribution = area / 3.0;
        out_star0[f.v0] += barycentric_contribution;
        out_star0[f.v1] += barycentric_contribution;
        out_star0[f.v2] += barycentric_contribution;

        // Compute localized interior cotangents for geometric ratios
        double cot0 = dot(sub(v1, v0), sub(v2, v0)) / norm(cross(sub(v1, v0), sub(v2, v0)));
        double cot1 = dot(sub(v0, v1), sub(v2, v1)) / norm(cross(sub(v0, v1), sub(v2, v1)));
        double cot2 = dot(sub(v0, v2), sub(v1, v2)) / norm(cross(sub(v0, v2), sub(v1, v2)));

        auto accumulate_edge_star = [&](uint32_t u, uint32_t v, double cot_val) {
            OrientedEdge canonical{std::min(u, v), std::max(u, v)};
            out_star1[edge_to_idx[canonical]] += cot_val * 0.5;
        };

        // Accumulate opposite angle weights onto edge elements (Primal-to-Dual 1-forms)
        accumulate_edge_star(f.v1, f.v2, cot0);
        accumulate_edge_star(f.v0, f.v2, cot1);
        accumulate_edge_star(f.v0, f.v1, cot2);
    }
}

// ==========================================================
// NEW EXTENSION: HOMOLOGICAL GENERATOR CYCLES ISOLATION (Z1 / B1)
// ==========================================================
// Homological Generator Cycles Isolation (\(H_1 = Z_1 / B_1\)):
// A geometric annulus mesh containing a physical topological void
// is used to verify implementation details.
//
// The method computes the complete space of 1-cycles,
// \(Z_1 = \ker(\partial_1)\), using linear system reductions.
//
// Subtracted structural boundary paths, \(B_1 = \text{im}(\partial_2)\),
// isolate the fundamental non-trivial loops encircling structural
// boundary configurations. The code produces an output dimension of exactly 1,
// identifying the underlying loop generator asset.
//
std::vector<std::vector<double>> compute_matrix_kernel(const std::vector<std::vector<double>>& M,
                                                      uint32_t rows, uint32_t cols)
{
    auto A = M;
    std::vector<int32_t> pivot_col(rows, -1);
    uint32_t r = 0;

    for (uint32_t c = 0; c < cols && r < rows; ++c) {
        uint32_t pivot_row = r;
        while (pivot_row < rows && std::abs(A[pivot_row][c]) < 1e-7) {
            pivot_row++;
        }
        if (pivot_row == rows) continue;

        std::swap(A[r], A[pivot_row]);
        pivot_col[r] = c;

        for (uint32_t i = 0; i < rows; ++i) {
            if (i != r && std::abs(A[i][c]) > 1e-7) {
                double factor = A[i][c] / A[r][c];
                for (uint32_t j = c; j < cols; ++j) {
                    A[i][j] -= factor * A[r][j];
                }
            }
        }
        r++;
    }

    std::vector<bool> is_pivot(cols, false);
    for (uint32_t i = 0; i < r; ++i) {
        if (pivot_col[i] != -1) is_pivot[pivot_col[i]] = true;
    }

    std::vector<std::vector<double>> kernel_basis;
    for (uint32_t c = 0; c < cols; ++c) {
        if (!is_pivot[c]) {
            std::vector<double> vec(cols, 0.0);
            vec[c] = 1.0;
            for (uint32_t i = 0; i < r; ++i) {
                uint32_t pc = pivot_col[i];
                vec[pc] = -A[i][c] / A[i][pc];
            }
            kernel_basis.push_back(vec);
        }
    }
    return kernel_basis;
}

std::vector<std::vector<double>> isolate_homology_generators(const SparseMatrix& d2,
                                                            uint32_t num_edges,
                                                            uint32_t num_faces,
                                                            const std::vector<std::vector<double>>& cycle_basis)
{
    if (cycle_basis.empty()) return {};

    uint32_t num_cycles = static_cast<uint32_t>(cycle_basis.size());
    uint32_t total_cols = num_faces + num_cycles;
    std::vector<std::vector<double>> A(num_edges, std::vector<double>(total_cols, 0.0));

    for (const auto& entry : d2) {
        A[entry.row][entry.col] = entry.value;
    }

    for (uint32_t c = 0; c < num_cycles; ++c) {
        for (uint32_t e = 0; e < num_edges; ++e) {
            A[e][num_faces + c] = cycle_basis[c][e];
        }
    }

    uint32_t r = 0;
    std::vector<uint32_t> generator_indices;

    for (uint32_t c = 0; c < total_cols && r < num_edges; ++c) {
        uint32_t pivot_row = r;
        while (pivot_row < num_edges && std::abs(A[pivot_row][c]) < 1e-7) {
            pivot_row++;
        }
        if (pivot_row == num_edges) continue;

        std::swap(A[r], A[pivot_row]);

        for (uint32_t i = 0; i < num_edges; ++i) {
            if (i != r && std::abs(A[i][c]) > 1e-7) {
                double factor = A[i][c] / A[r][c];
                for (uint32_t j = c; j < total_cols; ++j) {
                    A[i][j] -= factor * A[r][j];
                }
            }
        }

        // If the cycle vector column produces a new distinct pivot, it signifies a non-trivial generator
        if (c >= num_faces) {
            generator_indices.push_back(c - num_faces);
        }
        r++;
    }

    std::vector<std::vector<double>> actual_generators;
    for (uint32_t idx : generator_indices) {
        actual_generators.push_back(cycle_basis[idx]);
    }
    return actual_generators;
}

int main() {
    // Generate a geometric annulus complex (hollow ring) to evaluate non-trivial 1-homology cycles
    std::vector<Pnt3D<double>> annulus_vertices = {
        {{1.0, 0.0, 0.0}},    {{-0.5, 0.866, 0.0}}, {{-0.5, -0.866, 0.0}}, // Inner circle
        {{2.0, 0.0, 0.0}},    {{-1.0, 1.732, 0.0}}, {{-1.0, -1.732, 0.0}}  // Outer circle
    };

    std::vector<Face> annulus_faces = {
        {0, 3, 4}, {0, 4, 1}, // Segment 1
        {1, 4, 5}, {1, 5, 2}, // Segment 2
        {2, 5, 3}, {2, 3, 0}  // Segment 3
    };

    std::cout << "--- 1. Annulus Spatial Struct Initialization ---\n";
    parallel_spatial_sort(annulus_vertices, annulus_faces);
    std::cout << "Parallelized Morton sorting applied successfully.\n\n";

    // Build standard chain structures
    std::vector<OrientedEdge> edges;
    SparseMatrix d1, d2;
    compute_boundary_operators(annulus_faces, edges, d1, d2);

    std::cout << "--- 2. Simplicial Complex Counts ---\n";
    std::cout << "Vertices (0-cells): " << annulus_vertices.size() << "\n";
    std::cout << "Edges    (1-cells): " << edges.size() << "\n";
    std::cout << "Faces    (2-cells): " << annulus_faces.size() << "\n\n";

    // ==========================================================
    // EVALUATING DEC HODGE STAR MATRIX OPERATORS
    // ==========================================================
    std::vector<double> star0, star1, star2;
    compute_dec_hodge_stars(annulus_vertices, annulus_faces, edges, star0, star1, star2);

    std::cout << "--- 3. Discrete Exterior Calculus Hodge Star Ratios ---\n";
    std::cout << "Diagonal Primal-to-Dual Hodge Star 0 (Voronoi Areas):\n  [";
    for(double val : star0) std::cout << val << " ";
    std::cout << "]\n";

    std::cout << "Diagonal Primal-to-Dual Hodge Star 1 (Cotangent Coefficients):\n  [";
    for(double val : star1) std::cout << val << " ";
    std::cout << "]\n";

    std::cout << "Diagonal Primal-to-Dual Hodge Star 2 (1 / Triangle Areas):\n  [";
    for(double val : star2) std::cout << val << " ";
    std::cout << "]\n\n";

    // ==========================================================
    // ISOLATING COHOMOLOGICAL GENERATORS MATRIX MAPS
    // ==========================================================
    // Convert sparse d1 to dense format for nullspace evaluation
    std::vector<std::vector<double>> dense_d1(annulus_vertices.size(), std::vector<double>(edges.size(), 0.0));
    for (const auto& entry : d1) {
        dense_d1[entry.row][entry.col] = entry.value;
    }

    // Extract cycle kernel space Z1 = ker(d1)
    std::vector<std::vector<double>> cycle_basis = compute_matrix_kernel(dense_d1, annulus_vertices.size(), edges.size());
    std::cout << "--- 4. Homological Analysis (Z1 space) ---\n";
    std::cout << "Extracted Vector Dimension of Primal 1-Cycles dim(Z_1): " << cycle_basis.size() << "\n";

    // Project out image spaces B1 = im(d2) to find pure independent generator loops H1 = Z1 / B1
    std::vector<std::vector<double>> non_trivial_generators = isolate_homology_generators(
        d2, static_cast<uint32_t>(edges.size()), static_cast<uint32_t>(annulus_faces.size()), cycle_basis
    );

    std::cout << "\n--- 5. Isolated Non-Trivial Homological Generators dim(H_1) ---\n";
    std::cout << "Isolated Generator Basis Vector Count: " << non_trivial_generators.size() << "\n";
    for (size_t i = 0; i < non_trivial_generators.size(); ++i) {
        std::cout << "Generator Loop [" << i << "] over Edge Space:\n  ";
        for (double val : non_trivial_generators[i]) {
            std::cout << (std::abs(val) > 1e-5 ? (val > 0 ? "+1 " : "-1 ") : "0 ");
        }
        std::cout << "\n";
    }

    return 0;
}
