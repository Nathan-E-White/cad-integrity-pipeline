#pragma once

#include "cad_mat/voronoi.hpp"

#include <cstdint>
#include <expected>
#include <limits>
#include <span>
#include <string>
#include <vector>

namespace cad::mat {

enum class ExactDuplicateDisposition { merge };
enum class CosphericalInputDisposition { record_cgal_symbolic_perturbation };

struct ConstructionPolicy {
    ExactDuplicateDisposition exact_duplicates = ExactDuplicateDisposition::merge;
    CosphericalInputDisposition cospherical_inputs =
        CosphericalInputDisposition::record_cgal_symbolic_perturbation;
};

struct ConstructionLimits {
    std::uint64_t input_samples = std::numeric_limits<std::uint64_t>::max();
    std::uint64_t constructed_samples = std::numeric_limits<std::uint64_t>::max();
    std::uint64_t cells = std::numeric_limits<std::uint64_t>::max();
    std::uint64_t logical_owned_bytes = std::numeric_limits<std::uint64_t>::max();
    std::uint64_t construction_work = std::numeric_limits<std::uint64_t>::max();
    std::uint64_t output_bytes = std::numeric_limits<std::uint64_t>::max();
};

enum class RecordedDegeneracyDisposition { none, cgal_symbolic_perturbation };

struct ConstructionUsage {
    /// Adapter-owned logical payload at materialization. This excludes allocator
    /// overhead and CGAL's private storage.
    std::uint64_t logical_owned_bytes = 0;
    /// One unit per admission visit, correspondence visit, insertion, emitted
    /// cell, and finite-finite cospherical predicate.
    std::uint64_t construction_work = 0;
    /// Logical bytes retained by the snapshot, correspondence, and dependency tag.
    std::uint64_t output_bytes = 0;
};

struct ConstructionEvidence {
    std::uint64_t input_sample_count = 0;
    std::uint64_t constructed_sample_count = 0;
    std::uint64_t exact_duplicate_count = 0;
    int affine_dimension = 0;
    std::uint64_t finite_cell_count = 0;
    std::uint64_t infinite_cell_count = 0;
    RecordedDegeneracyDisposition degeneracy = RecordedDegeneracyDisposition::none;
    ConstructionUsage usage;
    std::string dependency_revision;
    std::uint64_t numeric_conversion_count = 0;
};

struct ConstructionResult;
struct ConstructionError;

class ConstructedSampleMap {
public:
    [[nodiscard]] std::uint64_t constructed_sample_count() const noexcept {
        return offsets_.empty() ? 0 : offsets_.size() - 1;
    }

    /// Original input ordinals for one canonical constructed sample.
    [[nodiscard]] std::span<const SampleId> originals_for(
        SampleId constructed_sample) const noexcept;
    [[nodiscard]] std::span<const std::uint64_t> offsets() const noexcept { return offsets_; }
    [[nodiscard]] std::span<const SampleId> original_sample_ids() const noexcept {
        return original_sample_ids_;
    }

private:
    std::vector<std::uint64_t> offsets_;
    std::vector<SampleId> original_sample_ids_;

    friend std::expected<ConstructionResult, ConstructionError> build_delaunay(
        std::span<const Point3>, const ConstructionPolicy&, const ConstructionLimits&);
};

struct ConstructionResult {
    DelaunaySnapshot snapshot;
    ConstructedSampleMap original_samples_by_constructed_sample;
    ConstructionEvidence evidence;
};

enum class ConstructionLimitKind {
    none,
    input_samples,
    constructed_samples,
    cells,
    logical_owned_bytes,
    construction_work,
    output_bytes,
};

enum class ConstructionErrorCode {
    invalid_input,
    unsupported_policy,
    reserved_or_unrepresentable_sample_id,
    reserved_or_unrepresentable_cell_id,
    size_arithmetic_overflow,
    insufficient_affine_dimension,
    numerical_conversion_failure,
    dependency_failure,
    allocation_failure,
    limit_exceeded,
};

struct ConstructionError {
    ConstructionErrorCode code;
    ConstructionLimitKind limit = ConstructionLimitKind::none;
    std::uint64_t observed = 0;
    std::uint64_t maximum = 0;
    SampleId sample = no_sample;
};

[[nodiscard]] std::expected<ConstructionResult, ConstructionError> build_delaunay(
    std::span<const Point3> samples, const ConstructionPolicy& policy,
    const ConstructionLimits& limits);

}  // namespace cad::mat
