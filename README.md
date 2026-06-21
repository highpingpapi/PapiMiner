# PapiMiner

PapiMiner is a local console for Pearl **PlainProof** mining.

- [中文说明](README.zh-CN.md)
- [English README](README.en.md)
- [Kernel Roadmap / 自研 Kernel 路线](docs/KERNEL_ROADMAP.md)

## Status

PapiMiner v0.2 is a launcher and monitor. It can start a plain miner profile,
show GPU/runtime status, tail logs, and parse local TH/s plus share results.

The current default backend uses the open-source Akoya plain miner. PapiMiner
does not claim to ship an original CUDA kernel yet.

## Quick Start

On Windows, double-click:

```text
启动 PapiMiner.cmd
```

Or run:

```powershell
.\PapiMiner.ps1 serve --host 127.0.0.1 --port 8788
```

Then open:

```text
http://127.0.0.1:8788/
```

## What It Includes

- Plain miner profile import
- Start/stop controls
- GPU temperature, power, and utilization display
- Runtime logs
- Akoya plain miner log parser
- Local profile files under `local/`

## Development

```powershell
python -m pytest -q
python .\tools\local_audit.py --output .\local\test-runs\audit.json
```
