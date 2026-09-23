#include "cad_mat/nurbs.hpp"
#include "common.hpp"
#include <cstring>
#include <limits>
#include <pybind11/numpy.h>
#include <stdexcept>

namespace py = pybind11;
namespace {
using namespace cad::nurbs;
using Size = std::uint64_t;
Size add(Size a, Size b) {
  if (b > std::numeric_limits<Size>::max() - a)
    throw std::overflow_error("NURBS allocation size overflow");
  return a + b;
}
Size mul(Size a, Size b) {
  if (a && b > std::numeric_limits<Size>::max() / a)
    throw std::overflow_error("NURBS allocation size overflow");
  return a * b;
}
void check(const py::array &a, int ndim) {
  if (!a.dtype().is(py::dtype::of<double>()) || a.ndim() != ndim ||
      !(a.flags() & py::array::c_style))
    throw py::value_error("NURBS arrays require native float64 C-contiguous layout");
  for (int axis = 0; axis < ndim; ++axis)
    if (static_cast<Size>(a.shape(axis)) > std::numeric_limits<std::uint32_t>::max())
      throw std::overflow_error("NURBS dimension exceeds uint32");
}
template<class T> std::vector<T> copy(const py::array &a, Size count) {
  std::vector<T> out(count);
  if (count) std::memcpy(out.data(), a.data(), count * sizeof(T));
  return out;
}
[[noreturn]] void arithmetic_error(const char *message) {
  PyErr_SetString(PyExc_ArithmeticError, message);
  throw py::error_already_set();
}
[[noreturn]] void error(SurfaceError e) {
  switch (e.code) {
  case SurfaceErrorCode::invalid_degree:
    throw py::value_error("invalid_degree");
  case SurfaceErrorCode::invalid_knot_vector:
    throw py::value_error("invalid_knot_vector");
  case SurfaceErrorCode::parameter_out_of_domain:
    throw py::value_error("parameter_out_of_domain");
  case SurfaceErrorCode::nonfinite_input:
    throw py::value_error("nonfinite_input");
  case SurfaceErrorCode::invalid_derivative_order:
    throw py::value_error("invalid_derivative_order");
  case SurfaceErrorCode::input_too_large:
    throw std::overflow_error("input_too_large");
  case SurfaceErrorCode::control_net_shape_mismatch:
    throw py::value_error("control_net_shape_mismatch");
  case SurfaceErrorCode::nonpositive_weight:
    throw py::value_error("nonpositive_weight");
  case SurfaceErrorCode::invalid_regularity_tolerance:
    throw py::value_error("invalid_regularity_tolerance");
  case SurfaceErrorCode::rational_denominator_underflow:
    arithmetic_error("rational_denominator_underflow");
  case SurfaceErrorCode::nonfinite_derivative:
    arithmetic_error("nonfinite_derivative");
  case SurfaceErrorCode::singular_surface:
    arithmetic_error("singular_surface");
  }
  throw std::logic_error("unknown NURBS surface error");
}
template<class T> py::array_t<T> array(std::span<const T> values,
                                      std::vector<py::ssize_t> shape) {
  py::array_t<T> out(shape);
  if (!values.empty()) std::memcpy(out.mutable_data(), values.data(), values.size_bytes());
  return out;
}
py::array_t<double> points(std::span<const Point3> values, py::ssize_t u, py::ssize_t v) {
  py::array_t<double> out({u, v, py::ssize_t{3}});
  auto *p = out.mutable_data();
  for (auto x : values) { *p++ = x.x; *p++ = x.y; *p++ = x.z; }
  return out;
}
}
void bind_nurbs(py::module_ &m) {
  m.def("evaluate_nurbs", [](std::uint32_t pu, std::uint32_t pv,
      const py::array &ku, const py::array &kv, const py::array &cp,
      const py::array &u, const py::array &v, double tolerance, bool reject,
      Size max_input, Size max_owned, Size max_output, Size max_work) {
    check(ku, 1); check(kv, 1); check(cp, 3); check(u, 1); check(v, 1);
    if (cp.shape(2) != 4) throw py::value_error("NURBS control net requires (Nu,Nv,4)");
    if (pu > static_cast<unsigned>(std::numeric_limits<int>::max()) ||
        pv > static_cast<unsigned>(std::numeric_limits<int>::max()))
      throw py::value_error("invalid_degree");
    Size input = 0;
    for (auto a : {&ku, &kv, &cp, &u, &v}) input = add(input, mul(a->size(), 8));
    const Size nu = u.size(), nv = v.size(), lu = Size{pu} + 1, lv = Size{pv} + 1;
    const auto count = mul(nu, nv);
    const auto output = mul(count, 81); // 10 doubles and a byte per sample
    const auto basis = add(mul(nu, add(4, mul(24, lu))), mul(nv, add(4, mul(24, lv))));
    // Conservative simultaneous payload bound, including both scratch arrays,
    // normalized net, native results and independently owned NumPy exports.
    const auto scratch = mul(8, add(add(mul(lu, lu), mul(4, lu)),
                                    add(mul(lv, lv), mul(4, lv))));
    const auto owned = add(add(input, mul(cp.size(), 8)), add(basis, add(scratch, mul(2, output))));
    const auto work = add(mul(6, mul(count, mul(lu, lv))),
                          add(mul(6, mul(nu, mul(lu, lu))), mul(6, mul(nv, mul(lv, lv)))));
    if (input > max_input || owned > max_owned || output > max_output || work > max_work)
      throw BudgetExceeded("NURBS input/owned/output/work budget exceeded");
    static_assert(sizeof(HomogeneousPoint) == 4 * sizeof(double));
    SurfaceSpec spec{pu, pv, copy<double>(ku, ku.size()), copy<double>(kv, kv.size()),
      copy<HomogeneousPoint>(cp, cp.size()/4),
      static_cast<std::uint32_t>(cp.shape(0)), static_cast<std::uint32_t>(cp.shape(1))};
    auto us = copy<double>(u, nu), vs = copy<double>(v, nv);
    auto result = [&] {
      py::gil_scoped_release release;
      return evaluate_surface(spec, {us, vs, tolerance,
        reject ? SingularPolicy::reject : SingularPolicy::mask});
    }();
    if (!result) error(result.error());
    const auto &r = *result;
    const std::vector<py::ssize_t> shape{u.size(), v.size()};
    py::dict d;
    d["points"] = points(r.points(), u.size(), v.size());
    d["normals"] = points(r.normals(), u.size(), v.size());
    d["principal_max"] = array(r.principal_max(), shape);
    d["principal_min"] = array(r.principal_min(), shape);
    d["mean"] = array(r.mean(), shape);
    d["gaussian"] = array(r.gaussian(), shape);
    py::array_t<bool> mask(shape);
    for (Size i=0; i<count; ++i) mask.mutable_data()[i] = r.valid_mask()[i] != 0;
    d["valid_mask"] = std::move(mask);
    return d;
  }, py::arg("degree_u"), py::arg("degree_v"), py::arg("knots_u").noconvert(),
     py::arg("knots_v").noconvert(), py::arg("control_points").noconvert(),
     py::arg("u").noconvert(), py::arg("v").noconvert(), py::arg("tolerance"),
     py::arg("reject"), py::arg("max_input_bytes"), py::arg("max_owned_bytes"),
     py::arg("max_output_bytes"), py::arg("max_work_steps"));
}
