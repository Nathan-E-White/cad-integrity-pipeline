#pragma once

// DECLARATION-ONLY SCAFFOLD: not linked into production targets.
// Contract and activation gates: docs/NATIVE_EXTENSION_FILE_PLAN.md.
// Forward declarations intentionally leave representation choices open; prefer
// refinement of existing carriers. New types remain welcome where warranted.
#include <expected>
#include <memory>

namespace cad::uv {

struct IndexRequest;
struct QueryRequest;
struct Locations;
struct LocationError;
class Locator {
public:
  [[nodiscard]] static std::expected<Locator, LocationError>
  create(const IndexRequest&);
  [[nodiscard]] std::expected<Locations, LocationError>
  locate(const QueryRequest&) const;
private:
  struct Storage;
  explicit Locator(std::shared_ptr<const Storage>);
  std::shared_ptr<const Storage> owner_;
};

} // namespace cad::uv
