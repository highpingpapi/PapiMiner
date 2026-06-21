# Akoya Hot Path A/B - 2026-06-21

This run tested whether an upstream Akoya consumer-kernel scheduling variant
improves the Ada/sm89 plain-mining path.

## Scope

- PlainProof mining only.
- Same pool, same GPU class, same mining shape.
- No wallet address, worker name, host name, or local machine path is recorded
  in this file.

## Mining Shape

- `M = 4096`
- `N = 131072`
- `K = 4096`
- CUDA graph iteration enabled.
- Stats interval: 2 seconds.
- Measurement window: about 75 seconds per candidate.

## Candidate

`akoya-delay-a-fragment-v0`

Build switches:

```text
PEARL_GEMM_ARCH=ada
PEARL_GEMM_LOCAL_ARCH=sm_89
PEARL_GEMM_CONSUMER_S2R_B_FIRST=1
PEARL_GEMM_CONSUMER_DELAY_A_FRAGMENT=1
PEARL_GEMM_CONSUMER_HOIST_C_VIEW=1
```

## Result

| Build | Samples | Avg TH/s | Min TH/s | Max TH/s | Shares on wire | Accepted |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Clean Ada baseline | 14 | 91.756 | 88.870 | 92.560 | 6 | 6 |
| Delay A fragment | 14 | 91.039 | 87.730 | 91.710 | 3 | 3 |

The candidate is proof-valid because accepted shares were observed, but it is
slower than the clean baseline in this short window. Reject it for now.

## Interpretation

The SASS changed, so the switch is not a no-op. MMA and LDSM instruction counts
stayed the same, which suggests this mainly changes scheduling/register
lifetime rather than removing compute. That makes it a useful negative result:
this exact scheduling direction does not explain the higher 120-140 TH/s class
claims.

Next candidate: `akoya-raw-b-x1-v0`, which targets B operand materialization
more directly.
