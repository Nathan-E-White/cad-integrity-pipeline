add_executable(simplicial_tests simplicial_tests.cpp)
target_link_libraries(simplicial_tests PRIVATE cad::simplicial)
cad_native_test(simplicial_tests simplicial)

# A real consumer exercises include paths, namespace coexistence and static links.
add_executable(native_consumer_tests native_consumer_tests.cpp)
target_link_libraries(native_consumer_tests PRIVATE cad::simplicial cad::nurbs cad::voronoi)
cad_native_test(native_consumer_tests integration)
