# Kernel Roadmap / 自研 Kernel 路线

## 中文

PapiMiner 当前不是自研 CUDA kernel miner。它现在是 plain miner 控制台，默认调用
开源 Akoya plain miner。

之前的大量实验并不是“已经完成一个独立 kernel”，而是在做三类准备工作：

1. **理解 proof 形状**：弄清 PlainProof 需要哪些输入、tile、header、share、
   verifier，以及什么东西会导致 invalid share。
2. **找性能瓶颈**：测试 CUDA graph、tile shape、runtime 参数、SASS 差异、
   shared memory / L1 carveout、launch bounds、XOR reducer 等候选。
3. **建立验收标准**：只看本地 TH/s 不够，必须能证明矿池 accepted share，
   最好能做同一矿池、同一功耗、同一窗口下的 A/B。

### 目标

把 PapiMiner 从“调用上游 Akoya miner 的控制台”推进到：

> 一个可替换、可验证、可 A/B 测试的 Pearl PlainProof CUDA backend。

### 里程碑

1. **Baseline 固化**
   - 使用当前 Akoya plain miner 跑稳定窗口。
   - 记录 TH/s、accepted/rejected share、温度、功耗。
   - 作为后续所有 kernel 候选的基线。

2. **最小 CAPI Backend**
   - 做一个独立 `libpearl_gemm_capi` 兼容 backend。
   - 第一版允许很慢，但必须 proof-valid。
   - 目标是能被 Akoya miner 调用，并能在矿池 accepted。

3. **CUDA Kernel 候选**
   - 从最小正确 kernel 开始。
   - 逐步测试 tile shape、memory layout、CUDA graph、register pressure、
     occupancy、shared memory / L1 取舍。
   - 每个候选必须记录 hash、构建参数、日志和 share 结果。

4. **Live A/B Gate**
   - 候选必须在真实矿池窗口里提交 accepted share。
   - 只把 accepted share 且 TH/s 稳定提升的候选晋级。
   - 无效 share、duplicate 过多、崩溃、CUDA driver error 都直接淘汰。

5. **开源发布**
   - 只发布可复现源码、构建脚本、示例配置。
   - 不发布本地钱包、worker、真实日志、机器路径或私有 benchmark 文件。

### 当前诚实状态

- 控制台：已可用。
- 默认 plain miner：调用开源 Akoya。
- 自研 kernel：还没有作为公开源码发布。
- 当前本地已验证的有效窗口：约 108-110 TH/s 档，来自 Akoya/上游 backend。
- 下一步：做一个最小 proof-valid CAPI backend，再谈优化到 120+ TH/s。

## English

PapiMiner is not yet a custom CUDA kernel miner. Today it is a plain mining
console that launches the open-source Akoya plain miner by default.

The previous experiments did not complete a standalone original kernel. They
were preparation work in three areas:

1. **Proof shape**: understand PlainProof inputs, tiles, headers, shares,
   verifier behavior, and invalid-share failure modes.
2. **Performance bottlenecks**: test CUDA graph, tile shapes, runtime knobs,
   SASS deltas, shared memory / L1 carveout, launch bounds, XOR reducers, and
   related candidates.
3. **Acceptance gates**: local TH/s is not enough. A candidate must prove pool
   accepted shares, ideally in a same-pool, same-power, same-window A/B test.

### Goal

Move PapiMiner from:

> a console that launches Akoya plain miner

to:

> a replaceable, verifiable, A/B-testable Pearl PlainProof CUDA backend.

### Milestones

1. **Freeze the Baseline**
   - Run stable Akoya plain miner windows.
   - Record TH/s, accepted/rejected shares, temperature, and power.
   - Use this as the baseline for every future kernel candidate.

2. **Minimal CAPI Backend**
   - Build an independent `libpearl_gemm_capi` compatible backend.
   - The first version may be slow, but it must be proof-valid.
   - It must be callable by Akoya miner and accepted by the pool.

3. **CUDA Kernel Candidates**
   - Start from the minimal correct kernel.
   - Test tile shape, memory layout, CUDA graph, register pressure, occupancy,
     and shared memory / L1 tradeoffs.
   - Record every candidate's hash, build flags, logs, and share results.

4. **Live A/B Gate**
   - A candidate must submit accepted shares on a real pool.
   - Promote only candidates with accepted shares and stable TH/s improvement.
   - Invalid shares, too many duplicates, crashes, or CUDA driver errors reject
     the candidate.

5. **Open-Source Release**
   - Publish reproducible source, build scripts, and example configs.
   - Do not publish local wallets, workers, real logs, machine paths, or private
     benchmark files.

### Honest Current State

- Console: working.
- Default plain miner: uses open-source Akoya.
- Custom kernel: not yet published as open source.
- Current valid local window: around 108-110 TH/s, from Akoya/upstream backend.
- Next step: build a minimal proof-valid CAPI backend before chasing 120+ TH/s.
