cmake_minimum_required(VERSION 4.3)
project(cad_native LANGUAGES CXX)

include(CTest)
include(cmake/NativeChecks.cmake)
find_package(Threads REQUIRED)

add_library(simplicial STATIC SimplicialComplex.cpp)
target_include_directories(simplicial PUBLIC "${CMAKE_CURRENT_SOURCE_DIR}")
target_compile_features(simplicial PUBLIC cxx_std_26)
target_link_libraries(simplicial PRIVATE Threads::Threads)
cad_native_strict(simplicial)

add_subdirectory(nurbs)
add_subdirectory(voronoi)
# Preserve the original parent target names without recompiling their sources.
add_library(nurbs ALIAS cad_mat_nurbs)
add_library(voronoi ALIAS cad_mat_voronoi)

if(BUILD_TESTING)
  add_executable(simplicial_tests tests/simplicial_tests.cpp)
  target_link_libraries(simplicial_tests PRIVATE simplicial)
  cad_native_test(simplicial_tests)
endif()
