# windows-disk-cleanup

Windows 磁盘/文件夹的可审计清理：只读扫描 → 离线 HTML 报告供用户勾选 → 页面一键复制选择 JSON → Agent 二次校验后删除 → 清理报告。

它不是“一键清理大师”：**扫描不删、页面不删、用户明确勾选并粘贴后才删**。规则库覆盖系统升级残留、Windows 更新/临时/日志、用户与浏览器缓存、开发工具与项目构建产物、凭据/保留项；对 `node_modules`、`.venv` 这类大目录只统计大小、不展开子项。每次会话还可以把可复用的成功路径/失败教训写回 public/local 经验库，`used>=3` 后人工毕业为规则或文档。

## 何时触发

- “C 盘满了/帮我清理 C 盘”“扫描 D 盘看看什么占空间”“清理下载/缓存/旧项目”
- “生成一份磁盘清理报告”“windows disk cleanup”“free up disk space”
- 需要先看清单再决定删什么，且希望删除后可审计
- 不触发：只想分析单个文件、让 Agent 直接删除给定路径、非 Windows、分区/格式化/系统重装/驱动管理

## 工作方式

1. `doctor` 检查 Windows、Python、PowerShell、管理员与目标盘，并检索历史经验。
2. `scan` 只读遍历：已知缓存作为叶子只计大小；系统目录按白名单剪枝；用户目录分层识别。
3. 生成 `report.html`：目录总览、清理建议、大小/文件数/说明/建议；用户勾选并复制选择 JSON。
4. `delete --dry-run` 逐条对照 `scan.json`、保护清单与 reparse 检查；通过后 `--yes` 执行。
5. 生成 `cleanup-report.html` + `cleanup.json`：逐项状态、处理量、实际可用空间变化、失败原因。
6. 有可复用结论时写回经验库；`used>=3` 或反复验证后人工毕业为规则/文档。

完整协议见 [SKILL.md](SKILL.md)；选择/保护/失败细节见 [references/扫描与删除协议.md](references/扫描与删除协议.md)。

## 依赖

- Windows 10/11
- Python 3.9+（纯标准库；推荐 uv，`bin/` 启动器会自动使用 uv，找不到则回退系统 Python）
- 回收站模式需要 Windows PowerShell 5.1+
- 系统级目录（`Windows.old`、`Windows\Temp`、更新缓存等）通常需要管理员权限

## 安装

随仓库统一分发：

```bash
bash scripts/skills-link.sh windows-disk-cleanup
bash scripts/skills-doctor.sh
```

也可以把 `skills/windows-disk-cleanup/` 整个目录拷走使用；入口不依赖当前工作目录。

## 快速开始

Git Bash：

```bash
BIN="skills/windows-disk-cleanup/bin/windows-disk-cleanup"

# 1. 环境
bash "$BIN" doctor --root "C:\\" --json

# 2. 只读扫描（全盘可加 --max-seconds 900）
bash "$BIN" scan --root "C:\\" --output-dir "E:/reports/c-drive" --json

# 3. 打开 E:/reports/c-drive/report.html，勾选后复制 JSON，
#    原样保存为 E:/reports/c-drive/selection.json，然后预演：
bash "$BIN" delete --selection "E:/reports/c-drive/selection.json" --dry-run --json

# 4. 预演通过后执行
bash "$BIN" delete --selection "E:/reports/c-drive/selection.json" --yes --json
```

PowerShell/cmd：

```bat
skills\windows-disk-cleanup\bin\windows-disk-cleanup.cmd scan --root "C:\" --output-dir "E:\reports\c-drive" --json
```

直接用 uv：

```bash
uv run --project skills/windows-disk-cleanup windows-disk-cleanup --help
```

## 命令

### `scan`

```text
scan --root <盘符|文件夹> [--output-dir DIR] [--min-size MB] [--listing-depth N]
     [--max-entries N] [--max-seconds S] [--exclude PATTERN]...
     [--allow-network] [--json] [--progress|--quiet] [--rules FILE]
```

- `--min-size`：通用大目录阈值，默认 50MB；规则命中的缓存不受此限制。
- `--listing-depth`：通用大目录列出深度，默认 3；已知规则仍会在更深层匹配。
- `--max-entries`：HTML 最多嵌入条目，默认 1500；完整数据始终在 `scan.json`。
- `--max-seconds`：扫描时间上限，0 表示不限；达到上限会标记 `partial`。
- `--exclude`：按路径或名称排除（可重复），例如 `--exclude node_modules --exclude "D:\\Projects"`。
- `--allow-network`：允许扫描网络/未知类型驱动器；默认拒绝。
- `--json`：stdout 单行 JSON；进度/诊断走 stderr。

输出目录默认 `~/disk-cleanup/<时间戳>/`；若目录已有 `scan.json`/`report.html` 会拒绝覆盖。

### `delete`

```text
delete --selection <selection.json> [--scan scan.json] [--mode recycle|permanent]
       [--dry-run | --yes] [--confirm] [--allow-review] [--json]
```

- 不带 `--yes` 永远只预演，不删除。
- `--mode` 覆盖选择 JSON 的全部逐条方式；不会降低确认要求。
- `--confirm`：用户已在聊天中明确确认时，替代报告页确认框。
- `--allow-review`：选择包含 `review`（未识别目录）时必须加。
- 退出码：0 成功；1 有失败/部分删除（报告仍生成）；2 选择/参数错误。

### `doctor` / `rules` / `enrich`

- `doctor --root <path> --json`：检查系统/依赖/权限/盘类型/可写性。
- `rules --check --json`：校验内置规则库；`rules --json` 导出规则。
- `enrich --scan scan.json --enrichment enrichment.json [--check]`：应用 AI 深化分析（Agent 对未命中规则目录的受限只读探索结论），合并展示信息并重渲染增强报告（默认输出 `enriched/`）。**只补展示信息与「AI 参考」建议，不改删除判定**；协议见 [references/深化分析协议.md](references/深化分析协议.md)。

## 报告页

`report.html` 是单文件页面，样式经 Tailwind CDN 加载（联网打开才有样式；离线时顶部有降级提示，数据与复制功能不受影响）：

- **清理建议**：默认视图，只列建议清理/安全/谨慎/待定项；默认按建议度排序，可切换按大小/名称。
- **分类筛选行**（表格上方，每维一行）：清单与计数固定（按当前视图统计，不随其它维度变化，避免条目跳动），可任意组合；生效中的筛选以可移除标签列出：归属（系统/应用/开发工具/用户文件/虚拟机）、性质（缓存/日志与转储/构建产物/安装包与更新残留/临时文件/用户内容/配置与凭据/未识别）、生态（Node.js/Python/… 仅在「开发工具」下出现）；窄屏时自动堆叠到表格上方。另有建议档与 AI 分析状态筛选、关键词搜索。
- **目录总览**：顶层目录与用户数据目录，包括标记为保留的系统项。
- **全部条目**：完整报告条目（受 `--max-entries` 限制，分页每页 100 条）。
- **紧凑行 + 详情展开**：每条目单行（展开箭头 · 标题 · 路径 · 关键徽章 · 大小 · 文件数 · 方式 · 说明摘要 · 时间），行高约 36px、一屏 12+ 条；点箭头展开完整路径、说明、建议、风险、AI 依据与分类；说明列悬浮可见全文。
- **逐条删除方式**：行内「♻ 回收站 / ✕ 彻底」图标切换（悬浮有说明），默认回收站；需管理员的条目有徽标。
- 勾选后底部选择栏显示已选数量/大小，检测父子重叠与待定项；必须勾选确认框才能复制。
- 复制内容是一个带说明的 JSON 代码块（schema 2，含逐条方式 `modes`），交由 Agent 保存为 `selection.json`。
- AI 深化分析（可选）：Agent 对未命中规则的目录做受限只读探索后，`enrich` 生成增强报告。高置信判定会把「待定」提升为明确档位（**AI 定档** 徽章，提升后不再需要 `--allow-review`），其余为「AI 分析」徽章（只补分类与说明、悬浮见依据）；AI 永远不能放宽可删范围。

浏览器禁止剪贴板时会弹出手动复制框；选择 JSON 也可以从弹窗全选复制。

## 安全模型

- **扫描与报告只读**；页面没有删除按钮。
- **二次校验**：`delete` 要求 `scan_id` 一致、路径在 `scan.json` 中、`selectable: true`、`recommendation != keep`，并再跑独立保护清单（`safety.py`）。
- **系统保护**：Windows/System32/WinSxS/Installer/DriverStore、Program Files、ProgramData 根、用户配置文件根、AppData 根、桌面/文档/图片/视频/音乐/OneDrive、`.git/.ssh/.gnupg/.aws/.azure/.kube/.docker`、页面/休眠/交换文件、回收站目录本身均拒绝删除。
- **白名单**：只允许明确标记的系统临时/日志/错误报告/字体缓存等；详见协议文档。
- **reparse point**：junction/symlink 不跟随、不删除；报告中标记为保留。
- **父子重叠**：只删父目录，子项标记 `skipped_covered`。
- **失败如实报告**：占用/权限/长路径进入 `failed/partial`，不会为了“成功”去删父目录或停服务。
- **默认回收站**：移入回收站不等于释放空间；清空后才释放。彻底删除不可恢复。

## 规则库

- 数据源：[assets/rules.json](assets/rules.json)（226 条，2026-10-28）。
- 可读目录与来源：[references/目录规则库.md](references/目录规则库.md)。
- 规则类型：精确路径、路径后缀、glob、正则、名称 + `requires_inside`/`requires_sibling_any`。
- 建议等级：`suggest`（建议清理）/ `safe` / `caution` / `keep`（建议保留）；`review`（待定）是未命中规则的兜底档。
- 语言标注：94 条开发类规则带 `language`（nodejs/python/…/tools，受控枚举），供报告页语言筛选。
- 维护：改 JSON → `rules --check --json` → 同步规则文档 → 跑测试 → 升次位版本。

## 经验闭环

每次会话不是“记流水账”，只沉淀**可复用**的成功路径与失败教训：

- **public 层**：`memory/lessons/*.json` + `memory/INDEX.md`，可提交；只写规则 id、路径后缀、错误类型、参数、通用做法，不写完整用户路径/用户名/凭据。
- **local 层**：`memory/local/`，gitignored；可写本机路径细节、项目名，便于下次定位。

```bash
S="skills/windows-disk-cleanup"
mem() { python "$S/scripts/memory.py" "$@"; }

# 开工检索（doctor 后、scan 前）
mem search --query "<目标类型> scan timeout permission" --json

# 删除前检索
mem search --query "delete permission recycle locked long path" --json

# 写回 / 使用 / 毕业 / 校验
mem record --kind failure --scope delete --trigger "access denied" \
  --finding "..." --action "..." --json
mem used <ID> --json
mem graduate <ID> --to "rules.json#..." --json
mem check --json
```

- 实际改变动作才 `used`；`used>=3` 变 candidate，人工改规则/文档并跑测试后才毕业。
- `memory/local/` 可保存完整路径；`memory/INDEX.md` 是自动生成的公开索引。

当前公开经验见 [memory/INDEX.md](memory/INDEX.md)；schema、隐私、毕业门见 [references/经验闭环.md](references/经验闭环.md)。

## 排障

| 现象 | 处理 |
| --- | --- |
| `找不到 uv/python/python3/py` | 安装 uv（<https://docs.astral.sh/uv/>）或 Python 3.9+ |
| 回收站模式失败/找不到 PowerShell | 用 `--mode permanent`，或安装 Windows PowerShell 5.1 |
| `Access is denied` / 系统项失败 | 以管理员身份重跑同一命令；不要手工改权限 |
| 文件被占用 | 关闭对应程序/编辑器/浏览器后重试；或接受 `failed/partial` |
| 报告没有想要的目录 | 降低 `--min-size`、增大 `--listing-depth`，或直接 `--root` 指向该子目录重新扫描 |
| 全盘扫描太慢 | 加 `--max-seconds 600`；或用 `--exclude` 排除大目录；结果会标记 `partial` |
| `invalid: 不在本次扫描结果中` | 选择过期/路径被移动；重新打开对应 `report.html` 复制，不要手改 JSON |
| `requires_allow_review` | 选择含未识别目录；确认用途后加 `--allow-review` |
| 复制按钮无反应 | 浏览器拦截剪贴板；在弹窗中全选复制 |
| 空间没变化 | 回收站模式需清空回收站；或条目被占用/部分删除 |

## 文档

- [SKILL.md](SKILL.md) — Agent 固定工作流与硬规则（权威来源）
- [references/目录规则库.md](references/目录规则库.md) — 规则分类、226 条明细、官方来源
- [references/扫描与删除协议.md](references/扫描与删除协议.md) — 选择 JSON、校验/保护清单、失败处理
- [references/经验闭环.md](references/经验闭环.md) — 经验 schema、检索/写回/毕业、public/local 隐私
- [memory/INDEX.md](memory/INDEX.md) — 当前公开经验索引（自动生成）
- [docs/测试集.md](docs/测试集.md) — 行为协议回归（63 条自动化测试 + 人工用例）
- [docs/需求与设计文档.md](docs/需求与设计文档.md) — 架构、安全模型、扫描策略、决策

许可：MIT（仓库根 [LICENSE](../../LICENSE)）。
