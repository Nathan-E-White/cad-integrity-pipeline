cmake_minimum_required(VERSION 4.3)
project(cad_mat_nurbs VERSION 0.1.0 LANGUAGES CXX)

if(CMAKE_CURRENT_SOURCE_DIR STREQUAL CMAKE_CURRENT_BINARY_DIR)
  message(FATAL_ERROR "Use an out-of-source build for nurbs")
endif()
if(PROJECT_IS_TOP_LEVEL)
  include(CTest)
endif()
include("${CMAKE_CURRENT_LIST_DIR}/../cmake/NativeChecks.cmake")

add_library(cad_mat_nurbs STATIC src/nurbs.cpp)
add_library(cad::nurbs ALIAS cad_mat_nurbs)
target_sources(cad_mat_nurbs PUBLIC FILE_SET HEADERS
  BASE_DIRS "${CMAKE_CURRENT_SOURCE_DIR}/include"
  FILES include/cad_mat/nurbs.hpp)
cad_native_library(cad_mat_nurbs)

if(BUILD_TESTING)
  add_executable(cad_mat_nurbs_tests tests/nurbs_tests.cpp)
  target_link_libraries(cad_mat_nurbs_tests PRIVATE cad::nurbs)
  cad_native_test(cad_mat_nurbs_tests nurbs)
endif()
