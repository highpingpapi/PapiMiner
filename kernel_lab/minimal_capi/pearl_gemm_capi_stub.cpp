#include "pearl_gemm_capi_stub.h"

namespace {
constexpr int kUnimplemented = -34001;
constexpr int kBadArgument = -34002;

struct StubWorkspace {
  int32_t m;
  int32_t n;
  int32_t k;
  int32_t r;
  bool params_installed;
};
}  // namespace

extern "C" {

int pearl_capi_abi_version(void) { return 2; }

const char* pearl_capi_build_profile(void) {
  return "papiminer-minimal-capi-stub";
}

int pearl_capi_supports_sm(int major, int minor) {
  // Keep the stub loadable for RTX 30/40 class testing, but it still cannot
  // produce a valid proof until the CUDA implementation replaces the hot path.
  if (major == 8 && (minor == 6 || minor == 9)) return 1;
  return 0;
}

int pearl_capi_get_host_signal_sync_size(void) {
  return 16;
}

int pearl_capi_get_host_signal_header_size(void) {
  return 128;
}

int64_t pearl_capi_get_required_scratchpad_bytes(
    int64_t matrix_bytes, int threads_per_block) {
  if (matrix_bytes < 0 || threads_per_block <= 0) return kBadArgument;
  return matrix_bytes + static_cast<int64_t>(threads_per_block) * 1024;
}

int pearl_capi_workspace_alloc(
    int32_t m, int32_t n, int32_t k, int32_t r,
    int, int, void** out_workspace, void*) {
  if (!out_workspace || m <= 0 || n <= 0 || k <= 0 || r <= 0) {
    return kBadArgument;
  }
  *out_workspace = new StubWorkspace{m, n, k, r, false};
  return 0;
}

int pearl_capi_workspace_free(void* workspace, void*) {
  delete static_cast<StubWorkspace*>(workspace);
  return 0;
}

int pearl_capi_workspace_install_params(void* workspace, const void* params) {
  if (!workspace || !params) return kBadArgument;
  static_cast<StubWorkspace*>(workspace)->params_installed = true;
  return 0;
}

int pearl_capi_iter(void* workspace, uint64_t, void*, void*) {
  if (!workspace) return kBadArgument;
  if (!static_cast<StubWorkspace*>(workspace)->params_installed) return -3;
  return kUnimplemented;
}

int pearl_capi_iter_batch(
    void* workspace, uint64_t, void* const*, int32_t count, void*) {
  if (!workspace || count <= 0) return kBadArgument;
  if (!static_cast<StubWorkspace*>(workspace)->params_installed) return -3;
  return kUnimplemented;
}

int pearl_capi_iter_batch_graph_prepare(
    void* workspace, void* const*, int32_t count, void*) {
  if (!workspace || count <= 0) return kBadArgument;
  if (!static_cast<StubWorkspace*>(workspace)->params_installed) return -3;
  return kUnimplemented;
}

int pearl_capi_iter_batch_graph_launch(void* workspace, uint64_t, void*) {
  if (!workspace) return kBadArgument;
  if (!static_cast<StubWorkspace*>(workspace)->params_installed) return -3;
  return kUnimplemented;
}

int pearl_capi_noisy_gemm(const void*, void*) {
  return kUnimplemented;
}

}  // extern "C"
