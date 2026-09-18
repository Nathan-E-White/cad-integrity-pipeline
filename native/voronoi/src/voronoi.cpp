#include "cad_mat/voronoi.hpp"

#include <algorithm>
#include <cmath>
#include <limits>
#include <map>
#include <tuple>

namespace cad::mat {
namespace {

[[nodiscard]] CellKey cell_key(const DelaunayCell& cell) {
    auto ids = cell.vertex_ids;
    std::sort(ids.begin(), ids.end());
    return {ids};
}

[[nodiscard]] bool has_distinct_vertices(const DelaunayCell& cell) {
    const auto key = cell_key(cell);
    return std::adjacent_find(key.sample_ids.begin(), key.sample_ids.end()) == key.sample_ids.end();
}

[[nodiscard]] bool has_valid_vertex_kind(const DelaunayCell& cell) {
    const auto infinite_vertices = std::count(cell.vertex_ids.begin(), cell.vertex_ids.end(), no_sample);
    return cell.is_finite ? infinite_vertices == 0 : infinite_vertices == 1;
}

[[nodiscard]] bool is_finite(const Point3& point) {
    return std::isfinite(point.x) && std::isfinite(point.y) && std::isfinite(point.z);
}

[[nodiscard]] std::array<SampleId, 3> facet_opposite(const DelaunayCell& cell, std::size_t vertex) {
    std::array<SampleId, 3> facet{};
    std::size_t destination = 0;
    for (std::size_t source = 0; source < cell.vertex_ids.size(); ++source) {
        if (source != vertex) {
            facet[destination++] = cell.vertex_ids[source];
        }
    }
    std::sort(facet.begin(), facet.end());
    return facet;
}

[[nodiscard]] bool has_reciprocal_facet(const DelaunayCell& neighbor, CellId cell,
                                        const std::array<SampleId, 3>& facet) {
    for (std::size_t side = 0; side < neighbor.neighbors.size(); ++side) {
        if (neighbor.neighbors[side] == cell && facet_opposite(neighbor, side) == facet) {
            return true;
        }
    }
    return false;
}

}  // namespace

std::expected<VoronoiDual, ExtractionError> extract_finite_voronoi_dual(
    const DelaunaySnapshot& snapshot) {
    if (snapshot.cells.size() > std::numeric_limits<CellId>::max()) {
        return std::unexpected(ExtractionError{ExtractionErrorCode::too_many_cells, no_neighbor});
    }

    std::map<CellKey, CellId> canonical_cells;
    std::vector<std::pair<CellKey, CellId>> finite_cells;
    finite_cells.reserve(snapshot.cells.size());
    for (CellId id = 0; id < snapshot.cells.size(); ++id) {
        const auto& cell = snapshot.cells[id];
        if (!has_distinct_vertices(cell)) {
            return std::unexpected(ExtractionError{ExtractionErrorCode::duplicate_vertex_in_cell, id});
        }
        if (!has_valid_vertex_kind(cell)) {
            return std::unexpected(ExtractionError{ExtractionErrorCode::invalid_cell_vertex_kind, id});
        }
        const auto key = cell_key(cell);
        if (canonical_cells.contains(key)) {
            return std::unexpected(ExtractionError{ExtractionErrorCode::duplicate_cell, id});
        }
        canonical_cells.emplace(key, id);
        if (!cell.is_finite) {
            continue;
        }
        if (!is_finite(cell.circumcenter) || !std::isfinite(cell.sampled_radius)
            || cell.sampled_radius < 0.0) {
            return std::unexpected(
                ExtractionError{ExtractionErrorCode::nonfinite_finite_cell_measurement, id});
        }
        finite_cells.emplace_back(key, id);
    }

    // Validate every supplied incidence, including those which touch the
    // infinite vertex. Infinite cells do not emit graph features, but they
    // remain bridge evidence and cannot be malformed silently.
    for (CellId cell_id = 0; cell_id < snapshot.cells.size(); ++cell_id) {
        const auto& cell = snapshot.cells[cell_id];
        for (std::size_t side = 0; side < cell.neighbors.size(); ++side) {
            const CellId neighbor_id = cell.neighbors[side];
            if (neighbor_id == no_neighbor) {
                continue;
            }
            if (neighbor_id >= snapshot.cells.size()) {
                return std::unexpected(
                    ExtractionError{ExtractionErrorCode::neighbor_out_of_range, cell_id, neighbor_id});
            }
            if (neighbor_id == cell_id) {
                return std::unexpected(
                    ExtractionError{ExtractionErrorCode::nonreciprocal_neighbor, cell_id, neighbor_id});
            }
            if (!has_reciprocal_facet(snapshot.cells[neighbor_id], cell_id,
                                      facet_opposite(cell, side))) {
                return std::unexpected(
                    ExtractionError{ExtractionErrorCode::nonreciprocal_neighbor, cell_id, neighbor_id});
            }
        }
    }

    std::sort(finite_cells.begin(), finite_cells.end());
    VoronoiDual dual;
    dual.nodes_.reserve(finite_cells.size());
    std::vector<NodeId> node_for_cell(snapshot.cells.size(), no_neighbor);
    for (NodeId node = 0; node < finite_cells.size(); ++node) {
        const auto [key, cell_id] = finite_cells[node];
        const auto& cell = snapshot.cells[cell_id];
        node_for_cell[cell_id] = node;
        dual.nodes_.push_back({node, key, cell.circumcenter, cell.sampled_radius, key.sample_ids});
    }

    for (CellId cell_id = 0; cell_id < snapshot.cells.size(); ++cell_id) {
        const auto& cell = snapshot.cells[cell_id];
        if (!cell.is_finite) {
            continue;
        }
        for (std::size_t side = 0; side < cell.neighbors.size(); ++side) {
            const CellId neighbor_id = cell.neighbors[side];
            if (neighbor_id == no_neighbor || !snapshot.cells[neighbor_id].is_finite
                || cell_id >= neighbor_id) {
                continue;
            }
            const NodeId first = node_for_cell[cell_id];
            const NodeId second = node_for_cell[neighbor_id];
            if (first == no_neighbor || second == no_neighbor) {
                return std::unexpected(
                    ExtractionError{ExtractionErrorCode::nonreciprocal_neighbor, cell_id, neighbor_id});
            }
            dual.edges_.push_back({std::min(first, second), std::max(first, second),
                                   facet_opposite(cell, side)});
        }
    }

    std::sort(dual.edges_.begin(), dual.edges_.end(), [](const RawMedialEdge& left,
                                                          const RawMedialEdge& right) {
        return std::tie(left.first_node, left.second_node, left.shared_facet)
            < std::tie(right.first_node, right.second_node, right.shared_facet);
    });
    dual.edges_.erase(std::unique(dual.edges_.begin(), dual.edges_.end(),
                                  [](const RawMedialEdge& left, const RawMedialEdge& right) {
                                      return left.first_node == right.first_node
                                          && left.second_node == right.second_node
                                          && left.shared_facet == right.shared_facet;
                                  }),
                      dual.edges_.end());
    return dual;
}

}  // namespace cad::mat
