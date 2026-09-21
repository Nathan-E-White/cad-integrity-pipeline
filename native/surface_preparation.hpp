#pragma once

// DECLARATION-ONLY SCAFFOLD: not linked into production targets.
// Contract and activation gates: docs/NATIVE_EXTENSION_FILE_PLAN.md.
// Forward declarations intentionally leave representation choices open; prefer
// refinement of existing carriers. New types remain welcome where warranted.
#include <expected>

namespace cad::surface {

struct PreparationRequest;
struct PreparationResult;
struct SurfaceError;
struct OperatorRequest;
struct OperatorResult;
struct ChartRequest;
struct ChartAssessment;
[[nodiscard]] std::expected<PreparationResult, SurfaceError>
prepare(const PreparationRequest&);
[[nodiscard]] std::expected<OperatorResult, SurfaceError>
assemble(const OperatorRequest&);
[[nodiscard]] std::expected<ChartAssessment, SurfaceError>
qualify_chart(const ChartRequest&);

} // namespace cad::surface
