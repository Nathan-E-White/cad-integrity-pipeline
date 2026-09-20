cmake_minimum_required(VERSION 4.3)
project(native)

set(CMAKE_CXX_STANDARD 26)

include_directories(voronoi/include)
include_directories(voronoi/include/cad_mat)
include_directories(nurbs/include/)
include_directories(nurbs/include/cad_mat)


add_library(
        voronoi
        OBJECT
        voronoi/include/cad_mat/voronoi.hpp
        voronoi/src/voronoi.cpp
)

add_library(
        nurbs
        OBJECT
        nurbs/include/cad_mat/nurbs.hpp
        nurbs/src/nurbs.cpp
)
add_library(simplicial SimplicialComplex.cpp SimplicialComplex.hpp)
target_include_directories(simplicial PUBLIC "${CMAKE_CURRENT_SOURCE_DIR}")
target_compile_features(simplicial PUBLIC cxx_std_26)
find_package(Threads REQUIRED)
target_link_libraries(simplicial PRIVATE Threads::Threads)
if(CMAKE_CXX_COMPILER_ID MATCHES "Clang|GNU")
  target_compile_options(simplicial PRIVATE -Wall -Wextra -Werror -pedantic)
endif()
include(CTest)
if(BUILD_TESTING)
  add_executable(simplicial_tests tests/simplicial_tests.cpp)
  target_link_libraries(simplicial_tests PRIVATE simplicial)
  if(CMAKE_CXX_COMPILER_ID MATCHES "Clang|GNU")
    target_compile_options(simplicial_tests PRIVATE -Wall -Wextra -Werror -pedantic)
  endif()
  add_test(NAME simplicial_tests COMMAND simplicial_tests)
endif()
