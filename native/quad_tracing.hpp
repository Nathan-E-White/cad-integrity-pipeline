#pragma once
#include "SimplicialComplex.hpp"
#include <compare>
#include <expected>
#include <memory>
#include <span>

namespace cad::trace {
using Id = std::int64_t;
enum class EntityDomain : std::uint8_t { none, seed, vertex, edge, face };
template <EntityDomain Domain> struct LocalId {
  Id value;
  constexpr LocalId(Id ordinal = -1) : value(ordinal) {}
  auto operator<=>(const LocalId &) const = default;
};
using SeedId = LocalId<EntityDomain::seed>;
using VertexId = LocalId<EntityDomain::vertex>;
using EdgeId = LocalId<EntityDomain::edge>;
using FaceId = LocalId<EntityDomain::face>;
struct Seed {
  SeedId id;
  VertexId vertex;
  EdgeId edge;
  bool operator==(const Seed &) const = default;
};
enum class ErrorCode : std::uint8_t {
  invalid_patch,
  invalid_seed,
  storage_budget,
  work_budget,
  output_budget,
  numerical_range
};
struct TraceError {
  ErrorCode code;
  EntityDomain domain = EntityDomain::none;
  Id entity = -1;
  TraceError(ErrorCode value) : code(value) {}
  template <EntityDomain Domain>
  TraceError(ErrorCode value, LocalId<Domain> id)
      : code(value), domain(Domain), entity(id.value) {}
};
struct Limits {
  std::uint64_t max_owned_bytes = 512000000, max_work_steps = 50000000,
                max_output_bytes = 256000000, max_events = 1000000,
                max_segments = 1000000;
};
struct Usage {
  std::uint64_t owned_bytes = 0, work_steps = 0, output_bytes = 0;
};
struct QuadStorage;
class AdmittedQuadPatch {
public:
  // Retains the assessed owner; adds quad-specific guarantees, never repairs
  // winding.
  static std::expected<AdmittedQuadPatch, TraceError>
  create(cad::simplicial::PolygonalAssessment assessment,
         const Limits &limits = {});
  const cad::simplicial::PolygonalInput &input() const noexcept;
  std::span<const Id> boundary_edges() const noexcept;
  std::span<const Seed> canonical_seeds() const noexcept;
  Usage usage() const noexcept;

private:
  explicit AdmittedQuadPatch(std::shared_ptr<const QuadStorage> owner);
  std::shared_ptr<const QuadStorage> owner_;
  friend struct Tracer;
};
enum class Reason : std::uint8_t {
  advance,
  boundary,
  deposited_track,
  self_collision,
  opposing,
  simultaneous,
  right_hand,
  extraordinary
};
enum class Stop : std::uint8_t {
  none,
  work_budget,
  event_budget,
  segment_budget,
  output_budget
};
// Times are exact half-edge steps. A midpoint endpoint is indicated by
// vertex=-1.
struct Segment {
  SeedId seed;
  EdgeId edge;
  VertexId from_vertex, to_vertex;
  std::uint64_t start2, end2;
};
struct Event {
  std::uint64_t time2;
  SeedId seed;
  EdgeId edge;
  VertexId vertex;
  Reason reason;
  SeedId blocker;
  std::uint64_t deposited_time2 = 0;
};
struct TraceResult {
  AdmittedQuadPatch patch;
  bool canonical;
  Stop stop = Stop::none;
  std::optional<std::uint64_t> last_committed_time2;
  std::vector<Seed> seeds;
  std::vector<Segment> segments;
  std::vector<Event> events;
  std::vector<SeedId> unfinished;
  Usage usage;
};
// All supplied seeds launch at time zero, unit topological speed. An arbitrary
// seed set uses the same rules but is explicitly not the canonical full launch.
[[nodiscard]] std::expected<TraceResult, TraceError>
trace_quads(const AdmittedQuadPatch &, std::span<const Seed>,
            const Limits & = {});
} // namespace cad::trace
