"""Build the private CPU extension with the same C++26 contract as native CMake."""
from setuptools import Extension, setup
import pybind11

setup(ext_modules=[Extension(
    "cad_integrity._native",
    sources=["native/bindings/nurbs.cpp", "native/nurbs/src/nurbs.cpp", "native/bindings/quad.cpp", "native/quad_tracing.cpp", "native/bindings/module.cpp", "native/bindings/brep.cpp", "native/brep_realization.cpp", "native/bindings/surface.cpp", "native/bindings/uv.cpp", "native/uv_location.cpp", "native/surface_preparation.cpp", "native/f2_reduction.cpp", "native/SimplicialComplex.cpp"],
    depends=["native/nurbs/include/cad_mat/nurbs.hpp", "native/quad_tracing.hpp", "native/brep_realization.hpp", "native/surface_storage.hpp", "native/uv_location.hpp", "native/bindings/common.hpp", "native/surface_preparation.hpp", "native/f2_reduction.hpp", "native/SimplicialComplex.hpp"],
    include_dirs=[pybind11.get_include(), "native/nurbs/include"],
    language="c++",
    extra_compile_args=["-std=c++2c", "-Wall", "-Wextra", "-Werror", "-pedantic"],
)])
