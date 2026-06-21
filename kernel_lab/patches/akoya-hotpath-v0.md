# Akoya Hot Path Candidate Notes

Target upstream files, read-only reference:

- `native/pearl-gemm/csrc/capi/pearl_gemm_capi.h`
- `native/pearl-gemm/csrc/capi/pearl_gemm_capi.cpp`
- `native/pearl-gemm/csrc/consumer/transcript_gemm_kernel.cu`
- `native/pearl-gemm/csrc/consumer/manual_akoya_mainloop.cuh`
- `native/pearl-gemm/csrc/capi/Makefile`

## Current Hot Path

Akoya's per-nonce hot path is:

1. `pearl_capi_lcg_int7_fill`
2. `pearl_capi_tensor_hash`
3. `pearl_capi_commitment_hash_from_merkle_roots`
4. `pearl_capi_noise_gen`
5. `pearl_capi_noisy_gemm`

The useful kernel target is step 5, especially the consumer transcript GEMM.
Changing the C# launcher or pool protocol will not move the 110 TH/s ceiling
unless the GPU hot path changes.

## First Candidate

`akoya-delay-a-fragment-v0`

Build-time switches:

```text
PEARL_GEMM_ARCH=ada
PEARL_GEMM_LOCAL_ARCH=sm_89
PEARL_GEMM_CONSUMER_S2R_B_FIRST=1
PEARL_GEMM_CONSUMER_DELAY_A_FRAGMENT=1
PEARL_GEMM_CONSUMER_HOIST_C_VIEW=1
```

Reason:

- The upstream source already guards this path as proof-preserving.
- It changes register lifetime and B/A ldmatrix issue order.
- It targets the bottleneck class that prior experiments pointed at:
  ldmatrix/MMA scheduling and temporary fragment pressure.

Promotion gate:

1. transcript/proof gate passes,
2. SASS hot path differs from baseline,
3. same-window pool A/B has accepted shares,
4. TH/s improvement is stable and not bought with rejected shares.
