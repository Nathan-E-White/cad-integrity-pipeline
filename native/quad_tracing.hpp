#pragma once

// DECLARATION-ONLY SCAFFOLD: not linked into production targets.
// Contract and activation gates: docs/NATIVE_EXTENSION_FILE_PLAN.md.
// Forward declarations intentionally leave representation choices open; prefer
// refinement of existing carriers. New types remain welcome where warranted.
#include <expected>

namespace cad::trace {

struct QuadTraceRequest;
struct TraceResult;
struct TraceError;
[[nodiscard]] std::expected<TraceResult, TraceError>
trace_quads(const QuadTraceRequest&);

} // namespace cad::trace
