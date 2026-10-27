---
name: windows-disk-cleanup
description: >-
  为 Windows 磁盘或文件夹做可审计的清理：只读扫描目录并按内置规则库给出「这是什么、为什么占空间、能不能删」的建议，
  生成离线 HTML 报告供用户勾选，页面一键复制选择 JSON，Agent 再按选择安全删除并生成清理报告。
  当用户说「清理 C 盘」「磁盘满了」「扫描 D 盘/某个文件夹看什么占空间」「生成磁盘清理报告」「帮我清理下载/缓存」，
  或英文 "clean up C drive" "free up disk space" "disk cleanup report" "what is taking up space" 时使用。
  只想分析单个文件/目录、让 Agent 直接删除用户给定的具体路径、非 Windows 系统，或要做分区/格式化/系统重装/驱动管理时，不要使用本 skill。
license: MIT
compatibility: Windows 10/11；Python 3.9+（推荐 uv，也可直接用 python）；回收站模式需要 Windows PowerShell 5.1+；系统级目录通常需要管理员权限
metadata:
  version: 0.2.0
  category: system
---

# windows-disk-cleanup · 先扫描、再勾选、最后删除

## 0. 硬规则（先读）

1. **扫描只读**：`scan` 不删除、不移动、不改权限；只有 `delete --yes` 会删。
2. **不替用户选**：报告生成后不自动勾选、不猜测要删什么；必须等用户粘贴报告页复制的选择 JSON。
3. **只用本 skill 的删除入口**：禁止直接用 `Remove-Item`、`rd /s`、`del /f`、`shutil.rmtree`、资源管理器脚本删除用户路径。
4. **不越界**：只删 `scan.json` 中 `selectable: true` 的条目；系统盘根、Windows、Program Files、ProgramData 根、用户配置文件根、AppData 根、凭据目录、`.git` 一律不删。
5. **不强行解锁**：不为删除停止服务、杀进程、改 ACL、关 Defender、改注册表；被占用就如实报告。
6. **不自动跑系统工具**：DISM、cleanmgr、Storage Sense、Windows Update 重置只作为建议，不替用户执行。
7. **默认回收站**：`recycle` 是默认方式；`permanent` 只在用户选择或明确要求“更快/彻底删除”时使用。
8. **不自动提权**：需要管理员权限的系统项，提示用户以管理员身份重跑，不自行提权。
9. **不伪造结果**：失败/部分删除/跳过都写进报告；回收站模式不说成“空间已释放”。
10. **不改证据**：不编辑 `scan.json` / `selection.json` 来加入路径；发现选择无效就停下来说明。
11. **经验不泄密**：public 经验不写完整用户路径、用户名、凭据或用户文件名；本机路径用 `--privacy local`。
12. **不自动改规则**：经验只是候选；毕业必须人工改 `rules.json` / `SKILL.md` / `references/`，并跑 `rules --check` + 全量测试。

## 0.5 经验闭环（跨会话）

设 `S` = 本 skill 根目录；bash 用 `mem() { python "$S/scripts/memory.py" "$@"; }`（PowerShell 直接 `python "$S\scripts\memory.py" ...`）。

- doctor 后/scan 前：`mem search --scope scan --query "<目标类型> scan timeout permission appdata" --json`
- dry-run 前：`mem search --scope delete --query "delete permission recycle locked long path" --json`
- 命中读 `finding/action`；实际改变动作才 `mem used <ID> --json`。
- 收尾四问：环境坑/规则误判漏判/流程摩擦/成功路径；只写可复用结论。
- public/local；`used>=3`→candidate；人工改规则+测试后 `mem graduate`；schema 见 `references/经验闭环.md`。

## 1. 固定工作流（6 步）

设 `S` = 本 skill 根目录，`BIN` = `bash "$S/bin/windows-disk-cleanup"`（Windows cmd/PowerShell 用 `"$S\bin\windows-disk-cleanup.cmd"`）。`OUT` = 本次输出目录。

### 第 0 步：确认目标

- 用户必须给出**盘符或文件夹**。只说“清理一下电脑/磁盘满了”时，先问清是哪个盘/哪个文件夹，不要自己挑。
- 目标明确时不要重复盘问参数；直接采用默认：大目录阈值 50MB、列出深度 3、报告最多 1500 条、输出到 `~/disk-cleanup/<时间戳>/`。
- 全盘扫描可能几分钟；AppData/项目大目录可先加 `--max-seconds 30–60`，全盘可 900；告诉用户“扫描只读，先出报告，删除要你勾选确认”。
- 用户指定输出目录时用用户的；否则用默认目录，不要写到用户项目源码目录里。

### 第 1 步：环境检查

```bash
$BIN doctor --root "<目标>" --json
```

- `ok: false`：只处理 error 级检查（非 Windows、目标不存在、光驱/不可读），修不了就停止。
- `uv`/`powershell`/`admin` 是 warn：记下来。无 PowerShell 时回收站模式不可用，报告里要说明“只能彻底删除”；非管理员时系统项可能失败。
- 检索经验：`mem search --scope scan --query "<目标类型> scan timeout permission appdata" --json`；命中就把相关 `finding/action` 并入本次环境判断。

### 第 2 步：只读扫描

```bash
$BIN scan --root "<目标>" --output-dir "$OUT" --json
```

- 读取 stdout JSON：`scan_id`、`report`、`scan_json`、`stats`、`summary`、`top`、`notes`。
- `stats.partial: true`：说明达到时间上限或部分目录不可读，结果不完整；在交付时明确说。
- `summary.safe/caution/review` 为 0 且 `top` 为空：如实告诉用户没有发现可清理项，不要硬凑。
- 不要用 `scan.json` 的全量条目刷屏；只引用 `top` 和汇总。
- 经验命中改变了参数（如限时、排除、深扫）时，交付里说明；实际改变动作后 `mem used <ID> --json`。

### 第 3 步：交付报告并等待勾选

用绝对路径给用户报告链接，例如 `[report.html](E:/data/.../report.html)`，并给一句话摘要：

> 扫描完成：安全清理 N 项约 X GB，谨慎清理 M 项约 Y GB，待确认 K 项。打开报告页勾选要删的条目，选择删除方式并勾选确认框，点击「复制选中路径」，把 JSON 粘贴回来。

同时说明：

- 本页只做选择，不会删除文件；默认不选中任何项。
- 回收站模式可恢复；彻底删除不可恢复。
- 「待确认 / review」是未命中规则的目录，删除前必须核实用途。
- 父子目录同时勾选时，删除以父目录为准。

**然后停止本轮，等用户粘贴选择。** 不要替用户勾选，不要先删“明显是缓存”的条目。

### 第 4 步：接收选择并预演

1. 把用户粘贴的内容**原样**保存为 `$OUT/selection.json`（UTF-8）。不要把 paths 摘出来单独传，不要改 `scan_id`。
2. 检索删除经验：`mem search --scope delete --query "delete permission recycle locked long path" --json`；命中就按 `action` 调整重试/提示策略。
3. 预演：

   ```bash
   $BIN delete --selection "$OUT/selection.json" --dry-run --json
   ```

4. 按返回 JSON 处理：
   - `invalid` 非空 → **停止**，逐条说明 `reason`（路径不在扫描结果、被保护、扫描过期等），让用户重新从报告页复制。
   - `missing` 非空 → 说明哪些条目已不存在；可继续，最终报告会标记 `skipped_missing`。
   - `covered` 非空 → 父子重叠，正常；只删父目录。
   - `requires_allow_review: true` → 选择含 `review` 项；执行加 `--allow-review`，并再次向用户点明涉及哪些路径。
   - `confirmed: false` → 用户没在报告页勾确认框；请用户重新复制，或在用户明确说“确认删除”后加 `--confirm`。
   - `planned` 为空 → 没有可执行项，停止。

### 第 5 步：执行删除并生成清理报告

预演通过后：

```bash
$BIN delete --selection "$OUT/selection.json" --yes --json
# 含 review 项时：
$BIN delete --selection "$OUT/selection.json" --yes --allow-review --json
```

- 不要加 `--mode permanent` 覆盖用户选择；除非用户在报告页选了彻底删除，或在聊天中明确要求。
- 读取返回 JSON：`cleanup_report`、`cleanup_json`、`summary`、`items`、`notes`。
- 退出码 1 表示有 `failed/partial`，但清理报告已经生成；不要丢弃报告。

### 第 6 步：汇报与经验写回

给用户：

- 清理报告链接（绝对路径）。
- `summary`：选中/成功/失败/跳过，`moved_bytes_h`（处理量）与 `volume_freed_h`（实际可用空间变化）。
- 失败项前 3 条的路径 + 错误 + 处理建议（关闭占用程序、管理员重跑、改用彻底删除）。
- 回收站模式：提醒“文件在回收站，清空后才释放空间”。
- 审计文件：`scan.json`、`selection.json`、`cleanup.json` 留在 `OUT`。

收尾四问：**环境坑？规则误判/漏判？流程摩擦？可复用的成功路径？** 有可复用结论才写回：

```bash
mem record --kind failure --scope delete --trigger "access denied" \
  --finding "<发生了什么>" --action "<下次怎么做>" \
  --rule-id <rule_id> --error-type PermissionError --privacy public --json
```

- 例行成功不记；单次用户偏好、完整用户路径、凭据不写 public。
- 经验实际改变了动作 → `mem used <ID> --json`。
- `used >= 3` 或反复验证稳定 → 只提议毕业；人工改规则/文档并跑测试后 `mem graduate <ID> --to "<位置>"`。

不要重新扫描、不要自动清空回收站、不要继续删除用户没选的条目。需要再清一个盘时让用户重新发起。

## 2. 命令与退出码

| 命令 | 作用 | 关键参数 |
| --- | --- | --- |
| `doctor --root <path> --json` | Windows/Python/PowerShell/管理员/盘类型/可写性 | `--root` 默认当前目录 |
| `scan --root <path> --output-dir <dir> --json` | 只读扫描，写 `scan.json` + `report.html` | `--min-size MB`（50）、`--listing-depth`（3）、`--max-entries`（1500）、`--max-seconds`（0 不限）、`--exclude PATTERN`（可重复）、`--allow-network` |
| `delete --selection <file> --dry-run --json` | 校验 + 预演，不删除 | `--scan` 显式指定 scan.json |
| `delete --selection <file> --yes --json` | 执行删除，写 `cleanup.json` + `cleanup-report.html` | `--mode recycle\|permanent`、`--confirm`、`--allow-review` |
| `rules --check --json` | 校验内置规则库 | `--rules` 自定义规则文件（维护用） |
| `python scripts/memory.py search/record/used/graduate/check` | 经验检索/写回/毕业/校验；默认 `memory/` | `--json`；public 可提交，local gitignored |

退出码：`0` 成功；`1` 业务失败（扫描不完整、删除失败/部分删除）；`2` 用法/选择错误（路径无效、未确认、schema 不符）。`--json` 时 stdout 始终是单个 JSON 对象，进度/诊断在 stderr。

## 3. 选择协议（摘要）

报告页复制的 JSON 至少包含：

```json
{
  "skill": "windows-disk-cleanup",
  "schema": 1,
  "scan_id": "...",
  "scan_file": "E:\\...\\scan.json",
  "root": "C:\\Users\\...\\AppData\\Local",
  "mode": "recycle",
  "confirmed": true,
  "paths": ["C:\\Users\\...\\AppData\\Local\\npm-cache"]
}
```

- `paths` 只接受 `scan.json` 中存在的条目；不能手工加子文件或扫描外路径。
- `mode` 是 `recycle`（默认）或 `permanent`。
- `confirmed` 来自报告页确认框；`--confirm` 只用于用户在聊天中明确确认后替代它。
- 选择含 `review` 项时，执行必须加 `--allow-review`。
- 详细校验规则、保护清单、失败状态见 `references/扫描与删除协议.md`。

## 4. 报告与判断纪律

- **报告页是选择器，不是删除器**：页面没有删除按钮；复制出的 JSON 才触发删除。
- **大小口径**：逻辑大小；硬链接/压缩/稀疏文件与资源管理器可能不同。WinSxS 不深入统计，避免硬链接失真。
- **安全/谨慎/待确认/保留**：分别对应“可再生成”“可能含数据”“未识别”“不可删”；不要把待确认项说成安全项。
- **父子重叠**：报告摘要按最深可清理项合计；表格仍逐条列出，删除时以父目录为准。
- **系统项**：C 盘系统项通常需要管理员；普通权限会话不要承诺一定成功。
- **回收站**：`moved_bytes` 是移入量，`volume_freed` 才是可用空间变化；清空前可用空间可能不变。
- **失败**：如实列出，不重试掩盖；锁定文件让用户关闭程序，权限问题让用户以管理员重跑。

## 5. 按需读取

| 场景 | 读取 |
| --- | --- |
| 某个目录是什么、为什么建议删/保留、规则分类与来源 | `references/目录规则库.md` |
| selection JSON 字段、校验/保护清单、dry-run、权限/占用/长路径/回收站失败 | `references/扫描与删除协议.md` |
| 经验 schema、检索/写回/used/毕业、public/local 隐私 | `references/经验闭环.md`、`memory/INDEX.md` |
| CLI 参数、安装、依赖、报告页说明、排障 | `README.md` |
| 行为协议回归 | `docs/测试集.md` |

## 6. 边界

- 仅 Windows 10/11；不支持 Linux/macOS。
- 不做分区、格式化、系统重装、驱动管理、注册表清理、磁盘碎片整理。
- 不做数据恢复；回收站模式尽力而为，不保证所有文件都能进回收站。
- 默认拒绝网络位置/光驱；确需扫描网络位置加 `--allow-network`，但删除仍受保护清单约束。
- 不监控实时磁盘变化；每次清理都从新的 scan 开始。
- 不保证释放量：硬链接、压缩、稀疏文件、回收站、被占用文件都会影响实际可用空间。
- 经验库是本机数据：public 层不得写凭据/完整用户路径；local 层不入库。
- 经验不会自动改规则；毕业是人工代码/文档变更，必须过 `rules --check` + 全量测试。

## 7. 参考

- `references/目录规则库.md` — 226 条目录规则（系统/用户/开发/项目/凭据）与官方来源。
- `references/扫描与删除协议.md` — 选择 JSON、二次校验、保护清单、失败处理。
- `references/经验闭环.md` — 经验 schema、检索/写回/毕业、隐私边界。
- `memory/INDEX.md` — 当前公开经验索引（自动生成）。
- `README.md` — 安装、用法、报告页与排障。
- `docs/需求与设计文档.md` — 架构、安全模型、规则 schema、扫描策略与决策。
- `docs/测试集.md` — 固定工作流的行为断言。
