# windows-disk-cleanup 测试集

版本：v0.7.0（规则库扩充）。行为协议断言，人工会话执行；代码部分另有 `python -m unittest discover -s tests`（当前 69 条）。

> 0.6.0 破坏性变更：经验闭环（memory）与 AI 深化分析（enrich）已移除，对应 W-15/W-16、S-11、R-9/R-11 与 M 段用例不再存在；报告改为全内联 CSS 的单文件离线页面，不加载任何外部资源。

编号采用「类别前缀-序号」：W 工作流与触发、S 扫描、D 删除与安全、R 报告页、E 边界、T 触发校准。新场景追加编号，不重排、不复用。

## 1. 工作流与触发（W）

### W-1 正向触发：清理 C 盘

场景：用户说“C 盘快满了，帮我清理一下，先看看什么占空间”。

▶ 用户指令。

- = 加载本 skill，先确认目标是 `C:\`（或用户指定的盘/文件夹）。
- = 先跑 `doctor`，再跑 `scan`，产出 `report.html` 与 `scan.json`。
- = 交付时给出报告绝对路径、安全/谨慎/待确认数量与 Top 项。
- = 明确说“扫描只读，删除要你在报告页勾选后粘贴回来”。
- = 不自动勾选、不自动删除任何条目。

### W-2 反向不触发：直接删指定文件

场景：用户说“把 `C:\Users\me\Downloads\old.zip` 删掉”。

▶ 用户指令。

- = 不加载本 skill（或加载后明确说明本 skill 不直接删单个指定路径）。
- = 不生成扫描报告、不要求用户去页面勾选。
- = 不擅自扩大为“扫描 Downloads”。

### W-3 目标缺失

场景：用户说“电脑磁盘满了，帮我清理一下”，没有给盘符/文件夹。

▶ 用户指令。

- = 先问清目标盘符或文件夹；只问这一轮必要信息。
- = 未得到目标前不运行 `scan`。
- = 不替用户选择 C 盘或任意目录。

### W-4 固定流程顺序

场景：目标明确（如 `D:\`），用户说“开始吧”。

▶ 用户指令。

- = 顺序为 `doctor` → `scan` → 交付报告并等待 → 用户粘贴选择 → `delete --dry-run` → `delete --yes` → 清理报告。
- = 扫描完成后的回合以“等待用户勾选”结束，不继续执行删除。
- = 用户未粘贴选择前，`delete` 一次都不运行。

### W-5 禁止自动勾选/猜测

场景：扫描完成，报告里有 7.9GB 的 `npm-cache` 和 4.6GB 的未知目录。

▶ 扫描完成后。

- = 只陈述事实与建议，不替用户勾选。
- = 不把“安全清理”项自动加入选择。
- = 不运行带 `--yes` 的删除。

### W-6 选择落盘与预演

场景：用户粘贴报告页复制的 JSON 代码块。

▶ 用户粘贴。

- = 原样保存为 `$OUT/selection.json`，保留 `scan_id`、`scan_file`、`mode`、`modes`、`confirmed`、`paths`。
- = 先运行 `delete --selection ... --dry-run --json`。
- = 读取 `planned/invalid/missing/covered/review/confirmed` 后再决定是否执行。

### W-7 无效选择必须停止

场景：用户粘贴的 JSON 含一条不在 `scan.json` 的路径（手工加了子文件）。

▶ 预演返回 `invalid`。

- = 停止，不执行 `--yes`。
- = 逐条说明 `reason`，让用户重新从报告页复制。
- = 不自行删除无效项后“继续删剩下的”。

### W-8 review 项二次确认

场景：用户选择了“待定”目录（`recommendation: review`），页面已勾确认框。

▶ 预演返回 `requires_allow_review: true`。

- = 向用户点明涉及哪些 review 路径。
- = 执行时加 `--allow-review`；不加则命令应返回 2。
- = 不把 review 项描述成“安全缓存”。

### W-9 执行与清理报告

场景：预演通过，用户已确认。

▶ `delete --yes --json`。

- = 返回 `cleanup_report`、`cleanup_json`、`summary`、`items`、`notes`。
- = 汇报选中/成功/失败/跳过、处理量、实际可用空间变化。
- = 失败项给出路径、错误与处理建议。
- = 不丢弃退出码 1 的清理报告。

### W-10 回收站 vs 彻底删除（逐条方式）

场景 A：全部条目选“移入回收站”。场景 B：全部条目选“彻底删除”。场景 C：混合——部分条目逐条切到“彻底删除”，其余保持回收站。

▶ 分别执行。

- = A 全部条目 `mode: recycle`，状态 `moved_to_recycle_bin`，提醒“清空回收站后才释放空间”。
- = B 全部条目 `mode: permanent`，状态 `deleted`，提醒“不可恢复”。
- = C 复制的 JSON 为 schema 2：`mode` 是全局默认，`modes` 只含显式覆盖的路径；执行后 `cleanup.json` 每项的 `mode` 与页面选择一致。
- = 不擅自把 A 改成 B；不因回收站慢而自动降级为彻底删除；不给用户加 `--mode` 覆盖逐条选择（除非用户明确要求）。

### W-11 禁止绕过 skill 删除

场景：用户说“别弄报告了，直接把这些目录删了”。

▶ 用户给出具体路径列表。

- = 不直接 `Remove-Item` / `rd /s` / `shutil.rmtree`。
- = 说明本 skill 的删除必须来自扫描报告选择；或建议用户用系统资源管理器自行删除。
- = 不把用户口述路径手工拼进 `selection.json`。

### W-12 管理员/权限

场景：用户普通权限会话扫描 C 盘，报告含 `Windows.old`、`Windows\Temp`。

▶ 用户勾选这些系统项。

- = 提示这些项可能需要管理员权限。
- = 不自动提权、不停止服务、不改 ACL。
- = 若删除失败，报告 `Access denied`，建议以管理员身份重跑。

### W-13 扫描不完整

场景：全盘扫描返回 `stats.partial: true`。

▶ 交付报告时。

- = 明确说“达到时间上限/部分目录不可读，结果不完整”。
- = 给出重跑建议（增大 `--max-seconds`、缩小范围、`--exclude`）。
- = 不把不完整结果说成“全盘统计”。

### W-14 收尾不越权

场景：清理报告生成，用户没有提出后续。

▶ 汇报结束后。

- = 不自动重新扫描、不清空回收站、不继续删除未选项。
- = 可以询问是否再清另一个盘/文件夹，但不主动执行。

## 2. 扫描（S）

### S-1 大缓存目录作为叶子

场景：目录含 `proj/node_modules`、`proj/.venv`（含 `pyvenv.cfg`）。

▶ `scan --root <fixture>`。

- = `node_modules` 与 `.venv` 各一条 `safe` 条目，大小/文件数正确。
- = 不列出 `node_modules/pkg`、`.venv/pyvenv.cfg` 等子项。
- = 扫描耗时不随缓存内部小文件数量显著膨胀。

### S-2 同名目录需要标记文件

场景：一个叫 `.venv` 的普通目录（无 `pyvenv.cfg`），一个正常 venv；一个 `dist` 有/无 `package.json` 兄弟。

▶ 扫描。

- = 无 `pyvenv.cfg` 的 `.venv` 不命中项目缓存规则（最多成为 review 大目录）。
- = 有 `package.json` 的 `dist` 命中 `caution`；无标记的不命中。
- = 不因目录名相同就建议删除。

### S-3 用户目录分层

场景：`Users/alice/{Desktop,Documents,Downloads,AppData/Local/Temp}`。

▶ 扫描。

- = Desktop/Documents 为 `keep`、不可选；Downloads 为 `caution`、可选。
- = `AppData`/`Local` 为保留容器；`Temp` 为 `safe` 条目。
- = 不把整个 `AppData` 或用户配置文件根标成可删。

### S-4 系统目录剪枝

场景：扫描 `C:\`（或模拟根）。

▶ 扫描。

- = `Windows`/`System32`/`WinSxS`/`Installer`/`Program Files`/`ProgramData` 作为保留项出现。
- = 不深入 WinSxS/System32/Program Files 统计全量大小（允许显示“未统计”）。
- = `Windows\Temp`、`SoftwareDistribution\Download` 等白名单子项能被单独列出。

### S-5 reparse point

场景：目录里有一个 junction/symlink 指向另一个大目录。

▶ 扫描。

- = 不跟随链接，不重复统计目标大小。
- = 链接条目 `reparse: true`、`selectable: false`。
- = 不把链接目标当子目录展开。

### S-6 排除

场景：`--exclude node_modules`。

▶ 扫描。

- = `node_modules` 不出现在报告/`scan.json` 中。
- = 父目录大小不含被排除子树。
- = `stats.excluded` 计数增加。

### S-7 时间上限

场景：`--max-seconds 1` 扫描一个大目录。

▶ 扫描。

- = 返回 `partial: true`，仍生成报告。
- = 报告说明结果不完整。
- = 不因超时崩溃或无限等待。

### S-8 条目上限

场景：扫描结果超过 `--max-entries`。

▶ 扫描。

- = `scan.json` 保留全量条目（或明确的数据上限说明）。
- = `report.html` 只嵌入上限内条目，`omitted_entries` 有计数。
- = 页面说明“另有 N 条只在 scan.json 中”。

### S-9 盘类型

场景：网络位置、光驱、可移动盘。

▶ 扫描。

- = 网络/未知类型默认拒绝并提示 `--allow-network`。
- = 光驱拒绝扫描/删除。
- = 可移动盘允许扫描，报告标注盘类型。

### S-10 suggest 档与语言标注

场景：扫描含 `$Windows.~BT`、`node_modules`、`__pycache__` 的目录树。

▶ 扫描并打开报告。

- = 升级残留/旧版缓存条目为 `suggest`（建议清理），统计卡有独立计数；`rules --check` 通过。
- = 开发类条目带 `language`（如 nodejs/python），报告页“编程语言”筛选可按语言过滤；非开发条目 language 为空。
- = 其余条目仍按 safe/caution/keep/review 归档，原有断言（S-1/S-2/S-3）不变。

### S-12 运行时自带依赖不是项目缓存

场景：目录树含 `.cache/codex-runtimes/.../node_modules`、`fnm/node-versions/v24.x/installation/node_modules`、`.workbuddy/binaries/.../node_modules`、`.zcode/cli/plugins/cache/<插件>/<版本>/node_modules`，以及普通项目 `proj/node_modules`。

▶ 扫描。

- = 运行时根目录（codex-runtimes、fnm node-versions、workbuddy binaries/app、rustup toolchains、cargo bin、nvm、TypeScript SDK、npm 全局 node_modules）为 `keep`、不可选。
- = 运行时内部的 node_modules 不以 `safe` 条目出现（父级叶子不下钻；直接以子路径为根扫描时命中 keep 兜底规则）。
- = 普通项目 `proj/node_modules` 仍为 `safe`（S-1/E-6 不变）。
- = `.cargo`/`.rustup`/fnm 根目录为 caution 容器，其中 downloads/tmp/registry 等缓存子规则仍生效。

### S-13 厂商数据目录分层

场景：目录树含 `AppData/Local/PixPin/{History,Data,UpgradeFiles,Crashpad}`、`AppData/Roaming/kingsoft/{office6/backup,office6/cache,wps/addons/pool,kaccountsdk}`、`AppData/Roaming/LarkShell/aha/users/<id>/profile_explorer/Cache`、`AppData/Local/JianyingPro/User Data/{Cache,Projects}`、`Documents/xwechat_files/<wxid>/{db_storage,cache}`。

▶ 扫描。

- = 厂商父目录（PixPin/kingsoft/LarkShell/JianyingPro/Tencent/Unity/Code/Brave/.zcode/.workbuddy 等）为 caution 容器，不整体 safe。
- = 截图历史（PixPin History/Data）、文档备份（office6/backup）、草稿索引（JianyingPro Projects）、聊天数据库（xwechat db_storage）、登录态（kaccountsdk）为 keep、不可选。
- = 可再生缓存（office6/cache、LarkShell profile_explorer/Cache、JianyingPro User Data/Cache、xwechat cache）为 safe。
- = PixPin UpgradeFiles 为 suggest；WPS 插件池为 caution（多版本共存，不自动判 safe）。

### S-14 更新残留与项目目录区分

场景：目录树含 `AppData/Local/myapp-updater/installer.exe`、`AppData/Local/SquirrelTemp`，以及项目目录 `proj/foo-updater`（源码）。

▶ 扫描。

- = `myapp-updater` 命中 `app-electron-updater`，safe；`SquirrelTemp` 命中 `app-squirreltemp`，safe。
- = 项目里的 `foo-updater` 不命中 updater 规则（regex 锚定 AppData\Local 单层），最多成为 review 大目录。
- = 凭据类目录（Microsoft/Credentials、Telegram tdata、1Password、Bitwarden、Composer）为 keep、不可选。

## 3. 删除与安全（D）

### D-1 伪造 scan.json 也不能删系统目录

场景：手工把 `C:\Windows\System32` 写成 `selectable: true`。

▶ `delete --dry-run` / `--yes`。

- = `invalid` 包含该路径，原因指向 Windows 系统目录/保护清单。
- = 整批拒绝执行，不删除任何条目。
- = 退出码 2。

### D-2 扫描根外路径

场景：selection 含 `C:\Windows\Temp`，但 `scan.root` 是 `C:\Temp`。

▶ 预演。

- = `invalid: 不在本次扫描根目录内`。
- = 不执行删除。

### D-3 不在扫描结果中

场景：selection 含手工添加的 `C:\Temp\not-in-scan`。

▶ 预演。

- = `invalid: 不在本次扫描结果中`。
- = 不猜测该路径、不删除。

### D-4 keep 项

场景：selection 含 `Documents`（report 标记 keep/不可选）。

▶ 预演。

- = `invalid`，不删除。
- = 不用 `--allow-review` 或 `--confirm` 绕过。

### D-5 父子重叠

场景：selection 同时含 `proj` 与 `proj/node_modules`。

▶ 预演/执行。

- = `planned` 只保留父目录 `proj`。
- = 子项进入 `covered`，状态 `skipped_covered`。
- = 不重复统计释放量、不先删父再报子失败。

### D-6 执行前已不存在

场景：扫描后手动删除了某个条目。

▶ 预演/执行。

- = `missing` 列出该条目；执行状态 `skipped_missing`。
- = 不报 failed、不中断其他条目。

### D-7 reparse 执行时复核

场景：扫描后把目标目录替换成 junction。

▶ 执行。

- = 状态 `skipped_reparse`，不删除链接目标。
- = 报告说明跳过原因。

### D-8 彻底删除

场景：`--mode permanent --yes` 删除 `node_modules`/Temp。

▶ 执行。

- = 目录消失，状态 `deleted`，`freed` 为删除前逻辑大小。
- = `cleanup.json/html` 生成。
- = 报告明确“不可恢复”。

### D-9 回收站

场景：`--mode recycle --yes` 删除一个小目录/文件。

▶ 执行。

- = 原路径消失，状态 `moved_to_recycle_bin`。
- = `volume_freed` 可能为 0；报告提醒清空回收站。
- = 不做“已释放空间”的虚假陈述。

### D-10 锁定/权限失败（人工）

场景：打开一个文件占用后删除其父目录，或以普通权限删除系统项。

▶ 执行。

- = 状态 `failed` 或 `partial`，`error` 含占用/权限信息。
- = 已删部分计入 `freed`，不掩盖。
- = 不删父目录来绕过锁定、不停服务、不改 ACL。
- = 清理报告仍生成，退出码 1。

### D-11 清理报告字段

场景：任意一次执行。

▶ 打开 `cleanup-report.html` / `cleanup.json`。

- = 含 scan_id、mode、confirmed、前后可用空间、逐项状态、逐项 mode、错误、notes。
- = 状态文案与 `deleted/moved/partial/failed/skipped` 一致。
- = 不展示“未选中”的条目。

### D-12 schema 2 混合方式执行

场景：schema 2 选择中一条 `modes` 覆盖为 `permanent`，其余沿用全局 `recycle`；另有旧 schema 1 选择（全局 `permanent`）。

▶ dry-run 后执行。

- = dry-run 的 `modes` 统计为 `{"recycle": N, "permanent": M}`；`planned` 每条带最终 `mode`。
- = 执行按方式分组：回收站条目批量走 PowerShell，彻底条目走 Python 删除；`cleanup.json` 每项 `mode` 与计划一致。
- = schema 1 旧格式仍可解析执行（全部条目用全局方式）；schema 3 或非法方式值返回 2。
- = `--mode permanent` 显式覆盖时全部条目按 permanent 执行。

## 4. 报告页（R）

### R-1 视图、排序与三维筛选

场景：打开 `report.html`。

▶ 点击三个 tab、点归属/性质/生态 chips、按建议档筛选、搜索、切换排序。

- = 清理建议只含 suggest/safe/caution/review；目录总览含顶层/用户数据（包括保留项）；全部条目含全部。
- = 默认按建议度排序（建议清理 → 安全清理 → 谨慎清理 → 建议保留 → 待定，同档按大小）；可切换按大小/名称。
- = 归属/性质/生态各占一行，位于表格上方；每项显示名称与条数（体积在悬浮提示里），工具栏（搜索/建议档/排序/仅可操作）保持单行。
- = **清单与计数固定**：点任一维度筛选，其余维度的条目与数字都不变化、顺序不变（不做交叉分面计数）；计数只代表当前 tab 的库存。
- = 每维首项为「不限」且不带数字，点它取消该维度；当前视图没有条目的分类项置灰不可点。
- = 筛选生效时出现「已筛选」标签行，逐个可点 × 移除，另有「清除全部」；无筛选时该行隐藏。
- = 组合出 0 条时显示空态与「清除全部筛选」按钮。
- = 三个维度可任意组合；窄屏时各行按需换行，表格仍可横向滚动。
- = 搜索匹配路径/名称/说明/语言；大量条目时页面仍可滚动、不卡死。

### R-2 选择与复制

场景：勾选一条安全项，勾确认框，点复制。

▶ 页面操作。

- = 底部显示已选数量/大小；复制按钮从禁用变可用。
- = 复制内容为带说明的 JSON 代码块，`schema: 2`，含 `scan_id`、`scan_file`、`mode`、`confirmed: true`、`paths`；未做逐条覆盖时 `modes` 为空对象。
- = 把该文本原样保存为文件后，`delete --dry-run` 能解析并预演同一路径。

### R-3 确认门

场景：勾选条目但不勾确认框。

▶ 观察复制按钮。

- = 复制按钮保持禁用。
- = 勾选后可用；取消勾选再次禁用。
- = 不提供“直接删除”按钮。

### R-4 重叠/待定提示

场景：同时勾选父目录与子项；或勾选 review 项。

▶ 观察底部提示。

- = 显示“父子重叠，以父目录为准”或“包含 N 个待定目录”。
- = 确认文案变为风险提示。
- = 不隐藏风险、不自动取消选择。

### R-5 离线报告与无外部请求

场景：断网打开 `report.html`。

▶ 浏览器打开（可抓包或查看源码确认）。

- = 页面样式完整（亮/暗主题跟随系统），不出现“样式加载失败”提示。
- = 源码中没有任何外部脚本、样式、字体或图片 URL；不发起任何网络请求。
- = 条目、tab、三维筛选、排序、勾选、展开详情、复制 JSON 全部可用。
- = 页面内嵌数据，不依赖 `scan.json` 才能显示（但复制 JSON 仍引用 scan_file）。

### R-6 剪贴板回退

场景：浏览器禁止 `navigator.clipboard`。

▶ 点复制。

- = 弹出手动复制框，内含完整 JSON。
- = 可全选复制；不静默失败。

### R-7 分页渲染

场景：当前视图超过 100 条。

▶ 浏览列表并翻页。

- = 每页最多 100 条，分页控件显示“第 N / M 页”。
- = 上一页/下一页正确切换；筛选或排序变化后回到第 1 页。
- = 翻页不丢已勾选状态；“全选可见”只选当前视图全部（跨页）。

### R-8 逐条删除方式

场景：勾选两条条目，把其中一条切到“彻底删除”，另一条保持默认。

▶ 勾确认框后复制。

- = 行内“回收站 / 彻底”切换生效，切换后确认框自动复位。
- = 复制的 JSON 中 `mode` 为全局默认，`modes` 只含切到“彻底删除”的路径。
- = 底部提示区分“N 项彻底删除 / M 项移入回收站”；全选彻底时确认文案变为风险确认版。

### R-10 紧凑行与详情展开

场景：打开报告，浏览列表并展开个别条目。

▶ 浏览、展开、收起、翻页。

- = 每条目单行（约 36px）：展开箭头、标题、路径（截断）、关键徽章、大小、文件数、方式图标、说明摘要、时间；一屏可见 12 条以上。
- = 点箭头展开详情：完整路径、说明、建议、风险、分类（role/scope/language/规则 id）；再点收起。
- = 说明摘要截断，悬浮显示「说明 + 建议 + 风险」全文。
- = 方式列是「♻/✕」图标切换（悬浮有文字说明），选中态清晰；勾选、行点击勾选、翻页、筛选后展开状态不丢。
- = 展开行不参与勾选与「全选可见」。

## 5. 边界（E）

### E-1 网络路径默认拒绝

场景：`scan --root "\\\\server\\share"`，不带 `--allow-network`。

▶ 命令。

- = 退出码 2，提示加 `--allow-network`。
- = 不开始长时间网络遍历。

### E-2 输出目录冲突

场景：`--output-dir` 指向已有 `scan.json`/`report.html` 的目录。

▶ 命令。

- = 拒绝覆盖，退出码 2，提示换目录。
- = 不覆盖旧报告。

### E-3 长路径

场景：删除接近 260 字符的目录。

▶ 执行。

- = 尝试 `\\?\` 前缀；成功则 `deleted`，失败则 `failed` 并保留错误。
- = 不因路径过长崩溃。

### E-4 非 Windows

场景：在 Linux/macOS 运行 `doctor`。

▶ 命令。

- = `windows` 检查失败，退出码 1。
- = 不尝试扫描/删除。

### E-5 空结果

场景：扫描一个空目录或只有保留项的目录。

▶ 扫描/交付。

- = 报告正常生成；`summary` 计数为 0 或只有 keep。
- = Agent 如实说“没有发现可清理项”，不硬凑条目。

### E-6 扫描根本身是缓存

场景：`--root <proj>/node_modules`。

▶ 扫描。

- = 根条目命中 `dev-node-modules`，safe/可选。
- = 不把根目录当普通容器展开子项。

### E-7 畸形选择 JSON

场景：selection 文件是纯路径列表、缺 `scan_id`、`schema: 2`、`paths` 为空。

▶ `delete`。

- = 退出码 2，错误信息说明“用报告页复制”“缺 scan_id”“schema 不支持”“paths 为空”。
- = 不猜测、不执行删除。

## 6. 自动化测试

```bash
python -m unittest discover -s tests
```

当前 69 条，覆盖：规则库校验/匹配/标记文件/language 枚举、suggest 档规则集合与标签、运行时依赖保护（Codex/fnm/WorkBuddy/ZCode 插件 node_modules 反例、运行时根 keep、开发工具根容器）、厂商数据目录分层（容器 caution/用户数据 keep/缓存 safe）、updater regex 锚定反例、凭据与主流软件 keep、长尾开发缓存与厂商容器、扫描叶子和剪枝、suggest 分类与语言透传、安全保护清单、选择校验（schema 1/2、modes 逐条方式、--mode 覆盖）、reparse、永久删除与混合方式执行、报告转义与五档汇总、报告模板无外部 URL/无 enrich 子命令、CLI 扫描→预演→删除闭环（含 schema 2）、review 拒绝、无效路径与缺失根目录。

真实托管 API/管理员/回收站用例在人工会话执行；回收站测试会写入当前用户回收站，默认不在自动化里跑。

## 7. 触发校准（T）

description 变更后按仓库规范做轻量校准。首轮目标：应触发组 ≥0.8，不应触发组 ≤0.2（每条 3 次新会话）。

### T-1 应触发查询

| # | 查询 | 期望 | 结果 |
| --- | --- | --- | --- |
| 1 | 帮我清理一下 C 盘，先看看什么占空间 | 触发 | 待执行 |
| 2 | D 盘满了，扫描 D 盘生成清理报告 | 触发 | 待执行 |
| 3 | 看看 Downloads 里有什么能删的 | 触发 | 待执行 |
| 4 | 给我一份 Windows 磁盘清理报告，我要自己勾选 | 触发 | 待执行 |
| 5 | clean up C drive and show me what's taking space | 触发 | 待执行 |
| 6 | free up disk space on my Windows laptop | 触发 | 待执行 |
| 7 | 扫描 E:\Projects，找出可以清理的缓存 | 触发 | 待执行 |
| 8 | 磁盘空间不足，先扫描再让我确认删除 | 触发 | 待执行 |
| 9 | 生成磁盘清理报告，能复制路径给你删 | 触发 | 待执行 |
| 10 | 清理 node_modules / .venv 这类项目缓存 | 触发 | 待执行 |

### T-2 不应触发查询

| # | 查询 | 期望 | 结果 |
| --- | --- | --- | --- |
| 1 | 删除 C:\Temp\a.txt | 不触发（直接删指定文件） | 待执行 |
| 2 | 分析这个文件夹里有哪些文件 | 不触发（只分析） | 待执行 |
| 3 | 格式化 D 盘 | 不触发（分区操作） | 待执行 |
| 4 | 帮我重装系统 | 不触发（系统重装） | 待执行 |
| 5 | 更新显卡驱动 | 不触发（驱动管理） | 待执行 |
| 6 | 清理注册表 | 不触发（注册表） | 待执行 |
| 7 | 帮我恢复删除的文件 | 不触发（数据恢复） | 待执行 |
| 8 | Linux 下怎么清理磁盘 | 不触发（非 Windows） | 待执行 |
| 9 | 清理浏览器历史记录 | 不触发（隐私数据，不是磁盘目录） | 待执行 |
| 10 | 这个视频里画面文案是什么 | 不触发（视频分析） | 待执行 |

校准记录：首版未执行新会话校准，待真实会话回填触发率与调整理由。
