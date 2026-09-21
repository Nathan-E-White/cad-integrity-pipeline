#include "../f2_reduction.hpp"
#include <pybind11/numpy.h>
#include <pybind11/pybind11.h>
#include <cstring>
#include <stdexcept>

namespace py = pybind11;
namespace {
using Row = std::int64_t;
struct BudgetExceeded : std::runtime_error { using std::runtime_error::runtime_error; };

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
}
PYBIND11_MODULE(_native, module) {
    py::register_exception<BudgetExceeded>(module, "BudgetExceeded");
    py::register_exception_translator([](std::exception_ptr pointer) {
        try { if (pointer) std::rethrow_exception(pointer); }
        catch (const std::length_error& error) { PyErr_SetString(PyExc_OverflowError, error.what()); }
    });
    module.def("reduce_f2", &reduce, py::arg("offsets").noconvert(), py::arg("values").noconvert(),
               py::arg("evidence"), py::arg("max_columns"), py::arg("max_stored_entries"),
               py::arg("max_xor_steps"), py::arg("max_trace_entries"), py::arg("max_output_bytes"));
}
