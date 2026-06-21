# Open Source Readiness / 开源准备清单

Date / 日期: 2026-06-21

## Short Verdict / 简短结论

Do not publish the full outer workspace. It contains local logs, pool caches,
wallet addresses, machine paths, downloaded PDFs, and generated benchmark
artifacts.

不要公开外层整个工作目录。那里混有本地日志、矿池缓存、钱包地址、机器路径、
下载的 PDF 和 benchmark 产物。

The safer open-source root is:

```text
work/papiminer
```

更安全的开源根目录是：

```text
work/papiminer
```

## Publishable / 可以公开

- Core app / 核心程序：`PapiMiner.py`, `papiminer_core.py`, `PapiMiner.ps1`
- Launcher helpers / 启动脚本：`Launch-PapiMiner.ps1`, `Stop-PapiMiner.ps1`, `.cmd` launchers
- Web UI / 前端：`web/index.html`, `web/app.js`, `web/styles.css`
- Tests / 测试：`tests/`
- Example config / 示例配置：`.env.example`, `config.example.json`
- Public docs / 公开文档：`README.md`, `docs/OPEN_SOURCE_READINESS.md`, `docs/PUBLIC_REVIEW_CHECKLIST.md`
- License / 许可证：`LICENSE`

## Keep Local / 只留本地

- `local/`
- `local/test-runs/`
- `local/run-logs/`
- Raw benchmark JSON and miner logs / 原始 benchmark JSON 和 miner 日志
- Real wallet addresses, worker names, LAN IPs, Windows user paths / 真实钱包地址、worker 名、局域网 IP、本机路径
- Downloaded model weights / 已下载模型权重
- Downloaded paper PDFs / 已下载论文 PDF
- Raw PapiMiner experiment notes under `docs/papiminer-akoya-*.md` / 原始 PapiMiner 实验笔记
- Top-level temporary or backup folders / 外层临时与备份目录

## Current Risk Findings / 当前风险发现

The first privacy scan found these classes of sensitive or local-only material
in the wider workspace and raw lab notes:

- Real PRL receive/mining addresses in dashboard caches and experiment docs
- Local Windows profile paths
- LAN details from remote miner experiments
- Exchange and pool dashboard caches
- Raw logs and JSON ledgers with machine/runtime details
- Copied research PDFs that should be linked, not redistributed blindly

第一轮隐私扫描在外层工作区和原始实验笔记里发现过这些风险：

- dashboard 缓存和实验文档里有真实 PRL 地址
- 本地 Windows 用户目录路径
- 远程矿机实验留下的局域网信息
- 交易所和矿池 dashboard 缓存
- 带有机器/runtime 信息的原始日志和 JSON 账本
- 下载的论文 PDF；公开仓库里建议放链接，不直接重新分发

## Release Rule / 发布规则

Create a clean repository from `work/papiminer`, then run the privacy scan
before the first commit. Do not initialize git at the outer workspace.

从 `work/papiminer` 新建干净仓库，第一次 commit 前先跑隐私扫描。
不要在外层工作目录初始化 git。

Recommended first public commit:

```text
README.md
LICENSE
.gitignore
.env.example
config.example.json
PapiMiner.py
papiminer_core.py
PapiMiner.ps1
Launch-PapiMiner.ps1
Stop-PapiMiner.ps1
web/
tests/
tools/
docs/OPEN_SOURCE_READINESS.md
docs/PUBLIC_REVIEW_CHECKLIST.md
local/README.md
local/.gitkeep
```

## Why Not Publish Every Experiment Yet / 为什么暂时不公开全部实验

The raw PapiMiner notes are useful, but they were written as a lab notebook.
They may include live pool addresses, exact artifact names, local paths, and
short-lived test assumptions. Publish a redacted research report later instead
of the raw notes.

PapiMiner 原始笔记有价值，但它们是实验室笔记，可能包含真实矿池地址、
具体产物名、本地路径和短期测试假设。后续应该整理一份脱敏研究报告，
而不是直接公开原始笔记。
