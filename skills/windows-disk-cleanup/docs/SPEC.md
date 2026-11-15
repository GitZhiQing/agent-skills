# windows-disk-cleanup 需求与设计文档

版本：v0.7.0　日期：2026-11-15

## 1. 问题与目标

### 1.1 问题

Windows 清理的难点不是“找到大目录”，而是：

1. **不知道目录是什么**：同名目录（`build`、`Cache`、`.venv`）在不同位置含义完全不同。
2. **不敢删**：WinSxS、Installer、ProgramData、用户配置、`.git` 等误删代价高。
3. **删除不可审计**：脚本一键 `rd /s` 没有清单、没有确认、失败也不知道删了什么。
4. **报告不可操作**：纯文本报告无法让用户勾选，也没法把选择可靠地交回 Agent。

### 1.2 目标

- 用户给出盘符或文件夹，Agent 按固定工作流只读扫描。
- 生成一份**离线、可筛选、可勾选**的 HTML 报告，列出目录是什么、大小、建议、风险。
- 用户勾选后，页面**一键复制选择 JSON**；Agent 二次校验后删除。
- 删除后生成清理报告：逐项状态、处理量、实际可用空间变化、失败原因。
- 对 `node_modules`、`.venv` 等大型缓存，确认类型后只统计总大小，不展开子项。
- Python 纯标准库，可用 uv 运行；PowerShell 负责回收站与少量系统信息。

### 1.3 非目标

- 不做分区/格式化/系统重装/驱动管理/注册表清理。
- 不做数据恢复、实时监控、常驻服务。
- 不做“一键智能清理”：不替用户勾选、不自动执行系统工具。
- 不保证覆盖所有软件；未识别目录必须以 `review` 呈现。
- 不承诺释放量：硬链接、压缩、稀疏文件、回收站、占用文件都会影响实际可用空间。

## 2. 方案

### 2.1 架构

```text
skills/windows-disk-cleanup/
  bin/windows-disk-cleanup(.cmd)     # 位置无关启动器（uv → python 回退）
  src/disk_cleanup/
    cli.py                            # doctor / scan / delete / rules
    scanner.py                        # 遍历、剪枝、叶子测量、用户目录分类
    rules.py                          # 规则加载、匹配、保护前缀、兴趣路径
    safety.py                         # 独立删除保护（不信任 scan.json）
    selection.py                      # 选择 JSON 解析 + 二次校验
    cleaner.py                        # 永久删除 / 回收站 / 清理结果
    report.py                         # HTML/JSON 渲染、摘要去重
    winutil.py                        # 盘信息、长路径、reparse、PowerShell、格式化
    model.py                          # Entry/ScanResult/DeleteResult
  assets/
    rules.json                        # 250 条规则（权威）
    report.template.html              # 扫描报告（单文件离线）
    cleanup.template.html             # 清理报告
    ps/probe.ps1                      # 回收站大小 / 卷信息
    ps/recycle.ps1                    # 移入回收站
  references/
    rules-catalog.md                      # 规则可读目录 + 来源
    protocol.md                  # 选择/保护/失败协议
  tests/                              # 52 条 unittest
```

### 2.2 数据流

```text
用户目标
  │
  ├─ doctor（环境事实）
  ├─ scan（只读）──► scan.json（全量）+ report.html（可勾选）
  │                         │
  │                         └─ 用户勾选 → 复制 selection JSON
  │
  ├─ delete --dry-run ──► 逐条对照 scan.json + safety.py
  │                         │
  └─ delete --yes ──────► 永久删除 / 回收站 ──► cleanup.json + cleanup-report.html
```

### 2.3 扫描策略

**三层目录处理：**

| 层 | 处理 | 例子 |
| --- | --- | --- |
| 规则命中 `leaf` | 计算总大小/文件数，不深入列子项 | `node_modules`、`.venv`、Temp、浏览器缓存 |
| 规则命中 `skip` | 记录保留条目，不进入、不统计 | WinSxS、System32、Program Files、Installer |
| 规则命中 `container` | 记录容器，继续向下找可清理子项 | Windows、ProgramData、AppData、Users |

**关键剪枝：**

- `Windows`/`ProgramData` 只在规则库声明的兴趣路径下遍历（`Temp`、`SoftwareDistribution\Download`、`Logs`、`WER` 等），其余分支不进入。
- `Program Files` 直接跳过；项目类名称规则（`node_modules`、`__pycache__`）在 `Program Files`/`Windows`/`ProgramData` 内不生效，避免删掉应用自带依赖。
- 用户配置文件根、桌面/文档/图片/视频/音乐/OneDrive 等标记为 keep；`Downloads` 标记 caution，允许用户在页面上逐项确认。
- 通用大目录只保留最外层：`App`、`App/Cache`、`App/Cache/Sub` 同时超阈值时，只保留 `App`；已知缓存仍单独列出。
- reparse point（junction/symlink）不跟随、不删除；顶层链接记录为保留项，深层链接只在命中规则时记录。
- 时间上限达到时停止遍历，标记 `partial`，已发现的条目仍生成报告。

**用户目录识别：**

- 以 `name == Users` 或 `looks_like_profile()`（含 `AppData` + `NTUSER.DAT`/`Desktop`）识别用户配置文件根。
- 配置文件根的直接子目录按标准文件夹表分类；`AppData` 继续向下，`AppData\Local|Roaming|LocalLow` 的直接子目录作为候选大目录。
- 该启发式避免把 `C:\Users` 整个删掉，也避免把 UWP 包内的 `AppData` 误判为根。

### 2.4 规则 schema

```json
{
  "id": "dev-venv",
  "title": "Python 虚拟环境（.venv）",
  "category": "项目构建产物",
  "scope": "project",
  "match": {
    "type": "basename",
    "pattern": ".venv",
    "requires_inside": ["pyvenv.cfg"]
  },
  "mode": "leaf",
  "recommendation": "safe",
  "method": "permanent",
  "description": "...",
  "action": "...",
  "risk": "..."
}
```

- `match.type`：`exact` / `suffix` / `basename` / `glob` / `prefix` / `regex`。
- `requires_inside`：目录内必须存在匹配文件；`requires_sibling_any`：父目录必须有项目标记。
- `mode`：`leaf` / `skip` / `container` / `normal`。
- `recommendation`：`suggest`（确认无用的废弃文件，最高优先级）/ `safe` / `caution` / `keep`；`review`（待定）是未命中规则的兜底档，不出现在规则里。
- `language`（可选）：开发类规则的语言/生态标注（nodejs/python/rust/…/vscode/jetbrains/git/ai/tools，受控枚举），用于报告页「生态」筛选；非开发规则留空。
- `target`：`dir`（默认）/ `file`；文件规则走单独 `match_file`，避免对百万文件逐条正则。
- `selectable` 可覆盖默认；`keep` 和 `manual` 默认不可选。

### 2.5 选择与删除协议

- 选择 JSON schema 2：`scan_id`、`scan_file`、`root`、`mode`（全局默认方式）、`modes`（可选的逐条覆盖，只含与全局默认不同的路径）、`confirmed`、`paths`；schema 1（全局 `mode`，无 `modes`）旧格式仍可执行。
- `delete` 逐条检查：scan_id 一致、路径在 `scan.root` 内、在 `scan.entries` 中、`selectable: true`、`recommendation != keep`、`safety.protected_reason()` 为空、不是 reparse、父子重叠只保留父。
- 任何 `invalid` 整批拒绝（不会删一半）。
- 执行要求 `--yes` + (`confirmed` 或 `--confirm`)；含 `review` 项还要 `--allow-review`；`suggest` 与 `safe` 同等对待，无额外门槛。
- 执行按逐条方式分组：回收站条目批量走 PowerShell + `Microsoft.VisualBasic.FileIO.FileSystem`；彻底删除条目用 Python 自底向上删除，遇到只读先清只读位，链接不跟随。`--mode` 显式传入时覆盖全部逐条方式。
- 失败不回滚；报告区分 `deleted` / `moved_to_recycle_bin` / `partial` / `failed` / `skipped_*`，`cleanup.json` 每项记录实际使用的 `mode`。

### 2.6 报告设计

- 单文件 HTML，完全离线：CSS 与 JS 全部内联，不加载 CDN、字体或任何外部资源，断网打开样式完整。
- 三个视图：清理建议（suggest/safe/caution/review）、目录总览（顶层/用户数据）、全部条目；默认按建议度排序（suggest→safe→caution→keep→review），可切换按大小/名称。
- 三维筛选导航（chips，带条数与体积，可组合）：归属（5 值）/ 性质（8 值）/ 生态（17 值，仅「开发工具」归属下显示）；另有建议档筛选。
- 每行：勾选框、名称/路径、大小、文件数、逐条删除方式（回收站/彻底，默认回收站）、说明/建议操作/风险、修改时间、徽标（需管理员/部分统计/链接）。
- 列表分页渲染（每页 100 条），大列表不全量重建 DOM。
- 底部选择栏：已选数量/大小、父子重叠提示、review/permanent 提示、全局默认方式、确认框、复制按钮。
- 复制失败时弹手动复制框；不静默失败。
- 摘要大小按“最深可清理项”合计，避免父子重复；表格仍逐条列出。
- `report.html` 只嵌入最多 `--max-entries` 条；完整数据在 `scan.json`。

### 2.7 性能

实测（2026-10-27，本机）：

| 目标 | 规模 | 耗时 | 结果 |
| --- | --- | --- | --- |
| `E:\code\ai\skills` | 558 dirs / 6,160 files / 296MB | 0.5s | 32 条，完整 |
| `C:\Users\<user>\AppData\Local` | 62k dirs / 447k files / 44GB | 30s（上限 30s） | 642 条，partial |
| `C:\Users\<user>\AppData\Local` 首次未去噪 | 78k dirs / 539k files / 48GB | 45s（上限 45s） | 9,082 条，主要噪音为 reparse/嵌套通用目录 |

优化点：叶子缓存不展开、系统目录白名单剪枝、深层 reparse 不记录、通用大目录只留最外层、`match_file` 只对文件名 hint 调用。

## 3. 关键决策

| # | 决策 | 理由 |
| --- | --- | --- |
| D1 | 扫描与删除分离，两个子命令 | 扫描可随时重跑；删除必须基于确定的 scan_id，避免“边扫边删” |
| D2 | 报告页只复制选择，不直接删除 | 浏览器无法安全删除本地任意路径；删除必须由本地 CLI 二次校验 |
| D3 | 选择 JSON 带 scan_id/scan_file | 防止选择过期、跨扫描误删；也方便 Agent 落盘 |
| D4 | 独立 safety.py 再次保护 | 不信任 scan.json（可能被手工编辑/规则 bug）；纵深防御 |
| D5 | 已知缓存作为 leaf | `node_modules`/`.venv` 子文件太多，展开会让报告和扫描爆炸 |
| D6 | 系统目录按白名单剪枝 | WinSxS/System32/Program Files 全量统计既慢又误导；只进入明确可清理子项 |
| D7 | 默认回收站 | 可恢复优先；彻底删除只在用户明确选择时使用 |
| D8 | 用户数据默认 keep，Downloads 单独 caution | 桌面/文档等整目录删除风险过高；Downloads 是常见清理目标但仍是用户数据 |
| D9 | 通用大目录只留最外层 | 避免 `App`/`App/Cache`/`App/Cache/Sub` 重复刷屏；已知缓存仍逐条列出 |
| D10 | 规则库用 JSON，不用 YAML/代码 | 纯数据、可校验、无执行风险；`rules --check` 做 schema 校验 |
| D11 | 项目同名目录需标记文件 | `.venv` 需 `pyvenv.cfg`、`dist` 需 `package.json` 等，降低误判 |
| D12 | 不自动跑 DISM/cleanmgr/Storage Sense | 这些工具会改系统状态，必须由用户主动执行；本 skill 只建议 |
| D13 | 不直接删 Docker/WSL VHDX | VHDX 是虚拟机磁盘，直接删会丢数据；只提示 prune + compact |
| D14 | reparse 不跟随 | 避免重复统计、跨盘遍历、误删链接目标 |
| D15 | HTML 摘要去重、表格不去重 | 摘要要能回答“大概能清多少”；表格要保留上下文和父子关系 |
| D16 | 报告条目上限 + scan.json 全量 | 页面要能打开；审计数据不能丢 |
| D17 | 分类值 `system` | 现有 category 值集无系统维护类；本 skill 首次引入，规范 §3 同步 |
| D18 | uv 启动器用 `--no-project` | 纯标准库，无需安装项目/构建后端；避免首次运行因网络拉 hatchling 失败 |
| D21 | 建议分级扩为五档，suggest 只标「确认无用的废弃文件」 | 升级残留/旧版缓存值得与普通可再生成缓存区分；首批 12 条（系统升级残留 8 + 旧版 IE/npm 缓存 4） |
| D22 | 开发规则标注受控 language 枚举 | 「生态」筛选需要语言粒度；受控枚举（17 值）防拼写漂移，`rules --check` 兜底 |
| D23 | 逐条删除方式用 schema 2 + 平行 modes 映射 | paths 保持字符串数组，向后兼容 schema 1；modes 只含显式覆盖，payload 简洁 |
| D24 | 报告样式全部内联，不依赖 CDN | 单文件离线可用，无网络请求；避免 CDN 不可达时样式全失，报告可在断网/隔离环境直接打开 |
| D27 | 分类改为三个正交维度：归属/性质/生态 | 清理工具的心智模型是「我要清 Chrome/npm/系统」；原「大类+细类」把归属与性质混在一层（虚拟化被塞进「编程语言」、构建产物与语言并列）。受控词表由 `model.py` 唯一定义，规则与报告共用，自由文本归「未识别」 |

## 4. 数据与接口

### 4.1 scan.json

关键字段：

```json
{
  "schema": 1,
  "scan_id": "20261027-102033-1920",
  "root": "C:\\Users\\wangj\\AppData\\Local",
  "root_display": "C:\\Users\\wangj\\AppData\\Local",
  "started_at": "...",
  "finished_at": "...",
  "duration_s": 30.3,
  "volume": {"total": 0, "used": 0, "free": 0, "filesystem": "NTFS", "drive_type": "fixed"},
  "environment": {"admin": false, "drive_type_label": "本地磁盘"},
  "stats": {"dirs": 62168, "files": 446617, "bytes": 44446118725, "errors": 0, "partial": true},
  "options": {"min_size": 52428800, "listing_depth": 3, "max_entries": 1500},
  "entries": [
    {
      "path": "...", "kind": "dir", "size": 8478221889, "files": 136265,
      "rule_id": "dev-npm-cache-local", "recommendation": "safe",
      "selectable": true, "method": "permanent", "requires_admin": false,
      "description": "...", "action": "...", "risk": "..."
    }
  ],
  "notes": ["..."],
  "errors": [{"path": "...", "error": "PermissionError: ..."}]
}
```

### 4.2 selection.json

见 `references/protocol.md` §1；核心字段 `scan_id` / `scan_file` / `root` / `mode`（全局默认方式）/ `modes`（可选逐条覆盖）/ `confirmed` / `paths`。

### 4.3 cleanup.json

含 `scan_id`、`root`、`mode`（全局默认方式）、`dry_run`、`confirmed`、`volume_before/after`、`summary`（selected/deleted/partial/failed/skipped/moved_bytes/volume_freed）、`items`（path/title/category/recommendation/size/status/mode/freed/error/covered_by）、`notes`。

### 4.4 CLI 退出码

- `0`：成功（扫描完成；删除全部成功/仅 missing/covered）。
- `1`：业务失败（扫描失败、删除有 failed/partial、IO 错误）。
- `2`：用法/选择错误（目标不存在、选择 schema/scan_id/路径无效、未确认、review 未加 `--allow-review`）。

## 5. 安全与隐私

- 全部本地运行；无网络上传、无遥测、无外部 API。
- 报告包含本机路径、目录大小、修改时间；用户应自行决定是否分享。
- 不读取文件内容；只读取目录项与 stat 元数据。
- 不收集凭据；`.ssh/.gnupg/.aws/.azure/.kube/.docker` 明确保留。
- PowerShell 只传路径与临时 JSON 文件，不拼接执行用户输入的命令。
- 规则库不含可执行代码；匹配器不 `eval`。
- 删除前二次校验；系统保护清单独立于规则库。
- 报告页无任何外部资源请求，路径与统计只留在本机生成的 HTML/JSON 中。

## 6. 测试与验收

- 自动化：`python -m unittest discover -s tests`（52 条）。
- 真实扫描：本仓库（0.5s）、AppData\Local（30s 上限，62k dirs）。
- 浏览器验收：Edge headless + Playwright，验证亮/暗主题、tab、搜索、筛选、勾选、确认、复制、page→CLI 预演闭环。
- 报告离线验收：断网打开 `report.html` / `cleanup-report.html`，样式与交互完整，无外部 URL 请求。
- 人工回归：`docs/TESTS.md` W/S/D/R/E/T。

## 7. 开放问题

1. **全盘 C: 基准**：尚未在完整 C: 上跑完整扫描；预计数分钟，需要在不同机器回填耗时/条目数。
2. **UWP 包缓存**：`Packages\*\LocalCache` 的内容因应用而异，`caution` 是否足够保守需更多样本。
3. **回收站大小探测**：`Shell.Application` COM 在大回收站上可能较慢；当前失败时 size 未知，不阻塞扫描。
4. **用户配置文件启发式**：`looks_like_profile` 依赖 `AppData` + `NTUSER.DAT/Desktop`；极端自定义目录可能识别不到，需回填。
5. **Windows 10 兼容**：代码使用 3.9+ 标准库，未在 Win10 实机回归；`SystemTemp` 等新目录按可选处理。
6. **长路径**：已加 `\\?\`，但 PowerShell 回收站 API 对超长路径支持有限；需要真实样本。
7. **本地化**：规则文案为中文；英文用户可能需要 i18n，当前未做。
8. **Docker/WSL 压缩**：只给建议，不自动执行 `Optimize-VHD`/`diskpart`；是否提供可选半自动步骤待评估。

## 8. 变更记录

- 2026-11-15：0.7.0 规则库扩充（第一批：运行时保护）。新增「运行时/安装（保留）」分类 19 条 keep 规则，保护 Codex/WorkBuddy/ZCode 插件自带运行时、fnm/nvm 安装的 Node、npm 全局包、TypeScript SDK、rustup 工具链与 cargo bin，修复通用 `node_modules` 规则把运行时依赖误标 safe 的问题（含子路径 glob 兜底）；`.cargo`/`.rustup`/fnm 根目录降为 caution 容器，ZCode 插件缓存 caution 叶子。规则 226 → 250 条，单测 47 → 52 条。
- 2026-11-11：0.6.0 破坏性重构。彻底移除经验闭环与 AI 深化分析：删除 `memory/`、`scripts/memory.py`、`src/disk_cleanup/enrich.py`、`references/memory-loop.md`、`references/enrichment-protocol.md`、CLI `enrich` 子命令，以及 `Entry` 的 enriched/advice/confidence/tier_source/evidence 字段；报告移除 AI 定档/AI 参考徽章与 AI 状态筛选。两个报告模板改为全内联 CSS 的单文件离线页面，移除 Tailwind CDN 与所有外部资源请求。单测 63 → 47 条。
- 2026-10-28：0.5.x 报告与分类升级。建议分级扩为五档（新增 suggest 建议清理）；新增归属/性质/生态三个正交受控维度（`model.py` 唯一定义），报告页改为带条数与体积计数的 chips 导航；逐条删除方式与 schema 2（`modes` 可选覆盖）；分页渲染与紧凑行详情。
- 2026-10-27：0.1.0 首版。规则库 226 条；扫描/报告/选择/删除/清理报告全链路；真实仓库与 AppData 扫描、浏览器交互与 page→CLI 协议验证。
