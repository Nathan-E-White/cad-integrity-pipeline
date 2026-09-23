#include "quad_tracing.hpp"
#include <algorithm>
#include <limits>
#include <map>
#include <queue>
#include <set>

namespace cad::trace {
struct QuadStorage {
  cad::simplicial::PolygonalAssessment assessment;
  std::vector<std::vector<Id>> incident;
  // ccw[2*edge + endpoint] is the next edge counterclockwise at that endpoint.
  std::vector<Id> ccw;
  std::vector<bool> boundary;
  std::vector<Seed> seeds;
  Usage usage;
  explicit QuadStorage(cad::simplicial::PolygonalAssessment a)
      : assessment(std::move(a)) {}
};
namespace {
struct Failure {
  TraceError error;
};
void charge(std::uint64_t &used, std::uint64_t n, std::uint64_t width,
            std::uint64_t limit, ErrorCode code) {
  if (used > limit || n > (limit - used) / width)
    throw Failure{{code}};
  used += n * width;
}
std::size_t ix(Id id) { return static_cast<std::size_t>(id); }
template <EntityDomain D> std::size_t ix(LocalId<D> id) { return ix(id.value); }
Id edge_id(Id token) { return (token < 0 ? -token : token) - 1; }
std::size_t slot(const cad::simplicial::PolygonalInput &raw, Id e, Id v) {
  return 2 * ix(e) + (raw.edges[ix(e)][0] == v ? 0 : 1);
}
} // namespace
AdmittedQuadPatch::AdmittedQuadPatch(std::shared_ptr<const QuadStorage> owner)
    : owner_(std::move(owner)) {}
const cad::simplicial::PolygonalInput &
AdmittedQuadPatch::input() const noexcept {
  return owner_->assessment.input();
}
std::span<const Id> AdmittedQuadPatch::boundary_edges() const noexcept {
  return owner_->assessment.facts().boundary_edge_ids;
}
std::span<const Seed> AdmittedQuadPatch::canonical_seeds() const noexcept {
  return owner_->seeds;
}
Usage AdmittedQuadPatch::usage() const noexcept { return owner_->usage; }
std::expected<AdmittedQuadPatch, TraceError>
AdmittedQuadPatch::create(cad::simplicial::PolygonalAssessment assessment,
                          const Limits &limits) {
  try {
    if (!assessment.admitted_cells() ||
        !assessment.facts().inconsistent_orientation_edge_ids.empty())
      return std::unexpected(TraceError{ErrorCode::invalid_patch});
    const auto &raw = assessment.input();
    if (raw.edges.size() >
        static_cast<std::uint64_t>(std::numeric_limits<Id>::max() / 2))
      return std::unexpected(TraceError{ErrorCode::numerical_range});
    Usage usage;
    // Existing retained assessment plus conservative extra topology workspace.
    charge(usage.owned_bytes, assessment.usage().owned_bytes, 1,
           limits.max_owned_bytes, ErrorCode::storage_budget);
    charge(usage.owned_bytes, raw.vertices.size(), 128, limits.max_owned_bytes,
           ErrorCode::storage_budget);
    charge(usage.owned_bytes, raw.edges.size(), 256, limits.max_owned_bytes,
           ErrorCode::storage_budget);
    charge(usage.owned_bytes, raw.face_coedges.size(), 256,
           limits.max_owned_bytes, ErrorCode::storage_budget);
    if (usage.owned_bytes > std::numeric_limits<std::size_t>::max())
      return std::unexpected(TraceError{ErrorCode::storage_budget});
    auto work = [&] {
      charge(usage.work_steps, 1, 1, limits.max_work_steps,
             ErrorCode::work_budget);
    };
    auto out = std::make_shared<QuadStorage>(std::move(assessment));
    out->incident.resize(raw.vertices.size());
    out->boundary.resize(raw.vertices.size());
    out->ccw.assign(2 * raw.edges.size(), -1);
    std::set<std::array<Id, 2>> unique_edges;
    for (std::size_t e = 0; e < raw.edges.size(); ++e) {
      work();
      auto ends = raw.edges[e];
      out->incident[ix(ends[0])].push_back(static_cast<Id>(e));
      out->incident[ix(ends[1])].push_back(static_cast<Id>(e));
      std::sort(ends.begin(), ends.end());
      if (!unique_edges.insert(ends).second)
        return std::unexpected(
            TraceError{ErrorCode::invalid_patch, EdgeId{static_cast<Id>(e)}});
    }
    for (Id e : out->assessment.facts().boundary_edge_ids) {
      work();
      for (Id v : raw.edges[ix(e)])
        out->boundary[ix(v)] = true;
    }
    // Each pair of quads can share at most one edge or one vertex. A pair
    // of common vertices must be an edge in both, not a diagonal.
    std::map<std::array<Id, 2>, std::pair<Id, bool>> vertex_pairs;
    std::set<std::array<Id, 2>> face_pairs;
    for (std::size_t f = 0; f + 1 < raw.face_offsets.size(); ++f) {
      work();
      const auto begin = ix(raw.face_offsets[f]);
      if (raw.face_offsets[f + 1] - raw.face_offsets[f] != 4)
        return std::unexpected(
            TraceError{ErrorCode::invalid_patch, FaceId{static_cast<Id>(f)}});
      std::array<Id, 4> vertices;
      for (std::size_t j = 0; j < 4; ++j) {
        work();
        Id token = raw.face_coedges[begin + j], e = edge_id(token);
        Id v = raw.edges[ix(e)][token > 0 ? 0 : 1];
        vertices[j] = v;
        out->ccw[slot(raw, e, v)] =
            edge_id(raw.face_coedges[begin + (j + 3) % 4]);
      }
      for (std::size_t i = 0; i < 4; ++i)
        for (std::size_t j = i + 1; j < 4; ++j) {
          work();
          std::array<Id, 2> pair{vertices[i], vertices[j]};
          std::sort(pair.begin(), pair.end());
          bool adjacent = j == i + 1 || (i == 0 && j == 3);
          auto [it, inserted] = vertex_pairs.emplace(
              pair, std::pair{static_cast<Id>(f), adjacent});
          if (!inserted &&
              (!adjacent || !it->second.second ||
               !face_pairs.insert({it->second.first, static_cast<Id>(f)})
                    .second))
            return std::unexpected(TraceError{ErrorCode::invalid_patch,
                                              FaceId{static_cast<Id>(f)}});
        }
    }
    // Disconnected components are admitted independently under the same policy.
    for (std::size_t v = 0; v < out->incident.size(); ++v) {
      work();
      bool extraordinary = out->boundary[v] ? out->incident[v].size() > 3
                                            : out->incident[v].size() != 4;
      for (Id e : out->incident[v]) {
        work();
        if (extraordinary)
          out->seeds.push_back(
              {static_cast<Id>(slot(raw, e, static_cast<Id>(v))),
               static_cast<Id>(v), e});
      }
    }
    std::sort(out->seeds.begin(), out->seeds.end(),
              [](auto a, auto b) { return a.id < b.id; });
    charge(usage.output_bytes, out->seeds.size(), sizeof(Seed),
           limits.max_output_bytes, ErrorCode::output_budget);
    out->usage = usage;
    return AdmittedQuadPatch(std::move(out));
  } catch (const Failure &f) {
    return std::unexpected(f.error);
  }
}
struct Tracer {
  struct Pending {
    std::uint64_t time2, start2;
    std::size_t seed;
    Id edge, from, to;
    bool midpoint = false;
    bool operator>(const Pending &b) const {
      return std::tie(time2, seed) > std::tie(b.time2, b.seed);
    }
  };
  static std::expected<TraceResult, TraceError>
  run(const AdmittedQuadPatch &patch, std::span<const Seed> supplied,
      const Limits &limits) {
    try {
      const auto &owner = *patch.owner_;
      const auto &raw = patch.input();
      TraceResult result{patch, false, Stop::none, {}, {}, {}, {}, {}, {}};
      auto &usage = result.usage;
      // Heap, frontier, per-vertex deposition, scratch batches and validated
      // seeds.
      charge(usage.owned_bytes, raw.vertices.size(), 128,
             limits.max_owned_bytes, ErrorCode::storage_budget);
      charge(usage.owned_bytes, supplied.size(), 1024, limits.max_owned_bytes,
             ErrorCode::storage_budget);
      if (usage.owned_bytes > std::numeric_limits<std::size_t>::max())
        return std::unexpected(TraceError{ErrorCode::storage_budget});
      charge(usage.work_steps, raw.vertices.size(), 2, limits.max_work_steps,
             ErrorCode::work_budget);
      charge(usage.work_steps, supplied.size(), 128, limits.max_work_steps,
             ErrorCode::work_budget);
      charge(usage.output_bytes, supplied.size(), sizeof(Seed) + sizeof(Id),
             limits.max_output_bytes, ErrorCode::output_budget);
      result.seeds.assign(supplied.begin(), supplied.end());
      std::sort(result.seeds.begin(), result.seeds.end(),
                [](auto a, auto b) { return a.id < b.id; });
      std::set<std::pair<Id, Id>> launches;
      for (std::size_t i = 0; i < result.seeds.size(); ++i) {
        auto s = result.seeds[i];
        if (s.id < 0 || s.vertex < 0 || ix(s.vertex) >= raw.vertices.size() ||
            s.edge < 0 || ix(s.edge) >= raw.edges.size() ||
            (i && result.seeds[i - 1].id == s.id) ||
            (raw.edges[ix(s.edge)][0] != s.vertex &&
             raw.edges[ix(s.edge)][1] != s.vertex) ||
            !launches.emplace(s.vertex.value, s.edge.value).second)
          return std::unexpected(TraceError{ErrorCode::invalid_seed, s.id});
      }
      result.canonical =
          std::ranges::equal(result.seeds, patch.canonical_seeds());
      std::vector<bool> active(result.seeds.size(), true);
      constexpr auto never = std::numeric_limits<std::uint64_t>::max();
      std::vector<std::uint64_t> deposited(raw.vertices.size(), never);
      std::vector<std::vector<Id>> depositors(raw.vertices.size());
      std::vector<Pending> frontier;
      for (std::size_t i = 0; i < result.seeds.size(); ++i) {
        auto s = result.seeds[i];
        deposited[ix(s.vertex)] = 0;
        depositors[ix(s.vertex)].push_back(s.id.value);
        auto ends = raw.edges[ix(s.edge)];
        frontier.push_back({2, 0, i, s.edge.value, s.vertex.value,
                            ends[0] == s.vertex ? ends[1] : ends[0]});
      }
      std::priority_queue<Pending, std::vector<Pending>, std::greater<Pending>>
          queue;
      auto schedule = [&] {
        // All launches in a frontier have the same exact time and unit speed.
        // Opposite uses meet halfway; there are no speculative later segments.
        std::map<Id, std::size_t> edge_launch;
        for (std::size_t i = 0; i < frontier.size(); ++i) {
          auto [it, inserted] = edge_launch.emplace(frontier[i].edge, i);
          if (!inserted) {
            auto &a = frontier[it->second];
            auto &b = frontier[i];
            if (a.from == b.from)
              throw Failure{{ErrorCode::invalid_seed}};
            a.midpoint = b.midpoint = true;
            --a.time2;
            --b.time2;
          }
        }
        for (auto p : frontier)
          queue.push(p);
        frontier.clear();
      };
      schedule();
      while (!queue.empty()) {
        auto time = queue.top().time2;
        std::vector<Pending> batch;
        while (!queue.empty() && queue.top().time2 == time) {
          batch.push_back(queue.top());
          queue.pop();
        }
        auto n = static_cast<std::uint64_t>(batch.size());
        // Reserve a whole simultaneous time batch before any evidence/state
        // commit.
        if (n > limits.max_events - result.events.size()) {
          result.stop = Stop::event_budget;
          break;
        }
        if (n > limits.max_segments - result.segments.size()) {
          result.stop = Stop::segment_budget;
          break;
        }
        if (n > (limits.max_output_bytes - usage.output_bytes) /
                    (sizeof(Segment) + sizeof(Event))) {
          result.stop = Stop::output_budget;
          break;
        }
        if (n > (limits.max_work_steps - usage.work_steps) / 256) {
          result.stop = Stop::work_budget;
          break;
        }
        usage.work_steps += n * 256;
        std::map<std::pair<bool, Id>, std::vector<std::size_t>> groups;
        for (std::size_t i = 0; i < batch.size(); ++i)
          groups[{batch[i].midpoint,
                  batch[i].midpoint ? batch[i].edge : batch[i].to}]
              .push_back(i);
        std::vector<Event> events(batch.size());
        for (const auto &[location, group] : groups) {
          (void)location;
          for (auto k : group) {
            const auto p = batch[k];
            const Id id = result.seeds[p.seed].id.value;
            Event ev{time, id, p.edge, p.midpoint ? -1 : p.to, Reason::advance,
                     -1,   0};
            if (p.midpoint) {
              ev.reason = Reason::opposing;
              ev.blocker =
                  result.seeds[batch[group[0] == k ? group[1] : group[0]].seed]
                      .id;
              ev.deposited_time2 = time;
            } else if (owner.boundary[ix(p.to)]) {
              ev.reason = Reason::boundary;
            } else if (deposited[ix(p.to)] != never) {
              const auto &previous = depositors[ix(p.to)];
              bool self = std::ranges::find(previous, id) != previous.end();
              ev.reason =
                  self ? Reason::self_collision : Reason::deposited_track;
              ev.blocker =
                  self ? id
                       : *std::min_element(previous.begin(), previous.end());
              ev.deposited_time2 = deposited[ix(p.to)];
            } else if (owner.incident[ix(p.to)].size() != 4) {
              ev.reason = Reason::extraordinary;
            } else if (group.size() >= 3) {
              ev.reason = Reason::simultaneous;
              ev.deposited_time2 = time;
            } else if (group.size() == 2) {
              const auto other = batch[group[0] == k ? group[1] : group[0]];
              Id next = owner.ccw[slot(raw, p.edge, p.to)];
              if (next < 0)
                throw Failure{{ErrorCode::invalid_patch, VertexId{p.to}}};
              if (owner.ccw[slot(raw, next, p.to)] == other.edge)
                ev.reason = Reason::opposing;
              else if (next == other.edge)
                ev.reason = Reason::right_hand;
              if (ev.reason != Reason::advance) {
                ev.blocker = result.seeds[other.seed].id;
                ev.deposited_time2 = time;
              }
            }
            events[k] = ev;
          }
        }
        // All outcomes were decided against the same previously deposited
        // prefix.
        for (std::size_t k = 0; k < batch.size(); ++k) {
          const auto p = batch[k];
          const auto ev = events[k];
          result.segments.push_back(
              {ev.seed, p.edge, p.from, ev.vertex, p.start2, time});
          result.events.push_back(ev);
          active[p.seed] = ev.reason == Reason::advance;
          if (!p.midpoint &&
              (deposited[ix(p.to)] == never || deposited[ix(p.to)] == time)) {
            deposited[ix(p.to)] = time;
            depositors[ix(p.to)].push_back(ev.seed.value);
          }
          if (active[p.seed]) {
            Id next = owner.ccw[slot(raw, p.edge, p.to)];
            if (next < 0 || owner.incident[ix(p.to)].size() != 4)
              throw Failure{{ErrorCode::invalid_patch, VertexId{p.to}}};
            next = owner.ccw[slot(raw, next, p.to)];
            if (next < 0 || time > never - 2)
              throw Failure{{ErrorCode::numerical_range, VertexId{p.to}}};
            const auto ends = raw.edges[ix(next)];
            frontier.push_back({time + 2, time, p.seed, next, p.to,
                                ends[0] == p.to ? ends[1] : ends[0]});
          }
        }
        usage.output_bytes += n * (sizeof(Segment) + sizeof(Event));
        result.last_committed_time2 = time;
        schedule();
      }
      for (std::size_t i = 0; i < active.size(); ++i)
        if (active[i])
          result.unfinished.push_back(result.seeds[i].id);
      return result;
    } catch (const Failure &f) {
      return std::unexpected(f.error);
    }
  }
};
std::expected<TraceResult, TraceError>
trace_quads(const AdmittedQuadPatch &patch, std::span<const Seed> seeds,
            const Limits &limits) {
  return Tracer::run(patch, seeds, limits);
}
} // namespace cad::trace
