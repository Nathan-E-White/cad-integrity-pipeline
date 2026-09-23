#pragma once
#include <pybind11/pybind11.h>
#include <stdexcept>
struct BudgetExceeded : std::runtime_error {
  using std::runtime_error::runtime_error;
};
void bind_surface(pybind11::module_ &module);

void bind_uv(pybind11::module_ &module);

void bind_brep(pybind11::module_ &module);

void bind_quad(pybind11::module_ &module);
