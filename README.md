# PapiMiner

PapiMiner is a small local console for **PlainProof-only Pearl mining**.

PapiMiner 是一个本地 Pearl plain miner 控制台。它只做普通 PlainProof 挖矿启动、停止、日志和显卡状态观察。

## Scope

PapiMiner intentionally stays narrow: it only manages plain miner profiles.
AI experiments belong in the separate local research project `papipearls`.

PapiMiner 故意保持很窄：它只管理 plain miner 档案。AI 实验放在独立的本地研究项目 `papipearls`。

## Features

- Start and stop a plain miner profile.
- Import local plain miner run profiles.
- Select GPU, worker name, pool host, and PRL receive address.
- Show local GPU temperature, power, utilization, and runtime log tail.
- Keep wallet addresses, worker names, local paths, and logs under `local/`.

## Start

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

## Local Files

Ignored local-only files:

- `local/run-profiles.local.json`
- `local/runtime.local.json`
- `local/settings.local.json`
- `local/run-logs/`
- `local/backgrounds/`

## Development Checks

```powershell
python -m pytest -q
python .\tools\local_audit.py --output .\local\test-runs\github-redteam-audit.json
```

Expected:

- tests pass
- privacy hits: `0`
