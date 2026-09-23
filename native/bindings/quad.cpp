#include "../quad_tracing.hpp"
#include "common.hpp"
#include <cstring>
#include <pybind11/numpy.h>
#include <pybind11/stl.h>
namespace py = pybind11;
namespace {
using namespace cad::trace;
[[noreturn]] void error(TraceError e) {
  auto message =
      "Quad operation code " + std::to_string(static_cast<int>(e.code)) + " " +
      std::array<const char *, 5>{"request", "seed", "vertex", "edge",
                                  "face"}[static_cast<std::size_t>(e.domain)] +
      " " + std::to_string(e.entity);
  if (e.code == ErrorCode::invalid_patch || e.code == ErrorCode::invalid_seed)
    throw py::value_error(message);
  if (e.code == ErrorCode::numerical_range)
    throw std::overflow_error(message);
  throw BudgetExceeded(message);
}
template <class T> T take(std::expected<T, TraceError> r) {
  if (!r)
    error(r.error());
  return std::move(*r);
}
void check(const py::array &a, const py::dtype &dtype, int ndim,
           int width = 0) {
  if (!a.dtype().is(dtype) || a.ndim() != ndim ||
      !(a.flags() & py::array::c_style) || (ndim == 2 && a.shape(1) != width))
    throw py::value_error("Quad arrays require native float64/int64 "
                          "C-contiguous declared layout");
}
template <class T> std::vector<T> copy(const py::array &a, std::size_t count) {
  std::vector<T> v(count);
  if (count)
    std::memcpy(v.data(), a.data(), count * sizeof(T));
  return v;
}
py::dict usage(Usage u) {
  py::dict d;
  d["owned_bytes"] = u.owned_bytes;
  d["work_steps"] = u.work_steps;
  d["output_bytes"] = u.output_bytes;
  return d;
}
py::list seeds(std::span<const Seed> values) {
  py::list out;
  for (auto s : values)
    out.append(py::make_tuple(s.id.value, s.vertex.value, s.edge.value));
  return out;
}
py::dict patch_arrays(const AdmittedQuadPatch &p) {
  const auto &r = p.input();
  py::dict d;
  d["vertices"] = r.vertices;
  d["edges"] = r.edges;
  d["face_offsets"] = r.face_offsets;
  d["face_coedges"] = r.face_coedges;
  d["boundary_edges"] =
      std::vector<Id>(p.boundary_edges().begin(), p.boundary_edges().end());
  d["seeds"] = seeds(p.canonical_seeds());
  d["usage"] = usage(p.usage());
  return d;
}
py::dict result_arrays(const TraceResult &r) {
  py::dict d;
  d["canonical"] = r.canonical;
  d["stop"] = static_cast<int>(r.stop);
  d["last_committed_time2"] = r.last_committed_time2;
  d["seeds"] = seeds(r.seeds);
  py::list unfinished;
  for (auto id : r.unfinished)
    unfinished.append(id.value);
  d["unfinished"] = unfinished;
  d["usage"] = usage(r.usage);
  py::list segments, events;
  for (auto s : r.segments)
    segments.append(py::make_tuple(s.seed.value, s.edge.value,
                                   s.from_vertex.value, s.to_vertex.value,
                                   s.start2, s.end2));
  for (auto e : r.events)
    events.append(py::make_tuple(e.time2, e.seed.value, e.edge.value,
                                 e.vertex.value, static_cast<int>(e.reason),
                                 e.blocker.value, e.deposited_time2));
  d["segments"] = segments;
  d["events"] = events;
  return d;
}
} // namespace
void bind_quad(py::module_ &m) {
  using namespace cad::trace;
  py::class_<Limits>(m, "QuadLimits")
      .def(py::init<std::uint64_t, std::uint64_t, std::uint64_t, std::uint64_t,
                    std::uint64_t>());
  py::class_<TraceResult>(m, "QuadTraceResult").def("arrays", &result_arrays);
  py::class_<AdmittedQuadPatch>(m, "QuadPatch")
      .def("arrays", &patch_arrays)
      .def(
          "trace",
          [](const AdmittedQuadPatch &p, const py::array &a, Limits limits) {
            check(a, py::dtype::of<Id>(), 2, 3);
            auto n = static_cast<std::uint64_t>(a.shape(0));
            if (n > limits.max_owned_bytes / 1024)
              throw BudgetExceeded("Quad seed copy budget");
            static_assert(sizeof(Seed) == 3 * sizeof(Id));
            auto owned = copy<Seed>(a, n);
            auto r = [&] {
              py::gil_scoped_release release;
              return trace_quads(p, owned, limits);
            }();
            return take(std::move(r));
          },
          py::arg("seeds").noconvert(), py::arg("limits"));
  m.def(
      "prepare_quad_patch",
      [](const py::array &v, const py::array &e, const py::array &o,
         const py::array &c, const std::string &unit, std::uint64_t input_bytes,
         std::uint64_t owned_bytes, std::uint64_t steps,
         std::uint64_t output_bytes) {
        using namespace cad::simplicial;
        check(v, py::dtype::of<double>(), 2, 3);
        check(e, py::dtype::of<Id>(), 2, 2);
        check(o, py::dtype::of<Id>(), 1);
        check(c, py::dtype::of<Id>(), 1);
        std::uint64_t total = 0;
        for (const auto *a : {&v, &e, &o, &c}) {
          auto n = static_cast<std::uint64_t>(a->size());
          if (n > (input_bytes - total) / 8)
            throw BudgetExceeded("Quad input byte budget");
          total += 8 * n;
        }
        LengthUnit u;
        if (unit == "mm")
          u = LengthUnit::Millimeter;
        else if (unit == "cm")
          u = LengthUnit::Centimeter;
        else if (unit == "m")
          u = LengthUnit::Meter;
        else if (unit == "in")
          u = LengthUnit::Inch;
        else
          throw py::value_error("Unknown quad length unit");
        PolygonalInput raw{copy<std::array<double, 3>>(v, v.shape(0)),
                           copy<std::array<Id, 2>>(e, e.shape(0)),
                           copy<Id>(o, o.size()), copy<Id>(c, c.size()), u};
        auto assessment = [&] {
          py::gil_scoped_release release;
          return assess_polygonal(
              std::move(raw), {input_bytes, owned_bytes, steps, output_bytes});
        }();
        if (!assessment) {
          if (assessment.error() == PolygonalError::invalid_input)
            throw py::value_error("Invalid quad input");
          throw BudgetExceeded(
              "Quad polygonal assessment budget " +
              std::to_string(static_cast<int>(assessment.error())));
        }
        auto spent = assessment->usage();
        auto result = [&] {
          py::gil_scoped_release release;
          return AdmittedQuadPatch::create(
              std::move(*assessment),
              {owned_bytes, steps - spent.work_steps, output_bytes});
        }();
        return take(std::move(result));
      },
      py::arg("vertices").noconvert(), py::arg("edges").noconvert(),
      py::arg("offsets").noconvert(), py::arg("coedges").noconvert(),
      py::arg("unit"), py::arg("input_bytes"), py::arg("owned_bytes"),
      py::arg("steps"), py::arg("output_bytes"));
}
