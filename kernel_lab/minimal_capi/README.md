# Minimal CAPI Backend

This is the first owned backend boundary for PapiMiner.

It is intentionally a stub today: the exported names mirror Akoya's
`libpearl_gemm_capi` ABI, but the proof-generating functions return explicit
negative error codes until a real CUDA implementation is added.

Why keep a stub?

- It gives us a stable list of symbols to implement.
- It lets tests protect the ABI shape before CUDA work starts.
- It separates "can be loaded by the miner" from "is fast".

The first real milestone is not speed. It is:

1. build a shared library with the same exported C symbols,
2. make Akoya miner load it,
3. pass transcript/proof validation,
4. submit at least one accepted share in a tiny live window.

Only after that should candidate work chase 120-140 TH/s.
