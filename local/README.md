# local/

This folder is local-only and is ignored by git.

这个目录只放本机数据，不进入开源仓库。

Typical files:

- `run-profiles.local.json`: plain miner launch profiles
- `runtime.local.json`: current process state
- `settings.local.json`: UI settings
- `run-logs/`: miner logs
- `backgrounds/`: local UI background images

Do not place seed phrases, private keys, wallet database files, exchange passwords, or API secrets here.

不要在这里保存助记词、私钥、钱包数据库、交易所密码或 API 密钥。
