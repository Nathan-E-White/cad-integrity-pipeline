#pragma once
#include "surface_preparation.hpp"

namespace cad::uv {
using surface::Id;
using surface::Point;
using surface::UV;
struct Policy {
  double barycentric_tolerance = 1e-9;
  double xyz_relative_tolerance = 1e-8;
};
struct Limits {
  std::uint64_t max_input_bytes = 256000000;
  std::uint64_t max_owned_bytes = 512000000;
  std::uint64_t max_work_steps = 50000000;
  std::uint64_t max_output_bytes = 256000000;
  std::uint64_t max_candidates_per_query = 1000000;
};
struct Usage {
  std::uint64_t input_bytes = 0, owned_bytes = 0, work_steps = 0,
                output_bytes = 0;
};
enum class Operation { index, query };
enum class ErrorCode {
  invalid_input,
  numerical_range,
  input_budget,
  storage_budget,
  work_budget,
  output_budget,
  candidate_budget
};
struct LocationError {
  ErrorCode code;
  Operation operation;
  Id query = -1, triangle = -1;
};
enum class Status { outside, unique, agreeing, ambiguous, budget_exceeded };
struct Candidate {
  Id triangle, source_face;
  std::array<double, 3> barycentric;
  Point xyz;
};
struct Record {
  Status status = Status::outside;
  std::optional<Point> resolved;
  double maximum_discrepancy = 0;
};
struct IndexRequest {
  surface::AdmittedChart chart;
  Policy policy = {};
  Limits limits = {};
};
struct QueryRequest {
  std::span<const UV> queries;
  Limits limits = {};
};
class Locations {
public:
  [[nodiscard]] const std::vector<Record> &records() const { return records_; }
  [[nodiscard]] const std::vector<Candidate> &candidates() const {
    return candidates_;
  }
  [[nodiscard]] const std::vector<std::uint64_t> &offsets() const {
    return offsets_;
  }
  [[nodiscard]] const surface::AdmittedChart &chart() const { return chart_; }
  [[nodiscard]] Policy policy() const { return policy_; }
  [[nodiscard]] Usage usage() const { return usage_; }
  [[nodiscard]] std::optional<LocationError> exhaustion() const {
    return exhaustion_;
  }

private:
  Locations(surface::AdmittedChart chart, Policy policy)
      : chart_(std::move(chart)), policy_(policy) {}
  surface::AdmittedChart chart_;
  Policy policy_;
  std::vector<Record> records_;
  std::vector<Candidate> candidates_;
  std::vector<std::uint64_t> offsets_;
  Usage usage_;
  std::optional<LocationError> exhaustion_;
  friend class Locator;
};
class Locator {
public:
  [[nodiscard]] static std::expected<Locator, LocationError>
      create(IndexRequest);
  [[nodiscard]] std::expected<Locations, LocationError>
      locate(QueryRequest) const;
  [[nodiscard]] Usage usage() const;

private:
  struct Storage;
  explicit Locator(std::shared_ptr<const Storage> storage)
      : owner_(std::move(storage)) {}
  std::shared_ptr<const Storage> owner_;
};
} // namespace cad::uv
