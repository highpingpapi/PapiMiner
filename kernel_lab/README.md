# Kernel Lab

This folder tracks the PapiMiner custom kernel effort.

PapiMiner currently launches and monitors an upstream plain miner. The kernel
lab is the place where we turn the prior experiments into a reproducible path
toward an original Pearl PlainProof backend.

## Boundary

- PlainProof mining only.
- No AI inference scheduler.
- No pool-routed inference jobs.
- No wallet, worker, host name, LAN IP, or local machine path in committed
  files.

AI/useful-work experiments belong in a separate project. PapiMiner should stay
small enough to reason about and test.

## Target

Build a replaceable Pearl PlainProof backend that is:

- proof-valid,
- callable through the same launcher/profile system,
- benchmarkable against the upstream baseline,
- accepted by a real pool during a live A/B window,
- eventually capable of challenging the 120-140 TH/s class on a supported
  consumer GPU.

## What The Earlier Experiments Were

They were not a finished custom CUDA kernel. They were the groundwork:

- proof-shape work: what data must be bound into a valid PlainProof/share;
- CAPI work: how a backend can plug into the upstream miner boundary;
- performance search: which knobs change TH/s and which compile to the same
  hot path;
- acceptance gates: how to reject fake speedups that do not produce accepted
  shares.

The current best evidence says simple runtime knobs are not enough. The next
useful work is lower-level kernel work around shared-memory layout, fragment
materialization, register lifetime, and the GEMM/transcript boundary.

## Files

- `candidates.json`: baseline, candidate list, and acceptance gates.
- `tools/suggest_next_candidate.py`: prints the next candidate to work on.
- `patches/`: human-readable patch plans. These are specs, not automatic edits
  to upstream code.
