# Public Review Checklist / 公开前逐文件检查清单

Date / 日期: 2026-06-21

## Repository Root / 仓库根目录

Only publish the PapiMiner project folder:

```text
work/papiminer
```

只公开 PapiMiner 项目目录：

```text
work/papiminer
```

Do not publish the outer workspace. The outer workspace contains local logs,
model files, downloaded papers, experiment notes, and machine-specific data.

不要公开外层工作区。外层工作区里有本地日志、模型文件、下载论文、实验笔记和机器相关数据。

## Must Stay Local / 绝不能上传

These paths are intentionally ignored by git:

- `local/`
- `local/run-logs/`
- `local/test-runs/`
- `local/*.local.json`
- `docs/papiminer-akoya-*.md`
- `docs/*candidate*.md`
- `docs/*.private.md`
- `references/**/*.pdf`
- `__pycache__/`
- `.pytest_cache/`
- model weight files such as `*.safetensors`, `*.gguf`, `*.bin`, `*.pt`, `*.onnx`
- binaries and profiler outputs such as `*.exe`, `*.dll`, `*.so`, `*.ncu-rep`, `*.ptx`, `*.cubin`

这些路径已经被 git 忽略，不应该进入 GitHub。

## Public Files To Review / 建议逐个检查的公开文件

Root files:

- `.env.example`
- `.gitignore`
- `LICENSE`
- `README.md`
- `config.example.json`
- `PapiMiner.py`
- `papiminer_core.py`
- `PapiMiner.ps1`
- `Launch-PapiMiner.ps1`
- `Stop-PapiMiner.ps1`
- `启动 PapiMiner.cmd`
- `停止 PapiMiner.cmd`

Docs:

- `docs/OPEN_SOURCE_READINESS.md`
- `docs/PUBLIC_REVIEW_CHECKLIST.md`
- `local/README.md`
- `local/.gitkeep`
- `references/papers/README.md`

Web UI:

- `web/index.html`
- `web/app.js`
- `web/styles.css`

Tests:

- `tests/smoke_papiminer.py`
- `tests/test_parse_akoya_miner_log.py`
- `tests/test_runtime_command.py`
- `tests/test_smoke_papiminer.py`

Tools:

- `tools/local_audit.py`
- `tools/monitor_runtime.ps1`
- `tools/parse_akoya_miner_log.py`

The hashcore benchmark and candidate-search tools are intentionally not part of
the first public package. They can be published later as a separate redacted
research bundle.

hashcore benchmark 和候选搜索工具不进入首个公开包。它们之后可以整理成单独的
脱敏研究包再发布。

## Red-Team Privacy Questions / 红队隐私检查问题

When reviewing each public file, search for:

- real PRL wallet addresses
- worker names tied to a real machine
- Windows usernames or profile paths
- LAN IP addresses
- exchange account details
- API keys, tokens, cookies, passwords
- raw logs with hostnames or runtime paths
- screenshots or copied data containing account details
- downloaded PDFs or model weights

逐文件看时，重点找这些东西：

- 真实 PRL 钱包地址
- 真实机器绑定的 worker 名
- Windows 用户名或本地路径
- 局域网 IP
- 交易所账户信息
- API key、token、cookie、密码
- 带主机名或本地路径的原始日志
- 带账户信息的截图或复制数据
- 下载的 PDF 或模型权重

## Local Verification Commands / 本地复查命令

From the repository root:

```powershell
python .\tools\local_audit.py --output .\local\test-runs\github-redteam-audit.json
git -c core.quotepath=false ls-files -co --exclude-standard
git -c core.quotepath=false status --short --ignored
python -m pytest -q
```

Expected result:

- privacy hits: `0`
- tests: pass
- `local/`, raw lab notes, PDFs, logs, caches, and weights show as ignored

预期结果：

- 隐私命中：`0`
- 测试通过
- `local/`、原始实验笔记、PDF、日志、缓存和模型权重都显示为 ignored

## Upload Flow / 上传流程

After manual review:

```powershell
git add -A
git commit -m "Initial public PapiMiner release"
git remote add origin <YOUR_GITHUB_REPO_URL>
git push -u origin main
```

Replace `<YOUR_GITHUB_REPO_URL>` with the real empty GitHub repository URL.

把 `<YOUR_GITHUB_REPO_URL>` 换成你新建的空 GitHub 仓库地址。

## Second-Computer Review / 另一台电脑复查

On another computer:

```powershell
git clone <YOUR_GITHUB_REPO_URL>
cd papiminer
```

Then open the repository in GitHub or VS Code and repeat the red-team privacy
questions above. If anything looks personal, remove it before announcing the
repository publicly.

在另一台电脑 clone 后，再按上面的红队问题复查一遍。如果看到任何个人信息，
先删掉再公开宣传。
