# PapiMiner

PapiMiner is a local Pearl mining and useful-work control panel. It helps you
import local models, start or stop open-source miners, chat with a local
OpenAI-compatible vLLM endpoint, and inspect useful-work evidence after each
request.

PapiMiner 是一个本地 Pearl 挖矿与 useful-work 控制台：可以导入本地模型，
启动或停止开源矿工，连接本地 OpenAI-compatible vLLM 接口，并在每次请求后
查看 useful-work 证据。

## Features / 功能

- Import local model paths and miner run profiles.
- Start and stop local plain-mining or vLLM useful-work processes.
- Select GPUs without storing machine-specific details in the public repo.
- Inspect runtime status, logs, GPU telemetry, useful-work metrics, and share deltas.
- Keep wallet addresses, worker names, local paths, logs, and model weights under `local/`.

- 导入本地模型路径和矿工运行档案。
- 启动/停止 plain mining 或 vLLM useful-work 本地进程。
- 选择 GPU，但不把机器细节写进公开仓库。
- 查看运行状态、日志、GPU 信息、useful-work 指标和 share 增量。
- 钱包地址、worker 名、本地路径、日志、模型权重都留在 `local/`。

## Privacy / 隐私边界

The public repository should contain code, docs, tests, and redacted examples
only. PapiMiner does not store seed phrases, private keys, wallet database
files, exchange passwords, API secrets, model weights, or raw miner logs.

公开仓库只应包含代码、文档、测试和脱敏示例。PapiMiner 不保存助记词、私钥、
钱包数据库、交易所密码、API 密钥、模型权重或原始矿工日志。

Before publishing, read:

- `docs/OPEN_SOURCE_READINESS.md`
- `docs/PUBLIC_REVIEW_CHECKLIST.md`

发布前请先看：

- `docs/OPEN_SOURCE_READINESS.md`
- `docs/PUBLIC_REVIEW_CHECKLIST.md`

## Start / 启动

Double-click:

```text
启动 PapiMiner.cmd
```

Or run:

```powershell
.\PapiMiner.ps1 serve --host 127.0.0.1 --port 8788
```

Open:

```text
http://127.0.0.1:8788/
```

## Mock Test / Mock 测试

Use this when a real vLLM or miner process is not running:

```powershell
.\PapiMiner.ps1 mock-vllm --host 127.0.0.1 --port 8890
.\PapiMiner.ps1 --api-base http://127.0.0.1:8890 serve --host 127.0.0.1 --port 8788
```

The mock server simulates metrics and share deltas for UI testing only. It does
not produce real PRL rewards.

Mock server 只用于测试 UI，会模拟指标和 share 增量，不产生真实 PRL 收益。

## Useful-Work Evidence / Useful-Work 证据

PapiMiner records metrics before and after each local request, including token
usage, GEMM/CAPI/launch deltas, useful hash-rate signals, pool registration,
and accepted/rejected share deltas when the miner exposes them.

PapiMiner 会在每次本地请求前后记录指标，包括 token 用量、GEMM/CAPI/launch
增量、useful hash-rate 信号、矿池注册状态，以及矿工暴露的 accepted/rejected
share 增量。

`Useful H/s` alone is not proof of PRL income. Accepted shares or pool-side
account movement are the stronger evidence.

单独的 `Useful H/s` 不等于 PRL 收益证明；accepted share 或矿池账户变化才是更强证据。

## Development Checks / 开发检查

```powershell
python .\tools\local_audit.py --output .\local\test-runs\github-redteam-audit.json
python -m pytest -q
```

Expected:

- privacy hits: `0`
- tests: pass

预期：

- 隐私命中：`0`
- 测试通过
