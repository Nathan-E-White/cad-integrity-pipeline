cmake_minimum_required(VERSION 4.3)
project(cad_native VERSION 0.1.0 DESCRIPTION "CAD geometry and topology kernels" LANGUAGES CXX)

if(CMAKE_CURRENT_SOURCE_DIR STREQUAL CMAKE_CURRENT_BINARY_DIR)
  message(FATAL_ERROR "Use an out-of-source build: cmake -S native -B build/native")
endif()
if(PROJECT_IS_TOP_LEVEL)
  include(CTest)
endif()
include(cmake/NativeChecks.cmake)
find_package(Threads REQUIRED)
include(f2.cmake)

add_library(simplicial STATIC SimplicialComplex.cpp)
add_library(cad::simplicial ALIAS simplicial)
target_sources(simplicial PUBLIC FILE_SET HEADERS
  BASE_DIRS "${CMAKE_CURRENT_SOURCE_DIR}" FILES SimplicialComplex.hpp)
cad_native_library(simplicial)
target_link_libraries(simplicial PRIVATE Threads::Threads)

add_subdirectory(nurbs)
add_subdirectory(voronoi)
# Compatibility names retain the same implementation and never compile it twice.
add_library(nurbs ALIAS cad_mat_nurbs)
add_library(voronoi ALIAS cad_mat_voronoi)

option(CAD_NATIVE_CHECK_SCAFFOLDS "Compile unfinished declarations without advertising libraries" OFF)
if(CAD_NATIVE_CHECK_SCAFFOLDS)
  include(cmake/ScaffoldChecks.cmake)
endif()
if(BUILD_TESTING)
  add_subdirectory(tests)
endif()
