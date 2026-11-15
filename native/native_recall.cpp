#include <cmath>
#include <cstdint>

#include "simd/basic_func.h"

extern "C" void
angular_distances(const float* base,
                  const float* query,
                  const int64_t* ids,
                  uint64_t count,
                  uint64_t dim,
                  float* output) {
    for (uint64_t i = 0; i < count; ++i) {
        const float* item = base + ids[i] * dim;
        output[i] = 1 - vsag::avx512::InnerProduct(query, item, &dim) /
                            std::sqrt(vsag::avx512::InnerProduct(query, query, &dim) *
                                      vsag::avx512::InnerProduct(item, item, &dim));
    }
}
