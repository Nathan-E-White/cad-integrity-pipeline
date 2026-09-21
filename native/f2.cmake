# Active F2 reduction target; independent of the declaration-only extensions.
add_library(cad_f2 STATIC "${CMAKE_CURRENT_LIST_DIR}/f2_reduction.cpp")
add_library(cad::f2 ALIAS cad_f2)
target_sources(cad_f2 PUBLIC FILE_SET HEADERS
  BASE_DIRS "${CMAKE_CURRENT_LIST_DIR}" FILES "${CMAKE_CURRENT_LIST_DIR}/f2_reduction.hpp")
cad_native_library(cad_f2)
if(BUILD_TESTING)
  add_executable(f2_tests "${CMAKE_CURRENT_LIST_DIR}/tests/f2_tests.cpp")
  target_link_libraries(f2_tests PRIVATE cad::f2)
  cad_native_test(f2_tests f2)
endif()
