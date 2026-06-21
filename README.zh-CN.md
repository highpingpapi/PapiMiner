# PapiMiner 中文说明

PapiMiner 是一个本地 Pearl PlainProof 挖矿控制台。

当前 v0.2 的定位很明确：它是启动器和监控面板，不是完整自研 CUDA miner。
默认后端使用开源 Akoya plain miner；PapiMiner 负责导入运行档案、启动/停止、
显示 GPU 状态、查看日志、解析 TH/s 和 share 结果。

## 功能

- 导入 plain miner 运行档案
- 启动 / 停止 miner
- 选择 GPU、worker、矿池和 PRL 收款地址
- 显示 GPU 温度、功耗、利用率
- 显示运行进程和日志
- 解析 Akoya plain miner 日志里的 TH/s 与 share 结果

## 快速启动

Windows 上可以双击：

```text
启动 PapiMiner.cmd
```

或者用 PowerShell：

```powershell
.\PapiMiner.ps1 serve --host 127.0.0.1 --port 8788
```

然后打开：

```text
http://127.0.0.1:8788/
```

## 运行档案

运行档案就是一张启动卡片，里面可以写 miner 程序路径、工作目录、GPU、矿池、
worker、PRL 收款地址和启动参数模板。

默认档案指向 Akoya plain miner。如果以后接入自研 CUDA kernel，也会先通过运行
档案接入，保证同一个控制台可以对比不同后端。

## 本地算力

PapiMiner 会读取日志里的：

```text
hashes/s=... TH/s
accepted=True
```

所以它显示的是 miner 日志和矿池 share 返回共同组成的运行证据。不同显卡、
驱动、功耗和矿池状态都会影响结果。

## 自研 Kernel 路线

下一阶段目标不是继续把控制台写复杂，而是把 GPU 核心从“调用上游 miner”推进到
“可替换、可验证、可 A/B 的自研 kernel”。路线见：

[Kernel Roadmap / 自研 Kernel 路线](docs/KERNEL_ROADMAP.md)

## 开发检查

```powershell
python -m pytest -q
python .\tools\local_audit.py --output .\local\test-runs\audit.json
```
