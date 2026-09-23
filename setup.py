"""Build the private CPU extension with the same C++26 contract as native CMake."""
from setuptools import Extension, setup
import pybind11

setup(ext_modules=[Extension(
    "cad_integrity._native",
    sources=["native/bindings/module.cpp", "native/bindings/surface.cpp", "native/bindings/uv.cpp", "native/uv_location.cpp", "native/surface_preparation.cpp", "native/f2_reduction.cpp", "native/SimplicialComplex.cpp"],
    depends=["native/uv_location.hpp", "native/bindings/common.hpp", "native/surface_preparation.hpp", "native/f2_reduction.hpp", "native/SimplicialComplex.hpp"],
    include_dirs=[pybind11.get_include()],
    language="c++",
    extra_compile_args=["-std=c++2c", "-Wall", "-Wextra", "-Werror", "-pedantic"],
)])
