#include "cad_mat/voronoi.hpp"

#include <array>
#include <cassert>
#include <cstdint>
#include <limits>

namespace {

using cad::mat::CellId;
using cad::mat::DelaunaySnapshot;
using cad::mat::FiniteCell;
using cad::mat::Point3;
using cad::mat::extract_finite_voronoi_dual;

constexpr CellId no_neighbor = std::numeric_limits<CellId>::max();

FiniteCell cell(std::array<std::uint64_t, 4> vertices, std::array<CellId, 4> neighbors,
                Point3 center) {
    return FiniteCell{vertices, neighbors, center, 1.0, true};
}

void extracts_the_finite_dual_of_two_adjacent_cells() {
    DelaunaySnapshot snapshot{
        {
            cell({4, 1, 3, 2}, {1, no_neighbor, no_neighbor, no_neighbor}, {0.0, 0.0, 0.0}),
            cell({1, 2, 3, 5}, {no_neighbor, no_neighbor, no_neighbor, 0}, {1.0, 0.0, 0.0}),
        },
    };

    const auto result = extract_finite_voronoi_dual(snapshot);

    assert(result.has_value());
    assert(result->nodes.size() == 2);
    assert(result->edges.size() == 1);
    assert((result->edges[0].shared_facet == std::array<std::uint64_t, 3>{1, 2, 3}));
    assert(result->edges[0].first_node == 0);
    assert(result->edges[0].second_node == 1);
}

void rejects_a_nonreciprocal_neighbor_relation() {
    DelaunaySnapshot snapshot{
        {
            cell({1, 2, 3, 4}, {1, no_neighbor, no_neighbor, no_neighbor}, {0.0, 0.0, 0.0}),
            cell({1, 2, 3, 5}, {no_neighbor, no_neighbor, no_neighbor, no_neighbor},
                 {1.0, 0.0, 0.0}),
        },
    };

    const auto result = extract_finite_voronoi_dual(snapshot);

    assert(!result.has_value());
}

void ignores_an_infinite_neighbor() {
    DelaunaySnapshot snapshot{
        {
            cell({1, 2, 3, 4}, {1, no_neighbor, no_neighbor, no_neighbor}, {0.0, 0.0, 0.0}),
            FiniteCell{{1, 2, 3, 5}, {no_neighbor, no_neighbor, no_neighbor, 0}, {}, 0.0, false},
        },
    };

    const auto result = extract_finite_voronoi_dual(snapshot);

    assert(result.has_value());
    assert(result->nodes.size() == 1);
    assert(result->edges.empty());
}

void canonicalizes_node_identity_across_cell_order() {
    const DelaunaySnapshot first{
        {
            cell({4, 1, 3, 2}, {1, no_neighbor, no_neighbor, no_neighbor}, {0.0, 0.0, 0.0}),
            cell({1, 2, 3, 5}, {no_neighbor, no_neighbor, no_neighbor, 0}, {1.0, 0.0, 0.0}),
        },
    };
    const DelaunaySnapshot second{
        {
            cell({1, 2, 3, 5}, {no_neighbor, no_neighbor, no_neighbor, 1}, {1.0, 0.0, 0.0}),
            cell({4, 1, 3, 2}, {0, no_neighbor, no_neighbor, no_neighbor}, {0.0, 0.0, 0.0}),
        },
    };

    const auto first_dual = extract_finite_voronoi_dual(first);
    const auto second_dual = extract_finite_voronoi_dual(second);

    assert(first_dual.has_value());
    assert(second_dual.has_value());
    assert(first_dual->nodes.size() == second_dual->nodes.size());
    assert(first_dual->edges.size() == second_dual->edges.size());
    assert(first_dual->nodes[0].supporting_cell == second_dual->nodes[0].supporting_cell);
    assert(first_dual->nodes[1].supporting_cell == second_dual->nodes[1].supporting_cell);
    assert(first_dual->edges[0].shared_facet == second_dual->edges[0].shared_facet);
}

void rejects_duplicate_vertices_in_a_cell() {
    DelaunaySnapshot snapshot{
        {
            cell({1, 1, 2, 3}, {no_neighbor, no_neighbor, no_neighbor, no_neighbor},
                 {0.0, 0.0, 0.0}),
        },
    };

    const auto result = extract_finite_voronoi_dual(snapshot);

    assert(!result.has_value());
}

}  // namespace

int main() {
    extracts_the_finite_dual_of_two_adjacent_cells();
    rejects_a_nonreciprocal_neighbor_relation();
    ignores_an_infinite_neighbor();
    canonicalizes_node_identity_across_cell_order();
    rejects_duplicate_vertices_in_a_cell();
}
