#include "f2_reduction.hpp"

#include <algorithm>
#include <iterator>
#include <limits>
#include <map>
#include <span>

namespace cad::f2 {
namespace {
using Row = std::int64_t;
using Count = std::uint64_t;
bool fits(Count current, Count extra, Count limit) {
    return current <= limit && extra <= limit - current;
}
void append(Columns& target, std::span<const Row> values) {
    target.values.insert(target.values.end(), values.begin(), values.end());
    target.offsets.push_back(static_cast<Row>(target.values.size()));
}
}

std::expected<ReductionResult, ReductionError>
reduce(const Columns& input, EvidenceMode mode, const Limits& limits) {
    using enum ReductionError;
    if (input.offsets.empty() || input.offsets.front() != 0 ||
        input.values.size() > static_cast<Count>(std::numeric_limits<Row>::max()) ||
        input.offsets.back() != static_cast<Row>(input.values.size()) ||
        (mode != EvidenceMode::rank_only && mode != EvidenceMode::reduced_columns &&
         mode != EvidenceMode::full_trace)) return std::unexpected(invalid_input);
    if (input.offsets.size() - 1 > limits.max_columns ||
        input.values.size() > limits.max_stored_entries) return std::unexpected(input_budget);
    for (std::size_t i = 1; i < input.offsets.size(); ++i) {
        if (input.offsets[i] < input.offsets[i-1] ||
            input.offsets[i] > static_cast<Row>(input.values.size()))
            return std::unexpected(invalid_input);
        const auto column = std::span(input.values).subspan(
            static_cast<std::size_t>(input.offsets[i-1]),
            static_cast<std::size_t>(input.offsets[i] - input.offsets[i-1]));
        if (std::adjacent_find(column.begin(), column.end(), std::greater_equal<Row>{}) != column.end())
            return std::unexpected(invalid_input);
    }
    ReductionResult result;
    // Four initial offset sentinels and four usage counters. Counts bound packed
    // int64 payload only, not allocator capacity or Python object overhead.
    result.output_bytes = 8 * sizeof(Row);
    if (result.output_bytes > limits.max_output_bytes) return std::unexpected(output_budget);
    auto reserve_output = [&](Count entries) {
        if (entries > (limits.max_output_bytes - result.output_bytes) / sizeof(Row)) return false;
        result.output_bytes += entries * sizeof(Row);
        return true;
    };
    auto record_trace = [&](std::span<const Row> column) -> std::expected<void, ReductionError> {
        if (!fits(result.trace_entries, column.size(), limits.max_trace_entries))
            return std::unexpected(trace_budget);
        if (!reserve_output(column.size() + 1)) return std::unexpected(output_budget);
        append(result.traces, column);
        result.trace_entries += column.size();
        return {};
    };
    std::map<Row, std::vector<Row>> pivots;
    for (std::size_t i = 1; i < input.offsets.size(); ++i) {
        std::vector<Row> column(input.values.begin() + input.offsets[i-1],
                                input.values.begin() + input.offsets[i]);
        if (mode == EvidenceMode::full_trace) {
            auto recorded = record_trace(column);
            if (!recorded) return std::unexpected(recorded.error());
        }
        while (!column.empty()) {
            const auto previous = pivots.find(column.back());
            if (previous == pivots.end()) {
                if (!fits(result.stored_entries, column.size(), limits.max_stored_entries))
                    return std::unexpected(storage_budget);
                // Account eventual pivot output before retaining its storage.
                if (!reserve_output(column.size() + 1)) return std::unexpected(output_budget);
                result.stored_entries += column.size();
                pivots.emplace(column.back(), column);
                break;
            }
            if (result.xor_steps == limits.max_xor_steps) return std::unexpected(work_budget);
            std::vector<Row> next;
            // Build bounded scratch without allocating an unbounded union first.
            auto left = column.begin();
            auto right = previous->second.begin();
            while (left != column.end() || right != previous->second.end()) {
                Row value;
                if (right == previous->second.end() ||
                    (left != column.end() && *left < *right)) value = *left++;
                else if (left == column.end() || *right < *left) value = *right++;
                else { ++left; ++right; continue; }
                if (!fits(result.stored_entries, next.size() + 1, limits.max_stored_entries))
                    return std::unexpected(work_budget);
                next.push_back(value);
            }
            column = std::move(next);
            ++result.xor_steps;
            if (mode == EvidenceMode::full_trace) {
                auto recorded = record_trace(column);
                if (!recorded) return std::unexpected(recorded.error());
            }
        }
        if (mode != EvidenceMode::rank_only) {
            if (!reserve_output(column.size() + 1)) return std::unexpected(output_budget);
            append(result.reduced, column);
        }
        if (mode == EvidenceMode::full_trace) {
            if (!reserve_output(1)) return std::unexpected(output_budget);
            result.trace_offsets.push_back(static_cast<Row>(result.traces.offsets.size() - 1));
        }
    }
    for (const auto& [row, column] : pivots) {
        (void)row;
        append(result.pivots, column);
    }
    return result;
}
} // namespace cad::f2
