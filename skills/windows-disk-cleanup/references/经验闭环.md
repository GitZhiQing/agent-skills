# 经验闭环

这份文档定义 `windows-disk-cleanup` 的跨会话经验层：Agent 如何检索上次的成功路径/失败教训，如何写回，如何毕业为规则或文档，以及哪些内容绝不能写。

## 目录

- [1. 目标与信噪比](#1-目标与信噪比)
- [2. 两层存储](#2-两层存储)
- [3. 经验 schema](#3-经验-schema)
- [4. 开工检索](#4-开工检索)
- [5. 写回钩子](#5-写回钩子)
- [6. used 与毕业](#6-used-与毕业)
- [7. 隐私与脱敏](#7-隐私与脱敏)
- [8. 命令](#8-命令)
- [9. 维护与校验](#9-维护与校验)
- [10. 种子经验](#10-种子经验)

## 1. 目标与信噪比

经验层只回答一个问题：**下次遇到相似场景，哪条做法已经被证明有效/无效？**

它不记录“这次扫描成功”这种例行结果。只有满足以下之一才值得写：

- 一个参数组合/顺序改变了结果（如 `--max-seconds` 让大目录扫描可用、`--exclude` 避开卡顿子树）。
- 一类错误反复出现（权限、占用、长路径、回收站不可用、选择过期）。
- 规则误判/漏判（用户拒绝了 `safe` 项、`review` 项被证明是明显缓存）。
- 流程摩擦（报告页复制失败、dry-run 报 invalid、清理报告字段不够用）。
- 用户稳定偏好（连续多次只选回收站、总是排除某个项目目录）。

**不写**：单次用户数据、完整用户文件名、凭据、未验证的猜测、一次偶发失败。

## 2. 两层存储

| 层 | 位置 | 入库 | 内容 |
| --- | --- | --- | --- |
| public | `memory/lessons/*.json` + `memory/INDEX.md` | 是（可提交/分享） | 规则 id、路径后缀、错误类型、参数、通用做法；不含完整用户路径/用户名/凭据 |
| local | `memory/local/lessons/*.json` + `memory/local/INDEX.md` | 否（gitignored） | 本机路径细节、特定项目/目录名、一次性环境结论 |

`memory/INDEX.md` 与 `memory/local/INDEX.md` 由 `scripts/memory.py` 生成；**JSON 是权威数据**，不要手工改表。`memory/local/` 已在 skill 的 `.gitignore` 中。

两层使用不同 ID 前缀：public `L-001`，local `P-001`。

## 3. 经验 schema

```json
{
  "schema": 1,
  "id": "L-004",
  "title": "删除失败不要删父目录绕过锁定",
  "kind": "failure",
  "scope": "delete",
  "trigger": ["locked", "permission", "partial"],
  "finding": "单个文件被占用时，父目录会 partial；删父目录会扩大影响并掩盖原因。",
  "action": "报告 partial/failed，建议关闭程序或管理员重跑；不杀进程、不停服务、不改 ACL。",
  "evidence": {
    "rule_ids": [],
    "error_types": ["PermissionError"],
    "options": {},
    "notes": ""
  },
  "used": 0,
  "status": "active",
  "privacy": "public",
  "skill_version": "0.2.0",
  "created_at": "2026-10-27T10:43:18+08:00",
  "last_used_at": null,
  "graduated_at": null,
  "graduated_to": null
}
```

字段：

| 字段 | 说明 |
| --- | --- |
| `kind` | `success`（成功路径）/ `failure`（失败教训）/ `preference`（稳定偏好） |
| `scope` | `scan` / `delete` / `report` / `rule` / `general` |
| `trigger` | 检索关键词；写用户会说的词、错误类型、规则 id、目录类型 |
| `finding` | 观察到的事实；不要写猜测 |
| `action` | 下次具体怎么做；可执行、可验证 |
| `evidence.rule_ids` | 命中的规则 id（如 `win-temp`、`dev-node-modules`） |
| `evidence.error_types` | 错误类型（如 `PermissionError`、`invalid_selection`） |
| `evidence.options` | 参数组合（如 `max_seconds=60`、`mode=recycle`） |
| `used` | 实际改变过动作的次数；不是检索次数 |
| `status` | `active` → `candidate`（used≥3）→ `graduated`；失效用 `retired` |
| `privacy` | 与所在层一致：public/local |
| `graduated_to` | 毕业后写入的位置，如 `rules.json#win-temp`、`SKILL.md#第-6-步` |

标题 `title` 用于索引摘要；`finding/action` 可以更长。`record` 会自动把 public 中的 `C:\Users\<name>` 脱敏为 `C:\Users\<user>`。

## 4. 开工检索

固定工作流里有两个检索点，一次命令、不占额外轮：

### 4.1 doctor 后、scan 前

```bash
python "$S/scripts/memory.py" search --scope scan \
  --query "<目标类型> scan timeout permission appdata" --json
```

目标类型示例：`c-drive`、`appdata`、`project`、`downloads`、`network`。命中后读 `finding/action`，把结论并入环境判断，例如：

- “上次 AppData 扫描 30s 上限可用” → 本次先加 `--max-seconds 60`。
- “上次某目录权限报错” → 本次先提示管理员。
- “上次回收站不可用” → 本次默认建议 `permanent`。

只有实际改变了动作才 `used`。

### 4.2 delete dry-run 前

```bash
python "$S/scripts/memory.py" search --scope delete \
  --query "delete permission recycle locked long path" --json
```

用于决定：

- 失败提示优先说“关闭占用程序”还是“管理员重跑”；
- 是否建议改用 `--mode permanent`；
- 是否需要提醒长路径/回收站限制。

## 5. 写回钩子

### 5.1 扫描收尾

记录条件：

- `stats.partial` 且原因是可复用的（时间上限、某类系统目录、权限）；
- 发现规则漏判（明显缓存却显示 review）；
- 发现规则误判（safe 项被用户明确拒绝）；
- 某个 `--exclude`/`--listing-depth`/`--min-size` 组合显著改善了结果。

示例：

```bash
python "$S/scripts/memory.py" record \
  --kind success --scope scan \
  --trigger appdata --trigger timeout \
  --title "AppData 大目录先限时" \
  --finding "AppData\\Local 目录数很大，完整扫描容易跑飞。" \
  --action "先加 --max-seconds 30–60，接受 partial 并在交付时说明。" \
  --option max_seconds=60 --privacy public --json
```

### 5.2 删除收尾

记录条件：

- `failed/partial` 有可复用的错误类型与处理方式；
- 回收站不可用、长路径失败、权限失败；
- 某个删除方式/顺序证明有效。

示例：

```bash
python "$S/scripts/memory.py" record \
  --kind failure --scope delete \
  --trigger "access denied" --trigger locked \
  --title "权限失败先提示管理员" \
  --finding "删除 Windows\\Temp 部分文件遇到 Access Denied。" \
  --action "提示以管理员身份重跑；不停止服务、不改 ACL。" \
  --rule-id win-temp --error-type PermissionError \
  --privacy public --json
```

- 完整路径/用户名：用 `--privacy local`。
- 单次用户偏好：`--kind preference --scope report --privacy local`（不要写成 public 的“用户永远喜欢…”）。

### 5.3 规则误判/漏判

差集推断，不需要页面额外按钮：

- `scan.json` 中 `safe/caution` 但不在 `selection.json`：用户拒绝了建议 → 可能是误判；
- `scan.json` 中 `review` 但被用户选中并成功删除 → 可能是漏判；
- `scan.json` 中明显的大目录没有条目 → 规则覆盖缺口。

记录为 `kind=failure, scope=rule`，`evidence.rule_ids` 写相关规则；**不要直接改 rules.json**。候选经验 `used>=3` 或多次独立验证后，才进入毕业流程。

## 6. used 与毕业

- `used` 只在经验实际改变了动作时 +1；只“看到”不加。
- `used >= 3` 时脚本把 `active` 改为 `candidate`，表示“可以考虑毕业”，不是自动毕业。
- 毕业流程：
  1. 人工修改 `assets/rules.json` / `SKILL.md` / `references/`；
  2. 跑 `python -m disk_cleanup rules --check --json`；
  3. 跑全量 `python -m unittest discover -s tests`；
  4. 验证通过后：

     ```bash
     python "$S/scripts/memory.py" graduate L-001 \
       --to "rules.json#win-temp" --note "已写入规则并回归" --json
     ```
- 毕业后默认检索不再返回该条；它已进入规则/文档，成为常驻知识。
- 经验不再适用时 `retire <ID> --reason "..."`，不要删除历史。

## 7. 隐私与脱敏

`record --privacy public` 会：

- 把 `%USERPROFILE%` / `%LOCALAPPDATA%` / `%APPDATA%` 的实际值替换为环境变量占位；
- 把 `C:\Users\<任意用户名>` 替换为 `C:\Users\<user>`；
- 拒绝包含 `password=`、`token=`、`api_key=`、私钥块等内容。

仍需要人工遵守：

- public 不写客户名、项目名、文件名、下载文件名；
- 只写规则 id、路径后缀（`\AppData\Local\Temp`）、错误类型、参数；
- 完整路径/项目名放 `--privacy local`；
- 凭据、密钥、Cookie、浏览器数据一律不写。

`check` 会检查 public 层是否残留未脱敏的用户路径、重复 ID、非法字段与密钥模式；`memory/local/` 在 `.gitignore` 中，但仍建议不要写入凭据。

## 8. 命令

```bash
mem() { python skills/windows-disk-cleanup/scripts/memory.py "$@"; }

# 检索（默认 active/candidate；--all-status 含 graduated/retired）
mem search --query "access denied appdata" --json
mem search --query "recycle" --scope delete --privacy local --json

# 写回
mem record --kind failure --scope delete --trigger "access denied" \
  --finding "..." --action "..." --rule-id win-temp \
  --error-type PermissionError --option mode=recycle \
  --privacy public --json

# 实际使用后
mem used L-001 --json

# 毕业/退役
mem graduate L-001 --to "rules.json#win-temp" --note "已回归" --json
mem retire L-004 --reason "已被新规则覆盖" --json

# 查看/校验
mem list --privacy all --json
mem check --json
mem index --json
```

退出码：0 成功；1 经验库错误（未找到、校验失败、密钥拦截）；2 用法错误（缺参数、非法枚举）。`--json` 输出单行 JSON。

## 9. 维护与校验

- `memory/INDEX.md` 是生成物；改经验请改 JSON 或走 `record/used/graduate/retire`。
- 每次规则/文档毕业必须同时跑 `rules --check` 与全量测试；禁止只改经验库就宣称规则已进化。
- `check` 只校验结构与隐私，不判断内容质量；内容质量由写回时的“可复用”标准保证。
- 经验条目数量不必追求多：10 条高信号经验比 100 条“扫描成功”有用。
- 版本升级时 `skill_version` 记录写入时的版本，便于回溯经验对应的行为基线。

## 10. 种子经验

首版包含 4 条真实种子：

- `L-001`（graduated）：AppData 大目录先限时、通用目录只留最外层 → `scanner.py#_prune_nested_generic`。
- `L-002`（graduated）：Windows `.cmd` 启动器必须 CRLF → `bin/windows-disk-cleanup.cmd` + `.gitattributes`。
- `L-003`（active）：报告页→CLI 协议用 Playwright override clipboard 验证 → 可复用的验证路径。
- `L-004`（active）：删除失败不要删父目录绕过锁定 → delete 失败处理。

种子只证明格式与流程；后续经验由每次真实会话按上述钩子生长。
