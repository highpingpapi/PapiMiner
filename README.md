# PapiMiner

PapiMiner is a small local console for **PlainProof-only Pearl mining**.

- [中文说明](README.zh-CN.md)
- [English README](README.en.md)

## What This Repository Is

This repository contains the open-source PapiMiner console, Windows launch scripts,
tests, and privacy checks. It is intentionally narrow: it starts and monitors
plain miner profiles, shows GPU/runtime status, and keeps local secrets out of
the repository.

## What This Repository Is Not

PapiMiner does not include wallet files, seed phrases, private keys, exchange
credentials, AI chat, vLLM useful-work routing, or pool-dispatched inference.
Those experiments belong in separate local projects.

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

## Local-Only Data

Everything machine-specific stays under `local/`, which is ignored by Git:

- miner run profiles
- wallet receiving addresses and worker names
- runtime state and process ids
- logs
- custom backgrounds

## Checks

```powershell
python -m pytest -q
python .\tools\local_audit.py --output .\local\test-runs\github-redteam-audit.json
```

Expected result: tests pass and privacy hits are `0`.
