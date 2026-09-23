#include "cad_mat/delaunay.hpp"

#include <CGAL/Delaunay_triangulation_3.h>
#include <CGAL/Delaunay_triangulation_cell_base_3.h>
#include <CGAL/Exact_predicates_exact_constructions_kernel.h>
#include <CGAL/Triangulation_cell_base_with_info_3.h>
#include <CGAL/Triangulation_data_structure_3.h>
#include <CGAL/Triangulation_vertex_base_with_info_3.h>
#include <CGAL/number_utils.h>
#include <CGAL/squared_distance_3.h>
#include <CGAL/version.h>

#include <algorithm>
#include <array>
#include <cmath>
#include <cstddef>
#include <limits>
#include <new>
#include <string_view>
#include <tuple>
#include <utility>
#include <vector>

namespace cad::mat {
namespace {

using Kernel = CGAL::Exact_predicates_exact_constructions_kernel;
using VertexBase = CGAL::Triangulation_vertex_base_with_info_3<SampleId, Kernel>;
using DelaunayCellBase = CGAL::Delaunay_triangulation_cell_base_3<Kernel>;
using CellBase = CGAL::Triangulation_cell_base_with_info_3<CellId, Kernel, DelaunayCellBase>;
using DataStructure = CGAL::Triangulation_data_structure_3<VertexBase, CellBase>;
using Triangulation = CGAL::Delaunay_triangulation_3<Kernel, DataStructure>;

struct IndexedPoint {
    Point3 point;
    SampleId original_sample;
};

[[nodiscard]] std::expected<std::uint64_t, ConstructionError> checked_add(
    std::uint64_t left, std::uint64_t right) {
    if (right > std::numeric_limits<std::uint64_t>::max() - left) {
        return std::unexpected(
            ConstructionError{ConstructionErrorCode::size_arithmetic_overflow});
    }
    return left + right;
}

[[nodiscard]] std::expected<std::uint64_t, ConstructionError> checked_multiply(
    std::uint64_t left, std::uint64_t right) {
    if (left != 0 && right > std::numeric_limits<std::uint64_t>::max() / left) {
        return std::unexpected(
            ConstructionError{ConstructionErrorCode::size_arithmetic_overflow});
    }
    return left * right;
}

[[nodiscard]] ConstructionError exceeded(ConstructionLimitKind kind, std::uint64_t observed,
                                         std::uint64_t maximum) {
    return {ConstructionErrorCode::limit_exceeded, kind, observed, maximum};
}

[[nodiscard]] bool finite(const Point3& point) noexcept {
    return std::isfinite(point.x) && std::isfinite(point.y) && std::isfinite(point.z);
}

[[nodiscard]] auto coordinates(const Point3& point) noexcept {
    return std::tuple{point.x, point.y, point.z};
}

[[nodiscard]] std::array<SampleId, 4> cell_key(const Triangulation& triangulation,
                                                const Triangulation::Cell_handle& cell) {
    std::array<SampleId, 4> key{};
    for (int index = 0; index < 4; ++index) {
        key[static_cast<std::size_t>(index)] = triangulation.is_infinite(cell->vertex(index))
            ? no_sample
            : cell->vertex(index)->info();
    }
    std::sort(key.begin(), key.end());
    return key;
}

[[nodiscard]] std::expected<double, ConstructionError> checked_double(const Kernel::FT& value) {
    const double converted = CGAL::to_double(value);
    if (!std::isfinite(converted) || (converted == 0.0 && value != Kernel::FT{0})) {
        return std::unexpected(
            ConstructionError{ConstructionErrorCode::numerical_conversion_failure});
    }
    return converted;
}

[[nodiscard]] std::expected<Point3, ConstructionError> checked_point(
    const Kernel::Point_3& point) {
    const auto x = checked_double(point.x());
    const auto y = checked_double(point.y());
    const auto z = checked_double(point.z());
    if (!x || !y || !z) {
        return std::unexpected(
            ConstructionError{ConstructionErrorCode::numerical_conversion_failure});
    }
    return Point3{*x, *y, *z};
}

}  // namespace

std::span<const SampleId> ConstructedSampleMap::originals_for(
    SampleId constructed_sample) const noexcept {
    if (constructed_sample >= constructed_sample_count()) {
        return {};
    }
    const auto first = offsets_[static_cast<std::size_t>(constructed_sample)];
    const auto last = offsets_[static_cast<std::size_t>(constructed_sample + 1)];
    return {original_sample_ids_.data() + first, static_cast<std::size_t>(last - first)};
}

std::expected<ConstructionResult, ConstructionError> build_delaunay(
    std::span<const Point3> samples, const ConstructionPolicy& policy,
    const ConstructionLimits& limits) {
    try {
        if (policy.exact_duplicates != ExactDuplicateDisposition::merge
            || policy.cospherical_inputs
                != CosphericalInputDisposition::record_cgal_symbolic_perturbation) {
            return std::unexpected(ConstructionError{ConstructionErrorCode::unsupported_policy});
        }
        if (samples.size() >= no_sample) {
            return std::unexpected(
                ConstructionError{ConstructionErrorCode::reserved_or_unrepresentable_sample_id});
        }
        if (samples.size() > limits.input_samples) {
            return std::unexpected(
                exceeded(ConstructionLimitKind::input_samples, samples.size(), limits.input_samples));
        }

        const auto initial_owned = checked_multiply(samples.size(), sizeof(IndexedPoint));
        const auto initial_output = checked_multiply(samples.size(), sizeof(SampleId));
        if (!initial_owned || !initial_output) {
            return std::unexpected(
                ConstructionError{ConstructionErrorCode::size_arithmetic_overflow});
        }
        if (*initial_owned > limits.logical_owned_bytes) {
            return std::unexpected(exceeded(ConstructionLimitKind::logical_owned_bytes,
                                            *initial_owned, limits.logical_owned_bytes));
        }
        if (*initial_output > limits.output_bytes) {
            return std::unexpected(exceeded(ConstructionLimitKind::output_bytes, *initial_output,
                                            limits.output_bytes));
        }

        std::vector<IndexedPoint> indexed;
        indexed.reserve(samples.size());
        for (std::size_t index = 0; index < samples.size(); ++index) {
            if (!finite(samples[index])) {
                return std::unexpected(ConstructionError{ConstructionErrorCode::invalid_input,
                                                          ConstructionLimitKind::none, 0, 0,
                                                          static_cast<SampleId>(index)});
            }
            indexed.push_back({samples[index], static_cast<SampleId>(index)});
        }
        std::sort(indexed.begin(), indexed.end(), [](const IndexedPoint& left,
                                                      const IndexedPoint& right) {
            return std::tie(left.point.x, left.point.y, left.point.z, left.original_sample)
                < std::tie(right.point.x, right.point.y, right.point.z, right.original_sample);
        });

        std::uint64_t constructed_sample_count = 0;
        for (std::size_t index = 0; index < indexed.size(); ++index) {
            if (index == 0
                || coordinates(indexed[index - 1].point) != coordinates(indexed[index].point)) {
                ++constructed_sample_count;
            }
        }
        if (constructed_sample_count > limits.constructed_samples) {
            return std::unexpected(exceeded(ConstructionLimitKind::constructed_samples,
                                            constructed_sample_count,
                                            limits.constructed_samples));
        }

        const auto twice_input = checked_multiply(samples.size(), 2);
        const auto preconstruction_work = twice_input
            ? checked_add(*twice_input, constructed_sample_count)
            : std::expected<std::uint64_t, ConstructionError>{std::unexpected(twice_input.error())};
        if (!preconstruction_work) {
            return std::unexpected(preconstruction_work.error());
        }
        if (*preconstruction_work > limits.construction_work) {
            return std::unexpected(exceeded(ConstructionLimitKind::construction_work,
                                            *preconstruction_work, limits.construction_work));
        }

        const auto offset_count = checked_add(constructed_sample_count, 1);
        const auto offset_bytes = offset_count
            ? checked_multiply(*offset_count, sizeof(std::uint64_t))
            : std::expected<std::uint64_t, ConstructionError>{std::unexpected(
                  offset_count.error())};
        const auto canonical_bytes = checked_multiply(constructed_sample_count, sizeof(Point3));
        auto preconstruction_output = offset_bytes;
        if (preconstruction_output) {
            preconstruction_output = checked_add(*preconstruction_output, *initial_output);
        }
        if (preconstruction_output) {
            preconstruction_output = checked_add(
                *preconstruction_output, std::string_view{CGAL_VERSION_STR}.size());
        }
        auto preconstruction_owned = preconstruction_output;
        if (preconstruction_owned) {
            preconstruction_owned = checked_add(*preconstruction_owned, *initial_owned);
        }
        if (preconstruction_owned && canonical_bytes) {
            preconstruction_owned = checked_add(*preconstruction_owned, *canonical_bytes);
        }
        if (!offset_bytes || !canonical_bytes || !preconstruction_output
            || !preconstruction_owned) {
            return std::unexpected(
                ConstructionError{ConstructionErrorCode::size_arithmetic_overflow});
        }
        if (*preconstruction_output > limits.output_bytes) {
            return std::unexpected(exceeded(ConstructionLimitKind::output_bytes,
                                            *preconstruction_output, limits.output_bytes));
        }
        if (*preconstruction_owned > limits.logical_owned_bytes) {
            return std::unexpected(exceeded(ConstructionLimitKind::logical_owned_bytes,
                                            *preconstruction_owned,
                                            limits.logical_owned_bytes));
        }

        std::vector<Point3> canonical_points;
        canonical_points.reserve(static_cast<std::size_t>(constructed_sample_count));
        ConstructedSampleMap sample_map;
        sample_map.offsets_.reserve(static_cast<std::size_t>(*offset_count));
        sample_map.original_sample_ids_.reserve(samples.size());
        sample_map.offsets_.push_back(0);
        for (const auto& item : indexed) {
            if (canonical_points.empty()
                || coordinates(canonical_points.back()) != coordinates(item.point)) {
                if (!canonical_points.empty()) {
                    sample_map.offsets_.push_back(sample_map.original_sample_ids_.size());
                }
                canonical_points.push_back(item.point);
            }
            sample_map.original_sample_ids_.push_back(item.original_sample);
        }
        if (!canonical_points.empty()) {
            sample_map.offsets_.push_back(sample_map.original_sample_ids_.size());
        }

        Triangulation triangulation;
        for (SampleId id = 0; id < canonical_points.size(); ++id) {
            const auto& point = canonical_points[static_cast<std::size_t>(id)];
            auto vertex = triangulation.insert(Kernel::Point_3{point.x, point.y, point.z});
            vertex->info() = id;
        }
        if (triangulation.dimension() < 3) {
            const auto dimension = std::max(triangulation.dimension(), 0);
            return std::unexpected(ConstructionError{
                ConstructionErrorCode::insufficient_affine_dimension,
                ConstructionLimitKind::none, static_cast<std::uint64_t>(dimension)});
        }

        const auto cell_count = triangulation.number_of_cells();
        if (cell_count > no_neighbor) {
            return std::unexpected(
                ConstructionError{ConstructionErrorCode::reserved_or_unrepresentable_cell_id});
        }
        if (cell_count > limits.cells) {
            return std::unexpected(
                exceeded(ConstructionLimitKind::cells, cell_count, limits.cells));
        }

        std::uint64_t finite_adjacency_sides = 0;
        for (auto cell = triangulation.all_cells_begin(); cell != triangulation.all_cells_end();
             ++cell) {
            if (triangulation.is_infinite(cell)) {
                continue;
            }
            for (int side = 0; side < 4; ++side) {
                const auto neighbor = cell->neighbor(side);
                if (!triangulation.is_infinite(neighbor)) {
                    ++finite_adjacency_sides;
                }
            }
        }
        const std::uint64_t degeneracy_checks = finite_adjacency_sides / 2;

        const auto work_with_cells = checked_add(*preconstruction_work, cell_count);
        const auto total_work = work_with_cells
            ? checked_add(*work_with_cells, degeneracy_checks)
            : std::expected<std::uint64_t, ConstructionError>{std::unexpected(
                  work_with_cells.error())};
        if (!total_work) {
            return std::unexpected(total_work.error());
        }
        if (*total_work > limits.construction_work) {
            return std::unexpected(exceeded(ConstructionLimitKind::construction_work, *total_work,
                                            limits.construction_work));
        }

        const auto cell_bytes = checked_multiply(cell_count, sizeof(DelaunayCell));
        auto output_bytes = cell_bytes;
        if (output_bytes) {
            output_bytes = checked_add(*output_bytes, *preconstruction_output);
        }
        if (!output_bytes) {
            return std::unexpected(
                ConstructionError{ConstructionErrorCode::size_arithmetic_overflow});
        }
        if (*output_bytes > limits.output_bytes) {
            return std::unexpected(exceeded(ConstructionLimitKind::output_bytes, *output_bytes,
                                            limits.output_bytes));
        }

        const auto handle_bytes = checked_multiply(cell_count, sizeof(Triangulation::Cell_handle));
        auto owned_bytes = checked_add(*preconstruction_owned, *cell_bytes);
        if (owned_bytes && handle_bytes) {
            owned_bytes = checked_add(*owned_bytes, *handle_bytes);
        }
        if (!handle_bytes || !owned_bytes) {
            return std::unexpected(
                ConstructionError{ConstructionErrorCode::size_arithmetic_overflow});
        }
        if (*owned_bytes > limits.logical_owned_bytes) {
            return std::unexpected(exceeded(ConstructionLimitKind::logical_owned_bytes, *owned_bytes,
                                            limits.logical_owned_bytes));
        }

        std::vector<Triangulation::Cell_handle> cells;
        cells.reserve(static_cast<std::size_t>(cell_count));
        for (auto cell = triangulation.all_cells_begin(); cell != triangulation.all_cells_end();
             ++cell) {
            cells.push_back(cell);
        }
        std::sort(cells.begin(), cells.end(), [&](const auto& left, const auto& right) {
            return cell_key(triangulation, left) < cell_key(triangulation, right);
        });
        for (CellId id = 0; id < cells.size(); ++id) {
            cells[id]->info() = id;
        }

        bool has_cospherical_adjacency = false;
        const auto sphere_side = Kernel{}.side_of_oriented_sphere_3_object();
        for (const auto& cell : cells) {
            if (triangulation.is_infinite(cell)) {
                continue;
            }
            for (int side = 0; side < 4; ++side) {
                const auto neighbor = cell->neighbor(side);
                if (triangulation.is_infinite(neighbor) || cell->info() >= neighbor->info()) {
                    continue;
                }
                const int opposite = neighbor->index(cell);
                if (sphere_side(cell->vertex(0)->point(), cell->vertex(1)->point(),
                                cell->vertex(2)->point(), cell->vertex(3)->point(),
                                neighbor->vertex(opposite)->point())
                    == CGAL::ON_ORIENTED_BOUNDARY) {
                    has_cospherical_adjacency = true;
                }
            }
        }

        ConstructionResult result;
        result.original_samples_by_constructed_sample = std::move(sample_map);
        result.snapshot.cells.reserve(cells.size());
        for (const auto& cell : cells) {
            DelaunayCell output{};
            output.is_finite = !triangulation.is_infinite(cell);
            for (int index = 0; index < 4; ++index) {
                const auto position = static_cast<std::size_t>(index);
                output.vertex_ids[position] = triangulation.is_infinite(cell->vertex(index))
                    ? no_sample
                    : cell->vertex(index)->info();
                output.neighbors[position] = cell->neighbor(index)->info();
            }
            if (output.is_finite) {
                const auto exact_center = triangulation.dual(cell);
                const auto center = checked_point(exact_center);
                const auto squared_radius = checked_double(
                    CGAL::squared_distance(exact_center, cell->vertex(0)->point()));
                if (!center || !squared_radius || *squared_radius < 0.0) {
                    return std::unexpected(ConstructionError{
                        ConstructionErrorCode::numerical_conversion_failure});
                }
                output.circumcenter = *center;
                output.sampled_radius = std::sqrt(*squared_radius);
                if (!std::isfinite(output.sampled_radius)) {
                    return std::unexpected(ConstructionError{
                        ConstructionErrorCode::numerical_conversion_failure});
                }
            }
            result.snapshot.cells.push_back(output);
        }

        result.evidence.input_sample_count = samples.size();
        result.evidence.constructed_sample_count = constructed_sample_count;
        result.evidence.exact_duplicate_count = samples.size() - constructed_sample_count;
        result.evidence.affine_dimension = triangulation.dimension();
        result.evidence.finite_cell_count = triangulation.number_of_finite_cells();
        result.evidence.infinite_cell_count = cell_count - result.evidence.finite_cell_count;
        result.evidence.degeneracy = has_cospherical_adjacency
            ? RecordedDegeneracyDisposition::cgal_symbolic_perturbation
            : RecordedDegeneracyDisposition::none;
        result.evidence.usage = {*owned_bytes, *total_work, *output_bytes};
        result.evidence.dependency_revision = CGAL_VERSION_STR;
        const auto conversions = checked_multiply(4, result.evidence.finite_cell_count);
        if (!conversions) {
            return std::unexpected(conversions.error());
        }
        result.evidence.numeric_conversion_count = *conversions;
        return result;
    } catch (const std::bad_alloc&) {
        return std::unexpected(ConstructionError{ConstructionErrorCode::allocation_failure});
    } catch (...) {
        return std::unexpected(ConstructionError{ConstructionErrorCode::dependency_failure});
    }
}

}  // namespace cad::mat
