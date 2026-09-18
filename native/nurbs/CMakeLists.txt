cmake_minimum_required(VERSION 4.3)

project(cad_mat_nurbs LANGUAGES CXX)

add_library(cad_mat_nurbs STATIC src/nurbs.cpp)
target_compile_features(cad_mat_nurbs PUBLIC cxx_std_26)
target_include_directories(cad_mat_nurbs PUBLIC include)

function(cad_mat_enable_strict_warnings target)
  if(CMAKE_CXX_COMPILER_ID MATCHES "Clang|GNU")
    target_compile_options(${target} PRIVATE -Wall -Wextra -Werror -pedantic)
  endif()
endfunction()

cad_mat_enable_strict_warnings(cad_mat_nurbs)

include(CTest)
if(BUILD_TESTING)
  add_executable(cad_mat_nurbs_tests tests/nurbs_tests.cpp)
  target_link_libraries(cad_mat_nurbs_tests PRIVATE cad_mat_nurbs)
  cad_mat_enable_strict_warnings(cad_mat_nurbs_tests)
  add_test(NAME cad_mat_nurbs_tests COMMAND cad_mat_nurbs_tests)
endif()
