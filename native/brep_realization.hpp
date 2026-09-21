#pragma once

// DECLARATION-ONLY SCAFFOLD: not linked into production targets.
// Contract and activation gates: docs/NATIVE_EXTENSION_FILE_PLAN.md.
// Forward declarations intentionally leave representation choices open; prefer
// refinement of existing carriers. New types remain welcome where warranted.
#include <expected>

namespace cad::occt_adapter {

struct RealizationRequest;
struct RealizationAssessment;
struct RealizationError;
[[nodiscard]] std::expected<RealizationAssessment, RealizationError>
realize(const RealizationRequest&);

} // namespace cad::occt_adapter
