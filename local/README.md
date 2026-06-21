# local/

This folder is for local-only state. Git ignores everything in this folder
except this README and `.gitkeep`.

这个目录只放本机数据。Git 默认忽略这里的所有内容，只保留这个 README
和 `.gitkeep`，方便新用户知道目录用途。

## Files / 文件

- `models.local.json`: local model path registry / 本地模型路径登记表
- `settings.local.json`: local UI settings / 背景图等本地外观设置
- `run-profiles.local.json`: Akoya or custom miner launch profiles / Akoya 或自定义 miner 启动档案
- `runtime.local.json`: current process state, pid, logs, start time / 当前进程、pid、日志和启动时间
- `run-logs/`: miner or vLLM process logs / miner 或 vLLM 运行日志
- `backgrounds/`: uploaded local background images / 上传的本地背景图

## Keep Local / 只留本地

Do not commit:

- seed phrases, private keys, exchange passwords
- wallet database files
- raw wallet addresses and worker names in public examples
- screenshots with host names, LAN IPs, wallet addresses, or account data
- full unredacted miner logs
- large model weight files

不要提交：

- 助记词、私钥、交易所密码
- 原始钱包数据库
- 未脱敏的钱包地址和 worker 名
- 带主机名、内网 IP、钱包地址或账户信息的截图
- 未脱敏的完整矿工日志
- 大模型权重文件

Wallet addresses and worker names are not private keys, but PapiMiner still
treats them as local-only so the open-source tree stays clean.

钱包地址和 worker 名不是私钥，但 PapiMiner 仍然把它们按 local-only 处理，
这样开源仓库会更干净。
