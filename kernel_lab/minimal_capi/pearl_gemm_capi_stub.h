#pragma once

#include <stdint.h>

#ifdef _WIN32
#define PAPI_PEARL_EXPORT __declspec(dllexport)
#else
#define PAPI_PEARL_EXPORT __attribute__((visibility("default")))
#endif

#ifdef __cplusplus
extern "C" {
#endif

PAPI_PEARL_EXPORT int pearl_capi_abi_version(void);
PAPI_PEARL_EXPORT const char* pearl_capi_build_profile(void);
PAPI_PEARL_EXPORT int pearl_capi_supports_sm(int major, int minor);
PAPI_PEARL_EXPORT int pearl_capi_get_host_signal_sync_size(void);
PAPI_PEARL_EXPORT int pearl_capi_get_host_signal_header_size(void);
PAPI_PEARL_EXPORT int64_t pearl_capi_get_required_scratchpad_bytes(
    int64_t matrix_bytes, int threads_per_block);

PAPI_PEARL_EXPORT int pearl_capi_workspace_alloc(
    int32_t m, int32_t n, int32_t k, int32_t r,
    int with_noise_A, int with_noise_B,
    void** out_workspace, void* stream);
PAPI_PEARL_EXPORT int pearl_capi_workspace_free(void* workspace, void* stream);
PAPI_PEARL_EXPORT int pearl_capi_workspace_install_params(
    void* workspace, const void* params);

PAPI_PEARL_EXPORT int pearl_capi_iter(
    void* workspace, uint64_t seed_lo,
    void* host_signal_header_pinned, void* stream);
PAPI_PEARL_EXPORT int pearl_capi_iter_batch(
    void* workspace, uint64_t seed_lo_start,
    void* const* host_signal_header_pinned_batch,
    int32_t count, void* stream);
PAPI_PEARL_EXPORT int pearl_capi_iter_batch_graph_prepare(
    void* workspace, void* const* host_signal_header_pinned_batch,
    int32_t count, void* stream);
PAPI_PEARL_EXPORT int pearl_capi_iter_batch_graph_launch(
    void* workspace, uint64_t seed_lo_start, void* stream);

PAPI_PEARL_EXPORT int pearl_capi_noisy_gemm(const void* params, void* stream);

#ifdef __cplusplus
}
#endif
