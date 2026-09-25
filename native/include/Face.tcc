#ifndef CAD_NATIVE_FACE_TCC
#define CAD_NATIVE_FACE_TCC

#include <cstdint>

// Internal representation for a triangular face
struct Face {
    std::uint32_t v0, v1, v2;
};

#endif
