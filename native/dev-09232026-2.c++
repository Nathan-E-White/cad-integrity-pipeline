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

// O(N) duplicate vertex deduplication with tolerance
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

// ==========================================================
// RESTORED FUNCTION: PARALLEL SPATIAL SORT & LAPLACIAN ASSEMBLER
// ==========================================================
template <typename T>
void spatial_sort_and_assemble_laplacian(std::vector<Pnt3D<T>>& vertices,
                                         std::vector<Face>& faces,
                                         std::map<std::pair<uint32_t, uint32_t>, T>& out_laplacian)
{
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

    // Parallelized sorting using C++17 execution policy
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

    auto add_weight = [&](uint32_t i, uint32_t j, T weight) {
        if (i > j) std::swap(i, j);
        out_laplacian[{i, j}] += weight;
    };

    for (const auto& f : faces) {
        Pnt3D<T> v0 = vertices[f.v0];
        Pnt3D<T> v1 = vertices[f.v1];
        Pnt3D<T> v2 = vertices[f.v2];

        T cot0 = dot(sub(v1, v0), sub(v2, v0)) / norm(cross(sub(v1, v0), sub(v2, v0)));
        T cot1 = dot(sub(v0, v1), sub(v2, v1)) / norm(cross(sub(v0, v1), sub(v2, v1)));
        T cot2 = dot(sub(v0, v2), sub(v1, v2)) / norm(cross(sub(v0, v2), sub(v1, v2)));

        add_weight(f.v1, f.v2, cot0 * 0.5);
        add_weight(f.v0, f.v2, cot1 * 0.5);
        add_weight(f.v0, f.v1, cot2 * 0.5);
    }
}

// Boundary Chain Operator extraction
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
            double orientation_sign = (seg.first , double> composition_product;

    std::vector<std::vector<std::pair<uint32_t, double>>> d1_by_col(num_edges);
    for (const auto& entry : d1) {
        d1_by_col[entry.col].push_back({entry.row, entry.value});
    }

    for (const auto& entry2 : d2) {
        uint32_t e = static_cast<uint32_t>(entry2.row);
        uint32_t f = static_cast<uint32_t>(entry2.col);
        double val2 = entry2.value;

        for (const auto& entry1 : d1_by_col[e]) {
            uint32_t v = entry1.first;
            double val1 = entry1.second;
            composition_product[{v, f}] += val1 * val2;
        }
    }

    for (const auto& item : composition_product) {
        if (std::abs(item.second) > 1e-7) {
            return false;
        }
    }
    return true;
}

// Discrete Exterior Calculus Hodge Star matrices setup
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

    std::map<OrientedEdge, uint32_t> edge_to_idx;
    for (uint32_t i = 0; i < edges.size(); ++i) {
        edge_to_idx[edges[i]] = i;
    }

    for (uint32_t f_idx = 0; f_idx < faces.size(); ++f_idx) {
        const auto& f = faces[f_idx];
        Pnt3D<T> v0 = vertices[f.v0];
        Pnt3D<T> v1 = vertices[f.v1];
        Pnt3D<T> v2 = vertices[f.v2];

        T area = norm(cross(sub(v1, v0), sub(v2, v0))) * 0.5;
        out_star2[f_idx] = (area > 1e-9) ? (1.0 / area) : 0.0;

        double barycentric_contribution = area / 3.0;
        out_star0[f.v0] += barycentric_contribution;
        out_star0[f.v1] += barycentric_contribution;
        out_star0[f.v2] += barycentric_contribution;

        double cot0 = dot(sub(v1, v0), sub(v2, v0)) / norm(cross(sub(v1, v0), sub(v2, v0)));
        double cot1 = dot(sub(v0, v1), sub(v2, v1)) / norm(cross(sub(v0, v1), sub(v2, v1)));
        double cot2 = dot(sub(v0, v2), sub(v1, v2)) / norm(cross(sub(v0, v2), sub(v1, v2)));

        auto accumulate_edge_star = [&](uint32_t u, uint32_t v, double cot_val) {
            OrientedEdge canonical{std::min(u, v), std::max(u, v)};
            out_star1[edge_to_idx[canonical]] += cot_val * 0.5;
        };

        accumulate_edge_star(f.v1, f.v2, cot0);
        accumulate_edge_star(f.v0, f.v2, cot1);
        accumulate_edge_star(f.v0, f.v1, cot2);
    }
}

// Dense column reduction for kernel matrix computation
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

// Homology groups generators selection (H1 space calculation)
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
        A[static_cast<uint32_t>(entry.row)][static_cast<uint32_t>(entry.col)] = entry.value;
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
    // Structural multi-segment annulus geometry setup
    std::vector<Pnt3D<double>> vertices = {
        {{1.0, 0.0, 0.0}},    {{-0.5, 0.866, 0.0}}, {{-0.5, -0.866, 0.0}},
        {{2.0, 0.0, 0.0}},    {{-1.0, 1.732, 0.0}}, {{-1.0, -1.732, 0.0}}
    };

    std::vector<Face> faces = {
        {0, 3, 4}, {0, 4, 1},
        {1, 4, 5}, {1, 5, 2},
        {2, 5, 3}, {2, 3, 0}
    };

    std::cout << "--- 1. Pipeline Re-initialization & Sorting ---\n";
    std::map<std::pair<uint32_t, uint32_t>, double> laplacian_weights;

    // Invoking the restored integrated parallel sort & cotangent weight assembler
    spatial_sort_and_assemble_laplacian(vertices, faces, laplacian_weights);
    std::cout << "Spatially sorted vertices and assembled cotangent weights via parallelized sorting policies.\n\n";

    // Structural chain systems assembly
    std::vector<OrientedEdge> edges;
    SparseMatrix d1, d2;
    compute_boundary_operators(faces, edges, d1, d2);

    // Invoking the restored chain complex identity validator
    bool identity_valid = verify_chain_complex_identity(d1, d2, static_cast<uint32_t>(edges.size()));
    std::cout  star0, star1, star2;
    compute_dec_hodge_stars(vertices, faces, edges, star0, star1, star2);

    std::cout << "--- 3. Discrete Exterior Calculus Structural Metrics ---\n";
    std::cout << "Hodge Star 0 entries (Voronoi vertex spaces count): " << star0.size() << "\n";
    std::cout << "Hodge Star 1 entries (Cotangent primal-to-dual maps): " << star1.size() << "\n";
    std::cout << "Hodge Star 2 entries (Inverse triangle dimensions): " << star2.size() << "\n\n";

    // Extracting kernel spaces and non-trivial homological homology cycles
    std::vector<std::vector<double>> dense_d1(vertices.size(), std::vector<double>(edges.size(), 0.0));
    for (const auto& entry : d1) {
        dense_d1[entry.row][entry.col] = entry.value;
    }

    std::vector<std::vector<double>> cycle_basis = compute_matrix_kernel(dense_d1, static_cast<uint32_t>(vertices.size()), static_cast<uint32_t>(edges.size()));
    std::vector<std::vector<double>> non_trivial_generators = isolate_homology_generators(
        d2, static_cast<uint32_t>(edges.size()), static_cast<uint32_t>(faces.size()), cycle_basis
    );

    std::cout << "--- 4. Isolated Non-Trivial Homological Generators dim(H_1) ---\n";
    std::cout << "Isolated Independent Loop Components: " << non_trivial_generators.size() << "\n";

    return 0;
}
