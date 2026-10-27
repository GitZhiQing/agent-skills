# windows-disk-cleanup 经验索引 — public（可提交）

> 本文件由 `scripts/memory.py` 生成；`lessons/*.json` 是权威数据，不要手工改表。
> public 条目不得包含完整用户路径、用户名、凭据或用户文件名；本机详情请用 `--privacy local`。
> 检索：`python scripts/memory.py search --query "<关键词>" --json`；毕业：`memory.py graduate <ID> --to <目标>`。

共 4 条：active 2 / candidate 0 / graduated 2 / retired 0

| ID | 类型 | 范围 | 触发 | 摘要 | used | 状态 |
| --- | --- | --- | --- | --- | --- | --- |
| [L-001](lessons/L-001-appdata.json) | success | scan | appdata, timeout, generic | AppData 大目录先限时，通用目录只留最外层 | 3 | graduated |
| [L-002](lessons/L-002-windows-cmd-crlf.json) | failure | general | cmd, crlf, launcher | Windows .cmd 启动器必须 CRLF | 0 | graduated |
| [L-003](lessons/L-003-cli-playwright-override-clipboard.json) | success | report | playwright, clipboard, selection | 报告页→CLI 协议用 Playwright override clipboard 验证 | 1 | active |
| [L-004](lessons/L-004-lesson.json) | failure | delete | locked, permission, partial | 删除失败不要删父目录绕过锁定 | 0 | active |
