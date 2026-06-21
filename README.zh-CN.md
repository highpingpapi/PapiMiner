# PapiMiner 中文说明

PapiMiner 是一个本地 Pearl PlainProof 挖矿控制台。它的目标很窄：导入
plain miner 运行档案，启动/停止矿工，观察显卡状态、日志和矿池 share 情况。

## 这个项目做什么

- 启动和停止 PlainProof miner。
- 导入本地运行档案，例如 miner 路径、工作目录、GPU、矿池和启动参数模板。
- 显示 GPU 温度、功耗、利用率、进程状态和日志尾部。
- 解析 Akoya plain miner 日志，方便看本地 TH/s 和 accepted share。
- 把钱包地址、worker 名、机器路径、日志等信息放进 `local/`，默认不上传 GitHub。

## 这个项目不做什么

PapiMiner 不是钱包，也不是交易机器人。它不会保存助记词、私钥、交易所密码、
钱包数据库或浏览器登录态。

PapiMiner 目前也不是 vLLM / useful-work 控制台，不处理池子派单推理。
AI 推理和 useful-work 实验应该放在单独项目里，避免 plain miner 仓库混乱。

## 快速启动

Windows 上可以双击：

```text
启动 PapiMiner.cmd
```

或者用 PowerShell：

```powershell
.\PapiMiner.ps1 serve --host 127.0.0.1 --port 8788
```

然后浏览器打开：

```text
http://127.0.0.1:8788/
```

## 导入运行档案

运行档案是一张“启动卡片”，通常包含：

- miner 程序路径
- 工作目录
- GPU 列表
- 矿池地址
- worker 名
- PRL 收款地址
- 日志路径
- 启动参数模板

这些内容可能暴露本地机器信息，所以默认写入 `local/run-profiles.local.json`，
不会进入开源仓库。

## 本地测试算力

PapiMiner 会从日志里读取 miner 打印的 `hashes/s=... TH/s`，并记录 share
是否被矿池接受。公开 README 不内置作者机器的真实算力、钱包或 worker，
因为这些数据会暴露个人环境，也容易被误当成通用承诺。

你可以用工具解析自己的日志：

```powershell
python .\tools\parse_akoya_miner_log.py .\local\run-logs\your-run.log
```

## 隐私边界

以下目录和文件是本地私有数据，默认被 `.gitignore` 忽略：

- `local/run-profiles.local.json`
- `local/runtime.local.json`
- `local/settings.local.json`
- `local/run-logs/`
- `local/backgrounds/`

上传 GitHub 前建议运行：

```powershell
python -m pytest -q
python .\tools\local_audit.py --output .\local\test-runs\github-redteam-audit.json
```

期望结果：测试通过，隐私命中数为 `0`。

## 开源原则

这个仓库优先保证三件事：

1. 公开代码里不包含私人信息。
2. plain miner 与 AI/useful-work 实验分开。
3. 本地测试结果可以复现，但不把个人机器参数写成公开承诺。
