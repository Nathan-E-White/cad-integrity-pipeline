#ifdef NDEBUG
#error "Native assertion tests must be built with assertions enabled"
#endif

#include "cad_mat/delaunay.hpp"

#include <algorithm>
#include <cassert>
#include <array>
#include <cmath>
#include <cstdint>
#include <limits>
#include <span>

namespace {

using cad::mat::ConstructionErrorCode;
using cad::mat::ConstructionLimitKind;
using cad::mat::ConstructionLimits;
using cad::mat::ConstructionPolicy;
using cad::mat::Point3;
using cad::mat::RecordedDegeneracyDisposition;
using cad::mat::build_delaunay;
using cad::mat::extract_finite_voronoi_dual;

constexpr std::array tetrahedron{
    Point3{0.0, 0.0, 0.0},
    Point3{1.0, 0.0, 0.0},
    Point3{0.0, 1.0, 0.0},
    Point3{0.0, 0.0, 1.0},
};

void rejects_empty_input_as_affinely_insufficient() {
    const auto result = build_delaunay(std::span<const Point3>{}, ConstructionPolicy{},
                                       ConstructionLimits{});

    assert(!result.has_value());
    assert(result.error().code == ConstructionErrorCode::insufficient_affine_dimension);

    for (std::size_t count = 1; count < tetrahedron.size(); ++count) {
        const auto short_result = build_delaunay(
            std::span<const Point3>{tetrahedron.data(), count}, ConstructionPolicy{},
            ConstructionLimits{});
        assert(!short_result.has_value());
        assert(short_result.error().code == ConstructionErrorCode::insufficient_affine_dimension);
    }
}

void constructs_a_tetrahedron_with_owned_identity_and_finite_dual() {
    const auto result = build_delaunay(tetrahedron, ConstructionPolicy{}, ConstructionLimits{});

    assert(result.has_value());
    assert(result->evidence.input_sample_count == 4);
    assert(result->evidence.constructed_sample_count == 4);
    assert(result->evidence.finite_cell_count == 1);
    assert(result->evidence.infinite_cell_count == 4);
    assert(result->snapshot.cells.size() == 5);
    assert(result->evidence.dependency_revision == "6.2");
    for (const auto& cell : result->snapshot.cells) {
        const auto sentinel_count = static_cast<std::size_t>(
            std::count(cell.vertex_ids.begin(), cell.vertex_ids.end(), cad::mat::no_sample));
        assert(sentinel_count == (cell.is_finite ? 0 : 1));
        for (const auto neighbor : cell.neighbors) {
            assert(neighbor != cad::mat::no_neighbor);
            assert(neighbor < result->snapshot.cells.size());
        }
    }
    constexpr std::array<cad::mat::SampleId, 4> expected_originals{0, 3, 2, 1};
    for (cad::mat::SampleId id = 0; id < expected_originals.size(); ++id) {
        const auto originals = result->original_samples_by_constructed_sample.originals_for(id);
        assert(originals.size() == 1);
        assert(originals[0] == expected_originals[id]);
    }
    const auto dual = extract_finite_voronoi_dual(result->snapshot);
    assert(dual.has_value());
    assert(dual->nodes().size() == 1);
    assert(dual->edges().empty());
}

void rejects_nonfinite_coordinates_and_affinely_degenerate_samples() {
    auto nonfinite = tetrahedron;
    nonfinite[2].y = std::numeric_limits<double>::infinity();
    const auto invalid = build_delaunay(nonfinite, ConstructionPolicy{}, ConstructionLimits{});
    assert(!invalid.has_value());
    assert(invalid.error().code == ConstructionErrorCode::invalid_input);
    assert(invalid.error().sample == 2);

    constexpr std::array collinear{
        Point3{0.0, 0.0, 0.0}, Point3{1.0, 0.0, 0.0},
        Point3{2.0, 0.0, 0.0}, Point3{3.0, 0.0, 0.0},
    };
    constexpr std::array coplanar{
        Point3{0.0, 0.0, 0.0}, Point3{1.0, 0.0, 0.0},
        Point3{0.0, 1.0, 0.0}, Point3{1.0, 1.0, 0.0},
    };
    assert(build_delaunay(collinear, ConstructionPolicy{}, ConstructionLimits{}).error().code
           == ConstructionErrorCode::insufficient_affine_dimension);
    assert(build_delaunay(coplanar, ConstructionPolicy{}, ConstructionLimits{}).error().code
           == ConstructionErrorCode::insufficient_affine_dimension);
}

void merges_exact_duplicates_and_retains_every_original_sample() {
    constexpr std::array samples{
        Point3{1.0, 0.0, 0.0}, Point3{0.0, 0.0, 0.0}, Point3{1.0, 0.0, 0.0},
        Point3{0.0, 1.0, 0.0}, Point3{0.0, 0.0, 1.0},
    };
    const auto result = build_delaunay(samples, ConstructionPolicy{}, ConstructionLimits{});

    assert(result.has_value());
    assert(result->evidence.input_sample_count == 5);
    assert(result->evidence.constructed_sample_count == 4);
    assert(result->evidence.exact_duplicate_count == 1);
    const auto first = result->original_samples_by_constructed_sample.originals_for(0);
    const auto duplicate = result->original_samples_by_constructed_sample.originals_for(3);
    assert(first.size() == 1 && first[0] == 1);
    assert(duplicate.size() == 2 && duplicate[0] == 0 && duplicate[1] == 2);
    assert(result->original_samples_by_constructed_sample.originals_for(4).empty());
}

void constructs_adjacent_tetrahedra_and_their_finite_dual_edge() {
    constexpr std::array samples{
        Point3{0.0, 0.0, 0.0}, Point3{2.0, 0.0, 0.0}, Point3{0.0, 2.0, 0.0},
        Point3{0.0, 0.0, 1.0}, Point3{0.0, 0.0, -2.0},
    };
    const auto result = build_delaunay(samples, ConstructionPolicy{}, ConstructionLimits{});
    assert(result.has_value());
    assert(result->evidence.finite_cell_count == 2);
    const auto dual = extract_finite_voronoi_dual(result->snapshot);
    assert(dual.has_value());
    assert(dual->nodes().size() == 2);
    assert(dual->edges().size() == 1);
}

void records_cgal_disposition_for_five_cospherical_samples() {
    constexpr std::array samples{
        Point3{1.0, 0.0, 0.0}, Point3{-1.0, 0.0, 0.0}, Point3{0.0, 1.0, 0.0},
        Point3{0.0, 0.0, 1.0}, Point3{0.0, 0.0, -1.0},
    };
    const auto result = build_delaunay(samples, ConstructionPolicy{}, ConstructionLimits{});
    assert(result.has_value());
    assert(result->evidence.degeneracy
           == RecordedDegeneracyDisposition::cgal_symbolic_perturbation);
}

bool same_snapshot(const cad::mat::DelaunaySnapshot& left,
                   const cad::mat::DelaunaySnapshot& right) {
    if (left.cells.size() != right.cells.size()) {
        return false;
    }
    for (std::size_t index = 0; index < left.cells.size(); ++index) {
        const auto& a = left.cells[index];
        const auto& b = right.cells[index];
        if (a.vertex_ids != b.vertex_ids || a.neighbors != b.neighbors
            || a.circumcenter.x != b.circumcenter.x || a.circumcenter.y != b.circumcenter.y
            || a.circumcenter.z != b.circumcenter.z || a.sampled_radius != b.sampled_radius
            || a.is_finite != b.is_finite) {
            return false;
        }
    }
    return true;
}

void normalizes_snapshot_identity_across_input_permutations() {
    constexpr std::array permuted{tetrahedron[2], tetrahedron[0], tetrahedron[3], tetrahedron[1]};
    const auto first = build_delaunay(tetrahedron, ConstructionPolicy{}, ConstructionLimits{});
    const auto second = build_delaunay(permuted, ConstructionPolicy{}, ConstructionLimits{});
    assert(first.has_value());
    assert(second.has_value());
    assert(same_snapshot(first->snapshot, second->snapshot));
}

void rejects_an_unrepresentable_extreme_circumradius() {
    constexpr double large = 1.0e308;
    constexpr std::array samples{
        Point3{0.0, 0.0, 0.0}, Point3{large, 0.0, 0.0},
        Point3{0.0, large, 0.0}, Point3{0.0, 0.0, large},
    };
    const auto result = build_delaunay(samples, ConstructionPolicy{}, ConstructionLimits{});
    assert(!result.has_value());
    assert(result.error().code == ConstructionErrorCode::numerical_conversion_failure);
}

void reports_each_exact_limit_and_accepts_its_boundary() {
    const auto baseline = build_delaunay(tetrahedron, ConstructionPolicy{}, ConstructionLimits{});
    assert(baseline.has_value());

    const auto expect_limit = [](ConstructionLimits limits, ConstructionLimitKind kind) {
        const auto result = build_delaunay(tetrahedron, ConstructionPolicy{}, limits);
        assert(!result.has_value());
        assert(result.error().code == ConstructionErrorCode::limit_exceeded);
        assert(result.error().limit == kind);
    };

    ConstructionLimits input;
    input.input_samples = 3;
    expect_limit(input, ConstructionLimitKind::input_samples);
    input.input_samples = 4;
    assert(build_delaunay(tetrahedron, ConstructionPolicy{}, input).has_value());

    ConstructionLimits constructed;
    constructed.constructed_samples = 3;
    expect_limit(constructed, ConstructionLimitKind::constructed_samples);
    constructed.constructed_samples = 4;
    assert(build_delaunay(tetrahedron, ConstructionPolicy{}, constructed).has_value());

    ConstructionLimits cells;
    cells.cells = 4;
    expect_limit(cells, ConstructionLimitKind::cells);
    cells.cells = 5;
    assert(build_delaunay(tetrahedron, ConstructionPolicy{}, cells).has_value());

    ConstructionLimits owned;
    owned.logical_owned_bytes = baseline->evidence.usage.logical_owned_bytes - 1;
    expect_limit(owned, ConstructionLimitKind::logical_owned_bytes);
    owned.logical_owned_bytes = baseline->evidence.usage.logical_owned_bytes;
    assert(build_delaunay(tetrahedron, ConstructionPolicy{}, owned).has_value());

    ConstructionLimits work;
    work.construction_work = baseline->evidence.usage.construction_work - 1;
    expect_limit(work, ConstructionLimitKind::construction_work);
    work.construction_work = baseline->evidence.usage.construction_work;
    assert(build_delaunay(tetrahedron, ConstructionPolicy{}, work).has_value());

    ConstructionLimits output;
    output.output_bytes = baseline->evidence.usage.output_bytes - 1;
    expect_limit(output, ConstructionLimitKind::output_bytes);
    output.output_bytes = baseline->evidence.usage.output_bytes;
    assert(build_delaunay(tetrahedron, ConstructionPolicy{}, output).has_value());
}

}  // namespace

int main() {
    rejects_empty_input_as_affinely_insufficient();
    constructs_a_tetrahedron_with_owned_identity_and_finite_dual();
    rejects_nonfinite_coordinates_and_affinely_degenerate_samples();
    merges_exact_duplicates_and_retains_every_original_sample();
    constructs_adjacent_tetrahedra_and_their_finite_dual_edge();
    records_cgal_disposition_for_five_cospherical_samples();
    normalizes_snapshot_identity_across_input_permutations();
    rejects_an_unrepresentable_extreme_circumradius();
    reports_each_exact_limit_and_accepts_its_boundary();
}
