#ifndef CAD_NATIVE_SPARSE_ENTRY_TCC
#define CAD_NATIVE_SPARSE_ENTRY_TCC

#include <cstdint>

// Sparse Matrix Triplet representation
struct SparseEntry {
    std::uint32_t row;
    std::uint32_t col;
    double value;
};

#endif