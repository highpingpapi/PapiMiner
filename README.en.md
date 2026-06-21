# PapiMiner English README

PapiMiner is a local console for Pearl **PlainProof-only** mining. Its scope is
deliberately small: import plain miner run profiles, start/stop a miner, and
inspect GPU status, logs, and pool share results.

## What It Does

- Starts and stops PlainProof miner profiles.
- Imports local run profiles such as miner path, working directory, GPUs, pool,
  worker name, and launch argument template.
- Shows GPU temperature, power, utilization, process status, and log tail.
- Parses Akoya plain miner logs so you can inspect local TH/s and accepted
  shares.
- Keeps wallet addresses, worker names, local paths, and logs under `local/`.

## What It Does Not Do

PapiMiner is not a wallet and not a trading bot. It does not store seed phrases,
private keys, exchange passwords, wallet databases, or browser sessions.

PapiMiner is also not the vLLM/useful-work console. AI inference and useful-work
experiments should live in a separate project so this repository stays focused
on plain mining.

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

## Run Profiles

A run profile is a local launch card. It can contain:

- miner executable path
- working directory
- GPU list
- pool host and port
- worker name
- PRL receiving address
- log path
- command template

These values can reveal local machine details, so PapiMiner stores them in
`local/run-profiles.local.json`, which is ignored by Git.

## Local Benchmarking

PapiMiner reads miner log lines such as `hashes/s=... TH/s` and share result
lines such as `accepted=True`. Public documentation does not include the
author's real wallet, worker, machine path, or long-running hashrate because
those values are local and should not be treated as a universal performance
claim.

You can parse your own log with:

```powershell
python .\tools\parse_akoya_miner_log.py .\local\run-logs\your-run.log
```

## Privacy Boundary

The following local-only files are ignored by Git:

- `local/run-profiles.local.json`
- `local/runtime.local.json`
- `local/settings.local.json`
- `local/run-logs/`
- `local/backgrounds/`

Before publishing, run:

```powershell
python -m pytest -q
python .\tools\local_audit.py --output .\local\test-runs\github-redteam-audit.json
```

Expected result: tests pass and privacy hits are `0`.

## Open-Source Rule

This repository follows three simple rules:

1. Public code must not contain private machine data.
2. Plain mining stays separate from AI/useful-work experiments.
3. Local benchmark data should be reproducible, not advertised as a universal
   promise.
