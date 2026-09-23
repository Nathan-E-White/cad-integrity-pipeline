add_executable(simplicial_tests simplicial_tests.cpp)
target_link_libraries(simplicial_tests PRIVATE cad::simplicial)
cad_native_test(simplicial_tests simplicial)

# A real consumer exercises include paths, namespace coexistence and static links.
add_executable(native_consumer_tests native_consumer_tests.cpp)
target_link_libraries(native_consumer_tests PRIVATE cad::simplicial cad::nurbs cad::voronoi)
cad_native_test(native_consumer_tests integration)

add_executable(polygonal_tests polygonal_tests.cpp)
target_link_libraries(polygonal_tests PRIVATE cad::simplicial)
cad_native_test(polygonal_tests polygonal)

add_executable(surface_tests surface_tests.cpp)
target_link_libraries(surface_tests PRIVATE cad::surface)
cad_native_test(surface_tests surface)

add_executable(uv_tests uv_tests.cpp)
target_link_libraries(uv_tests PRIVATE cad::uv)
cad_native_test(uv_tests uv)
