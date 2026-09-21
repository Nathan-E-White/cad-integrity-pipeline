#pragma once

// DECLARATION-ONLY SCAFFOLD: not linked into production targets.
// Contract and activation gates: docs/NATIVE_EXTENSION_FILE_PLAN.md.
// Forward declarations intentionally leave representation choices open; prefer
// refinement of existing carriers. New types remain welcome where warranted.
#include <expected>

namespace cad::mat {

struct ConstructionRequest;
struct ConstructionResult;
struct ConstructionError;
[[nodiscard]] std::expected<ConstructionResult, ConstructionError>
build_delaunay(const ConstructionRequest&);

} // namespace cad::mat
