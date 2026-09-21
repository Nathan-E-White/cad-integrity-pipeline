#include "SimplicialComplex.hpp"
#include "cad_mat/nurbs.hpp"
#include "cad_mat/voronoi.hpp"

#include <array>
#include <cstdlib>

int main() {
  const auto complex = cad::simplicial::SimplicialComplex::build({{0, 1, 2}});
  if (!complex || complex->get_tier(1).size() != 3) {
    return EXIT_FAILURE;
  }
  const std::array knots{0.0, 0.0, 1.0, 1.0};
  const std::array parameters{0.5};
  const auto basis = cad::nurbs::basis_derivatives(1, knots, parameters, 0);
  if (!basis || basis->derivative(0, 0, 0) != 0.5 ||
      basis->derivative(0, 0, 1) != 0.5) {
    return EXIT_FAILURE;
  }
  const auto dual = cad::mat::extract_finite_voronoi_dual({});
  if (!dual || !dual->nodes().empty() || !dual->edges().empty()) {
    return EXIT_FAILURE;
  }
  return EXIT_SUCCESS;
}
