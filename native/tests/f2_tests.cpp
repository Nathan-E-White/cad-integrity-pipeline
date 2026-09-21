#include "f2_reduction.hpp"
#include <cstdlib>
#include <iostream>

void require(bool condition) {
    if (!condition) { std::cerr << "F2 contract failed\n"; std::exit(1); }
}
int main() {
    using namespace cad::f2;
    const Columns columns{{0, 2, 4, 6}, {0, 1, 0, 2, 1, 2}};
    const Limits limits{3, 6, 2, 10, 1024};
    const auto result = reduce(columns, EvidenceMode::full_trace, limits);
    require(result.has_value());
    require(result->pivots.values == std::vector<std::int64_t>({0, 1, 0, 2}));
    require(result->reduced.offsets == std::vector<std::int64_t>({0, 2, 4, 4}));
    require(result->traces.values == std::vector<std::int64_t>({0, 1, 0, 2, 1, 2, 0, 1}));
    require(result->trace_offsets == std::vector<std::int64_t>({0, 1, 2, 5}));
    require(result->xor_steps == 2 && result->stored_entries == 4);
    auto bounded = limits;
    bounded.max_trace_entries = 7;
    require(reduce(columns, EvidenceMode::full_trace, bounded).error() == ReductionError::trace_budget);
    require(reduce(columns, EvidenceMode::rank_only, bounded).has_value());
    require(reduce(Columns{{0, 2, 1}, {0}}, EvidenceMode::rank_only, limits).error()
            == ReductionError::invalid_input);
    require(reduce(Columns{{0, 2}, {1, 1}}, EvidenceMode::rank_only, limits).error()
            == ReductionError::invalid_input);
}
