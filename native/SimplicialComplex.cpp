#include <iostream>
#include <vector>
#include <algorithm>
#include <concepts>
#include <expected>
#include <string>
#include <span>
#include <cstdint>
#include <numeric>

// Unifying error tracking using modern lightweight value types
enum class TopologyStatus : uint8_t {
    Success,
    DuplicateVertices,
    BudgetExceeded,
    InvalidDimension
};

inline std::string to_string(TopologyStatus status) {
        switch (status) {
        case TopologyStatus::Success:           return "Success";
        case TopologyStatus::DuplicateVertices: return "Structural error: Duplicate vertices found within a facet.";
        case TopologyStatus::BudgetExceeded:   return "Resource constraint: Complex size crossed allocation limits.";
        case TopologyStatus::InvalidDimension:  return "Boundary operator error: Requested dimension out of bounds.";
    }
    return "Unknown state.";
}

// Flat, un-fragmented representation of a simplex using an explicitly managed contiguous block
struct Simplex {
    std::vector<int> vertices;

    size_t dim() const noexcept {
        return vertices.empty() ? 0 : vertices.size() - 1;
    }

    auto operator<=>(const Simplex&) const = default;
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
        std::cout << "  row_ptr: "; for (auto p : row_ptr) std::cout << p << " ";
        std::cout << "\n  col_ind: "; for (auto c : col_ind) std::cout << c << " ";
        std::cout << "\n  values:  "; for (auto v : values) std::cout << static_cast<int>(v) << " ";
        std::cout << "\n\n";
    }
};

class SimplicialComplex {
private:
    // Memory Layout: A flat vector of dimensions, where each dimension holds a flat,
    // contiguous, lexicographically sorted vector of Simplices. This guarantees
    // maximum hardware prefetcher efficiency and cache-line saturation.
    std::vector<std::vector<Simplex>> spatial_tiers_;
    size_t max_dim_ = 0;

    // Micro-optimized zero-allocation comparator. Compares a lower-dimensional simplex
    // against an upper-dimensional simplex *as if* the upper simplex had its k-th vertex removed.
    // This allows complete binary search logic across spans without copying or allocating memory.
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

    // Binary search engine implementing the zero-allocation comparison routine
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

    // Blazing-fast factory using the Vector Sort-Unique pattern instead of tree-balanced std::sets.
    // Drastically lowers heap allocations by accumulating in flat staging arrays before deduplication.
    static std::expected<SimplicialComplex, TopologyStatus> build(
        const std::vector<std::vector<int>>& facets,
        size_t simplex_budget = 100'000)
    {
        if (facets.empty()) return SimplicialComplex({}, 0);

        // Determine ultimate dimension limits to scale out initial tracking buffers safely
        size_t calculated_max_dim = 0;
        for (const auto& f : facets) {
            if (!f.empty()) calculated_max_dim = std::max(calculated_max_dim, f.size() - 1);
        }

            std::vector<std::vector<Simplex>> staging_tiers(calculated_max_dim + 1);
        size_t total_allocated = 0;

        for (auto facet : facets) {
            if (facet.empty()) continue;

            std::sort(facet.begin(), facet.end());
            if (std::adjacent_find(facet.begin(), facet.end()) != facet.end()) {
                return std::unexpected(TopologyStatus::DuplicateVertices);
            }

            size_t n = facet.size();
            uint64_t subfaces = (1ULL << n) - 1;

            // Compute subface properties inline via bitmask permutations
            for (uint64_t mask = 1; mask <= subfaces; ++mask) {
                std::vector<int> face_vertices;
                face_vertices.reserve(std::popcount(mask));

                                for (size_t i = 0; i < n; ++i) {
                    if ((mask >> i) & 1) {
                        face_vertices.push_back(facet[i]);
                    }
                }

                size_t d = face_vertices.size() - 1;
                staging_tiers[d].push_back(Simplex{ .vertices = std::move(face_vertices) });
            }
        }

        // Deduplicate staging tiers sequentially via sorting and unique-filtering contiguous spans
        for (auto& tier : staging_tiers) {
            std::sort(tier.begin(), tier.end());
            auto unique_range = std::unique(tier.begin(), tier.end());
            tier.erase(unique_range, tier.end());
            total_allocated += tier.size();

            if (total_allocated > simplex_budget) [[unlikely]] {

                                return std::unexpected(TopologyStatus::BudgetExceeded);
            }
        }

        return SimplicialComplex(std::move(staging_tiers), calculated_max_dim);
    }

    std::span<const Simplex> get_tier(size_t d) const noexcept {
        return (d < spatial_tiers_.size()) ? spatial_tiers_[d] : std::span<const Simplex>{};
    }

    // High-Performance Two-Pass Zero-Sort CSR Assembly Engine.
    // Appending items in a sequential column-index execution sweep means column keys
    // are automatically sorted inside each row by default. Eliminates triplet sorting arrays entirely.
    std::expected<OksSparseCSR, TopologyStatus> boundary_operator(size_t d) const noexcept {
        if (d == 0 || d > max_dim_) return std::unexpected(TopologyStatus::InvalidDimension);

        auto current_cols = get_tier(d);
        auto lower_rows   = get_tier(d - 1);

                OksSparseCSR csr;
        csr.num_rows = lower_rows.size();
        csr.num_cols = current_cols.size();
        csr.row_ptr.assign(csr.num_rows + 1, 0);

        if (current_cols.empty()) return csr;

        // Pass 1: Scan structural hierarchies to calculate exact non-zero distributions per row
        for (size_t j = 0; j < current_cols.size(); ++j) {
            const auto& upper_simplex = current_cols[j];
            for (size_t k = 0; k < upper_simplex.vertices.size(); ++k) {
                size_t i = find_face_index(lower_rows, upper_simplex, k);
                if (i != std::string::npos) {
                    csr.row_ptr[i + 1]++; // Track offsets shifted by one position
                }
            }
        }

        // Generate cumulative row offset tracking pointers using a fast running prefix sum

                for (size_t i = 0; i < csr.num_rows; ++i) {
            csr.row_ptr[i + 1] += csr.row_ptr[i];
        }

        // Sizing the tracking buffers to perfectly match calculated non-zero targets
        size_t total_nnz = csr.row_ptr.back();
        csr.col_ind.resize(total_nnz);
        csr.values.resize(total_nnz);

        // Mirror active offset blocks to safely trace localized cursor coordinates
        std::vector<size_t> write_cursors = csr.row_ptr;

        // Pass 2: Fill internal tracking buffers. Processing columns sequentially from
        // 0 to num_cols-1 automatically orders column indices within row blocks.
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

int main() {
    // Setting up a basic 2-simplex configuration tracking a topological triangle
    std::vector<std::vector<int>> facets = { {10, 20, 30} };

    std::cout << "Assembling complex using unconstrained C++ optimization tactics...\n";
    auto complex_result = SimplicialComplex::build(facets);

    if (!complex_result) {

        std::cerr << "Initialization aborted: " << to_string(complex_result.error()) << "\n";
        return 1;
    }

    const auto& complex = *complex_result;
    std::cout << "0-Simplices cached: " << complex.get_tier(0).size() << "\n";
    std::cout << "1-Simplices cached: " << complex.get_tier(1).size() << "\n";
    std::cout << "2-Simplices cached: " << complex.get_tier(2).size() << "\n\n";

    // Extracting our boundary operator layout matrix
    auto boundary_op_2 = complex.boundary_operator(2);
    if (boundary_op_2) {
        boundary_op_2->print();
    }

    return 0;
}



