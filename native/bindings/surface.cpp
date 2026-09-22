#include "../surface_preparation.hpp"
#include "common.hpp"
#include <cstring>
#include <pybind11/numpy.h>
#include <pybind11/stl.h>

namespace py = pybind11;
namespace {
using namespace cad::surface;
void check(const py::array &a, const py::dtype &dtype, int ndim,
           py::ssize_t width = 0) {
  if (!a.dtype().is(dtype) || a.ndim() != ndim ||
      !(a.flags() & py::array::c_style) || (ndim == 2 && a.shape(1) != width))
    throw py::value_error("Surface arrays require native float64/int64 "
                          "C-contiguous layout and declared dimensions");
}
void budget(const SurfaceLimits &limits,
            std::initializer_list<const py::array *> arrays) {
  std::uint64_t bytes = 0;
  for (auto a : arrays) {
    auto n = static_cast<std::uint64_t>(a->size());
    if (n > (limits.max_input_bytes - bytes) / 8)
      throw BudgetExceeded("Surface binding input byte budget");
    bytes += n * 8;
  }
}
template <class T> std::vector<T> copy(const py::array &a, std::size_t count) {
  std::vector<T> out(count);
  if (count)
    std::memcpy(out.data(), a.data(), count * sizeof(T));
  return out;
}
template <class T> py::array_t<T> array(std::span<const T> v) {
  py::array_t<T> a(v.size());
  if (!v.empty())
    std::memcpy(a.mutable_data(), v.data(), v.size_bytes());
  return a;
}
template <class T, std::size_t N>
py::array_t<T> rows(std::span<const std::array<T, N>> v) {
  py::array_t<T> a(
      {static_cast<py::ssize_t>(v.size()), static_cast<py::ssize_t>(N)});
  if (!v.empty())
    std::memcpy(a.mutable_data(), v.data(), v.size_bytes());
  return a;
}
py::dict usage(const Usage &u) {
  py::dict d;
  d["input_bytes"] = u.input_bytes;
  d["owned_bytes"] = u.owned_bytes;
  d["work_steps"] = u.work_steps;
  d["output_bytes"] = u.output_bytes;
  return d;
}
[[noreturn]] void error(SurfaceError e) {
  const auto context = "Surface operation " +
                       std::to_string(static_cast<int>(e.operation)) +
                       " source face " + std::to_string(e.source_face) + ": ";
  switch (e.code) {
  case ErrorCode::input_budget:
    throw BudgetExceeded(context + "input byte budget");
  case ErrorCode::storage_budget:
    throw BudgetExceeded(context + "owned workspace budget");
  case ErrorCode::work_budget:
    throw BudgetExceeded(context + "work budget");
  case ErrorCode::output_budget:
    throw BudgetExceeded(context + "output byte budget");
  case ErrorCode::invalid_input:
    throw py::value_error(context + "invalid input");
  case ErrorCode::invalid_topology:
    throw py::value_error(context + "invalid oriented patch topology");
  case ErrorCode::invalid_geometry:
    throw py::value_error(context + "invalid or degenerate geometry");
  case ErrorCode::numerical_range:
    throw std::overflow_error(context + "numerical range exceeded");
  }
  throw std::logic_error("Unknown surface failure");
}
template <class T> T take(std::expected<T, SurfaceError> r) {
  if (!r)
    error(r.error());
  return std::move(*r);
}
py::dict surface_arrays(const Discretization &s) {
  py::dict d;
  d["vertices"] = rows(s.vertices());
  d["triangles"] = rows(s.triangles());
  d["triangle_edges"] = rows(s.triangle_edges());
  d["source_vertices"] = array(s.source_vertices());
  d["selected_faces"] = array(s.selected_faces());
  d["triangle_faces"] = array(s.triangle_faces());
  d["boundary_vertices"] = array(s.boundary_vertices());
  d["source_face_count"] = s.source_face_count();
  d["usage"] = usage(s.usage());
  return d;
}
} // namespace
void bind_surface(py::module_ &m) {
  using namespace cad::surface;
  py::class_<SurfaceLimits>(m, "SurfaceLimits")
      .def(py::init<std::uint64_t, std::uint64_t, std::uint64_t,
                    std::uint64_t>());
  py::class_<Discretization>(m, "Surface").def("arrays", &surface_arrays);
  py::class_<Operators>(m, "SurfaceOperators")
      .def("arrays", [](const Operators &op) {
        py::dict d;
        const auto &a = op.stiffness();
        d["offsets"] = array<Id>(a.offsets);
        d["columns"] = array<Id>(a.columns);
        d["values"] = array<double>(a.values);
        d["dimension"] = a.dimension;
        d["usage"] = usage(op.usage());
        return d;
      });
  py::class_<AdmittedChart>(m, "AdmittedChart")
      .def("uv", [](const AdmittedChart &c) { return rows(c.uv()); });
  m.def(
      "prepare_surface",
      [](const py::array &vertices, const py::array &edges,
         const py::array &offsets, const py::array &coedges,
         const std::string &unit, const py::array &faces, double tolerance,
         SurfaceLimits limits) {
        check(vertices, py::dtype::of<double>(), 2, 3);
        check(edges, py::dtype::of<Id>(), 2, 2);
        check(offsets, py::dtype::of<Id>(), 1);
        check(coedges, py::dtype::of<Id>(), 1);
        check(faces, py::dtype::of<Id>(), 1);
        budget(limits, {&vertices, &edges, &offsets, &coedges, &faces});
        cad::simplicial::LengthUnit u;
        if (unit == "mm")
          u = cad::simplicial::LengthUnit::Millimeter;
        else if (unit == "cm")
          u = cad::simplicial::LengthUnit::Centimeter;
        else if (unit == "m")
          u = cad::simplicial::LengthUnit::Meter;
        else if (unit == "in")
          u = cad::simplicial::LengthUnit::Inch;
        else
          throw py::value_error("Invalid surface unit");
        PreparationRequest r{{copy<Point>(vertices, vertices.shape(0)),
                              copy<std::array<Id, 2>>(edges, edges.shape(0)),
                              copy<Id>(offsets, offsets.size()),
                              copy<Id>(coedges, coedges.size()), u},
                             copy<Id>(faces, faces.size()),
                             {tolerance},
                             limits};
        auto result = [&] {
          py::gil_scoped_release release;
          return prepare(std::move(r));
        }();
        return take(std::move(result));
      },
      py::arg("vertices").noconvert(), py::arg("edges").noconvert(),
      py::arg("offsets").noconvert(), py::arg("coedges").noconvert(),
      py::arg("unit"), py::arg("faces").noconvert(), py::arg("tolerance"),
      py::arg("limits"));
  m.def(
      "assemble_surface",
      [](Discretization s, const py::array &faces, const py::array &weights,
         SurfaceLimits limits) {
        check(faces, py::dtype::of<Id>(), 1);
        check(weights, py::dtype::of<double>(), 1);
        if (faces.size() != weights.size())
          throw py::value_error("Confidence shape mismatch");
        budget(limits, {&faces, &weights});
        ConfidencePolicy c;
        auto f = copy<Id>(faces, static_cast<std::size_t>(faces.size()));
        auto w =
            copy<double>(weights, static_cast<std::size_t>(weights.size()));
        for (py::ssize_t i = 0; i < faces.size(); ++i)
          c.face_weights.emplace_back(f[i], w[i]);
        auto result = [&] {
          py::gil_scoped_release release;
          return assemble(std::move(s), std::move(c), limits);
        }();
        return take(std::move(result));
      },
      py::arg("surface"), py::arg("faces").noconvert(),
      py::arg("weights").noconvert(), py::arg("limits"));
  m.def(
      "qualify_surface_chart",
      [](Discretization s, const py::array &uv, int orientation,
         double tolerance, SurfaceLimits limits) {
        check(uv, py::dtype::of<double>(), 2, 2);
        budget(limits, {&uv});
        auto values = copy<UV>(uv, uv.shape(0));
        auto result = [&] {
          py::gil_scoped_release release;
          return qualify_chart(std::move(s), std::move(values),
                               {orientation, tolerance}, limits);
        }();
        auto r = take(std::move(result));
        py::dict d;
        d["triangle_count"] = r.quality.triangle_count;
        d["flipped_triangles"] = array<Id>(r.quality.flipped_triangles);
        d["degenerate_triangles"] = array<Id>(r.quality.degenerate_triangles);
        d["minimum_signed_double_area"] = r.quality.minimum_signed_double_area;
        d["maximum_conformal_distortion"] =
            r.quality.maximum_conformal_distortion;
        d["admitted"] =
            r.admitted ? py::cast(std::move(*r.admitted)) : py::none();
        d["usage"] = usage(r.usage);
        return d;
      },
      py::arg("surface"), py::arg("uv").noconvert(), py::arg("orientation"),
      py::arg("tolerance"), py::arg("limits"));
}
