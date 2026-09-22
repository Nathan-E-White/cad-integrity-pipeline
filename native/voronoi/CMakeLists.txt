cmake_minimum_required(VERSION 4.3)
project(cad_mat_voronoi VERSION 0.1.0 LANGUAGES CXX)

if(CMAKE_CURRENT_SOURCE_DIR STREQUAL CMAKE_CURRENT_BINARY_DIR)
  message(FATAL_ERROR "Use an out-of-source build for voronoi")
endif()
if(PROJECT_IS_TOP_LEVEL)
  include(CTest)
endif()
include("${CMAKE_CURRENT_LIST_DIR}/../cmake/NativeChecks.cmake")

add_library(cad_mat_voronoi STATIC src/voronoi.cpp
        ../Point3D.c++
        ../Point3D.tcc)
add_library(cad::voronoi ALIAS cad_mat_voronoi)
target_sources(cad_mat_voronoi PUBLIC FILE_SET HEADERS
  BASE_DIRS "${CMAKE_CURRENT_SOURCE_DIR}/include"
  FILES include/cad_mat/voronoi.hpp)
cad_native_library(cad_mat_voronoi)

if(BUILD_TESTING)
  add_executable(cad_mat_voronoi_tests tests/voronoi_tests.cpp
          ../Point3D.c++
          ../Point3D.tcc)
  target_link_libraries(cad_mat_voronoi_tests PRIVATE cad::voronoi)
  cad_native_test(cad_mat_voronoi_tests voronoi)
endif()
