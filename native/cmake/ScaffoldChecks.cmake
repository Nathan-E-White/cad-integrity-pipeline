# Compile-only hygiene checks. No numerical implementation or binding is implied.
add_library(cad_native_scaffold_checks OBJECT
  surface_preparation.cpp uv_location.cpp
  brep_realization.cpp quad_tracing.cpp voronoi/src/delaunay.cpp)
target_include_directories(cad_native_scaffold_checks PRIVATE
  "${CMAKE_CURRENT_SOURCE_DIR}" "${CMAKE_CURRENT_SOURCE_DIR}/voronoi/include")
target_compile_features(cad_native_scaffold_checks PRIVATE cxx_std_26)
cad_native_strict(cad_native_scaffold_checks)
