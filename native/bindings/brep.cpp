#include "../brep_realization.hpp"
#include "common.hpp"
#include <cstring>
#include <pybind11/numpy.h>
#include <pybind11/stl.h>
namespace py = pybind11;
namespace {
using namespace cad::occt_adapter;
void check(const py::array &a, const py::dtype &dtype, int width,
           std::uint64_t &bytes, const cad::surface::SurfaceLimits &limits) {
  if (!a.dtype().is(dtype) || !(a.flags() & py::array::c_style) ||
      a.ndim() != (width == 1 ? 1 : 2) || (width != 1 && a.shape(1) != width))
    throw py::value_error(
        "Realization requires native contiguous float64/int64 arrays");
  auto n = static_cast<std::uint64_t>(a.size());
  if (n > (limits.max_input_bytes - bytes) / 8)
    throw BudgetExceeded("Realization binding input budget");
  bytes += n * 8;
}
template <class T> std::vector<T> copy(const py::array &a) {
  std::vector<T> out(static_cast<std::size_t>(a.nbytes()) / sizeof(T));
  if (!out.empty())
    std::memcpy(out.data(), a.data(), static_cast<std::size_t>(a.nbytes()));
  return out;
}
const char *name(RealizationDiagnostic d) {
  switch (d) {
  case RealizationDiagnostic::invalid_evidence:
    return "invalid_evidence";
  case RealizationDiagnostic::coordinate_disagreement:
    return "coordinate_disagreement";
  case RealizationDiagnostic::degenerate_triangle:
    return "degenerate_triangle";
  case RealizationDiagnostic::edge_correspondence:
    return "edge_correspondence";
  case RealizationDiagnostic::orientation:
    return "orientation";
  case RealizationDiagnostic::nonmanifold_vertex:
    return "nonmanifold_vertex";
  }
  throw std::logic_error("Unknown realization diagnostic");
}
} // namespace
void bind_brep(py::module_ &m) {
  using namespace cad::occt_adapter;
  m.def(
      "realize_brep",
      [](const py::array &nodes, const py::array &keys,
         const py::array &triangles, const py::array &faces,
         const py::array &segments, const py::array &uses, Id face_count,
         Id vertex_count, double tolerance,
         cad::surface::SurfaceLimits limits) {
        std::uint64_t bytes = 0;
        check(nodes, py::dtype::of<double>(), 3, bytes, limits);
        check(keys, py::dtype::of<Id>(), 3, bytes, limits);
        check(triangles, py::dtype::of<Id>(), 3, bytes, limits);
        check(faces, py::dtype::of<Id>(), 1, bytes, limits);
        check(segments, py::dtype::of<Id>(), 4, bytes, limits);
        check(uses, py::dtype::of<Id>(), 1, bytes, limits);
        RealizationRequest request{copy<Point>(nodes),
                                   copy<Triangle>(keys),
                                   copy<Triangle>(triangles),
                                   copy<Id>(faces),
                                   copy<std::array<Id, 4>>(segments),
                                   copy<Id>(uses),
                                   face_count,
                                   vertex_count,
                                   tolerance,
                                   limits};
        auto result = [&] {
          py::gil_scoped_release release;
          return realize(std::move(request));
        }();
        if (!result)
          throw BudgetExceeded(
              "Realization native budget " +
              std::to_string(static_cast<int>(result.error().code)));
        py::dict out;
        std::vector<std::string> diagnostics;
        for (auto d : result->diagnostics)
          diagnostics.emplace_back(name(d));
        out["diagnostics"] = diagnostics;
        out["surface"] = result->admitted
                             ? py::cast(result->admitted->surface())
                             : py::none();
        py::array_t<Id> ids(result->admitted
                                ? result->admitted->native_vertex_ids().size()
                                : 0);
        if (result->admitted) {
          auto v = result->admitted->native_vertex_ids();
          if (!v.empty())
            std::memcpy(ids.mutable_data(), v.data(), v.size_bytes());
        }
        out["native_vertex_ids"] = std::move(ids);
        return out;
      },
      py::arg("nodes").noconvert(), py::arg("keys").noconvert(),
      py::arg("triangles").noconvert(), py::arg("faces").noconvert(),
      py::arg("segments").noconvert(), py::arg("uses").noconvert(),
      py::arg("face_count"), py::arg("vertex_count"), py::arg("tolerance"),
      py::arg("limits"));
}
