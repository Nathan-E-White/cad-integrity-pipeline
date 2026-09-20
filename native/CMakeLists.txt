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