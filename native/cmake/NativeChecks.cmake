include_guard(GLOBAL)

# Private project policy: do not modify a parent's directory-wide compiler flags.
option(CAD_NATIVE_WARNINGS_AS_ERRORS "Treat native project warnings as errors" ON)
option(CAD_NATIVE_SANITIZERS "Enable AddressSanitizer and UndefinedBehaviorSanitizer" OFF)

function(cad_native_strict target)
  set_target_properties(${target} PROPERTIES
    CXX_EXTENSIONS OFF
    CXX_STANDARD_REQUIRED ON
    COMPILE_WARNING_AS_ERROR "${CAD_NATIVE_WARNINGS_AS_ERRORS}")
  if(MSVC)
    target_compile_options(${target} PRIVATE /W4)
  elseif(CMAKE_CXX_COMPILER_ID MATCHES "^(AppleClang|Clang|GNU)$")
    target_compile_options(${target} PRIVATE -Wall -Wextra -Wpedantic)
  endif()
  if(CAD_NATIVE_SANITIZERS)
    if(MSVC OR NOT CMAKE_CXX_COMPILER_ID MATCHES "^(AppleClang|Clang|GNU)$")
      message(FATAL_ERROR "CAD_NATIVE_SANITIZERS requires GCC or a GNU-style Clang driver")
    endif()
    target_compile_options(${target} PRIVATE
      -fsanitize=address,undefined -fno-omit-frame-pointer)
    # Static library consumers must link the sanitizer runtime too.
    target_link_options(${target} PUBLIC -fsanitize=address,undefined)
  endif()
endfunction()

function(cad_native_library target)
  target_compile_features(${target} PUBLIC cxx_std_26)
  set_target_properties(${target} PROPERTIES POSITION_INDEPENDENT_CODE ON)
  cad_native_strict(${target})
endfunction()

function(cad_native_test target)
  cad_native_strict(${target})
  # Numerical assertions must execute in optimized configurations as well.
  if(MSVC)
    target_compile_options(${target} PRIVATE /UNDEBUG)
  else()
    target_compile_options(${target} PRIVATE -UNDEBUG)
  endif()
  add_test(NAME ${target} COMMAND ${target})
  set_tests_properties(${target} PROPERTIES
    TIMEOUT 120 LABELS "native;${ARGN}")
  if(CAD_NATIVE_SANITIZERS)
    set_tests_properties(${target} PROPERTIES ENVIRONMENT
      "ASAN_OPTIONS=halt_on_error=1;UBSAN_OPTIONS=halt_on_error=1:print_stacktrace=1")
  endif()
endfunction()
