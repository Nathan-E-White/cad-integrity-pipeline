#include "common.hpp"
#include "../f2_reduction.hpp"
#include "../SimplicialComplex.hpp"
#include <pybind11/numpy.h>
#include <pybind11/pybind11.h>
#include <cstring>
#include <stdexcept>

namespace py = pybind11;
namespace {
using Row = std::int64_t;

void check_array(const py::array& array) {
    if (!array.dtype().is(py::dtype::of<Row>()) || array.ndim() != 1 ||
        !(array.flags() & py::array::c_style))
        throw py::value_error("F_2 arrays must be one-dimensional C-contiguous native int64");
}
std::vector<Row> copy_array(const py::array& array) {
    std::vector<Row> result(static_cast<std::size_t>(array.size()));
    if (!result.empty()) std::memcpy(result.data(), array.data(), result.size() * sizeof(Row));
    return result;
}
py::array_t<Row> owned_array(const std::vector<Row>& values) {
    py::array_t<Row> result(values.size());
    if (!values.empty()) std::memcpy(result.mutable_data(), values.data(), values.size() * sizeof(Row));
    return result;
}
void translate(cad::f2::ReductionError error) {
    using enum cad::f2::ReductionError;
    switch (error) {
    case invalid_input: throw py::value_error("F_2 offsets or canonical columns are invalid");
    case input_budget: throw BudgetExceeded("F_2 input exceeds the configured reduction budget");
    case storage_budget: throw BudgetExceeded("F_2 fill-in exceeds the storage budget");
    case work_budget: throw BudgetExceeded("F_2 reduction exceeded its work/storage budget");
    case trace_budget: throw BudgetExceeded("F_2 trace exceeds the evidence budget");
    case output_budget: throw BudgetExceeded("F_2 output exceeds the output budget");
    }
}
py::dict reduce(const py::array& offsets, const py::array& values, const std::string& evidence,
                std::uint64_t columns, std::uint64_t stored, std::uint64_t steps,
                std::uint64_t trace, std::uint64_t output) {
    check_array(offsets);
    check_array(values);
    if (offsets.size() == 0) throw py::value_error("F_2 offsets must include a zero sentinel");
    if (static_cast<std::uint64_t>(offsets.size() - 1) > columns ||
        static_cast<std::uint64_t>(values.size()) > stored)
        translate(cad::f2::ReductionError::input_budget);
    cad::f2::EvidenceMode mode;
    if (evidence == "rank_only") mode = cad::f2::EvidenceMode::rank_only;
    else if (evidence == "reduced_columns") mode = cad::f2::EvidenceMode::reduced_columns;
    else if (evidence == "full_trace") mode = cad::f2::EvidenceMode::full_trace;
    else throw py::value_error("Unknown F_2 evidence mode");
    // Both arrays are copied while the GIL is held. No borrowed buffer is read
    // by numerical code, and no Python allocation occurs while the GIL is released.
    const cad::f2::Columns input{copy_array(offsets), copy_array(values)};
    const cad::f2::Limits limits{columns, stored, steps, trace, output};
    std::expected<cad::f2::ReductionResult, cad::f2::ReductionError> result;
    {
        py::gil_scoped_release release;
        result = cad::f2::reduce(input, mode, limits);
    }
    if (!result) translate(result.error());
    py::dict answer;
    answer["pivot_offsets"] = owned_array(result->pivots.offsets);
    answer["pivot_values"] = owned_array(result->pivots.values);
    answer["reduced_offsets"] = owned_array(result->reduced.offsets);
    answer["reduced_values"] = owned_array(result->reduced.values);
    answer["state_offsets"] = owned_array(result->traces.offsets);
    answer["state_values"] = owned_array(result->traces.values);
    answer["trace_offsets"] = owned_array(result->trace_offsets);
    answer["xor_steps"] = result->xor_steps;
    answer["stored_entries"] = result->stored_entries;
    answer["trace_entries"] = result->trace_entries;
    answer["output_bytes"] = result->output_bytes;
    return answer;
}
[[noreturn]] void polygonal_error(cad::simplicial::PolygonalError error) {
    using enum cad::simplicial::PolygonalError;
    switch (error) {
    case invalid_input: throw py::value_error("Invalid polygonal input layout, references, coordinates or unit");
    case input_budget: throw BudgetExceeded("Polygonal input exceeds the input byte budget");
    case storage_budget: throw BudgetExceeded("Polygonal assessment exceeds the workspace budget");
    case work_budget: throw BudgetExceeded("Polygonal assessment exceeds the work budget");
    case output_budget: throw BudgetExceeded("Polygonal assessment exceeds the output byte budget");
    }
    throw std::logic_error("Unknown polygonal error");
}
void polygonal_array(const py::array& array, const py::dtype& dtype, int ndim, py::ssize_t width = 0) {
    if (!array.dtype().is(dtype) || array.ndim() != ndim || !(array.flags() & py::array::c_style) ||
        (ndim == 2 && array.shape(1) != width))
        throw py::value_error("Polygonal arrays require native float64 XYZ and int64 connectivity in C-contiguous layout");
}
py::tuple incidence(const cad::simplicial::SparseCSR& matrix) {
    // Row/index sizes were checked against int64 before native admission.
    return py::make_tuple(owned_array(std::vector<Row>(matrix.row_ptr.begin(), matrix.row_ptr.end())),
        owned_array(std::vector<Row>(matrix.col_ind.begin(), matrix.col_ind.end())),
        owned_array(std::vector<Row>(matrix.values.begin(), matrix.values.end())),
        owned_array({static_cast<Row>(matrix.num_rows), static_cast<Row>(matrix.num_cols)}));
}
py::dict assess_polygonal(const py::array& vertices, const py::array& edges,
                         const py::array& offsets, const py::array& coedges, const std::string& unit,
                         std::uint64_t input_bytes, std::uint64_t owned_bytes,
                         std::uint64_t steps, std::uint64_t output_bytes) {
    using namespace cad::simplicial;
    polygonal_array(vertices, py::dtype::of<double>(), 2, 3);
    polygonal_array(edges, py::dtype::of<Row>(), 2, 2);
    polygonal_array(offsets, py::dtype::of<Row>(), 1);
    polygonal_array(coedges, py::dtype::of<Row>(), 1);
    std::uint64_t total = 0;
    for (const auto* array : {&vertices, &edges, &offsets, &coedges}) {
        const auto count = static_cast<std::uint64_t>(array->size());
        if (count > (input_bytes-total)/8) polygonal_error(PolygonalError::input_budget);
        total += count*8;
    }
    LengthUnit length_unit;
    if (unit == "mm") length_unit = LengthUnit::Millimeter;
    else if (unit == "cm") length_unit = LengthUnit::Centimeter;
    else if (unit == "m") length_unit = LengthUnit::Meter;
    else if (unit == "in") length_unit = LengthUnit::Inch;
    else polygonal_error(PolygonalError::invalid_input);
    PolygonalInput input;
    input.length_unit = length_unit;
    input.vertices.resize(static_cast<std::size_t>(vertices.shape(0)));
    input.edges.resize(static_cast<std::size_t>(edges.shape(0)));
    if (!input.vertices.empty()) std::memcpy(input.vertices.data(), vertices.data(), input.vertices.size()*sizeof(input.vertices[0]));
    if (!input.edges.empty()) std::memcpy(input.edges.data(), edges.data(), input.edges.size()*sizeof(input.edges[0]));
    input.face_offsets = copy_array(offsets); input.face_coedges = copy_array(coedges);
    const PolygonalLimits limits{input_bytes, owned_bytes, steps, output_bytes};
    auto result = [&] {
        py::gil_scoped_release release;
        return cad::simplicial::assess_polygonal(std::move(input), limits);
    }();
    if (!result) polygonal_error(result.error());
    const auto& facts = result->facts();
    py::dict answer;
    answer["boundary_edge_ids"] = owned_array(facts.boundary_edge_ids);
    answer["nonmanifold_edge_ids"] = owned_array(facts.nonmanifold_edge_ids);
    answer["inconsistent_orientation_edge_ids"] = owned_array(facts.inconsistent_orientation_edge_ids);
    answer["nonmanifold_vertex_ids"] = owned_array(facts.nonmanifold_vertex_ids);
    answer["unused_vertex_ids"] = owned_array(facts.unused_vertex_ids);
    answer["unused_edge_ids"] = owned_array(facts.unused_edge_ids);
    answer["invalid_face_ids"] = owned_array(facts.invalid_face_ids);
    answer["duplicate_face_ids"] = owned_array(facts.duplicate_face_ids);
    answer["collapsed_edge_ids"] = owned_array(facts.collapsed_edge_ids);
    answer["edge_offsets"] = owned_array(facts.edge_offsets);
    answer["edge_faces"] = owned_array(facts.edge_faces);
    answer["edge_signs"] = owned_array(facts.edge_signs);
    answer["edge_order"] = owned_array(facts.edge_order);

    answer["multipliers"] = owned_array(result->orientation().multipliers);
    answer["conflicting_edge_ids"] = owned_array(result->orientation().conflicting_edge_ids);
    answer["orientation_nonmanifold_edge"] = result->orientation().nonmanifold_edge
        ? py::cast(*result->orientation().nonmanifold_edge) : py::none();
    answer["admitted"] = result->admitted_cells().has_value();
    if (result->admitted_cells()) {
        answer["d1"] = incidence(result->admitted_cells()->boundary(1));
        answer["d2"] = incidence(result->admitted_cells()->boundary(2));
    }
    py::dict usage;
    usage["input_bytes"] = result->usage().input_bytes;
    usage["owned_bytes"] = result->usage().owned_bytes;
    usage["work_steps"] = result->usage().work_steps;
    usage["output_bytes"] = result->usage().output_bytes;
    answer["usage"] = usage;
    return answer;
}

}
PYBIND11_MODULE(_native, module) {
    py::register_exception<BudgetExceeded>(module, "BudgetExceeded");
    py::register_exception_translator([](std::exception_ptr pointer) {
        try { if (pointer) std::rethrow_exception(pointer); }
        catch (const std::length_error& error) { PyErr_SetString(PyExc_OverflowError, error.what()); }
    });
    bind_surface(module);
    bind_uv(module);
    bind_quad(module);
    bind_brep(module);
    module.def("assess_polygonal", &assess_polygonal,
               py::arg("vertices").noconvert(), py::arg("edges").noconvert(),
               py::arg("offsets").noconvert(), py::arg("coedges").noconvert(), py::arg("unit"),
               py::arg("max_input_bytes") = 256000000, py::arg("max_owned_bytes") = 512000000,
               py::arg("max_work_steps") = 50000000, py::arg("max_output_bytes") = 256000000);
    module.def("reduce_f2", &reduce, py::arg("offsets").noconvert(), py::arg("values").noconvert(),
               py::arg("evidence"), py::arg("max_columns"), py::arg("max_stored_entries"),
               py::arg("max_xor_steps"), py::arg("max_trace_entries"), py::arg("max_output_bytes"));
}
