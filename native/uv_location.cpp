#include "uv_location.hpp"
#include <algorithm>
#include <cmath>
#include <limits>
#include <numeric>

namespace cad::uv {
namespace {
struct Failure {
  LocationError error;
};
struct Meter {
  Limits limits;
  Usage usage;
  Operation operation;
  Id query = -1, triangle = -1;
  [[noreturn]] void fail(ErrorCode code) const {
    throw Failure{{code, operation, query, triangle}};
  }
  std::uint64_t sum(std::uint64_t a, std::uint64_t b) const {
    if (b > std::numeric_limits<std::uint64_t>::max() - a)
      fail(ErrorCode::numerical_range);
    return a + b;
  }
  std::uint64_t bytes(std::uint64_t n, std::uint64_t width) const {
    if (n > std::numeric_limits<std::uint64_t>::max() / width)
      fail(ErrorCode::numerical_range);
    return n * width;
  }
  void work() {
    if (usage.work_steps == limits.max_work_steps)
      fail(ErrorCode::work_budget);
    ++usage.work_steps;
  }
  void input(std::uint64_t n) {
    if (n > limits.max_input_bytes)
      fail(ErrorCode::input_budget);
    usage.input_bytes = n;
  }
  void owned(std::uint64_t n) {
    if (n > limits.max_owned_bytes)
      fail(ErrorCode::storage_budget);
    usage.owned_bytes = std::max(usage.owned_bytes, n);
  }
  void output(std::uint64_t n) {
    if (n > limits.max_output_bytes)
      fail(ErrorCode::output_budget);
    usage.output_bytes = n;
  }
};
bool resource(ErrorCode c) {
  return c == ErrorCode::storage_budget || c == ErrorCode::work_budget ||
         c == ErrorCode::output_budget || c == ErrorCode::candidate_budget;
}
// Outward-rounded interval operations on exact double coefficients. No
// fast-math.
constexpr double infinity = std::numeric_limits<double>::infinity();
constexpr double tiny = std::numeric_limits<double>::denorm_min();
double up(double x) { return std::nextafter(x, infinity); }
double down(double x) { return std::nextafter(x, -infinity); }
struct Interval {
  double lo, hi;
};
Interval product(double a, double b) {
  double p = a * b;
  return {down(p), up(p)};
}
struct Box {
  UV lo{infinity, infinity}, hi{-infinity, -infinity};
  void grow(const Box &b) {
    for (int k = 0; k < 2; ++k) {
      lo[k] = std::min(lo[k], b.lo[k]);
      hi[k] = std::max(hi[k], b.hi[k]);
    }
  }
  bool contains(UV q) const {
    return q[0] >= lo[0] && q[0] <= hi[0] && q[1] >= lo[1] && q[1] <= hi[1];
  }
};
struct Node {
  Box box;
  std::size_t begin, end, left = 0, right = 0;
};
struct TriangleData {
  UV origin;
  double scale;
  std::array<double, 4> inverse;
  Box box;
};
Box envelope(UV origin, double scale, const std::array<double, 4> &m,
             double tolerance) {
  const Box fallback{{-infinity, -infinity}, {infinity, infinity}};
  // M is the actual rounded inverse used by the predicate. Bound ||M^-1||_inf
  // using an interval determinant; this does not assume M exactly inverts the
  // UV edges.
  auto a = product(m[0], m[3]), b = product(m[1], m[2]);
  Interval det{down(a.lo - b.hi), up(a.hi - b.lo)};
  double lower = det.lo > 0 ? det.lo : det.hi < 0 ? -det.hi : 0;
  if (!(lower > 0) || !std::isfinite(lower))
    return fallback;
  double numerator = std::max(up(std::abs(m[3]) + std::abs(m[1])),
                              up(std::abs(m[2]) + std::abs(m[0])));
  double k = up(numerator / lower);
  double norm = std::max(up(std::abs(m[0]) + std::abs(m[1])),
                         up(std::abs(m[2]) + std::abs(m[3])));
  double g = up(up(16 * std::numeric_limits<double>::epsilon() * norm) * k);
  if (!std::isfinite(k) || !std::isfinite(norm) || !(g <= .5))
    return fallback;
  // If the computed b1,b2 are accepted, ||M x|| <= B + gamma ||M|| ||x||.
  // Thus ||x|| <= 2 K B. The other factor two bounds rounded
  // subtraction/division in x=(q-origin)/scale. Absolute underflow allowances
  // are included in B and R.
  double absolute = up(up(16 * tiny) * up(1 + norm));
  double bound = up(up(1 + tolerance) + absolute);
  double x_bound = up(up(2 * k) * bound);
  double roundoff =
      up(up(up(8 * std::numeric_limits<double>::epsilon() * norm) * x_bound) +
         absolute);
  Interval accepted{down(-tolerance - roundoff),
                    up(up(1 + tolerance) + roundoff)};
  auto divide = [&](double value) {
    double x = value / det.lo, y = value / det.hi;
    return Interval{down(std::min(x, y)), up(std::max(x, y))};
  };
  auto multiply = [](Interval x, Interval y) {
    std::array<double, 4> products{x.lo * y.lo, x.lo * y.hi, x.hi * y.lo,
                                   x.hi * y.hi};
    return Interval{down(*std::min_element(products.begin(), products.end())),
                    up(*std::max_element(products.begin(), products.end()))};
  };
  // Invert the rounded M with interval arithmetic, mapping the accepted b1/b2
  // rectangle (plus arithmetic error) back into UV. Ignoring b0 enlarges it
  // safely.
  std::array<Interval, 4> reverse{divide(m[3]), divide(-m[1]), divide(-m[2]),
                                  divide(m[0])};
  double reverse_error =
      up(up(up(8 * std::numeric_limits<double>::epsilon() * x_bound) * scale) +
         8 * tiny);
  Box box;
  for (int axis = 0; axis < 2; ++axis) {
    auto first = multiply(reverse[2 * axis], accepted),
         second = multiply(reverse[2 * axis + 1], accepted);
    double lo = down(first.lo + second.lo), hi = up(first.hi + second.hi);
    box.lo[axis] = down(down(origin[axis] + down(scale * lo)) - reverse_error);
    box.hi[axis] = up(up(origin[axis] + up(scale * hi)) + reverse_error);
    if (!std::isfinite(box.lo[axis]) || !std::isfinite(box.hi[axis]))
      return fallback;
  }
  return box;
}
TriangleData prepare_triangle(const surface::AdmittedChart &chart,
                              std::size_t id, Policy policy, Meter &meter) {
  meter.triangle = static_cast<Id>(id);
  auto t = chart.surface().triangles()[id];
  UV a = chart.uv()[t[0]], b = chart.uv()[t[1]], c = chart.uv()[t[2]];
  const double scale = std::max({std::abs(b[0] - a[0]), std::abs(b[1] - a[1]),
                                 std::abs(c[0] - a[0]), std::abs(c[1] - a[1])});
  if (!std::isfinite(scale) || scale <= 0)
    meter.fail(ErrorCode::numerical_range);
  double x = (b[0] - a[0]) / scale, y = (b[1] - a[1]) / scale;
  double z = (c[0] - a[0]) / scale, w = (c[1] - a[1]) / scale;
  double det = x * w - y * z;
  if (!std::isfinite(det) || det == 0)
    meter.fail(ErrorCode::numerical_range);
  std::array<double, 4> inv{w / det, -z / det, -y / det, x / det};
  for (auto value : inv)
    if (!std::isfinite(value))
      meter.fail(ErrorCode::numerical_range);
  return {a, scale, inv, envelope(a, scale, inv, policy.barycentric_tolerance)};
}
std::optional<Candidate> candidate(const surface::AdmittedChart &chart,
                                   const TriangleData &d, std::size_t id, UV q,
                                   Policy policy, Meter &meter) {
  meter.triangle = static_cast<Id>(id);
  meter.work();
  double x = (q[0] - d.origin[0]) / d.scale, y = (q[1] - d.origin[1]) / d.scale;
  double u = d.inverse[0] * x + d.inverse[1] * y,
         v = d.inverse[2] * x + d.inverse[3] * y;
  std::array<double, 3> bc{1 - u - v, u, v};
  for (auto b : bc)
    if (!std::isfinite(b))
      meter.fail(ErrorCode::numerical_range);
  const double e = policy.barycentric_tolerance;
  if (!std::all_of(bc.begin(), bc.end(),
                   [&](double b) { return b >= -e && b <= 1 + e; }))
    return {};
  auto t = chart.surface().triangles()[id];
  Point xyz{};
  // Scale each axis independently. Avoid overflowing intermediate weighted
  // sums.
  for (int k = 0; k < 3; ++k) {
    double s = 0;
    for (int j = 0; j < 3; ++j)
      s = std::max(s, std::abs(chart.surface().vertices()[t[j]][k]));
    if (s > 0) {
      double value = 0;
      for (int j = 0; j < 3; ++j)
        value += bc[j] * (chart.surface().vertices()[t[j]][k] / s);
      xyz[k] = value * s;
    }
    if (!std::isfinite(xyz[k]))
      meter.fail(ErrorCode::numerical_range);
  }
  return Candidate{static_cast<Id>(id), chart.surface().triangle_faces()[id],
                   bc, xyz};
}
// In-place iterative heapsort keeps sorting scratch constant and explicit.
// Both index ordering and candidate ordering use this private implementation.
template <class T, class Less> void heap_sort(std::span<T> values, Less less) {
  auto sift = [&](std::size_t root, std::size_t count) {
    while (root < count / 2) {
      std::size_t child = root * 2 + 1;
      if (child + 1 < count && less(values[child], values[child + 1]))
        ++child;
      if (!less(values[root], values[child]))
        break;
      std::swap(values[root], values[child]);
      root = child;
    }
  };
  for (std::size_t i = values.size() / 2; i > 0; --i)
    sift(i - 1, values.size());
  for (std::size_t end = values.size(); end > 1; --end) {
    std::swap(values[0], values[end - 1]);
    sift(0, end - 1);
  }
}
Record resolve(std::vector<Candidate> &group, double agreement, Meter &meter) {
  Record record;
  if (group.empty())
    return record;
  heap_sort<Candidate>(group, [&](const Candidate &a, const Candidate &b) {
    meter.work();
    return a.triangle < b.triangle;
  });
  record.status = group.size() == 1 ? Status::unique : Status::agreeing;
  record.resolved = group[0].xyz;
  for (std::size_t i = 1; i < group.size(); ++i) {
    meter.work();
    auto p = group[i].xyz, a = group[0].xyz;
    double distance = std::hypot(p[0] - a[0], p[1] - a[1], p[2] - a[2]);
    if (!std::isfinite(distance))
      meter.fail(ErrorCode::numerical_range);
    record.maximum_discrepancy = std::max(record.maximum_discrepancy, distance);
  }
  if (record.maximum_discrepancy > agreement) {
    record.status = Status::ambiguous;
    record.resolved.reset();
  }
  return record;
}
} // namespace
struct Locator::Storage {
  surface::AdmittedChart chart;
  Policy policy;
  Usage usage;
  std::vector<TriangleData> triangles;
  double agreement;
  std::vector<std::size_t> order;
  std::vector<Node> nodes;
  void build(Meter &meter) {
    const auto count = triangles.size();
    std::vector<std::size_t> pending;
    pending.reserve(count);
    nodes.push_back(Node{{}, 0, count});
    pending.push_back(0);
    while (!pending.empty()) {
      auto id = pending.back();
      pending.pop_back();
      meter.work();
      auto begin = nodes[id].begin, end = nodes[id].end;
      for (std::size_t i = begin; i < end; ++i) {
        meter.work();
        nodes[id].box.grow(triangles[order[i]].box);
      }
      if (end - begin <= 4)
        continue;
      const auto box = nodes[id].box;
      int axis = box.hi[1] - box.lo[1] > box.hi[0] - box.lo[0] ? 1 : 0;
      // Median split as in Point3D v5/v6; flat ranges and iterative workspace.
      heap_sort<std::size_t>(std::span(order).subspan(begin, end - begin),
                             [&](std::size_t a, std::size_t b) {
                               meter.work();
                               double x = triangles[a].origin[axis],
                                      y = triangles[b].origin[axis];
                               return x < y || (x == y && a < b);
                             });
      auto mid = begin + (end - begin) / 2;
      auto left = nodes.size(), right = left + 1;
      nodes[id].left = left;
      nodes[id].right = right;
      nodes.push_back(Node{{}, begin, mid});
      nodes.push_back(Node{{}, mid, end});
      pending.push_back(right);
      pending.push_back(left);
    }
  }
};
std::expected<Locator, LocationError> Locator::create(IndexRequest r) {
  Meter meter{r.limits, {}, Operation::index};
  try {
    if (!std::isfinite(r.policy.barycentric_tolerance) ||
        r.policy.barycentric_tolerance < 0 ||
        !std::isfinite(1 + r.policy.barycentric_tolerance) ||
        !std::isfinite(r.policy.xyz_relative_tolerance) ||
        r.policy.xyz_relative_tolerance < 0)
      meter.fail(ErrorCode::invalid_input);
    auto &surface = r.chart.surface();
    const auto count = surface.triangles().size();
    if (count > static_cast<std::uint64_t>(std::numeric_limits<Id>::max()))
      meter.fail(ErrorCode::numerical_range);
    auto input = meter.sum(meter.bytes(surface.vertices().size(), 48),
                           meter.bytes(count, 56));
    input = meter.sum(input, meter.bytes(surface.selected_faces().size() +
                                             surface.boundary_vertices().size(),
                                         8));
    meter.input(input);
    const auto retained =
        meter.sum(sizeof(Storage), meter.bytes(count, sizeof(TriangleData) +
                                                          sizeof(std::size_t) +
                                                          2 * sizeof(Node)));
    meter.owned(meter.sum(retained, meter.bytes(count, sizeof(std::size_t))));
    meter.output(retained);
    auto storage = std::make_shared<Storage>(
        Storage{std::move(r.chart), r.policy, {}, {}, 0, {}, {}});
    storage->triangles.reserve(count);
    for (std::size_t i = 0; i < count; ++i) {
      meter.work();
      storage->triangles.push_back(
          prepare_triangle(storage->chart, i, r.policy, meter));
    }
    Point lo = storage->chart.surface().vertices()[0], hi = lo;
    for (auto p : storage->chart.surface().vertices()) {
      meter.work();
      for (int k = 0; k < 3; ++k) {
        lo[k] = std::min(lo[k], p[k]);
        hi[k] = std::max(hi[k], p[k]);
      }
    }
    double scale = std::numeric_limits<double>::min();
    for (int k = 0; k < 3; ++k)
      scale = std::max(scale, hi[k] - lo[k]);
    storage->agreement = scale * r.policy.xyz_relative_tolerance;
    if (!std::isfinite(scale) || !std::isfinite(storage->agreement))
      meter.fail(ErrorCode::numerical_range);
    storage->order.resize(count);
    std::iota(storage->order.begin(), storage->order.end(), 0);
    storage->nodes.reserve(2 * count);
    storage->build(meter);
    storage->usage = meter.usage;
    return Locator(std::move(storage));
  } catch (const Failure &f) {
    return std::unexpected(f.error);
  }
}
Usage Locator::usage() const { return owner_->usage; }
std::expected<Locations, LocationError>
Locator::locate(QueryRequest request) const {
  Meter meter{request.limits, {}, Operation::query};
  try {
    const auto n = request.queries.size();
    if (n > static_cast<std::uint64_t>(std::numeric_limits<Id>::max()))
      meter.fail(ErrorCode::numerical_range);
    meter.input(meter.bytes(n, sizeof(UV)));
    auto metadata = meter.sum(meter.bytes(n, sizeof(Record)),
                              meter.bytes(meter.sum(n, 1), 8));
    meter.output(metadata);
    meter.owned(metadata);
    // Validate every input before producing any geometric result.
    for (std::size_t i = 0; i < n; ++i) {
      meter.query = static_cast<Id>(i);
      if (!std::isfinite(request.queries[i][0]) ||
          !std::isfinite(request.queries[i][1]))
        meter.fail(ErrorCode::invalid_input);
    }
    Locations out(owner_->chart, owner_->policy);
    out.records_.resize(n);
    out.offsets_.resize(n + 1, 0);
    for (std::size_t q = 0; q < n; ++q) {
      meter.query = static_cast<Id>(q);
      meter.triangle = -1;
      try {
        meter.work();
        std::vector<Candidate> group;
        const auto stack_bytes =
            meter.bytes(owner_->nodes.size(), sizeof(std::size_t));
        meter.owned(meter.sum(meter.usage.output_bytes, stack_bytes));
        std::vector<std::size_t> stack;
        stack.reserve(owner_->nodes.size());
        stack.push_back(0);
        while (!stack.empty()) {
          const auto &node = owner_->nodes[stack.back()];
          stack.pop_back();
          meter.work();
          if (!node.box.contains(request.queries[q]))
            continue;
          if (node.left) {
            stack.push_back(node.right);
            stack.push_back(node.left);
            continue;
          }
          for (std::size_t i = node.begin; i < node.end; ++i) {
            const auto t = owner_->order[i];
            meter.work();
            if (!owner_->triangles[t].box.contains(request.queries[q]))
              continue;
            auto hit = candidate(owner_->chart, owner_->triangles[t], t,
                                 request.queries[q], owner_->policy, meter);
            if (!hit)
              continue;
            meter.work();
            if (group.size() == request.limits.max_candidates_per_query)
              meter.fail(ErrorCode::candidate_budget);
            auto total =
                meter.sum(out.candidates_.size(), meter.sum(group.size(), 1));
            meter.output(
                meter.sum(metadata, meter.bytes(total, sizeof(Candidate))));
            meter.owned(meter.sum(
                stack_bytes,
                meter.sum(meter.usage.output_bytes,
                          meter.bytes(group.size() + 1, sizeof(Candidate)))));
            group.push_back(*hit);
          }
        }
        auto record = resolve(group, owner_->agreement, meter);
        out.candidates_.insert(out.candidates_.end(), group.begin(),
                               group.end());
        out.records_[q] = record;
        out.offsets_[q + 1] = out.candidates_.size();
      } catch (const Failure &f) {
        if (!resource(f.error.code))
          throw;
        out.exhaustion_ = f.error;
        for (std::size_t i = q; i < n; ++i) {
          out.records_[i].status = Status::budget_exceeded;
          out.offsets_[i + 1] = out.candidates_.size();
        }
        break;
      }
    }
    meter.usage.output_bytes =
        metadata + out.candidates_.size() * sizeof(Candidate);
    out.usage_ = meter.usage;
    return out;
  } catch (const Failure &f) {
    return std::unexpected(f.error);
  }
}
} // namespace cad::uv
