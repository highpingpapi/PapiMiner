# PapiMiner English README

PapiMiner is a local console for Pearl **PlainProof** mining.

The current v0.2 release is a launcher and monitor, not a full custom CUDA
miner. Its default backend uses the open-source Akoya plain miner. PapiMiner
imports run profiles, starts/stops a miner, shows GPU status, tails logs, and
parses local TH/s plus pool share results.

## Features

- Import plain miner run profiles
- Start and stop miner processes
- Select GPU, worker, pool, and PRL receiving address
- Show GPU temperature, power, and utilization
- Show runtime status and logs
- Parse Akoya plain miner logs for TH/s and share results

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

A run profile is a launch card. It can define the miner executable, working
directory, GPU list, pool, worker, PRL receiving address, and command template.

The built-in profile points to Akoya plain miner. A future custom CUDA kernel can
be plugged in through the same profile system, so different backends can be
tested side by side.

## Local Hashrate

PapiMiner reads log lines such as:

```text
hashes/s=... TH/s
accepted=True
```

The displayed result is therefore a combination of local miner logs and pool
share responses. GPU model, driver, power limit, and pool conditions can all
change the result.

## Custom Kernel Roadmap

The next milestone is not a larger UI. It is a replaceable, verifiable, A/B
testable custom GPU backend. See:

[Kernel Roadmap](docs/KERNEL_ROADMAP.md)

The active candidate list is tracked in:

[Kernel Lab](kernel_lab/README.md)

## Development

```powershell
python -m pytest -q
```
