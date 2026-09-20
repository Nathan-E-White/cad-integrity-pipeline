#include <iostream>
#include <vector>
#include <algorithm>
#include <set>
#include <map>
#include <expected>
#include <string>
#include <ranges>
#include <concepts>
#include <mdspan>
#include <linalg>
#include <numeric>
#include <stdfloat>

// Error taxonomy for geometric and resource allocation failures
enum class ComplexError {
    InvalidGeometry,
    RepeatedVertices,
    ResourceLimitExceeded,
    InvalidDimension
};

// String mapping for clear error descriptions
std::string to_string(ComplexError err) {
    switch (err) {
        case ComplexError::InvalidGeometry: return "A simplex requires one or more valid vertex IDs.";
        case ComplexError::RepeatedVertices: return "Repeated vertices detected within a single simplex.";
        case ComplexError::ResourceLimitExceeded: return "Simplex count exceeds the specified max budget.";
        case ComplexError::InvalidDimension: return "Requested dimension is out of bounds for this complex.";
    }
    return "Unknown error.";
}

/**
 * Flat zero allocation inline rep
 */
template <std::size_t Dim>
struct Simplex2 {

    std::array<int, 1 + Dim> vertices {};
    auto operator <=> (const Simplex2 &) const = default;
}

struct CSRKey {
    std::size_t k1;
    std::size_t k2;
    /// Homogeneous comparisons
    auto operator <=> (const CSRKey &) const = default;
    /// Heterogeneous comparisons
    auto operator <=> (const std::pair<std::size_t, std::size_t> & rhs) const {
        return std::tie(k1, k2) <=> std::tie(rhs.first, rhs.second);
    }
}

struct CSRIndexCompare {
    using is_transparent = void;

    auto operator ()(const CSRKey & lhs, const CSRKey & rhs) const -> bool {
        return lhs < rhs;
    }

    auto operator()(const CSRKey & lhs, std::pair<std::size_t, std::size_t> rhs) const -> bool {
        return std::tie(lhs.k1,lhs.k2) < std::tie(rhs.first, rhs.second);
    }

    auto operator()(std::pair<std::size_t,std::size_t> lhs, const CSRKey & rhs) const -> bool {
        return std::tie(lhs.first, lhs.second) < std::tie(rhs.k1, rhs.k2);
    }
}


struct CSRMatrix2 {
    auto data = std::flat_map<CSRKey, std::bfloat16_t, CSRIndexCompare>{};
}

// Immutable representation of a topological simplex with canonical vertex ordering
struct Simplex {

    std::vector<int> vertices;

    size_t dim() const {
        return vertices.empty() ? 0 : vertices.size() - 1;
    }

    // Modern C++20 default spaceship operator for strict lexicographical sorting
    auto operator<=>(const Simplex&) const = default;
};

// Factory function mimicking Python's __post_init__ validation and canonical sorting
std::expected<Simplex, ComplexError> make_simplex(std::vector<int> verts) {
    if (verts.empty()) {
        return std::unexpected(ComplexError::InvalidGeometry);
    }

    // Sort vertices to ensure structural identity (canonical ordering)
    std::sort(verts.begin(), verts.end());

    // Check for adjacent duplicates
    auto it = std::adjacent_find(verts.begin(), verts.end());
    if (it != verts.end()) {
        return std::unexpected(ComplexError::RepeatedVertices);
    }

    return Simplex{ .vertices = std::move(verts) };
}

// Compressed Sparse Row (CSR) matrix representation optimized for boundary operators
struct CSRMatrix {
    std::vector<size_t> row_ptr;
    std::vector<size_t> col_ind;
    std::vector<double> values; // Double precision to integrate natively with std::linalg
    size_t num_rows = 0;
    size_t num_cols = 0;

    void print() const {
        std::cout << "CSR Matrix (" << num_rows << " x " << num_cols << "):\n";
        std::cout << "  row_ptr: ";
        for (auto p : row_ptr) std::cout << p << " ";
        std::cout << "\n  col_ind: ";
        for (auto c : col_ind) std::cout << c << " ";
        std::cout << "\n  values:  ";
        for (auto v : values) std::cout << v << " ";
        std::cout << "\n\n";
    }
};

// Helper structure to sort boundary indices during conversion to CSR format
struct MatrixTriplet {
    size_t row;
    size_t col;
    double value;

    auto operator<=>(const MatrixTriplet&) const = default;
};

// Primary Simplicial Complex class ensuring downward closure property
class SimplicialComplex {
private:
    std::vector<Simplex> simplices_;
    size_t max_dim_ = 0;
    std::vector<std::vector<Simplex>> by_dim_;

    // Private constructor enforcing initialization via factory pattern
    SimplicialComplex(std::vector<Simplex> simplices, size_t max_dim, std::vector<std::vector<Simplex>> by_dim)
        : simplices_(std::move(simplices)), max_dim_(max_dim), by_dim_(std::move(by_dim)) {}

public:
    static std::expected<SimplicialComplex, ComplexError> build(
        const std::vector<std::vector<int>>& facets,
        size_t max_simplices = 50000)
    {
        std::set<Simplex> unique_simplices;

        for (const auto& facet : facets) {
            auto clean_facet_res = make_simplex(facet);
            if (!clean_facet_res) return std::unexpected(clean_facet_res.error());

            const auto& vertices = clean_facet_res->vertices;
            size_t n = vertices.size();
            if (n >= 64) return std::unexpected(ComplexError::ResourceLimitExceeded);

            uint64_t total_faces = (1ULL << n) - 1;
            if (unique_simplices.size() + total_faces > max_simplices) {
                return std::unexpected(ComplexError::ResourceLimitExceeded);
            }

            // Generate full downward closure via powerset bit manipulation
            for (uint64_t i = 1; i <= total_faces; ++i) {
                std::vector<int> face_verts;
                for (size_t j = 0; j < n; ++j) {
                    if ((i >> j) & 1) {
                        face_verts.push_back(vertices[j]);
                    }
                }
                unique_simplices.insert(Simplex{ .vertices = std::move(face_verts) });
            }
        }

        if (unique_simplices.size() > max_simplices) {
            return std::unexpected(ComplexError::ResourceLimitExceeded);
        }

        // Flatten and sort by dimension, then by vertex order
        std::vector<Simplex> all_simplices(unique_simplices.begin(), unique_simplices.end());
        std::sort(all_simplices.begin(), all_simplices.end(), [](const Simplex& a, const Simplex& b) {
            if (a.dim() != b.dim()) return a.dim() < b.dim();
            return a.vertices < b.vertices;
        });

        size_t max_dim = all_simplices.empty() ? 0 : all_simplices.back().dim();
        std::vector<std::vector<Simplex>> by_dim(max_dim + 1);
        for (const auto& s : all_simplices) {
            by_dim[s.dim()].push_back(s);
        }

        return SimplicialComplex(std::move(all_simplices), max_dim, std::move(by_dim));
    }

    std::span<const Simplex> get_simplices_of_dim(size_t d) const {
        if (d < by_dim_.size()) {
            return by_dim_[d];
        }
        return {};
    }

    size_t max_dim() const { return max_dim_; }

    // Generates the d-th boundary operator matrix mapping d-chains to (d-1)-chains
    std::expected<CSRMatrix, ComplexError> boundary_operator(size_t d) const {
        if (d == 0) {
            return CSRMatrix{ .row_ptr = {0}, .num_rows = 0, .num_cols = get_simplices_of_dim(0).size() };
        }

        auto current = get_simplices_of_dim(d);
        auto lower = get_simplices_of_dim(d - 1);

        if (current.empty()) {
            return CSRMatrix{ .row_ptr = std::vector<size_t>(lower.size() + 1, 0), .num_rows = lower.size(), .num_cols = 0 };
        }

        // Establish spatial lookup map for index mapping
        std::map<std::vector<int>, size_t> lower_lookup;
        for (size_t i = 0; i < lower.size(); ++i) {
            lower_lookup[lower[i].vertices] = i;
        }

        std::vector<MatrixTriplet> triplets;

        // Populate elements using the alternating sum formula
        for (size_t j = 0; j < current.size(); ++j) {
            const auto& verts = current[j].vertices;
            for (size_t k = 0; k < verts.size(); ++k) {
                std::vector<int> face_verts;
                face_verts.reserve(verts.size() - 1);
                for (size_t idx = 0; idx < verts.size(); ++idx) {
                    if (idx != k) face_verts.push_back(verts[idx]);
                }

                auto it = lower_lookup.find(face_verts);
                if (it != lower_lookup.end()) {
                    double sign = (k % 2 == 0) ? 1.0 : -1.0;
                    triplets.push_back({ .row = it->second, .col = j, .value = sign });
                }
            }
        }

        // Sort triplets to ensure orderly row accumulation
        std::sort(triplets.begin(), triplets.end());

        CSRMatrix csr;
        csr.num_rows = lower.size();
        csr.num_cols = current.size();
        csr.row_ptr.assign(csr.num_rows + 1, 0);
        csr.col_ind.reserve(triplets.size());
        csr.values.reserve(triplets.size());

        for (const auto& t : triplets) {
            csr.col_ind.push_back(t.col);
            csr.values.push_back(t.value);
            csr.row_ptr[t.row + 1]++;
        }

        // Compute cumulative offset arrays for CSR format mapping
        for (size_t i = 0; i < csr.num_rows; ++i) {
            csr.row_ptr[i + 1] += csr.row_ptr[i];
        }

        return csr;
    }
};

int main() {
    // Define a 2-simplex (a solid triangle layout)
    std::vector<std::vector<int>> facets = { {1, 2, 3} };

    std::cout << "Constructing complex for a filled triangle..." << std::endl;
    auto complex_res = SimplicialComplex::build(facets);

    if (!complex_res) {
        std::cerr << "Initialization Error: " << to_string(complex_res.error()) << std::endl;
        return 1;
    }

    const auto& comp = *complex_res;

    // Verify correct properties across spatial hierarchies
    for (size_t d = 0; d <= comp.max_dim(); ++d) {
        std::cout << "Dimension " << d << " simplex count: " << comp.get_simplices_of_dim(d).size() << "\n";
    }
    std::cout << "\n";

    // Extract the 2-to-1 boundary operator matrix
    auto d2_matrix_res = comp.boundary_operator(2);
    if (!d2_matrix_res) return 1;
    const auto& boundary_2 = *d2_matrix_res;
    boundary_2.print();

    // Demonstrate modern C++26 standard linear algebra using std::mdspan layout conversions
    std::cout << "Converting to dense representation using C++26 std::mdspan & std::linalg...\n";

    std::vector<double> dense_buffer(boundary_2.num_rows * boundary_2.num_cols, 0.0);
    // Bind flat buffer layout into dynamic 2D grid matrix
    std::mdspan dense_matrix(dense_buffer.data(), boundary_2.num_rows, boundary_2.num_cols);

    // Inflate CSR configuration entries into the dense view layout structure
    for (size_t r = 0; r < boundary_2.num_rows; ++r) {
        for (size_t idx = boundary_2.row_ptr[r]; idx < boundary_2.row_ptr[r + 1]; ++idx) {
            size_t c = boundary_2.col_ind[idx];
            dense_matrix[r, c] = boundary_2.values[idx];
        }
    }

    // Set up chain inputs for evaluation
    std::vector<double> input_chain_vector = { 1.0 }; // Exactly one 2-simplex active
    std::vector<double> output_boundary_vector(boundary_2.num_rows, 0.0);

    // Instantiate 1D structural views via standard type deductions
    std::mdspan x_view(input_chain_vector.data(), boundary_2.num_cols);
    std::mdspan y_view(output_boundary_vector.data(), boundary_2.num_rows);

    // Invoke the C++26 matrix-vector compiler-optimized pipeline tool directly
    std::linalg::matrix_vector_product(dense_matrix, x_view, y_view);

    std::cout << "Resulting Boundary 1-Chain coordinates:\n";
    for (size_t i = 0; i < output_boundary_vector.size(); ++i) {
        std::cout << "  Face Index [" << i << "]: coefficient = " << y_view[i] << "\n";
    }

    return 0;
}
