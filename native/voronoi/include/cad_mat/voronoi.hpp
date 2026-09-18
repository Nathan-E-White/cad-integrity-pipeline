#pragma once

#include <array>
#include <cstdint>
#include <expected>
#include <span>
#include <vector>

namespace cad::mat {

using SampleId = std::uint64_t;
using CellId = std::uint32_t;
using NodeId = std::uint32_t;

/// Reserved; a bridge must not assign this value to an ordinary sample.
inline constexpr SampleId no_sample = UINT64_MAX;
/// Reserved; a bridge must not assign this value to an ordinary cell.
inline constexpr CellId no_neighbor = UINT32_MAX;

struct Point3 {
    double x;
    double y;
    double z;
};

/// A transient finite or infinite cell emitted by the Delaunay bridge.
///
/// ``vertex_ids`` retain the bridge's oriented local order. ``neighbors[i]``
/// denotes the cell across the facet opposite ``vertex_ids[i]``. An infinite
/// cell has no usable circumcenter and is never emitted as a Voronoi node.
struct DelaunayCell {
    std::array<SampleId, 4> vertex_ids;
    std::array<CellId, 4> neighbors;
    Point3 circumcenter;
    double sampled_radius;
    bool is_finite;
};

struct DelaunaySnapshot {
    std::vector<DelaunayCell> cells;
};

struct CellKey {
    std::array<SampleId, 4> sample_ids;
    auto operator<=>(const CellKey&) const = default;
};

struct RawMedialNode {
    NodeId id;
    CellKey supporting_cell;
    Point3 center;
    double sampled_radius;
    std::array<SampleId, 4> supports;
};

struct RawMedialEdge {
    NodeId first_node;
    NodeId second_node;
    std::array<SampleId, 3> shared_facet;
};

enum class ExtractionErrorCode {
    too_many_cells,
    duplicate_vertex_in_cell,
    invalid_cell_vertex_kind,
    duplicate_cell,
    nonfinite_finite_cell_measurement,
    neighbor_out_of_range,
    nonreciprocal_neighbor,
};

struct ExtractionError {
    ExtractionErrorCode code;
    CellId cell;
    CellId neighbor = no_neighbor;
};

/// A value-owned, read-only finite Voronoi-dual snapshot.
class VoronoiDual {
public:
    [[nodiscard]] std::span<const RawMedialNode> nodes() const noexcept {
        return nodes_;
    }

    [[nodiscard]] std::span<const RawMedialEdge> edges() const noexcept {
        return edges_;
    }

private:
    std::vector<RawMedialNode> nodes_;
    std::vector<RawMedialEdge> edges_;

    friend std::expected<VoronoiDual, ExtractionError> extract_finite_voronoi_dual(
        const DelaunaySnapshot& snapshot);
};

/// Extract the finite Voronoi dual represented by a Delaunay snapshot.
///
/// The bridge which supplies ``snapshot`` is responsible for robust Delaunay
/// predicates and circumcenter construction. This operation only validates
/// snapshot incidence, canonicalizes durable identities, and excludes every
/// infinite cell and dual ray from the finite medial graph.
[[nodiscard]] std::expected<VoronoiDual, ExtractionError> extract_finite_voronoi_dual(
    const DelaunaySnapshot& snapshot);

}  // namespace cad::mat
