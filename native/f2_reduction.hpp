#pragma once

#include <cstdint>
#include <expected>
#include <vector>

namespace cad::f2 {

// Signed labels preserve the host reducer's integer set semantics. Offsets count
// entries, not bytes. Every column is canonical (sorted, unique).
struct Columns {
    std::vector<std::int64_t> offsets{0};
    std::vector<std::int64_t> values;
};
enum class EvidenceMode { rank_only, reduced_columns, full_trace };
struct Limits {
    std::uint64_t max_columns, max_stored_entries, max_xor_steps;
    std::uint64_t max_trace_entries, max_output_bytes;
};
enum class ReductionError { invalid_input, input_budget, storage_budget, work_budget,
                            trace_budget, output_budget };
struct ReductionResult {
    Columns pivots; // increasing pivot row, the last value in each column
    Columns reduced;
    Columns traces; // flattened sequence of full column states
    std::vector<std::int64_t> trace_offsets{0}; // states per input column
    std::uint64_t xor_steps{}, stored_entries{}, trace_entries{}, output_bytes{};
};
// Budget failures yield no partial result. Allocation failures throw bad_alloc;
// vector representability failures throw length_error for binding translation.
[[nodiscard]] std::expected<ReductionResult, ReductionError>
reduce(const Columns&, EvidenceMode, const Limits&);

} // namespace cad::f2
