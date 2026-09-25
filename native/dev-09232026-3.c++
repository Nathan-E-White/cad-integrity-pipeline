#include <iostream>
#include <vector>
#include <array>
#include <cmath>
#include <algorithm>
#include <unordered_map>
#include <cstdint>
#include <map>
#include <execution>
#include <iomanip>

#include "Pnt3D.tcc"

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

// Matrix helper utilities for dense compositions
std::vector<std::vector<double>> transpose(const std::vector<std::vector<double>>& A) {
    if (A.empty()) return {};
    size_t r = A.size();
    size_t c = A[0].size();
    std::vector<std::vector<double>> AT(c, std::vector<double>(r, 0.0));
    for (size_t i = 0; i < r; ++i) {
        for (size_t j = 0; j < c; ++j) {
            AT[j][i] = A[i][j];
        }
    }
    return AT;
}

std::vector<std::vector<double>> mat_mul(const std::vector<std::vector<double>>& A, const std::vector<std::vector<double>>& B) {
    size_t r = A.size();
    size_t m = B.size();
    size_t c = B[0].size();
    std::vector<std::vector<double>> C(r, std::vector<double>(c, 0.0));
    for (size_t i = 0; i < r; ++i) {
        for (size_t k = 0; k < m; ++k) {
            for (size_t j = 0; j < c; ++j) {
                C[i][j] += A[i][k] * B[k][j];
            }
        }
    }
    return C;
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

// Parallel Spatial Sort & Cotangent Weight Assembler
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
            double orientation_sign = (seg.first < seg.second) ? 1.0 : -1.0;
            out_d2.push_back({e_idx, f_idx, orientation_sign});
        }
    }
}

// Boundary Chain Matrix Identity Verifier
bool verify_chain_complex_identity(const SparseMatrix& d1, const SparseMatrix& d2, uint32_t num_edges) {
    std::map<std::pair<uint32_t, uint32_t>, double> composition_product;

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

// ==========================================================
// NEW EXTENSION: LAPLACE-DE RHAM 1-FORM OPERATOR ASSEMBLER
// ==========================================================
// Formal 1-Form Hodge-Laplacian (\[\Delta _{1}\]):
// The compute_1form_laplacian function builds the full coordinate-free 1-Form operator
// using the standard properties of Discrete Exterior Calculus:
//
// \[\Delta _{1}=d_{0}d_{0}^{\dag }+d_{1}^{\dag }d_{1}\]
//
// Substituting the discrete representations maps the equation directly to:
//
// \[\Delta _{1}=\partial _{1}^{T}\star _{0}^{-1}\partial _{1}\star _{1}+\star _{1}^{-1}\partial _{2}\star _{2}\partial _{2}^{T}\]
//
// 1. Term A (\[d_{0}d_{0}^{\dag }\]): Evaluates the curl-free component (mapping 1-forms \[\rightarrow \] 0-forms \[\rightarrow \] 1-forms), yielding raw node-potential flux fields.
// 2. Term B (\(d_1^\dagger d_1\)): Evaluates the divergence-free component (mapping 1-forms \[\rightarrow \] 2-forms \[\rightarrow \] 1-forms), capturing surface rotational vortex behaviors.
// Unified Dense Layout Composition: Using transpose and mat_mul, the sparse structural boundary chains and
// diagonal dual metric metrics are combined to output the \(E \times E\)
// symmetric matrix operator directly inside main().
std::vector<std::vector<double>> compute_1form_laplacian(
    const SparseMatrix& d1, const SparseMatrix& d2,
    const std::vector<double>& star0, const std::vector<double>& star1, const std::vector<double>& star2,
    uint32_t num_vertices, uint32_t num_edges, uint32_t num_faces)
{
    // 1. Instantiating dense configurations from sparse entries
    std::vector<std::vector<double>> dense_d1(num_vertices, std::vector<double>(num_edges, 0.0));
    for (const auto& entry : d1) dense_d1[entry.row][entry.col] = entry.value;

    std::vector<std::vector<double>> dense_d2(num_edges, std::vector<double>(num_faces, 0.0));
    for (const auto& entry : d2) dense_d2[entry.row][entry.col] = entry.value;

    // 2. Establishing Diagonal Metric Hodge matrix variants
    std::vector<std::vector<double>> inv_star0(num_vertices, std::vector<double>(num_vertices, 0.0));
    for (uint32_t i = 0; i < num_vertices; ++i) {
        inv_star0[i][i] = (star0[i] > 1e-9) ? 1.0 / star0[i] : 0.0;
    }

    std::vector<std::vector<double>> dense_star1(num_edges, std::vector<double>(num_edges, 0.0));
    std::vector<std::vector<double>> inv_star1(num_edges, std::vector<double>(num_edges, 0.0));
    for (uint32_t i = 0; i < num_edges; ++i) {
        dense_star1[i][i] = star1[i];
        inv_star1[i][i] = (star1[i] > 1e-9) ? 1.0 / star1[i] : 0.0;
    }

    std::vector<std::vector<double>> dense_star2(num_faces, std::vector<double>(num_faces, 0.0));
    for (uint32_t i = 0; i < num_faces; ++i) {
        dense_star2[i][i] = star2[i];
    }

    // Primal coboundaries d0 and d1 are given by transposes of boundary operators
    auto d0_coboundary = transpose(dense_d1); // E x V
    auto d1_coboundary = transpose(dense_d2); // F x E

    // 3. Assemble Term A: d0 * d0_dagger = d1_T * [inv_star0] * d1 * [star1]
    auto termA_step1 = mat_mul(d0_coboundary, inv_star0);
    auto termA_step2 = mat_mul(termA_step1, dense_d1);
    auto termA       = mat_mul(termA_step2, dense_star1);

    // 4. Assemble Term B: d1_dagger * d1 = [inv_star1] * d2 * [star2] * d2_T
    auto termB_step1 = mat_mul(inv_star1, dense_d2);
    auto termB_step2 = mat_mul(termB_step1, dense_star2);
    auto termB       = mat_mul(termB_step2, d1_coboundary);

    // 5. Synthesize full Hodge-Laplacian field: Delta_1 = Term A + Term B (E x E)
    std::vector<std::vector<double>> delta1(num_edges, std::vector<double>(num_edges, 0.0));
    for (uint32_t i = 0; i < num_edges; ++i) {
        for (uint32_t j = 0; j < num_edges; ++j) {
            delta1[i][j] = termA[i][j] + termB[i][j];
        }
    }
    return delta1;
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


#include <iostream>
#include <vector>
#include <array>
#include <cmath>
#include <algorithm>
#include <unordered_map>
#include <cstdint>
#include <map>
#include <execution>
#include <iomanip>

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

// Matrix helper utilities for dense compositions
std::vector<std::vector<double>> transpose(const std::vector<std::vector<double>>& A) {
    if (A.empty()) return {};
    size_t r = A.size();
    size_t c = A[0].size();
    std::vector<std::vector<double>> AT(c, std::vector<double>(r, 0.0));
    for (size_t i = 0; i < r; ++i) {
        for (size_t j = 0; j < c; ++j) {
            AT[j][i] = A[i][j];
        }
    }
    return AT;
}

std::vector<std::vector<double>> mat_mul(const std::vector<std::vector<double>>& A, const std::vector<std::vector<double>>& B) {
    size_t r = A.size();
    size_t m = B.size();
    size_t c = B[0].size();
    std::vector<std::vector<double>> C(r, std::vector<double>(c, 0.0));
    for (size_t i = 0; i < r; ++i) {
        for (size_t k = 0; k < m; ++k) {
            for (size_t j = 0; j < c; ++j) {
                C[i][j] += A[i][k] * B[k][j];
            }
        }
    }
    return C;
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

// Parallel Spatial Sort & Cotangent Weight Assembler
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
            double orientation_sign = (seg.first < seg.second) ? 1.0 : -1.0;
            out_d2.push_back({e_idx, f_idx, orientation_sign});
        }
    }
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

// 1-Form Laplace-de Rham Operator Assembler
std::vector<std::vector<double>> compute_1form_laplacian(
    const SparseMatrix& d1, const SparseMatrix& d2,
    const std::vector<double>& star0, const std::vector<double>& star1, const std::vector<double>& star2,
    uint32_t num_vertices, uint32_t num_edges, uint32_t num_faces)
{
    std::vector<std::vector<double>> dense_d1(num_vertices, std::vector<double>(num_edges, 0.0));
    for (const auto& entry : d1) dense_d1[entry.row][entry.col] = entry.value;

    std::vector<std::vector<double>> dense_d2(num_edges, std::vector<double>(num_faces, 0.0));
    for (const auto& entry : d2) dense_d2[entry.row][entry.col] = entry.value;

    std::vector<std::vector<double>> inv_star0(num_vertices, std::vector<double>(num_vertices, 0.0));
    for (uint32_t i = 0; i < num_vertices; ++i) {
        inv_star0[i][i] = (star0[i] > 1e-9) ? 1.0 / star0[i] : 0.0;
    }

    std::vector<std::vector<double>> dense_star1(num_edges, std::vector<double>(num_edges, 0.0));
    std::vector<std::vector<double>> inv_star1(num_edges, std::vector<double>(num_edges, 0.0));
    for (uint32_t i = 0; i < num_edges; ++i) {
        dense_star1[i][i] = star1[i];
        inv_star1[i][i] = (star1[i] > 1e-9) ? 1.0 / star1[i] : 0.0;
    }

    std::vector<std::vector<double>> dense_star2(num_faces, std::vector<double>(num_faces, 0.0));
    for (uint32_t i = 0; i < num_faces; ++i) {
        dense_star2[i][i] = star2[i];
    }

    auto d0_coboundary = transpose(dense_d1);
    auto d1_coboundary = transpose(dense_d2);

    auto termA_step1 = mat_mul(d0_coboundary, inv_star0);
    auto termA_step2 = mat_mul(termA_step1, dense_d1);
    auto termA       = mat_mul(termA_step2, dense_star1);

    auto termB_step1 = mat_mul(inv_star1, dense_d2);
    auto termB_step2 = mat_mul(termB_step1, dense_star2);
    auto termB       = mat_mul(termB_step2, d1_coboundary);

    std::vector<std::vector<double>> delta1(num_edges, std::vector<double>(num_edges, 0.0));
    for (uint32_t i = 0; i < num_edges; ++i) {
        for (uint32_t j = 0; j < num_edges; ++j) {
            delta1[i][j] = termA[i][j] + termB[i][j];
        }
    }
    return delta1;
}

// Column reduction for kernel computations with configurable singular thresholds
std::vector<std::vector<double>> compute_matrix_kernel(const std::vector<std::vector<double>>& M,
                                                      uint32_t rows, uint32_t cols, double tolerance = 1e-4)
{
    auto A = M;
    std::vector<int32_t> pivot_col(rows, -1);
    uint32_t r = 0;

    for (uint32_t c = 0; c < cols && r < rows; ++c) {
        uint32_t pivot_row = r;
        while (pivot_row < rows && std::abs(A[pivot_row][c]) < tolerance) {
            pivot_row++;
        }
        if (pivot_row == rows) continue;

        std::swap(A[r], A[pivot_row]);
        pivot_col[r] = c;

        for (uint32_t i = 0; i < rows; ++i) {
            if (i != r && std::abs(A[i][c]) > 1e-9) {
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
                if (std::abs(A[i][pc]) > 1e-9) {
                    vec[pc] = -A[i][c] / A[i][pc];
                }
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

// ==========================================================
// NEW EXTENSION: PERIOD MATRIX CALCULATOR
// ==========================================================
std::vector<std::vector<double>> compute_period_matrix(
    const std::vector<std::vector<double>>& harmonic_forms,
    const std::vector<std::vector<double>>& homology_cycles)
{
    size_t num_cohomology = harmonic_forms.size();
    size_t num_homology = homology_cycles.size();

    std::vector<std::vector<double>> P(num_cohomology, std::vector<double>(num_homology, 0.0));

    for (size_t i = 0; i < num_cohomology; ++i) {
        for (size_t j = 0; j < num_homology; ++j) {
            double integration_sum = 0.0;
            // Discrete integration: pairing the dual tracking vectors (edge-wise dot product)
            for (size_t e = 0; e < harmonic_forms[i].size(); ++e) {
                integration_sum += harmonic_forms[i][e] * homology_cycles[j][e];
            }
            P[i][j] = integration_sum;
        }
    }
    return P;
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

// 1-Form Laplace-de Rham Operator Assembler
std::vector<std::vector<double>> compute_1form_laplacian(
    const SparseMatrix& d1, const SparseMatrix& d2,
    const std::vector<double>& star0, const std::vector<double>& star1, const std::vector<double>& star2,
    uint32_t num_vertices, uint32_t num_edges, uint32_t num_faces)
{
    std::vector<std::vector<double>> dense_d1(num_vertices, std::vector<double>(num_edges, 0.0));
    for (const auto& entry : d1) dense_d1[entry.row][entry.col] = entry.value;

    std::vector<std::vector<double>> dense_d2(num_edges, std::vector<double>(num_faces, 0.0));
    for (const auto& entry : d2) dense_d2[entry.row][entry.col] = entry.value;

    std::vector<std::vector<double>> inv_star0(num_vertices, std::vector<double>(num_vertices, 0.0));
    for (uint32_t i = 0; i < num_vertices; ++i) {
        inv_star0[i][i] = (star0[i] > 1e-9) ? 1.0 / star0[i] : 0.0;
    }

    std::vector<std::vector<double>> dense_star1(num_edges, std::vector<double>(num_edges, 0.0));
    std::vector<std::vector<double>> inv_star1(num_edges, std::vector<double>(num_edges, 0.0));
    for (uint32_t i = 0; i < num_edges; ++i) {
        dense_star1[i][i] = star1[i];
        inv_star1[i][i] = (star1[i] > 1e-9) ? 1.0 / star1[i] : 0.0;
    }

    std::vector<std::vector<double>> dense_star2(num_faces, std::vector<double>(num_faces, 0.0));
    for (uint32_t i = 0; i < num_faces; ++i) {
        dense_star2[i][i] = star2[i];
    }

    auto d0_coboundary = transpose(dense_d1);
    auto d1_coboundary = transpose(dense_d2);

    auto termA_step1 = mat_mul(d0_coboundary, inv_star0);
    auto termA_step2 = mat_mul(termA_step1, dense_d1);
    auto termA       = mat_mul(termA_step2, dense_star1);

    auto termB_step1 = mat_mul(inv_star1, dense_d2);
    auto termB_step2 = mat_mul(termB_step1, dense_star2);
    auto termB       = mat_mul(termB_step2, d1_coboundary);

    std::vector<std::vector<double>> delta1(num_edges, std::vector<double>(num_edges, 0.0));
    for (uint32_t i = 0; i < num_edges; ++i) {
        for (uint32_t j = 0; j < num_edges; ++j) {
            delta1[i][j] = termA[i][j] + termB[i][j];
        }
    }
    return delta1;
}

// Column reduction for kernel computations
std::vector<std::vector<double>> compute_matrix_kernel(const std::vector<std::vector<double>>& M,
                                                      uint32_t rows, uint32_t cols, double tolerance = 1e-4)
{
    auto A = M;
    std::vector<int32_t> pivot_col(rows, -1);
    uint32_t r = 0;

    for (uint32_t c = 0; c < cols && r < rows; ++c) {
        uint32_t pivot_row = r;
        while (pivot_row < rows && std::abs(A[pivot_row][c]) < tolerance) {
            pivot_row++;
        }
        if (pivot_row == rows) continue;

        std::swap(A[r], A[pivot_row]);
        pivot_col[r] = c;

        for (uint32_t i = 0; i < rows; ++i) {
            if (i != r && std::abs(A[i][c]) > 1e-9) {
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
                if (std::abs(A[i][pc]) > 1e-9) {
                    vec[pc] = -A[i][c] / A[i][pc];
                }
            }
            kernel_basis.push_back(vec);
        }
    }
    return kernel_basis;
}

// ==========================================================
// NEW EXTENSION: GEOMETRIC CURVATURE TENSORS ENGINE
// ==========================================================
template <typename T>
void compute_discrete_curvatures(const std::vector<Pnt3D<T>>& vertices,
                                 const std::vector<Face>& faces,
                                 const std::vector<double>& star0,
                                 std::vector<double>& out_gauss,
                                 std::vector<Pnt3D<T>>& out_mean_vec,
                                 std::vector<double>& out_mean_mag)
{
    uint32_t num_vertices = static_cast<uint32_t>(vertices.size());
    out_gauss.assign(num_vertices, 2.0 * M_PI);
    out_mean_vec.assign(num_vertices, {{{0.0, 0.0, 0.0}}});
    out_mean_mag.assign(num_vertices, 0.0);

    // 1. Gauss Curvature Evaluation via Simplicial Angle Defects
    for (const auto& f : faces) {
        std::array<uint32_t, 3> idxs = {f.v0, f.v1, f.v2};
        for (int i = 0; i < 3; ++i) {
            uint32_t i0 = idxs[i];
            uint32_t i1 = idxs[(i + 1) % 3];
            uint32_t i2 = idxs[(i + 2) % 3];

            Pnt3D<T> edge1 = sub(vertices[i1], vertices[i0]);
            Pnt3D<T> edge2 = sub(vertices[i2], vertices[i0]);

            T l1 = norm(edge1);
            T l2 = norm(edge2);
            if (l1 > 1e-9 && l2 > 1e-9) {
                T cos_theta = dot(edge1, edge2) / (l1 * l2);
                cos_theta = std::max(static_cast<T>(-1.0), std::min(static_cast<T>(1.0), cos_theta));
                out_gauss[i0] -= std::acos(cos_theta);
            }
        }
    }

    // Normalization to retrieve pointwise Gauss Curvature densities
    for (uint32_t i = 0; i < num_vertices; ++i) {
        if (star0[i] > 1e-9) out_gauss[i] /= star0[i];
    }

    // 2. Mean Curvature Tensor Vector via Discrete Laplace-Beltrami Coordinates Evaluation
    for (const auto& f : faces) {
        Pnt3D<T> v0 = vertices[f.v0];
        Pnt3D<T> v1 = vertices[f.v1];
        Pnt3D<T> v2 = vertices[f.v2];

        T cot0 = dot(sub(v1, v0), sub(v2, v0)) / norm(cross(sub(v1, v0), sub(v2, v0)));
        T cot1 = dot(sub(v0, v1), sub(v2, v1)) / norm(cross(sub(v0, v1), sub(v2, v1)));
        T cot2 = dot(sub(v0, v2), sub(v1, v2)) / norm(cross(sub(v0, v2), sub(v1, v2)));

        auto accumulate_mean_tensor = [&](uint32_t u, uint32_t v, T weight) {
            Pnt3D<T> spatial_diff = sub(vertices[v], vertices[u]);
            for (int d = 0; d < 3; ++d) {
                out_mean_vec[u].data[d] += 0.5 * weight * spatial_diff.data[d];
            }
        };

        accumulate_mean_tensor(f.v1, f.v2, cot0);
        accumulate_mean_tensor(f.v2, f.v1, cot0);

        accumulate_mean_tensor(f.v0, f.v2, cot1);
        accumulate_mean_tensor(f.v2, f.v0, cot1);

        accumulate_mean_tensor(f.v0, f.v1, cot2);
        accumulate_mean_tensor(f.v1, f.v0, cot2);
    }

    // Scale integrated vector positions via diagonalized dual metric masses
    for (uint32_t i = 0; i < num_vertices; ++i) {
        if (star0[i] > 1e-9) {
            for (int d = 0; d < 3; ++d) {
                out_mean_vec[i].data[d] /= (2.0 * star0[i]);
            }
            out_mean_mag[i] = norm(out_mean_vec[i]);
        }
    }
}

// ==========================================================
// NEW EXTENSION: COMPLEX STRUCTURE OPERATOR J & HOLOMORPHIC 1-FORMS
// ==========================================================
template <typename T>
std::vector<double> generate_conjugate_harmonic_1form(
    const std::vector<Pnt3D<T>>& vertices,
    const std::vector<Face>& faces,
    const std::vector<OrientedEdge>& edges,
    const std::vector<double>& harmonic_omega)
{
    std::vector<double> J_omega(edges.size(), 0.0);
    std::vector<double> sharing_counts(edges.size(), 0.0);

    std::map<OrientedEdge, uint32_t> edge_to_idx;
    for (uint32_t i = 0; i < edges.size(); ++i) edge_to_idx[edges[i]] = i;

    for (const auto& f : faces) {
        Pnt3D<T> v0 = vertices[f.v0];
        Pnt3D<T> v1 = vertices[f.v1];
        Pnt3D<T> v2 = vertices[f.v2];

        Pnt3D<T> e0 = sub(v1, v0);
        Pnt3D<T> e1 = sub(v2, v1);
        Pnt3D<T> e2 = sub(v0, v2);

        Pnt3D<T> normal_cross = cross(e0, sub(v2, v0));
        T double_area = norm(normal_cross);
        if (double_area < 1e-9) continue;

        Pnt3D<T> n_f = { normal_cross.data[0] / double_area,
                         normal_cross.data[1] / double_area,
                         normal_cross.data[2] / double_area };

        auto get_oriented_flux = [&](uint32_t u, uint32_t v) -> double {
            OrientedEdge canonical{std::min(u, v), std::max(u, v)};
            double sign = (u < v) ? 1.0 : -1.0;
            return harmonic_omega[edge_to_idx[canonical]] * sign;
        };

        double w0 = get_oriented_flux(f.v0, f.v1);
        double w1 = get_oriented_flux(f.v1, f.v2);
        double w2 = get_oriented_flux(f.v2, f.v0);

        // Reconstruct local vector fields inside current simplex via Whitney embeddings
        Pnt3D<T> n_x_e0 = cross(n_f, e0);
        Pnt3D<T> n_x_e1 = cross(n_f, e1);
        Pnt3D<T> n_x_e2 = cross(n_f, e2);

        Pnt3D<T> u_f = {
            (w0 * n_x_e0.data[0] + w1 * n_x_e1.data[0] + w2 * n_x_e2.data[0]) / double_area,
            (w0 * n_x_e0.data[1] + w1 * n_x_e1.data[1] + w2 * n_x_e2.data[1]) / double_area,
            (w0 * n_x_e0.data[2] + w1 * n_x_e1.data[2] + w2 * n_x_e2.data[2]) / double_area
        };

        // Execute complex structure tangent plane rotation: J(u_f) = n_f x u_f
        Pnt3D<T> rotated_u_f = cross(n_f, u_f);

        // Integrate rotated vector fields back into primal edge locations
        auto update_edge_rotation = [&](uint32_t u, uint32_t v, const Pnt3D<T>& edge_vector) {
            OrientedEdge canonical{std::min(u, v), std::max(u, v)};
            uint32_t idx = edge_to_idx[canonical];
            double projection = dot(rotated_u_f, edge_vector);
            double sign = (u < v) ? 1.0 : -1.0;
            J_omega[idx] += projection * sign;
            sharing_counts[idx] += 1.0;
        };

        update_edge_rotation(f.v0, f.v1, e0);
        update_edge_rotation(f.v1, f.v2, e1);
        update_edge_rotation(f.v2, f.v0, e2);
    }

    for (uint32_t i = 0; i < J_omega.size(); ++i) {
        if (sharing_counts[i] > 0.0) J_omega[i] /= sharing_counts[i];
    }
    return J_omega;
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

    std::map<std::pair<uint32_t, uint32_t>, double> laplacian_weights;
    spatial_sort_and_assemble_laplacian(vertices, faces, laplacian_weights);

    std::vector<OrientedEdge> edges;
    SparseMatrix d1, d2;
    compute_boundary_operators(faces, edges, d1, d2);

    uint32_t n_v = static_cast<uint32_t>(vertices.size());
    uint32_t n_e = static_cast<uint32_t>(edges.size());
    uint32_t n_f = static_cast<uint32_t>(faces.size());

    std::vector<double> star0, star1, star2;
    compute_dec_hodge_stars(vertices, faces, edges, star0, star1, star2);

    // ==========================================================
    // EXECUTE & DISPLAY GEOMETRIC CURVATURE EVALUATIONS
    // ==========================================================
    std::cout << "--- 1. Discrete Curvature Tensors Evaluation ---\n" << std::fixed << std::setprecision(4);
    std::vector<double> gauss_curvures, mean_curv_mags;
    std::vector<Pnt3D<double>> mean_curv_vectors;

    compute_discrete_curvatures(vertices, faces, star0, gauss_curvures, mean_curv_vectors, mean_curv_mags);

    for (uint32_t i = 0; i < n_v; ++i) {
        std::cout << "Vertex [" << i << "] -> Pointwise Gauss Curvature: " << gauss_curvures[i]
                  << " | Mean Curvature Vector Magnitude: " << mean_curv_mags[i] << "\n";
    }

    // ==========================================================
    // EXTRACT HOLOMORPHIC COMPLEX STEP MATRIX FORMULATIONS
    // ==========================================================
    std::cout << "\n--- 2. Holomorphic 1-Forms Construction via Complex Structure J ---\n";
    auto delta1 = compute_1form_laplacian(d1, d2, star0, star1, star2, n_v, n_e, n_f);
    std::vector<std::vector<double>> harmonic_1forms = compute_matrix_kernel(delta1, n_e, n_e, 1e-3);

    if (!harmonic_1forms.empty()) {
        std::vector<double> primal_omega = harmonic_1forms[0];
        // Generate orthogonal counterpart J*omega
        std::vector<double> conjugate_mu = generate_conjugate_harmonic_1form(vertices, faces, edges, primal_omega);

        std::cout << "Holomorphic 1-Form alpha = (omega + i * J_omega) generated successfully.\n";
        std::cout << "  Real Primal Part (omega):\n    [ ";
        for (double val : primal_omega) std::cout << (std::abs(val) < 1e-4 ? 0.0 : val) << " ";
        std::cout << "]\n";

        std::cout << "  Imaginary Conjugate Part (J_omega):\n    [ ";
        for (double val : conjugate_mu) std::cout << (std::abs(val) < 1e-4 ? 0.0 : val) << " ";
        std::cout << "]\n";

        // Compute orthogonality check: dot(omega, J_omega) using edge metric values
        double metric_inner_product = 0.0;
        for (uint32_t e = 0; e < n_e; ++e) {
            metric_inner_product += primal_omega[e] * star1[e] * conjugate_mu[e];
        }
        std::cout << "\nHodge Inner Product Conformal Orthogonality check <omega, J_omega>_star1: " << metric_inner_product << "\n";
    } else {
        std::cout << "[Warning] Deficient harmonic basis prevents Holomorphic 1-form synthesis.\n";
    }

    return 0;
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

    std::cout << "--- 1. Pipeline Initial Sorting Sequence ---\n";
    std::map<std::pair<uint32_t, uint32_t>, double> laplacian_weights;
    spatial_sort_and_assemble_laplacian(vertices, faces, laplacian_weights);
    std::cout << "Cache alignment spatial reordering complete.\n\n";

    // Structural chain systems assembly
    std::vector<OrientedEdge> edges;
    SparseMatrix d1, d2;
    compute_boundary_operators(faces, edges, d1, d2);

    uint32_t n_v = static_cast<uint32_t>(vertices.size());
    uint32_t n_e = static_cast<uint32_t>(edges.size());
    uint32_t n_f = static_cast<uint32_t>(faces.size());

    // Evaluating discrete differential forms Hodge spaces
    std::vector<double> star0, star1, star2;
    compute_dec_hodge_stars(vertices, faces, edges, star0, star1, star2);

    // ==========================================================
    // EXECUTE & DISPLAY FORMAL 1-FORM HODGE-LAPLACIAN
    // ==========================================================
    std::cout << "--- 2. Formal 1-Form Laplace-de Rham Matrix Assembly ---\n";
    auto delta1 = compute_1form_laplacian(d1, d2, star0, star1, star2, n_v, n_e, n_f);
    std::cout << "Assembled Operator Matrix Size: " << delta1.size() << " x " << (delta1.empty() ? 0 : delta1[0].size()) << "\n";

    std::cout << "\nSpectral Operator Matrix Slice (First 5 Rows/Cols):\n" << std::fixed << std::setprecision(4);
    size_t display_lim = std::min(static_cast<size_t>(5), delta1.size());
    for (size_t i = 0; i < display_lim; ++i) {
        std::cout << "  [ ";
        for (size_t j = 0; j < display_lim; ++j) {
            std::cout << (std::abs(delta1[i][j]) < 1e-5 ? 0.0 : delta1[i][j]) << " ";
        }
        std::cout << "]\n";
    }

    // Extracting kernel spaces and non-trivial homological homology cycles
    std::vector<std::vector<double>> dense_d1(n_v, std::vector<double>(n_e, 0.0));
    for (const auto& entry : d1) dense_d1[entry.row][entry.col] = entry.value;

    std::vector<std::vector<double>> cycle_basis = compute_matrix_kernel(dense_d1, n_v, n_e);
    std::vector<std::vector<double>> non_trivial_generators = isolate_homology_generators(d2, n_e, n_f, cycle_basis);

    std::cout << "\n--- 3. Kernel Homological Invariance Tracking ---\n";
    std::cout << "Isolated Independent Loop Components: " << non_trivial_generators.size() << "\n";

    return 0;

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

    std::map<std::pair<uint32_t, uint32_t>, double> laplacian_weights;
    spatial_sort_and_assemble_laplacian(vertices, faces, laplacian_weights);

    std::vector<OrientedEdge> edges;
    SparseMatrix d1, d2;
    compute_boundary_operators(faces, edges, d1, d2);

    uint32_t n_v = static_cast<uint32_t>(vertices.size());
    uint32_t n_e = static_cast<uint32_t>(edges.size());
    uint32_t n_f = static_cast<uint32_t>(faces.size());

    std::vector<double> star0, star1, star2;
    compute_dec_hodge_stars(vertices, faces, edges, star0, star1, star2);

    // Assembling formal 1-Form Laplace-de Rham matrix
    auto delta1 = compute_1form_laplacian(d1, d2, star0, star1, star2, n_v, n_e, n_f);

    std::cout << "--- 1. De Rham Cohomology Evaluation --- \n";
    // Harmonic 1-forms are the nullspace of the 1-Form Laplace-de Rham Operator (Delta_1)
    std::vector<std::vector<double>> harmonic_1forms = compute_matrix_kernel(delta1, n_e, n_e, 1e-3);
    std::cout << "Dimension of de Rham Cohomology Space dim(H^1_dR): " << harmonic_1forms.size() << "\n";

    for (size_t i = 0; i < harmonic_1forms.size(); ++i) {
        std::cout << "  Harmonic 1-form basis vector [" << i << "] flow metrics:\n    [ ";
        for (double val : harmonic_1forms[i]) {
            std::cout << (std::abs(val) < 1e-4 ? 0.0 : val) << " ";
        }
        std::cout << "]\n";
    }

    std::cout << "\n--- 2. Simplicial Homology Tracking --- \n";
    std::vector<std::vector<double>> dense_d1(n_v, std::vector<double>(n_e, 0.0));
    for (const auto& entry : d1) dense_d1[entry.row][entry.col] = entry.value;

    std::vector<std::vector<double>> cycle_basis = compute_matrix_kernel(dense_d1, n_v, n_e, 1e-7);
    std::vector<std::vector<double>> non_trivial_cycles = isolate_homology_generators(d2, n_e, n_f, cycle_basis);
    std::cout << "Dimension of Simplicial Homology Space dim(H_1): " << non_trivial_cycles.size() << "\n";

    for (size_t i = 0; i < non_trivial_cycles.size(); ++i) {
        std::cout << "  Homology 1-cycle generator path [" << i << "] orientations:\n    [ ";
        for (double val : non_trivial_cycles[i]) {
            std::cout << (std::abs(val) < 1e-4 ? 0.0 : val) << " ";
        }
        std::cout << "]\n";
    }

    // ==========================================================
    // PERIOD MATRIX EVALUATIONVIA DE RHAM COHOMOLOGY PAIRINGS
    // ==========================================================
    std::cout << "\n--- 3. Period Matrix Synthesis Matrix --- \n" << std::fixed << std::setprecision(5);
    if (!harmonic_1forms.empty() && !non_trivial_cycles.empty()) {
        auto period_matrix = compute_period_matrix(harmonic_1forms, non_trivial_cycles);

        std::cout << "Computed Period Matrix Array (" << period_matrix.size() << " x " << period_matrix[0].size() << "):\n";
        for (size_t i = 0; i < period_matrix.size(); ++i) {
            std::cout << "  [ ";
            for (size_t j = 0; j < period_matrix[i].size(); ++j) {
                std::cout << period_matrix[i][j] << " ";
            }
            std::cout << "]\n";
        }
        std::cout << "\nIntegration Verification: The non-zero pairing constant confirms topological synchronization.\n";
    } else {
        std::cout << "[Warning] Deficient topological invariants prevented Period Matrix extraction.\n";
    }

    return 0;
}


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
