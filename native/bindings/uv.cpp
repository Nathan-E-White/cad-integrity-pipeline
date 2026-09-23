#include "../uv_location.hpp"
#include "common.hpp"
#include <cstring>
#include <pybind11/numpy.h>
#include <pybind11/stl.h>
namespace py = pybind11;
namespace {
using namespace cad::uv;
[[noreturn]] void error(LocationError e) {
  std::string context = "UV operation " +
                        std::to_string(static_cast<int>(e.operation)) +
                        " query " + std::to_string(e.query) + " triangle " +
                        std::to_string(e.triangle) + ": ";
  if (e.code == ErrorCode::invalid_input)
    throw py::value_error(context + "invalid input");
  if (e.code == ErrorCode::numerical_range)
    throw std::overflow_error(context + "numerical range");
  throw BudgetExceeded(context + "budget " +
                       std::to_string(static_cast<int>(e.code)));
}
template <class T> T take(std::expected<T, LocationError> value) {
  if (!value)
    error(value.error());
  return std::move(*value);
}
py::dict usage(Usage u) {
  py::dict d;
  d["input_bytes"] = u.input_bytes;
  d["owned_bytes"] = u.owned_bytes;
  d["work_steps"] = u.work_steps;
  d["output_bytes"] = u.output_bytes;
  return d;
}
py::dict arrays(const Locations &result) {
  const auto q = static_cast<py::ssize_t>(result.records().size());
  const auto c = static_cast<py::ssize_t>(result.candidates().size());
  py::array_t<std::uint8_t> status(q), valid(q);
  py::array_t<double> xyz({q, py::ssize_t(3)}), discrepancy(q);
  py::array_t<std::uint64_t> offsets(q + 1);
  py::array_t<Id> triangles(c), faces(c);
  py::array_t<double> bc({c, py::ssize_t(3)}),
      candidate_xyz({c, py::ssize_t(3)});
  for (py::ssize_t i = 0; i < q; ++i) {
    const auto &r = result.records()[i];
    status.mutable_data()[i] = static_cast<std::uint8_t>(r.status);
    valid.mutable_data()[i] = r.resolved.has_value();
    discrepancy.mutable_data()[i] = r.maximum_discrepancy;
    for (int k = 0; k < 3; ++k)
      xyz.mutable_data()[3 * i + k] = r.resolved ? (*r.resolved)[k] : 0;
  }
  for (py::ssize_t i = 0; i < c; ++i) {
    const auto &r = result.candidates()[i];
    triangles.mutable_data()[i] = r.triangle;
    faces.mutable_data()[i] = r.source_face;
    for (int k = 0; k < 3; ++k) {
      bc.mutable_data()[3 * i + k] = r.barycentric[k];
      candidate_xyz.mutable_data()[3 * i + k] = r.xyz[k];
    }
  }
  std::memcpy(offsets.mutable_data(), result.offsets().data(),
              result.offsets().size() * sizeof(std::uint64_t));
  py::dict d;
  d["status"] = status;
  d["valid"] = valid;
  d["resolved"] = xyz;
  d["discrepancy"] = discrepancy;
  d["offsets"] = offsets;
  d["triangles"] = triangles;
  d["source_faces"] = faces;
  d["barycentric"] = bc;
  d["xyz"] = candidate_xyz;
  d["usage"] = usage(result.usage());
  d["policy"] = py::make_tuple(result.policy().barycentric_tolerance,
                               result.policy().xyz_relative_tolerance);
  d["exhaustion"] = py::none();
  if (auto e = result.exhaustion())
    d["exhaustion"] =
        py::make_tuple(static_cast<int>(e->code), e->query, e->triangle);
  return d;
}
} // namespace
void bind_uv(py::module_ &m) {
  using namespace cad::uv;
  py::class_<Limits>(m, "UVLimits")
      .def(py::init<std::uint64_t, std::uint64_t, std::uint64_t, std::uint64_t,
                    std::uint64_t>());
  py::class_<Locations>(m, "UVLocations").def("arrays", &arrays);
  py::class_<Locator>(m, "UVLocator")
      .def("usage", [](const Locator &l) { return usage(l.usage()); })
      .def(
          "locate",
          [](const Locator &l, const py::array &a, Limits limits) {
            if (!a.dtype().is(py::dtype::of<double>()) || a.ndim() != 2 ||
                a.shape(1) != 2 || !(a.flags() & py::array::c_style))
              throw py::value_error("UV queries require native float64 "
                                    "C-contiguous (Q,2) layout");
            auto n = static_cast<std::uint64_t>(a.shape(0));
            if (n > limits.max_input_bytes / sizeof(UV))
              throw BudgetExceeded("UV binding input byte budget");
            std::vector<UV> owned(n);
            if (n)
              std::memcpy(owned.data(), a.data(), n * sizeof(UV));
            auto result = [&] {
              py::gil_scoped_release release;
              return l.locate({owned, limits});
            }();
            return take(std::move(result));
          },
          py::arg("queries").noconvert(), py::arg("limits"));
  m.def("prepare_uv_locator",
        [](cad::surface::AdmittedChart chart, double tolerance,
           double agreement, Limits limits) {
          auto result = [&] {
            py::gil_scoped_release release;
            return Locator::create(
                {std::move(chart), {tolerance, agreement}, limits});
          }();
          return take(std::move(result));
        });
}
