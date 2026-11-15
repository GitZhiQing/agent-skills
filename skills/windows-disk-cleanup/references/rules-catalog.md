# Windows 目录规则库

版本：v1　更新：2026-11-15　规则数：561

本文件是 [`assets/rules.json`](../assets/rules.json) 的可读目录；**JSON 是权威数据**，本表用于人工审阅与解释。修改规则后运行 `windows-disk-cleanup rules --check`，并同步本表。

## 目录

- [1. 这份规则库解决什么问题](#1-这份规则库解决什么问题)
- [2. 安全等级](#2-安全等级)
- [3. 扫描模式与判定](#3-扫描模式与判定)
- [4. 规则明细](#4-规则明细)
  - [系统升级残留（7）](#系统升级残留7)
  - [Windows 更新（6）](#windows-更新6)
  - [系统临时文件（3）](#系统临时文件3)
  - [系统日志与转储（13）](#系统日志与转储13)
  - [系统性能缓存（2）](#系统性能缓存2)
  - [系统组件（保留）（26）](#系统组件保留26)
  - [系统托管（6）](#系统托管6)
  - [回收站（1）](#回收站1)
  - [用户数据（43）](#用户数据43)
  - [用户临时文件（4）](#用户临时文件4)
  - [浏览器缓存（32）](#浏览器缓存32)
  - [应用缓存（167）](#应用缓存167)
  - [开发工具缓存（91）](#开发工具缓存91)
  - [包管理器缓存（29）](#包管理器缓存29)
  - [AI/模型缓存（3）](#ai模型缓存3)
  - [项目构建产物（44）](#项目构建产物44)
  - [项目配置（保留）（4）](#项目配置保留4)
  - [凭据/配置（保留）（18）](#凭据配置保留18)
  - [游戏平台（30）](#游戏平台30)
  - [虚拟机/容器（3）](#虚拟机容器3)
  - [运行时/安装（保留）（29）](#运行时安装保留29)
- [5. 维护与校验](#5-维护与校验)
- [6. 来源与核对日期](#6-来源与核对日期)
- [7. 已知限制](#7-已知限制)

## 1. 这份规则库解决什么问题

扫描报告对每个目录要回答三个问题：**这是什么、为什么占空间、能不能删**。规则库把答案固化为数据，避免每次让模型即兴判断。规则覆盖：

- **系统盘**：升级残留、Windows 更新缓存、系统临时文件、日志/转储、组件存储（WinSxS）、Installer、驱动存储、系统还原、回收站、页面/休眠文件。
- **用户目录**：Desktop/Documents/Downloads 等用户数据、AppData 下的临时文件/浏览器/应用缓存、OneDrive、UWP 缓存。
- **开发目录**：`node_modules`、`.venv`、`__pycache__`、`.next`、`dist/build/target`、包管理器缓存（npm/pnpm/yarn/pip/uv/cargo/go/nuget/gradle/maven/conda）、模型缓存。
- **其他盘**：顶层数据目录、`System Volume Information`、`$Recycle.Bin`、chkdsk 恢复目录、厂商驱动目录。

规则只描述“建议”，不执行删除。删除必须经过报告页勾选 + `delete` 子命令的二次校验（见 [扫描与删除协议](protocol.md)）。

## 2. 建议等级与语言标注

| 等级 | 报告文案 | 含义 | 默认是否可勾选 |
| --- | --- | --- | --- |
| `suggest` | 建议清理 | 确认无用的废弃文件（升级残留、旧版遗留缓存）；建议优先清理 | 是 |
| `safe` | 安全清理 | 缓存、临时文件、可再生成的构建产物；应用会重建或重新下载 | 是 |
| `caution` | 谨慎清理 | 可能包含用户数据、登录状态、离线内容，或需要重新配置 | 是（页面要求确认） |
| `review` | 待定 | 未命中内置规则的数据目录；必须由用户判断用途 | 是（执行需 `--allow-review`） |
| `keep` | 建议保留 | 系统组件、程序安装目录、凭据、不可恢复的数据 | 否（CLI 也会拒删） |

开发类规则另带 `language` 标注（nodejs/python/rust/go/java/dotnet/php/ruby/swift/cpp/dart/docker/vscode/jetbrains/git/ai/tools，受控枚举），供报告页「编程语言」筛选；`rules --check` 校验非法值。

## 3. 扫描模式与判定

| 模式 | 行为 | 典型对象 |
| --- | --- | --- |
| `leaf` | 只统计大小/文件数，**不深入列出子项** | `node_modules`、`.venv`、Temp、浏览器缓存 |
| `skip` | 记录条目但不进入，大小显示“未统计” | WinSxS、System32、Program Files、Installer |
| `container` | 记录容器并继续向下找可清理子项 | `Windows`、`ProgramData`、`AppData`、`Users` |
| `basename` + `requires_*` | 名称匹配后再检查标记文件，避免误判同名目录 | `.venv` 需 `pyvenv.cfg`；`dist` 需 `package.json` 等 |

判定顺序：精确路径 > 路径后缀 > glob/正则 > 名称规则；同一路径命中多条时取优先级更高、模式更长的规则。项目类名称规则不会在 `Program Files` / `Windows` / `ProgramData` 内生效，避免把应用自带依赖当项目缓存。

## 4. 规则明细

### 1. 系统升级残留（7）

| ID | 匹配 | 模式 | 建议 | 说明 | 建议操作 |
| --- | --- | --- | --- | --- | --- |
| `sys-esd` | `suffix` `\ESD` | leaf · 需管理员 | 建议清理 | Windows 升级/安装器下载的 ESD 镜像缓存。 | 确认没有正在进行的升级后可删。 |
| `sys-inplace-tr` | `suffix` `\$INPLACE.~TR` | leaf · 需管理员 | 建议清理 | 就地升级（in-place upgrade）留下的临时文件。 | 升级完成后可删。 |
| `sys-sysreset` | `suffix` `\$SysReset` | leaf · 需管理员 | 建议清理 | 系统重置/恢复过程留下的日志与回滚数据。 | 重置完成后可删。 |
| `sys-windows-bt` | `suffix` `\$Windows.~BT` | leaf · 需管理员 | 建议清理 | 功能更新下载/安装过程中产生的临时安装文件。 | 升级完成后可删；优先用磁盘清理的「临时 Windows 安装文件」。 |
| `sys-windows-old` | `suffix` `\Windows.old` | leaf · 需管理员 | 建议清理 | 系统升级后保留的上一版 Windows，通常 10–25 GB，用于回滚。 | 建议用「磁盘清理 → 清理系统文件 → 以前的 Windows 安装」删除；删除后无法回滚系统版本。 |
| `sys-windows-q` | `suffix` `\$Windows.~Q` | leaf · 需管理员 | 建议清理 | Windows 升级过程中的临时工作目录。 | 升级完成后可删。 |
| `sys-windows-ws` | `suffix` `\$Windows.~WS` | leaf · 需管理员 | 建议清理 | Windows 升级安装器留下的临时下载目录。 | 升级完成后可删。 |

### 2. Windows 更新（6）

| ID | 匹配 | 模式 | 建议 | 说明 | 建议操作 |
| --- | --- | --- | --- | --- | --- |
| `programdata-bits` | `suffix` `\ProgramData\Microsoft\Network\Downloader` | leaf · 需管理员 | 谨慎清理 | 后台智能传输服务（BITS）的下载队列与缓存。 | 确认没有正在进行的更新/下载后清理。 |
| `win-do-cache` | `suffix` `\Windows\DeliveryOptimization\Cache` | leaf · 需管理员 | 安全清理 | Windows 更新/商店下载的 P2P 分发缓存。 | 优先用磁盘清理的「Delivery Optimization Files」或 Delete-DeliveryOptimizationCache；更新进行中不要删。 |
| `win-update-datastore` | `suffix` `\Windows\SoftwareDistribution\DataStore` | leaf · 需管理员 | 保留 | Windows Update 的更新历史与配置数据库。 | 保留；只有重置 Windows Update 时才按官方步骤重命名/重建。 |
| `win-update-download` | `suffix` `\Windows\SoftwareDistribution\Download` | leaf · 需管理员 | 建议清理 | Windows Update 下载的更新包缓存，更新完成后通常不再需要。 | 建议先停止 wuauserv/bits 再清理，或用磁盘清理；服务运行中部分文件会被占用。 |
| `win-update-root` | `suffix` `\Windows\SoftwareDistribution` | container · 需管理员 | 保留 | Windows Update 服务的工作目录，包含下载缓存、历史数据库与状态。 | 不要整体删除；只清理其中的 Download 子目录。 |
| `win-winreagent` | `suffix` `\$WinREAgent` | skip · 需管理员 | 谨慎清理 | Windows 恢复环境（WinRE）更新期间生成的临时目录。 | 更新完成后建议用磁盘清理处理；不要手动删除更新进行中的目录。 |

### 3. 系统临时文件（3）

| ID | 匹配 | 模式 | 建议 | 说明 | 建议操作 |
| --- | --- | --- | --- | --- | --- |
| `programdata-retaildemo` | `suffix` `\ProgramData\Microsoft\Windows\RetailDemo` | leaf · 需管理员 | 安全清理 | 零售演示模式使用的示例内容。 | 普通用户可删。 |
| `win-systemtemp` | `suffix` `\Windows\SystemTemp` | leaf · 需管理员 | 安全清理 | Windows 11 引入的系统级临时目录，供服务和安装程序使用。 | 关闭正在安装的程序后清理。 |
| `win-temp` | `suffix` `\Windows\Temp` | leaf · 需管理员 | 安全清理 | 系统与安装程序共用的临时目录。 | 关闭正在安装的程序后清理；被占用的文件会自动跳过。 |

### 4. 系统日志与转储（13）

| ID | 匹配 | 模式 | 建议 | 说明 | 建议操作 |
| --- | --- | --- | --- | --- | --- |
| `file-memorydmp` | `suffix` `\MEMORY.DMP` | leaf · 文件 · 需管理员 | 谨慎清理 | 蓝屏后生成的完整内存转储，单文件可能很大。 | 不排查蓝屏问题时可删。 |
| `perflogs` | `suffix` `\PerfLogs` | leaf · 需管理员 | 安全清理 | Windows 性能监视器/数据收集器留下的日志，通常为空或很小。 | 可以清理；正在做性能采集时保留。 |
| `programdata-wer` | `suffix` `\ProgramData\Microsoft\Windows\WER` | leaf · 需管理员 | 安全清理 | Windows 错误报告（WER）的队列与存档。 | 可清理；正在排查崩溃时保留。 |
| `user-crashdumps` | `suffix` `\AppData\Local\CrashDumps` | leaf | 安全清理 | 应用程序崩溃时生成的转储文件。 | 不排查崩溃问题时可删。 |
| `user-wer` | `suffix` `\AppData\Local\Microsoft\Windows\WER` | leaf | 安全清理 | 当前用户的 Windows 错误报告队列与存档。 | 可清理。 |
| `win-livekernel` | `suffix` `\Windows\LiveKernelReports` | leaf · 需管理员 | 安全清理 | Windows 记录的内核/驱动异常转储。 | 不排查蓝屏/驱动问题时可以删除。 |
| `win-logs` | `suffix` `\Windows\Logs` | leaf · 需管理员 | 谨慎清理 | Windows 各组件的日志汇总目录。 | 只清理确认无用的旧日志；排障期间保留。 |
| `win-logs-cbs` | `suffix` `\Windows\Logs\CBS` | leaf · 需管理员 | 谨慎清理 | Windows 组件服务（CBS）日志，长期积累可能很大。 | 可清理旧日志；排查系统更新/组件问题时保留。 |
| `win-logs-wu` | `suffix` `\Windows\Logs\WindowsUpdate` | leaf · 需管理员 | 谨慎清理 | Windows Update 客户端日志。 | 可清理；更新故障排查时保留。 |
| `win-memorydmp` | `suffix` `\Windows\MEMORY.DMP` | leaf · 文件 · 需管理员 | 谨慎清理 | 完整内存转储，单文件通常数百 MB 到数 GB。 | 不排查蓝屏问题时可删；正在排查则先保留。 |
| `win-minidump` | `suffix` `\Windows\Minidump` | leaf · 需管理员 | 安全清理 | 蓝屏时生成的小型内存转储，用于分析崩溃原因。 | 不排查蓝屏问题时可删。 |
| `win-panther` | `suffix` `\Windows\Panther` | leaf · 需管理员 | 谨慎清理 | Windows 安装/升级过程日志。 | 安装完成后可清理；排查升级失败时保留。 |
| `win-system32-logfiles` | `suffix` `\Windows\System32\LogFiles` | leaf · 需管理员 | 谨慎清理 | 部分系统组件（如网络、打印）写入的日志。 | 确认没有排障需求后再清理。 |

### 5. 系统性能缓存（2）

| ID | 匹配 | 模式 | 建议 | 说明 | 建议操作 |
| --- | --- | --- | --- | --- | --- |
| `sys-fontcache` | `suffix` `\Windows\ServiceProfiles\LocalService\AppData\Local\FontCache` | leaf · 需管理员 | 安全清理 | 系统字体缓存，Windows 会按需重建。 | 停止 FontCache 服务后清理更彻底；也可以直接删除缓存文件。 |
| `win-prefetch` | `suffix` `\Windows\Prefetch` | leaf · 需管理员 | 保留 | 记录程序启动轨迹以加速冷启动，Windows 会自行维护。 | 保留；Microsoft 的说明是无需清理，删除后启动会暂时变慢。 |

### 6. 系统组件（保留）（26）

| ID | 匹配 | 模式 | 建议 | 说明 | 建议操作 |
| --- | --- | --- | --- | --- | --- |
| `local-programs` | `suffix` `\AppData\Local\Programs` | skip | 保留 | 只对当前用户安装的程序（VS Code、Cursor 等）。 | 保留；卸载程序请用设置/卸载器。 |
| `programdata-defender` | `suffix` `\ProgramData\Microsoft\Windows Defender` | skip · 需管理员 | 保留 | Defender 的定义、扫描历史与隔离区。 | 保留；用 Windows 安全中心管理。 |
| `programdata-package-cache` | `suffix` `\ProgramData\Package Cache` | skip · 需管理员 | 保留 | Visual Studio / 安装器保存的安装包缓存，用于修复与卸载。 | 保留；用 Visual Studio Installer 或对应卸载器清理。 |
| `programdata-search` | `suffix` `\ProgramData\Microsoft\Search` | skip · 需管理员 | 保留 | Windows Search 的索引数据库。 | 保留；需要重建时用「索引选项 → 高级 → 重建」。 |
| `sys-boot-dir` | `exact` `%SystemDrive%\Boot` | skip · 需管理员 | 保留 | 启动配置与启动管理器文件。 | 禁止删除。 |
| `sys-program-files` | `exact` `%SystemDrive%\Program Files` | container · 需管理员 | 保留 | 64 位程序的默认安装目录。 | 不要整体删除；卸载程序请用设置/卸载器。 |
| `sys-program-files-env` | `exact` `%ProgramFiles%` | container · 需管理员 | 保留 | 系统登记的 64 位程序安装目录（可能不在系统盘）。 | 不要整体删除。 |
| `sys-program-files-x86` | `exact` `%SystemDrive%\Program Files (x86)` | container · 需管理员 | 保留 | 32 位程序的默认安装目录。 | 不要整体删除；卸载程序请用设置/卸载器。 |
| `sys-programdata` | `exact` `%SystemDrive%\ProgramData` | container · 需管理员 | 保留 | 所有用户共享的应用数据、配置与缓存。 | 不要整体删除；只清理其中明确标记的缓存子目录。 |
| `sys-programdata-env` | `exact` `%ProgramData%` | container · 需管理员 | 保留 | 系统登记的共享应用数据目录。 | 不要整体删除。 |
| `sys-recovery` | `exact` `%SystemDrive%\Recovery` | skip · 需管理员 | 保留 | Windows 恢复环境（WinRE）与恢复脚本。 | 保留。 |
| `win-assembly` | `suffix` `\Windows\assembly` | skip · 需管理员 | 保留 | 旧版 .NET 全局程序集缓存（GAC）。 | 保留。 |
| `win-boot` | `suffix` `\Windows\Boot` | skip · 需管理员 | 保留 | 启动管理器与启动相关资源。 | 禁止删除。 |
| `win-catroot2` | `suffix` `\Windows\System32\catroot2` | skip · 需管理员 | 保留 | Windows 更新使用的目录签名数据库。 | 保留；只有按官方步骤重置更新组件时才重建。 |
| `win-config` | `suffix` `\Windows\System32\config` | skip · 需管理员 | 保留 | Windows 注册表文件与事务日志。 | 禁止删除或移动。 |
| `win-csc` | `suffix` `\Windows\CSC` | skip · 需管理员 | 保留 | 脱机文件/同步中心的本地缓存。 | 保留；用同步中心管理脱机文件。 |
| `win-dotnet` | `suffix` `\Windows\Microsoft.NET` | skip · 需管理员 | 保留 | .NET Framework 运行时与配置。 | 保留。 |
| `win-driverstore` | `suffix` `\Windows\System32\DriverStore` | skip · 需管理员 | 保留 | Windows 驱动包的集中存储，包含正在使用和可回滚的驱动。 | 保留；驱动管理用 pnputil / 设备管理器。 |
| `win-fonts` | `suffix` `\Windows\Fonts` | skip · 需管理员 | 保留 | 系统已安装字体。 | 保留；卸载字体请用设置/字体管理。 |
| `win-installer` | `suffix` `\Windows\Installer` | skip · 需管理员 | 保留 | MSI 安装包的缓存，用于程序修复、卸载和更新。 | 保留；不要用第三方清理工具批量删除。 |
| `win-root` | `exact` `%SystemDrive%\Windows` | container · 需管理员 | 保留 | Windows 操作系统目录，包含系统组件、驱动、更新缓存与日志。 | 不要整体删除；本工具只深入其中明确标记的可清理子目录。 |
| `win-servicing` | `suffix` `\Windows\servicing` | skip · 需管理员 | 保留 | Windows 更新/组件服务使用的离线组件与 LCU 数据。 | 保留；组件清理用 DISM。 |
| `win-system32` | `suffix` `\Windows\System32` | skip · 需管理员 | 保留 | Windows 核心系统文件与驱动目录。 | 禁止删除；本工具只会在其中清理明确标记的日志子目录。 |
| `win-syswow64` | `suffix` `\Windows\SysWOW64` | skip · 需管理员 | 保留 | 64 位 Windows 上的 32 位系统组件。 | 禁止删除。 |
| `win-winsxs` | `suffix` `\Windows\WinSxS` | skip · 需管理员 | 保留 | Windows 组件存储，包含系统文件的硬链接与旧组件。资源管理器显示的大小会因硬链接而失真。 | 禁止手动删除；需要清理时用 DISM /Online /Cleanup-Image /StartComponentCleanup。 |
| `windowsapps` | `suffix` `\AppData\Local\Microsoft\WindowsApps` | skip | 保留 | Windows 商店应用与命令别名。 | 保留。 |

### 7. 系统托管（6）

| ID | 匹配 | 模式 | 建议 | 说明 | 建议操作 |
| --- | --- | --- | --- | --- | --- |
| `file-dumpstack` | `suffix` `\DumpStack.log.tmp` | leaf · 文件 | 保留 | 系统崩溃转储相关的小型日志。 | 保留。 |
| `file-hiberfil` | `suffix` `\hiberfil.sys` | leaf · 文件 | 保留 | 休眠/快速启动使用的内存镜像文件，通常与物理内存同量级。 | 如需移除，管理员运行 powercfg /h off（会关闭休眠）；不要直接删文件。 |
| `file-pagefile` | `suffix` `\pagefile.sys` | leaf · 文件 | 保留 | Windows 虚拟内存页面文件，由系统管理。 | 保留；如需调整，用「系统属性 → 高级 → 性能 → 虚拟内存」。 |
| `file-swapfile` | `suffix` `\swapfile.sys` | leaf · 文件 | 保留 | UWP 应用使用的交换文件，由系统管理。 | 保留。 |
| `sys-config-msi` | `exact` `%SystemDrive%\Config.Msi` | skip · 需管理员 | 保留 | Windows Installer 安装/回滚期间使用的临时目录。 | 保留；安装程序运行期间尤其不要删除。 |
| `sys-volume-info` | `suffix` `\System Volume Information` | skip · 需管理员 | 保留 | 卷影副本、系统还原点与索引数据。 | 保留；用「系统保护」或 vssadmin 管理还原点。 |

### 8. 回收站（1）

| ID | 匹配 | 模式 | 建议 | 说明 | 建议操作 |
| --- | --- | --- | --- | --- | --- |
| `sys-recycle-bin` | `suffix` `\$Recycle.Bin` | skip · 不可选 | 谨慎清理 | 各用户删除的文件先进入这里；清空后才真正释放磁盘空间。 | 右键回收站 → 清空回收站，或 PowerShell Clear-RecycleBin；不要手动删除目录。 |

### 9. 用户数据（43）

| ID | 匹配 | 模式 | 建议 | 说明 | 建议操作 |
| --- | --- | --- | --- | --- | --- |
| `app-cloudmusic-library` | `suffix` `\CloudMusic\Library` | leaf | 谨慎清理 | 网易云音乐本地曲库/下载数据。 | 在云音乐内管理下载歌曲，不要直接删目录。 |
| `app-cloudmusic-localdata` | `suffix` `\CloudMusic\localdata` | leaf | 谨慎清理 | 网易云音乐本地数据（可能含下载内容）。 | 确认内容不再需要后清理。 |
| `app-codex-cli-sessions` | `suffix` `\.codex\sessions` | leaf | 谨慎清理 | Codex CLI 的会话历史（rollout 记录）。 | 确认不再需要历史会话后清理。 |
| `app-godot` | `suffix` `\AppData\Roaming\Godot` | leaf | 保留 | Godot 编辑器设置与导出模板。 | 保留；导出模板在编辑器内管理。 |
| `app-jianying-config` | `suffix` `\JianyingPro\User Data\Config` | leaf | 保留 | 剪映配置与草稿目录映射（draft_folder_mappings.json 等）。 | 保留。 |
| `app-jianying-projects` | `suffix` `\JianyingPro\User Data\Projects` | leaf | 保留 | 剪映草稿索引与元数据（root_meta_info.json 等），指向实际草稿目录。 | 禁止删除；在剪映内管理草稿。 |
| `app-pixpin-config` | `suffix` `\AppData\Local\PixPin\Config` | leaf | 保留 | PixPin 配置与自定义截图设置。 | 保留。 |
| `app-pixpin-data` | `suffix` `\AppData\Local\PixPin\Data` | leaf | 保留 | PixPin 贴图截图（png/meta/mark）、贴图窗口数据库与登录数据。 | 禁止删除；在 PixPin 内管理贴图。 |
| `app-pixpin-history` | `suffix` `\AppData\Local\PixPin\History` | leaf | 保留 | PixPin 截图历史（_ScreenshotRecord 的 .his 文件，截图原图+标注，不可再生成）。 | 禁止删除；在 PixPin 内管理历史记录。 |
| `app-qq-files` | `suffix` `\Documents\Tencent Files` | container | 谨慎清理 | QQ 聊天文件目录（Tencent Files）：接收的文件与图片。 | 不要整体删除；在 QQ 内管理文件。 |
| `app-vscode-user-history` | `suffix` `\Code\User\History` | leaf | 谨慎清理 | VS Code 本地文件历史（编辑快照，不可再生成）。 | 确认不需要找回旧版本后清理。 |
| `app-vscode-user-snippets` | `suffix` `\Code\User\snippets` | leaf | 保留 | 用户自定义代码片段。 | 保留。 |
| `app-wechat-files` | `suffix` `\Documents\xwechat_files` | container | 谨慎清理 | 微信 4.x 聊天文件目录（默认在文档，可自定义）：加密聊天数据库、图片/视频/文件。 | 不要整体删除；在微信内管理存储空间。 |
| `app-wechat-files-legacy` | `suffix` `\Documents\WeChat Files` | container | 谨慎清理 | 微信 3.x 聊天文件目录（WeChat Files）：消息数据库与接收的文件。 | 不要整体删除；在微信内管理存储空间。 |
| `app-wemail-attachments` | `suffix` `\Tencent\WeMail\attachments` | leaf | 谨慎清理 | 腾讯企业邮下载的附件（用户文件）。 | 确认附件已另存或不再需要后清理。 |
| `app-wemail-draft` | `suffix` `\Tencent\WeMail\local_draft` | leaf | 保留 | 腾讯企业邮的本地草稿（不可再生成）。 | 禁止删除。 |
| `app-wemeet-users` | `suffix` `\Tencent\WeMeet\Users` | leaf | 谨慎清理 | 腾讯会议的用户数据（会议记录/个人设置）。 | 确认不再需要后清理。 |
| `app-workbuddy-clipboard` | `suffix` `\.workbuddy\clipboard-images` | leaf | 谨慎清理 | WorkBuddy 缓存的剪贴板图片，可能含用户内容。 | 确认图片不再需要后清理。 |
| `app-workbuddy-memory` | `suffix` `\.workbuddy\memory` | leaf | 谨慎清理 | WorkBuddy 的长期记忆数据。 | 确认不再需要后清理。 |
| `app-workbuddy-sessions` | `suffix` `\.workbuddy\sessions` | leaf | 谨慎清理 | WorkBuddy 会话历史（用户数据）。 | 确认不再需要历史会话后清理。 |
| `app-workbuddy-skills` | `suffix` `\.workbuddy\skills` | leaf | 保留 | 用户安装的 WorkBuddy 技能。 | 保留。 |
| `app-wps-office6-backup` | `suffix` `\kingsoft\office6\backup` | leaf | 保留 | WPS 文档备份中心的本地备份（不可再生成）。 | 禁止删除；在 WPS 备份中心内管理。 |
| `app-wps-xlstart` | `suffix` `\kingsoft\wps\XLSTART` | leaf | 保留 | WPS/Excel 启动目录的模板与宏文件。 | 保留。 |
| `app-xwechat-allusers` | `suffix` `\Tencent\xwechat\All Users` | leaf | 谨慎清理 | 微信 4.x 的公共配置与 AI SDK 数据。 | 确认用途后再清理。 |
| `app-zcode-skills` | `suffix` `\.zcode\skills` | leaf | 保留 | 用户安装的 ZCode 技能（用户数据）。 | 保留。 |
| `app-zcode-workspace` | `suffix` `\.zcode\workspace` | leaf | 谨慎清理 | ZCode 工作区状态与会话索引。 | 确认不再需要历史会话后清理。 |
| `claude-3p-configlibrary` | `suffix` `\Claude-3p\configLibrary` | leaf | 谨慎清理 | Claude-3p 的配置库。 | 确认用途后再清理。 |
| `claude-3p-sessions` | `suffix` `\Claude-3p\local-agent-mode-sessions` | leaf | 谨慎清理 | Claude-3p 本地 agent 模式的会话数据。 | 确认不再需要历史会话后清理。 |
| `codebuddy-ext-data` | `suffix` `\CodeBuddyExtension\Data` | leaf | 谨慎清理 | CodeBuddy 扩展的本地数据（按用户隔离）。 | 确认不再需要后清理。 |
| `davinci-project-db` | `suffix` `\Blackmagic Design\DaVinci Resolve\Support` | leaf | 保留 | DaVinci Resolve 的工程数据库与支持文件。 | 禁止删除；在 Resolve 内管理工程。 |
| `dev-deno-location-data` | `suffix` `\deno\location_data` | leaf | 谨慎清理 | Deno 的 origin/localStorage 持久数据。 | 确认不再需要站点数据后清理。 |
| `dingtalk-storage` | `suffix` `\DingTalk\Storage` | leaf | 谨慎清理 | 钉钉离线文档存储。 | 确认文档已同步后清理。 |
| `listary-settings` | `suffix` `\Listary\UserProfile\Settings` | leaf | 保留 | Listary 偏好设置、路径历史与搜索历史。 | 保留。 |
| `sys-appdata` | `regex` `^[a-z]:\\users\\[^\\]+\\appdata$` | container | 保留 | 应用保存配置与缓存的根目录，分为 Local / Roaming / LocalLow。 | 不要整体删除；只清理其中明确标记的缓存子目录。 |
| `sys-appdata-local` | `regex` `^[a-z]:\\users\\[^\\]+\\appdata\\local$` | container | 保留 | 本机专用应用数据与缓存（不随漫游配置同步）。 | 不要整体删除；只清理其中明确标记的缓存子目录。 |
| `sys-appdata-locallow` | `regex` `^[a-z]:\\users\\[^\\]+\\appdata\\locallow$` | container | 保留 | 低权限/沙盒应用的数据目录，通常较小。 | 保留；不要整体删除。 |
| `sys-appdata-roaming` | `regex` `^[a-z]:\\users\\[^\\]+\\appdata\\roaming$` | container | 保留 | 应用配置、账户信息与可漫游数据。 | 保留；不要整体删除。 |
| `sys-users` | `exact` `%SystemDrive%\Users` | container · 需管理员 | 保留 | 所有用户配置文件的根目录，包含桌面、文档、下载、AppData 等。 | 不要整体删除；只清理用户明确选择的具体目录。 |
| `user-downloads` | `suffix` `\Downloads` | leaf | 谨慎清理 | 浏览器/应用默认的下载目录，通常包含安装包、文档与临时下载。 | 建议在资源管理器中逐项筛选，只删除确认不再需要的文件；不要整体清理。 |
| `wechat3-filestorage` | `glob` `*\WeChat Files\*\FileStorage` | leaf | 谨慎清理 | 微信 3.x 接收的文件/图片/视频。 | 确认文件已另存后再清理。 |
| `wechat3-msg` | `glob` `*\WeChat Files\*\Msg` | leaf | 谨慎清理 | 微信 3.x 的消息数据库。 | 在微信内管理；不要直接删除。 |
| `wechat4-db` | `glob` `*\xwechat_files\*\db_storage` | leaf | 保留 | 微信 4.x 的加密聊天数据库。 | 禁止删除。 |
| `wechat4-msg` | `glob` `*\xwechat_files\*\msg` | leaf | 谨慎清理 | 微信 4.x 聊天中的图片/视频/文件。 | 在微信内管理存储空间；确认文件已另存后再清理。 |

### 10. 用户临时文件（4）

| ID | 匹配 | 模式 | 建议 | 说明 | 建议操作 |
| --- | --- | --- | --- | --- | --- |
| `onedrivetemp` | `suffix` `\OneDriveTemp` | leaf | 安全清理 | OneDrive 同步过程使用的临时目录。 | 暂停同步后可清理。 |
| `user-explorer-cache` | `suffix` `\AppData\Local\Microsoft\Windows\Explorer` | leaf | 谨慎清理 | Windows 资源管理器的缩略图、图标与视图缓存。 | 可清理；资源管理器会重建，文件夹视图设置可能重置。 |
| `user-temp` | `suffix` `\AppData\Local\Temp` | leaf | 安全清理 | 当前用户与各程序写入的临时文件；关闭程序后大部分可删除。 | 关闭常用程序后清理；被占用的文件会自动跳过。 |
| `user-wincaches` | `suffix` `\AppData\Local\Microsoft\Windows\Caches` | leaf | 安全清理 | Windows shell 与部分系统组件的小型缓存。 | 可清理。 |

### 11. 浏览器缓存（32）

| ID | 匹配 | 模式 | 建议 | 说明 | 建议操作 |
| --- | --- | --- | --- | --- | --- |
| `app-brave-root` | `suffix` `\AppData\Local\BraveSoftware` | container | 谨慎清理 | Brave 浏览器数据目录，含书签、登录态与缓存。 | 不要整体删除；只清理明确标记的缓存子目录。 |
| `brave-cache` | `glob` `*\AppData\Local\BraveSoftware\Brave-Browser\User Data\*\Cache` | leaf | 安全清理 | Brave 各配置文件的网页缓存。 | 关闭 Brave 后清理。 |
| `brave-code-cache` | `glob` `*\AppData\Local\BraveSoftware\Brave-Browser\User Data\*\Code Cache` | leaf | 安全清理 | Brave 的 JavaScript/WebAssembly 编译缓存。 | 关闭 Brave 后清理。 |
| `brave-crashpad` | `suffix` `\BraveSoftware\Brave-Browser\User Data\Crashpad` | leaf | 安全清理 | Brave 的崩溃报告缓存。 | 可清理。 |
| `brave-crx-cache` | `glob` `*\BraveSoftware\Brave-Browser\User Data\*crx_cache` | leaf | 安全清理 | Brave 组件/扩展更新下载的 CRX 缓存。 | 关闭 Brave 后清理。 |
| `brave-dawn-cache` | `glob` `*\BraveSoftware\Brave-Browser\User Data\*Dawn*Cache*` | leaf | 安全清理 | Brave 的 DawnGraphiteCache/DawnWebGPUCache 图形缓存。 | 关闭 Brave 后清理。 |
| `brave-gpucache` | `glob` `*\AppData\Local\BraveSoftware\Brave-Browser\User Data\*\GPUCache` | leaf | 安全清理 | Brave 的 GPU 渲染缓存。 | 关闭 Brave 后清理。 |
| `brave-gpupersistentcache` | `suffix` `\BraveSoftware\Brave-Browser\User Data\GPUPersistentCache` | leaf | 安全清理 | Brave 的 GPU 持久缓存。 | 关闭 Brave 后清理。 |
| `brave-grshadercache` | `suffix` `\AppData\Local\BraveSoftware\Brave-Browser\User Data\GrShaderCache` | leaf | 安全清理 | Brave 的 GPU 着色器缓存。 | 关闭 Brave 后清理。 |
| `brave-shadercache` | `suffix` `\AppData\Local\BraveSoftware\Brave-Browser\User Data\ShaderCache` | leaf | 安全清理 | Brave 的着色器缓存。 | 关闭 Brave 后清理。 |
| `brave-sw-cache` | `glob` `*\AppData\Local\BraveSoftware\Brave-Browser\User Data\*\Service Worker\CacheStorage` | leaf | 安全清理 | Brave 的 Service Worker 离线缓存。 | 关闭 Brave 后清理。 |
| `chrome-cache` | `glob` `*\AppData\Local\Google\Chrome\User Data\*\Cache` | leaf | 安全清理 | Chrome 各配置文件的网页缓存。 | 关闭 Chrome 后清理；不要删除 User Data 下的其他目录。 |
| `chrome-code-cache` | `glob` `*\AppData\Local\Google\Chrome\User Data\*\Code Cache` | leaf | 安全清理 | Chrome 的 JavaScript/WebAssembly 编译缓存。 | 关闭 Chrome 后清理。 |
| `chrome-crashpad` | `suffix` `\Google\Chrome\User Data\Crashpad` | leaf | 安全清理 | Chrome 的崩溃报告缓存。 | 可清理。 |
| `chrome-crx-cache` | `glob` `*\Google\Chrome\User Data\*crx_cache` | leaf | 安全清理 | Chrome 组件/扩展更新下载的 CRX 缓存。 | 关闭 Chrome 后清理。 |
| `chrome-dawn-cache` | `glob` `*\Google\Chrome\User Data\*Dawn*Cache*` | leaf | 安全清理 | Chrome 的 DawnGraphiteCache/DawnWebGPUCache 图形缓存。 | 关闭 Chrome 后清理。 |
| `chrome-gpucache` | `glob` `*\AppData\Local\Google\Chrome\User Data\*\GPUCache` | leaf | 安全清理 | Chrome 的 GPU 着色器/渲染缓存。 | 关闭 Chrome 后清理。 |
| `chrome-gpupersistentcache` | `suffix` `\Google\Chrome\User Data\GPUPersistentCache` | leaf | 安全清理 | Chrome 的 GPU 持久缓存。 | 关闭 Chrome 后清理。 |
| `chrome-grshadercache` | `suffix` `\AppData\Local\Google\Chrome\User Data\GrShaderCache` | leaf | 安全清理 | Chrome 的 GPU 着色器缓存。 | 关闭 Chrome 后清理。 |
| `chrome-shadercache` | `suffix` `\AppData\Local\Google\Chrome\User Data\ShaderCache` | leaf | 安全清理 | Chrome 的着色器缓存。 | 关闭 Chrome 后清理。 |
| `chrome-sw-cache` | `glob` `*\AppData\Local\Google\Chrome\User Data\*\Service Worker\CacheStorage` | leaf | 安全清理 | Chrome 的 Service Worker 离线缓存。 | 关闭 Chrome 后清理。 |
| `edge-cache` | `glob` `*\AppData\Local\Microsoft\Edge\User Data\*\Cache` | leaf | 安全清理 | Edge 各配置文件的网页缓存。 | 关闭 Edge 后清理；不要删除 User Data 下的其他目录。 |
| `edge-code-cache` | `glob` `*\AppData\Local\Microsoft\Edge\User Data\*\Code Cache` | leaf | 安全清理 | Edge 的 JavaScript/WebAssembly 编译缓存。 | 关闭 Edge 后清理。 |
| `edge-gpucache` | `glob` `*\AppData\Local\Microsoft\Edge\User Data\*\GPUCache` | leaf | 安全清理 | Edge 的 GPU 着色器/渲染缓存。 | 关闭 Edge 后清理。 |
| `edge-sw-cache` | `glob` `*\AppData\Local\Microsoft\Edge\User Data\*\Service Worker\CacheStorage` | leaf | 安全清理 | Edge 的 Service Worker 离线缓存。 | 关闭 Edge 后清理。 |
| `firefox-cache2` | `glob` `*\AppData\Local\Mozilla\Firefox\Profiles\*\cache2` | leaf | 安全清理 | Firefox 各配置文件的网页缓存。 | 关闭 Firefox 后清理。 |
| `firefox-startupcache` | `glob` `*\AppData\Local\Mozilla\Firefox\Profiles\*\startupCache` | leaf | 安全清理 | Firefox 的启动缓存。 | 关闭 Firefox 后清理。 |
| `opera-cache` | `suffix` `\AppData\Local\Opera Software\Opera Stable\Cache` | leaf | 安全清理 | Opera 的网页缓存。 | 关闭 Opera 后清理。 |
| `user-inetcache` | `suffix` `\AppData\Local\Microsoft\Windows\INetCache` | leaf · 需管理员 | 建议清理 | Internet Explorer / 部分系统组件使用的网页缓存。 | 可清理。 |
| `user-temporary-internet-files` | `suffix` `\AppData\Local\Microsoft\Windows\Temporary Internet Files` | leaf · 需管理员 | 建议清理 | 旧版 Windows/IE 的临时 Internet 文件目录。 | 可清理。 |
| `user-webcache` | `suffix` `\AppData\Local\Microsoft\Windows\WebCache` | leaf · 需管理员 | 建议清理 | 旧版 IE/系统组件的 Web 缓存数据库。 | 关闭浏览器与相关程序后清理；文件常被占用。 |
| `vivaldi-cache` | `glob` `*\AppData\Local\Vivaldi\User Data\*\Cache` | leaf | 安全清理 | Vivaldi 各配置文件的网页缓存。 | 关闭 Vivaldi 后清理。 |

### 12. 应用缓存（167）

| ID | 匹配 | 模式 | 建议 | 说明 | 建议操作 |
| --- | --- | --- | --- | --- | --- |
| `adobe-media-cache` | `suffix` `\Adobe\Common\Media Cache` | leaf | 安全清理 | Adobe 媒体缓存的索引数据库。 | 关闭 Adobe 应用后清理。 |
| `adobe-media-cache-files` | `suffix` `\Adobe\Common\Media Cache Files` | leaf | 安全清理 | Premiere/After Effects 等共用的媒体衍生缓存（.cfa/.pek/.ims）。 | 在 Premiere 的 Media Cache 首选项删除，或关闭 Adobe 应用后清理。 |
| `adobe-peak-files` | `suffix` `\Adobe\Common\Peak Files` | leaf | 安全清理 | Adobe 音频波形峰值缓存。 | 关闭 Adobe 应用后清理。 |
| `amd-dxcache` | `suffix` `\AppData\Local\AMD\DxCache` | leaf | 安全清理 | AMD 驱动的 DirectX 着色器缓存。 | 可清理。 |
| `amd-glcache` | `suffix` `\AppData\Local\AMD\GLCache` | leaf | 安全清理 | AMD 驱动的 OpenGL 着色器缓存。 | 可清理。 |
| `app-adobe-roaming` | `suffix` `\AppData\Roaming\Adobe` | container | 谨慎清理 | Adobe 应用数据目录（设置、缓存与媒体缓存）。 | 不要整体删除；只清理明确标记的缓存子目录。 |
| `app-agent-browser` | `suffix` `\.agent-browser` | container | 谨慎清理 | agent-browser 工具数据目录（浏览器 profile 与缓存）。 | 不要整体删除；确认子目录用途后再清理。 |
| `app-baidunetdisk` | `suffix` `\AppData\Roaming\baidunetdisk` | container | 谨慎清理 | 百度网盘客户端数据目录，含登录态与缓存。 | 不要整体删除；确认子目录用途后再清理。 |
| `app-bilibili` | `suffix` `\AppData\Roaming\bilibili` | container | 谨慎清理 | 哔哩哔哩桌面客户端数据目录（Chromium 内核），含登录态与缓存。 | 不要整体删除；只清理明确标记的缓存子目录。 |
| `app-celsys` | `suffix` `\AppData\Roaming\CELSYS` | container | 谨慎清理 | CELSYS（CLIP STUDIO PAINT）数据目录，含设置与素材。 | 不要整体删除；在应用内管理素材。 |
| `app-cherrystudio` | `suffix` `\AppData\Roaming\CherryStudio` | container | 谨慎清理 | Cherry Studio 数据目录：会话、助手、知识库与缓存。 | 不要整体删除；只清理明确标记的缓存子目录。 |
| `app-cherrystudio-root` | `suffix` `\.cherrystudio` | container | 谨慎清理 | Cherry Studio 数据目录：配置、知识库与缓存。 | 不要整体删除；确认子目录用途后再清理。 |
| `app-clash-verge` | `suffix` `\AppData\Local\io.github.clash-verge-rev.clash-verge-rev` | container | 谨慎清理 | Clash Verge Rev 数据目录，含订阅配置与日志。 | 不要整体删除；确认子目录用途后再清理。 |
| `app-claude-3p` | `suffix` `\AppData\Local\Claude-3p` | container | 谨慎清理 | Claude 桌面版变体数据目录：Chromium 缓存、内置 claude-code 运行时与会话。 | 不要整体删除；只清理明确标记的缓存子目录。 |
| `app-cloudmusic` | `suffix` `\NetEase\CloudMusic` | container | 谨慎清理 | 网易云音乐客户端数据目录，含曲库、下载与缓存。 | 不要整体删除；只清理明确标记的缓存子目录。 |
| `app-cloudmusic-cache` | `suffix` `\CloudMusic\Cache` | leaf | 安全清理 | 网易云音乐的在线播放缓存。 | 退出云音乐后清理。 |
| `app-cloudmusic-cacheresource` | `suffix` `\CloudMusic\cacheresource` | leaf | 安全清理 | 网易云音乐的封面/资源缓存。 | 退出云音乐后清理。 |
| `app-cloudmusic-dumps` | `suffix` `\CloudMusic\dumps` | leaf | 安全清理 | 网易云音乐崩溃转储。 | 可清理。 |
| `app-cloudmusic-log` | `suffix` `\CloudMusic\Log` | leaf | 安全清理 | 网易云音乐运行日志。 | 可清理。 |
| `app-cloudmusic-temp` | `suffix` `\CloudMusic\Temp` | leaf | 安全清理 | 网易云音乐临时文件。 | 退出云音乐后清理。 |
| `app-cloudmusic-tempd` | `suffix` `\CloudMusic\TempD` | leaf | 安全清理 | 网易云音乐临时下载文件。 | 确认没有正在下载的歌曲后清理。 |
| `app-cloudmusic-update` | `suffix` `\CloudMusic\update` | leaf | 安全清理 | 网易云音乐下载的更新包。 | 确认已更新到新版本后清理。 |
| `app-codex-cli-log` | `suffix` `\.codex\log` | leaf | 安全清理 | Codex CLI 运行日志。 | 可清理。 |
| `app-codex-cli-root` | `suffix` `\.codex` | container | 谨慎清理 | Codex CLI 状态目录：配置、会话历史与日志。 | 不要整体删除；只清理日志子目录。 |
| `app-coze` | `suffix` `\AppData\Roaming\Coze` | container | 谨慎清理 | Coze（扣子）桌面版数据目录，含登录态与缓存。 | 不要整体删除；只清理明确标记的缓存子目录。 |
| `app-cross-filecache` | `suffix` `\Tencent\Cross\FileCache` | leaf | 安全清理 | 腾讯 Cross 组件的文件缓存。 | 可清理。 |
| `app-dingtalk` | `suffix` `\AppData\Roaming\DingTalk` | container | 谨慎清理 | 钉钉数据目录：本地消息、离线文档与缓存。 | 不要整体删除；优先用钉钉内置清理缓存。 |
| `app-dingtalk-133` | `suffix` `\AppData\Local\DingTalk_133` | container | 谨慎清理 | 钉钉变体版本数据目录。 | 不要整体删除；优先用应用内清理缓存。 |
| `app-electron-updater` | `regex` `\\AppData\\Local\\[^\\]+-updater$` | leaf | 安全清理 | Electron 应用（electron-builder NSIS updater）的更新包残留目录，通常是更新完成后的旧安装包。 | 确认应用已更新到最新版本后可清理。 |
| `app-figma` | `suffix` `\AppData\Roaming\Figma` | container | 谨慎清理 | Figma 桌面版数据目录：本地状态与缓存。 | 不要整体删除；确认离线改动已同步后只清理缓存。 |
| `app-google-root` | `suffix` `\AppData\Local\Google` | container | 谨慎清理 | Google 产品数据目录（Chrome/Chrome for Testing/更新器等）。 | 不要整体删除；按产品子目录分别判断。 |
| `app-hermes` | `suffix` `\AppData\Local\hermes` | container | 谨慎清理 | Hermes Agent 数据目录，可能含自带运行时与会话数据。 | 不要整体删除；确认子目录用途后再清理。 |
| `app-huion` | `suffix` `\AppData\Roaming\HuionTablet` | container | 谨慎清理 | 绘王（Huion）数位板驱动数据目录。 | 不要整体删除；确认子目录用途后再清理。 |
| `app-imput` | `suffix` `\AppData\Local\imput` | container | 谨慎清理 | imput 厂商目录，实际产品为 Helium 浏览器（Chromium 内核）。 | 不要整体删除；程序目录保留，只清理缓存。 |
| `app-jianying` | `suffix` `\AppData\Local\JianyingPro` | container | 谨慎清理 | 剪映专业版数据目录：含草稿索引、素材缓存与程序资源；草稿工程通常在用户指定目录。 | 不要整体删除；只清理明确标记的缓存子目录。 |
| `app-jianying-cache` | `suffix` `\JianyingPro\User Data\Cache` | leaf | 安全清理 | 剪映的特效/音乐/在线素材等缓存（数十个子目录），可重新下载。 | 关闭剪映后清理。 |
| `app-jianying-cef-cache` | `glob` `*\JianyingPro\User Data\CEF\*Cache*` | leaf | 安全清理 | 剪映内置 CEF 浏览器的 Cache/GPUCache/ShaderCache 等缓存。 | 关闭剪映后清理。 |
| `app-jianying-crash` | `suffix` `\JianyingPro\User Data\Crash` | leaf | 安全清理 | 剪映崩溃报告。 | 可清理。 |
| `app-jianying-download` | `suffix` `\JianyingPro\User Data\Download` | leaf | 谨慎清理 | 剪映下载的组件/资源，可能仍被引用。 | 确认内容不再需要后清理。 |
| `app-jianying-log` | `suffix` `\JianyingPro\User Data\Log` | leaf | 安全清理 | 剪映运行日志。 | 可清理。 |
| `app-jianying-tracking` | `suffix` `\JianyingPro\User Data\Tracking` | leaf | 安全清理 | 剪映的埋点/遥测数据。 | 可清理。 |
| `app-jianying-velog` | `suffix` `\JianyingPro\User Data\VELog` | leaf | 安全清理 | 剪映视频引擎日志。 | 可清理。 |
| `app-kingsoft` | `suffix` `\AppData\Roaming\kingsoft` | container | 谨慎清理 | WPS/金山产品数据目录：含登录态、云文档缓存、插件池与文档备份。 | 不要整体删除；只清理其中明确标记的缓存子目录。 |
| `app-lark` | `suffix` `\AppData\Roaming\Lark` | container | 谨慎清理 | Lark（飞书国际版）桌面数据目录，含登录态与缓存。 | 不要整体删除；确认子目录用途后再清理。 |
| `app-lark-cache` | `glob` `*\LarkShell\aha\users\*\profile_explorer\Cache` | leaf | 安全清理 | 飞书内置浏览器（profile_explorer）的网页缓存。 | 退出飞书后清理。 |
| `app-lark-code-cache` | `glob` `*\LarkShell\aha\users\*\profile_explorer\Code Cache` | leaf | 安全清理 | 飞书内置浏览器的 JavaScript 编译缓存。 | 退出飞书后清理。 |
| `app-lark-gpucache` | `glob` `*\LarkShell\aha\users\*\profile_explorer\GPUCache` | leaf | 安全清理 | 飞书内置浏览器的 GPU 渲染缓存。 | 退出飞书后清理。 |
| `app-lark-sw-cache` | `glob` `*\LarkShell\aha\users\*\profile_explorer\Service Worker\CacheStorage` | leaf | 安全清理 | 飞书内置浏览器的 Service Worker 离线缓存。 | 退出飞书后清理。 |
| `app-larkshell` | `suffix` `\AppData\Roaming\LarkShell` | container | 谨慎清理 | 飞书（Lark）桌面版数据目录，含登录态与内置浏览器缓存。 | 不要整体删除；只清理明确标记的浏览器缓存子目录。 |
| `app-lenovo` | `suffix` `\AppData\Local\Lenovo` | container | 谨慎清理 | 联想应用数据目录（Vantage 等）。 | 不要整体删除；确认子目录用途后再清理。 |
| `app-listary` | `suffix` `\AppData\Roaming\Listary` | container | 谨慎清理 | Listary 搜索工具数据目录：索引缓存与个人设置。 | 不要整体删除；只清理索引缓存。 |
| `app-logi` | `suffix` `\AppData\Local\Logi` | container | 谨慎清理 | 罗技（Logitech）应用数据目录。 | 不要整体删除；确认子目录用途后再清理。 |
| `app-marscode` | `suffix` `\.marscode` | container | 谨慎清理 | MarsCode（豆包）数据目录。 | 不要整体删除；确认子目录用途后再清理。 |
| `app-mchosehub` | `suffix` `\AppData\Roaming\MCHOSEHUB` | container | 谨慎清理 | MCHOSE 外设驱动_hub 数据目录。 | 不要整体删除；确认子目录用途后再清理。 |
| `app-microsoft-local` | `suffix` `\AppData\Local\Microsoft` | container | 谨慎清理 | Microsoft 产品数据目录（Edge/OneDrive/Office/Windows 组件等），含凭据与系统组件。 | 不要整体删除；按产品子目录分别判断。 |
| `app-mozilla` | `suffix` `\AppData\Roaming\Mozilla` | container | 谨慎清理 | Firefox 配置与缓存目录，含书签、密码与登录态。 | 不要整体删除；在 Firefox 内清理缓存。 |
| `app-netease` | `suffix` `\AppData\Local\NetEase` | container | 谨慎清理 | 网易产品数据目录（云音乐等），含曲库数据与缓存。 | 不要整体删除；按产品子目录分别判断。 |
| `app-nvidia-corp` | `suffix` `\AppData\Local\NVIDIA Corporation` | container | 谨慎清理 | NVIDIA 应用数据目录（GeForce Experience 等）。 | 不要整体删除；确认子目录用途后再清理。 |
| `app-nvidia-locallow` | `suffix` `\AppData\LocalLow\NVIDIA` | container | 谨慎清理 | NVIDIA 的 LocalLow 数据目录，含着色器缓存。 | 只清理明确标记的缓存子目录。 |
| `app-obsidian` | `suffix` `\AppData\Roaming\Obsidian` | container | 谨慎清理 | Obsidian 全局配置与元数据缓存；vault 在用户自选位置。 | 不要整体删除；只清理缓存类子目录。 |
| `app-openai-local` | `suffix` `\AppData\Local\OpenAI` | container | 谨慎清理 | OpenAI 产品数据目录（Codex 桌面版等），含自带运行时。 | 不要整体删除；运行时目录保留。 |
| `app-packages-root` | `suffix` `\AppData\Local\Packages` | container | 谨慎清理 | UWP/商店应用数据目录，每个应用含用户数据与缓存。 | 不要整体删除；只清理明确标记的 TempState/AC Temp 等子目录。 |
| `app-packet-tracer` | `suffix` `\AppData\Local\Cisco Packet Tracer` | container | 谨慎清理 | Cisco Packet Tracer 数据目录（日志与用户文件）。 | 不要整体删除；确认子目录用途后再清理。 |
| `app-pallas-download` | `suffix` `\Tencent\pallas\download_cache` | leaf | 安全清理 | 腾讯 pallas 组件的下载缓存。 | 可清理。 |
| `app-pgadmin` | `suffix` `\AppData\Roaming\pgadmin4` | container | 谨慎清理 | pgAdmin 4 数据目录，含服务器配置与会话数据库。 | 不要整体删除；确认子目录用途后再清理。 |
| `app-pixiv-reader` | `suffix` `\AppData\Local\com.pixiv.reader` | container | 谨慎清理 | pixiv 阅读器客户端数据目录。 | 不要整体删除；确认子目录用途后再清理。 |
| `app-pixpin` | `suffix` `\AppData\Local\PixPin` | container | 谨慎清理 | PixPin 截图工具数据目录：含截图历史、贴图数据、配置与升级残留。 | 不要整体删除；只清理其中明确标记的缓存/升级残留子目录。 |
| `app-pixpin-crashpad` | `suffix` `\AppData\Local\PixPin\Crashpad` | leaf | 安全清理 | PixPin 的崩溃报告缓存。 | 可清理。 |
| `app-pixpin-temp` | `suffix` `\AppData\Local\PixPin\Temp` | leaf | 安全清理 | PixPin 的临时文件目录。 | 退出 PixPin 后可清理。 |
| `app-pixpin-upgrade` | `suffix` `\AppData\Local\PixPin\UpgradeFiles` | leaf | 建议清理 | PixPin 升级后留下的旧版本安装包。 | 确认已升级到新版本后可清理。 |
| `app-qq-roaming` | `suffix` `\AppData\Roaming\QQ` | container | 谨慎清理 | QQ NT 架构数据目录，含聊天与用户数据。 | 不要整体删除；在 QQ 内管理聊天文件。 |
| `app-qq-stemp` | `suffix` `\Tencent\QQ\STemp` | leaf | 安全清理 | QQ 的临时文件目录。 | 退出 QQ 后可清理。 |
| `app-qqnt-stemp` | `suffix` `\Tencent\QQNT\STemp` | leaf | 安全清理 | QQ NT 架构的临时文件目录。 | 退出 QQ 后可清理。 |
| `app-qqtempsys` | `suffix` `\Tencent\QQTempSys` | leaf | 安全清理 | QQ 的系统级临时文件。 | 退出 QQ 后可清理。 |
| `app-quark` | `suffix` `\AppData\Local\QuarkCloudDrive` | container | 谨慎清理 | 夸克网盘客户端数据目录（Chromium 内核），含账户、书签与缓存。 | 不要整体删除；只清理明确标记的缓存子目录。 |
| `app-quark-cache` | `glob` `*\QuarkCloudDrive\User Data\*Cache*` | leaf | 安全清理 | 夸克网盘的 Chromium 缓存（Cache/Code Cache/GPUCache/Dawn/资源缓存等）。 | 退出夸克后清理。 |
| `app-quark-crashpad` | `suffix` `\QuarkCloudDrive\User Data\Crashpad` | leaf | 安全清理 | 夸克网盘崩溃报告缓存。 | 可清理。 |
| `app-quark-temp` | `suffix` `\QuarkCloudDrive\User Data\temp_data` | leaf | 安全清理 | 夸克网盘临时数据。 | 退出夸克后清理。 |
| `app-quark-ulog` | `suffix` `\QuarkCloudDrive\User Data\ulog` | leaf | 安全清理 | 夸克网盘运行日志。 | 可清理。 |
| `app-squirreltemp` | `basename` `SquirrelTemp` | leaf | 安全清理 | Squirrel.Windows 更新框架的临时目录。 | 确认没有正在进行的更新后清理。 |
| `app-telegram` | `suffix` `\AppData\Roaming\Telegram Desktop` | container | 谨慎清理 | Telegram 桌面版数据目录。 | 不要整体删除；用 Telegram 内置 Storage Usage 清理缓存。 |
| `app-tencent` | `suffix` `\AppData\Roaming\Tencent` | container | 谨慎清理 | 腾讯产品系数据目录（微信/QQ/企业微信/腾讯会议等），含登录态、聊天文件与缓存。 | 不要整体删除；只清理明确标记的临时/缓存子目录。 |
| `app-tencent-locallow` | `suffix` `\AppData\LocalLow\Tencent` | container | 谨慎清理 | 腾讯产品的 LocalLow 数据目录（游戏/组件数据）。 | 不要整体删除；确认子目录用途后再清理。 |
| `app-ticktick` | `suffix` `\AppData\Roaming\Tick_Tick` | container | 谨慎清理 | 滴答清单（TickTick）数据目录，含登录态与本地数据。 | 不要整体删除；确认任务已同步后再清理。 |
| `app-todesk` | `suffix` `\AppData\Local\ToDesk` | container | 谨慎清理 | ToDesk 远程控制数据目录，含登录态与配置。 | 不要整体删除；确认子目录用途后再清理。 |
| `app-vmware` | `suffix` `\AppData\Local\VMware` | container | 谨慎清理 | VMware 数据目录（日志与缓存）。 | 不要整体删除；确认子目录用途后再清理。 |
| `app-wedoc-cache` | `suffix` `\Tencent\Wedoc\cache` | leaf | 安全清理 | 腾讯文档客户端缓存。 | 确认文档已同步后清理。 |
| `app-wemail-cache` | `suffix` `\Tencent\WeMail\cache` | leaf | 安全清理 | 腾讯企业邮客户端缓存。 | 退出企业邮后清理。 |
| `app-workbuddy-cache` | `suffix` `\.workbuddy\cache` | leaf | 安全清理 | WorkBuddy 运行时缓存。 | 退出 WorkBuddy 后清理。 |
| `app-workbuddy-logs` | `suffix` `\.workbuddy\logs` | leaf | 安全清理 | WorkBuddy 运行日志。 | 可清理。 |
| `app-workbuddy-root` | `suffix` `\.workbuddy` | container | 谨慎清理 | WorkBuddy 状态目录：会话、记忆、数据库与缓存。 | 不要整体删除；只清理明确标记的缓存/日志子目录。 |
| `app-workbuddy-telemetry` | `suffix` `\.workbuddy\pending-telemetry` | leaf | 安全清理 | WorkBuddy 待发送的遥测数据。 | 可清理。 |
| `app-wps-addons-pool` | `suffix` `\kingsoft\wps\addons\pool` | leaf | 谨慎清理 | WPS 插件池（win-i386 等），同一插件多个版本目录共存，可达数 GB。 | 保留每个插件的最新版本，旧版本可删；建议在 WPS 设置中管理插件。 |
| `app-wps-cloud-files` | `suffix` `\kingsoft\WPS Cloud Files` | leaf | 谨慎清理 | WPS 云文档的本地缓存，可能包含未同步的编辑。 | 确认文档已同步后清理。 |
| `app-wps-download` | `suffix` `\kingsoft\wps\download` | leaf | 谨慎清理 | WPS 下载的安装包/模板/组件，可能仍被引用。 | 确认内容不再需要后清理。 |
| `app-wps-office6-cache` | `suffix` `\kingsoft\office6\cache` | leaf | 安全清理 | WPS office6 的运行时缓存。 | 关闭 WPS 后清理。 |
| `app-wps-office6-log` | `suffix` `\kingsoft\office6\log` | leaf | 安全清理 | WPS office6 运行日志。 | 可清理。 |
| `app-wps-office6-mediacache` | `suffix` `\kingsoft\office6\mediacache` | leaf | 安全清理 | WPS 的媒体/在线资源缓存。 | 关闭 WPS 后清理。 |
| `app-wps-office6-update` | `suffix` `\kingsoft\office6\update` | leaf | 安全清理 | WPS office6 下载的更新包。 | 确认已更新到新版本后清理。 |
| `app-wps-offlinelog` | `suffix` `\kingsoft\offlinelog` | leaf | 安全清理 | WPS 离线日志。 | 可清理。 |
| `app-wps-pdf-cache` | `suffix` `\kingsoft\PDF\Cache` | leaf | 安全清理 | WPS PDF 组件缓存。 | 关闭 WPS 后清理。 |
| `app-wps-personalofflinecache` | `suffix` `\kingsoft\personalofflinecache` | leaf | 谨慎清理 | WPS 个人离线缓存，可能包含离线文档。 | 确认离线内容不再需要后清理。 |
| `app-wxdrive` | `suffix` `\AppData\Roaming\WXDrive` | container | 谨慎清理 | 微信网盘（WXDrive）数据目录。 | 不要整体删除；确认文件已同步后再清理。 |
| `app-wxwork-log` | `suffix` `\Tencent\WXWork\Log` | leaf | 安全清理 | 企业微信运行日志。 | 可清理。 |
| `app-wxwork-upgrade` | `suffix` `\Tencent\WXWork\upgrade` | leaf | 安全清理 | 企业微信下载的升级包。 | 确认已升级到新版本后可清理。 |
| `app-xwechat-crashinfo` | `suffix` `\Tencent\xwechat\crashinfo` | leaf | 安全清理 | 微信 4.x 崩溃信息。 | 可清理。 |
| `app-xwechat-log` | `suffix` `\Tencent\xwechat\log` | leaf | 安全清理 | 微信 4.x（xwechat）运行日志。 | 可清理。 |
| `app-xwechat-update` | `suffix` `\Tencent\xwechat\update` | leaf | 安全清理 | 微信 4.x 更新暂存文件。 | 确认已更新到新版本后清理。 |
| `app-yuque` | `suffix` `\AppData\Roaming\yuque-desktop` | container | 谨慎清理 | 语雀桌面版数据目录，含登录态与离线文档。 | 不要整体删除；确认文档已同步后只清理缓存。 |
| `app-zcode-backup` | `suffix` `\.zcode\backup` | leaf | 谨慎清理 | ZCode 旧版本 CLI 的备份。 | 确认新版本稳定后清理。 |
| `app-zcode-cli-log` | `suffix` `\.zcode\cli\log` | leaf | 安全清理 | ZCode CLI 运行日志。 | 可清理。 |
| `app-zcode-desktop` | `suffix` `\AppData\Roaming\ZCode` | container | 谨慎清理 | ZCode 桌面版数据目录：会话缓存与远程组件资源。 | 不要整体删除；只清理明确标记的缓存子目录。 |
| `app-zcode-plugins-cache` | `suffix` `\.zcode\cli\plugins\cache` | leaf | 谨慎清理 | ZCode CLI 已安装插件的各版本副本，内含插件运行时依赖（node_modules）。 | 确认插件已更新、旧版本不再需要后清理；不要删除当前使用版本。 |
| `app-zcode-remote-assets` | `suffix` `\ZCode\remote-assets-cache` | leaf | 安全清理 | ZCode 桌面版下载的远程组件/更新资源缓存。 | 退出 ZCode 后清理。 |
| `app-zcode-root` | `suffix` `\.zcode` | container | 谨慎清理 | ZCode CLI 状态目录：会话、凭据、技能与插件缓存。 | 不要整体删除；只清理明确标记的日志/缓存子目录。 |
| `app-zcode-session-cache` | `glob` `*\Roaming\ZCode\session\*Cache*` | leaf | 安全清理 | ZCode 桌面版 session 下的 Chromium 缓存（Cache/Code Cache/GPUCache/Dawn/Shader 等）。 | 退出 ZCode 后清理。 |
| `app-zcode-v2-crash` | `suffix` `\.zcode\v2\crash` | leaf | 安全清理 | ZCode v2 崩溃转储。 | 可清理。 |
| `app-zcode-v2-logs` | `suffix` `\.zcode\v2\logs` | leaf | 安全清理 | ZCode v2 运行日志。 | 可清理。 |
| `bilibili-cache` | `glob` `*\Roaming\bilibili\*Cache*` | leaf | 安全清理 | 哔哩哔哩客户端的 Chromium 缓存（Cache/Code Cache/GPUCache/Dawn 等）。 | 退出客户端后清理。 |
| `bilibili-crashpad` | `suffix` `\bilibili\Crashpad` | leaf | 安全清理 | 哔哩哔哩客户端崩溃报告缓存。 | 可清理。 |
| `bilibili-logs` | `suffix` `\bilibili\logs` | leaf | 安全清理 | 哔哩哔哩客户端运行日志。 | 可清理。 |
| `cherrystudio-cache` | `glob` `*\CherryStudio\*Cache*` | leaf | 安全清理 | Cherry Studio 的 Chromium 缓存（Cache/Code Cache/GPUCache/Dawn 等）。 | 退出 Cherry Studio 后清理。 |
| `cherrystudio-logs` | `suffix` `\CherryStudio\logs` | leaf | 安全清理 | Cherry Studio 运行日志。 | 可清理。 |
| `claude-3p-cache` | `glob` `*\Claude-3p\*Cache*` | leaf | 安全清理 | Claude-3p 的 Chromium 缓存（Cache/Code Cache/GPUCache/Dawn 等）。 | 退出 Claude 后清理。 |
| `claude-3p-crashpad` | `suffix` `\Claude-3p\Crashpad` | leaf | 安全清理 | Claude-3p 崩溃报告缓存。 | 可清理。 |
| `claude-3p-logs` | `suffix` `\Claude-3p\logs` | leaf | 安全清理 | Claude-3p 运行日志。 | 可清理。 |
| `claude-3p-sentry` | `suffix` `\Claude-3p\sentry` | leaf | 安全清理 | Claude-3p 的 Sentry 崩溃/遥测数据。 | 可清理。 |
| `coze-cache` | `glob` `*\Roaming\Coze\*Cache*` | leaf | 安全清理 | Coze 桌面版的 Chromium 缓存（Cache/Code Cache/GPUCache 等）。 | 退出 Coze 后清理。 |
| `coze-logs` | `suffix` `\Coze\logs` | leaf | 安全清理 | Coze 桌面版运行日志。 | 可清理。 |
| `d3dscache` | `suffix` `\AppData\Local\D3DSCache` | leaf | 安全清理 | DirectX 游戏的着色器编译缓存。 | 可清理；游戏会重新编译着色器。 |
| `davinci-cacheclip` | `basename` `CacheClip` | leaf | 安全清理 | DaVinci Resolve 的渲染缓存/优化媒体（位置由首个媒体存储路径决定）。 | 在 Resolve 内 Clear Render Cache，或关闭 Resolve 后清理。 |
| `dingtalk-cache` | `suffix` `\DingTalk\Cache` | leaf | 安全清理 | 钉钉网页/媒体缓存。 | 退出钉钉后清理。 |
| `dingtalk-gpucache` | `suffix` `\DingTalk\GPUCache` | leaf | 安全清理 | 钉钉 GPU 渲染缓存。 | 退出钉钉后清理。 |
| `dingtalk-logs` | `suffix` `\DingTalk\Logs` | leaf | 安全清理 | 钉钉运行日志。 | 可清理。 |
| `discord-cache` | `suffix` `\AppData\Roaming\Discord\Cache` | leaf | 安全清理 | Discord 的网页/媒体缓存。 | 退出 Discord 后清理。 |
| `discord-code-cache` | `suffix` `\AppData\Roaming\Discord\Code Cache` | leaf | 安全清理 | Discord 的 JavaScript 编译缓存。 | 退出 Discord 后清理。 |
| `discord-gpucache` | `suffix` `\AppData\Roaming\Discord\GPUCache` | leaf | 安全清理 | Discord 的 GPU 渲染缓存。 | 退出 Discord 后清理。 |
| `figma-cache` | `glob` `*\Figma\DesktopProfile\*Cache*` | leaf | 安全清理 | Figma 桌面版的 Chromium 缓存（Cache/Code Cache/GPUCache）。 | 确认离线改动已同步后，退出 Figma 清理。 |
| `figma-crashpad` | `suffix` `\Figma\DesktopProfile\Crashpad` | leaf | 安全清理 | Figma 桌面版崩溃报告缓存。 | 可清理。 |
| `google-updater-crx` | `suffix` `\Google\GoogleUpdater\crx_cache` | leaf | 安全清理 | Google 更新器下载的组件 CRX 缓存。 | 可清理。 |
| `helium-cache` | `glob` `*\imput\Helium\User Data\*Cache*` | leaf | 安全清理 | Helium 浏览器的 Chromium 缓存（Cache/GPUCache/Shader/CRX 缓存等）。 | 退出浏览器后清理。 |
| `helium-crashpad` | `suffix` `\imput\Helium\User Data\Crashpad` | leaf | 安全清理 | Helium 浏览器崩溃报告缓存。 | 可清理。 |
| `helium-temp` | `suffix` `\imput\Helium\Temp` | leaf | 安全清理 | Helium 浏览器临时文件。 | 退出浏览器后清理。 |
| `intel-shadercache` | `suffix` `\AppData\Local\Intel\ShaderCache` | leaf | 安全清理 | Intel 显卡驱动的着色器缓存。 | 可清理。 |
| `listary-cache` | `suffix` `\Listary\UserProfile\Cache` | leaf | 安全清理 | Listary 的搜索索引缓存与引擎日志，可重建。 | 退出 Listary 后清理。 |
| `nvidia-dxcache` | `suffix` `\AppData\Local\NVIDIA\DXCache` | leaf | 安全清理 | NVIDIA 驱动的 DirectX 着色器缓存。 | 可清理；驱动会重新生成。 |
| `nvidia-glcache` | `suffix` `\AppData\Local\NVIDIA\GLCache` | leaf | 安全清理 | NVIDIA 驱动的 OpenGL 着色器缓存。 | 可清理。 |
| `nvidia-locallow-dxcache` | `suffix` `\AppData\LocalLow\NVIDIA\DXCache` | leaf | 安全清理 | NVIDIA DirectX 着色器/管线缓存（.nvph）。 | 可清理；驱动会重新生成。 |
| `obsidian-cache` | `glob` `*\Roaming\Obsidian\*Cache*` | leaf | 安全清理 | Obsidian 的 Chromium 缓存。 | 退出 Obsidian 后清理。 |
| `office-diagnostics` | `glob` `*\AppData\Local\Microsoft\Office\*\Diagnostics` | leaf | 安全清理 | Office 诊断日志。 | 可清理。 |
| `office-file-cache` | `glob` `*\AppData\Local\Microsoft\Office\*\OfficeFileCache` | leaf | 谨慎清理 | Office 文档的本地缓存，可能包含未同步的编辑。 | 关闭 Office 并确认文档已保存/同步后清理。 |
| `onedrive-logs` | `suffix` `\AppData\Local\OneDrive\logs` | leaf | 安全清理 | OneDrive 客户端日志。 | 可清理；同步故障排查时保留。 |
| `onedrive-ms-logs` | `suffix` `\AppData\Local\Microsoft\OneDrive\logs` | leaf | 安全清理 | Microsoft Store 版 OneDrive 日志。 | 可清理。 |
| `onedrive-setup-logs` | `suffix` `\AppData\Local\Microsoft\OneDrive\setup\logs` | leaf | 安全清理 | OneDrive 安装/更新日志。 | 可清理。 |
| `programdata-nvidia-downloader` | `suffix` `\ProgramData\NVIDIA Corporation\Downloader` | leaf · 需管理员 | 安全清理 | NVIDIA 驱动安装器下载的安装包缓存。 | 驱动安装完成后可删；再次安装会重新下载。 |
| `slack-cache` | `suffix` `\AppData\Roaming\Slack\Cache` | leaf | 安全清理 | Slack 的网页/媒体缓存。 | 退出 Slack 后清理。 |
| `slack-gpucache` | `suffix` `\AppData\Roaming\Slack\GPUCache` | leaf | 安全清理 | Slack 的 GPU 渲染缓存。 | 退出 Slack 后清理。 |
| `spotify-storage` | `suffix` `\AppData\Local\Spotify\Storage` | leaf | 谨慎清理 | Spotify 的离线歌曲与封面缓存，可能很大。 | 确认不需要离线收听后清理；重新下载会消耗流量。 |
| `teams-cache` | `suffix` `\AppData\Roaming\Microsoft\Teams\Cache` | leaf | 安全清理 | Teams 的网页/媒体缓存。 | 退出 Teams 后清理。 |
| `teams-code-cache` | `suffix` `\AppData\Roaming\Microsoft\Teams\Code Cache` | leaf | 安全清理 | Teams 的 JavaScript 编译缓存。 | 退出 Teams 后清理。 |
| `teams-gpucache` | `suffix` `\AppData\Roaming\Microsoft\Teams\GPUCache` | leaf | 安全清理 | Teams 的 GPU 渲染缓存。 | 退出 Teams 后清理。 |
| `uwp-ac-temp` | `glob` `*\AppData\Local\Packages\*\AC\Temp` | leaf | 安全清理 | UWP 应用兼容层使用的临时文件。 | 关闭对应应用后可清理。 |
| `uwp-localcache` | `glob` `*\AppData\Local\Packages\*\LocalCache` | leaf | 谨慎清理 | Windows 商店应用（UWP）的本地缓存，可能包含离线数据。 | 关闭对应应用后清理；重要离线内容先确认。 |
| `uwp-tempstate` | `glob` `*\AppData\Local\Packages\*\TempState` | leaf | 安全清理 | Windows 商店应用的临时状态目录。 | 关闭对应应用后可清理。 |
| `wechat3-cache` | `glob` `*\WeChat Files\*\FileStorage\Cache` | leaf | 安全清理 | 微信 3.x 各账号的文件缓存。 | 退出微信后清理。 |
| `wechat4-cache` | `glob` `*\xwechat_files\*\cache` | leaf | 安全清理 | 微信 4.x 各账号的缓存目录。 | 退出微信后清理。 |
| `wechat4-temp` | `glob` `*\xwechat_files\*\temp` | leaf | 安全清理 | 微信 4.x 各账号的临时文件。 | 退出微信后清理。 |

### 13. 开发工具缓存（91）

| ID | 匹配 | 模式 | 建议 | 说明 | 建议操作 |
| --- | --- | --- | --- | --- | --- |
| `app-codebuddy-cli` | `suffix` `\.codebuddy` | container | 谨慎清理 | CodeBuddy CLI 状态目录。 | 不要整体删除；确认子目录用途后再清理。 |
| `app-codebuddy-cn` | `suffix` `\AppData\Roaming\CodeBuddy CN` | container | 谨慎清理 | CodeBuddy CN（VS Code 内核）数据目录：用户设置、会话与缓存。 | 不要整体删除；只清理明确标记的缓存子目录。 |
| `app-codebuddy-ext` | `suffix` `\AppData\Local\CodeBuddyExtension` | container | 谨慎清理 | 腾讯 CodeBuddy 扩展数据目录：缓存、日志与本地数据。 | 不要整体删除；只清理缓存/日志子目录。 |
| `app-qoder` | `suffix` `\AppData\Roaming\Qoder` | container | 谨慎清理 | Qoder（VS Code 内核）数据目录：用户设置与缓存。 | 不要整体删除；只清理明确标记的缓存子目录。 |
| `app-qoder-cli` | `suffix` `\.qoder` | container | 谨慎清理 | Qoder CLI 状态目录。 | 不要整体删除；确认子目录用途后再清理。 |
| `app-trae` | `suffix` `\AppData\Roaming\Trae` | container | 谨慎清理 | Trae 国际版（VS Code 内核）数据目录。 | 不要整体删除；确认子目录用途后再清理。 |
| `app-trae-cn` | `suffix` `\AppData\Roaming\Trae CN` | container | 谨慎清理 | Trae CN（VS Code 内核）数据目录：用户设置、工作区状态与缓存。 | 不要整体删除；只清理明确标记的缓存子目录。 |
| `app-trae-cn-cli` | `suffix` `\.trae-cn` | container | 谨慎清理 | Trae CN CLI 状态目录。 | 不要整体删除；确认子目录用途后再清理。 |
| `app-vscode-backups` | `suffix` `\Code\Backups` | leaf | 谨慎清理 | VS Code 热退出备份的未保存文件。 | 确认没有未保存的工作后清理。 |
| `app-vscode-root` | `suffix` `\AppData\Roaming\Code` | container | 谨慎清理 | VS Code 数据目录：用户设置、工作区状态与缓存。 | 不要整体删除；只清理明确标记的缓存子目录。 |
| `app-vscode-user-global` | `suffix` `\Code\User\globalStorage` | leaf | 谨慎清理 | VS Code 扩展的全局状态，可能含登录态。 | 确认用途后再清理。 |
| `app-vscode-user-ws` | `suffix` `\Code\User\workspaceStorage` | leaf | 谨慎清理 | VS Code 各工作区的扩展状态（含聊天历史等）。 | 确认不再需要工作区状态后清理。 |
| `app-zed-local` | `suffix` `\AppData\Local\Zed` | container | 谨慎清理 | Zed 编辑器的数据目录：日志、扩展与工作区数据库。 | 不要整体删除；只清理日志子目录。 |
| `chrome-for-testing` | `suffix` `\Google\Chrome for Testing` | leaf | 安全清理 | 自动化测试用的 Chrome for Testing 浏览器（独立安装位置）。 | 可清理；需要时会重新下载。 |
| `codebuddy-cn-backups` | `suffix` `\CodeBuddy CN\Backups` | leaf | 谨慎清理 | CodeBuddy CN 热退出备份的未保存文件。 | 确认没有未保存的工作后清理。 |
| `codebuddy-cn-cache` | `suffix` `\CodeBuddy CN\Cache` | leaf | 安全清理 | CodeBuddy CN 的网页/扩展缓存。 | 关闭 CodeBuddy 后清理。 |
| `codebuddy-cn-cacheddata` | `suffix` `\CodeBuddy CN\CachedData` | leaf | 安全清理 | CodeBuddy CN 的 JavaScript 编译缓存。 | 关闭 CodeBuddy 后清理。 |
| `codebuddy-cn-cachedprofiles` | `suffix` `\CodeBuddy CN\CachedProfilesData` | leaf | 安全清理 | CodeBuddy CN 配置文件（Profile）的缓存数据。 | 关闭 CodeBuddy 后清理。 |
| `codebuddy-cn-code-cache` | `suffix` `\CodeBuddy CN\Code Cache` | leaf | 安全清理 | CodeBuddy CN 的代码编译缓存。 | 关闭 CodeBuddy 后清理。 |
| `codebuddy-cn-crash` | `suffix` `\CodeBuddy CN\CrashReport` | leaf | 安全清理 | CodeBuddy CN 崩溃报告。 | 可清理。 |
| `codebuddy-cn-dawn-cache` | `glob` `*\CodeBuddy CN\*Dawn*Cache*` | leaf | 安全清理 | CodeBuddy CN 的 DawnGraphiteCache/DawnWebGPUCache 图形缓存。 | 关闭 CodeBuddy 后清理。 |
| `codebuddy-cn-gpucache` | `suffix` `\CodeBuddy CN\GPUCache` | leaf | 安全清理 | CodeBuddy CN 的 GPU 渲染缓存。 | 关闭 CodeBuddy 后清理。 |
| `codebuddy-cn-logs` | `suffix` `\CodeBuddy CN\logs` | leaf | 安全清理 | CodeBuddy CN 运行日志。 | 可清理。 |
| `codebuddy-ext-cache` | `suffix` `\CodeBuddyExtension\Cache` | leaf | 安全清理 | CodeBuddy 扩展缓存。 | 关闭 IDE 后清理。 |
| `codebuddy-ext-logs` | `suffix` `\CodeBuddyExtension\Logs` | leaf | 安全清理 | CodeBuddy 扩展日志。 | 可清理。 |
| `cursor-cache` | `suffix` `\AppData\Roaming\Cursor\Cache` | leaf | 安全清理 | Cursor 编辑器的网页/扩展缓存。 | 关闭 Cursor 后清理。 |
| `cursor-cacheddata` | `suffix` `\AppData\Roaming\Cursor\CachedData` | leaf | 安全清理 | Cursor 的 JavaScript 编译缓存。 | 关闭 Cursor 后清理。 |
| `cursor-logs` | `suffix` `\AppData\Roaming\Cursor\logs` | leaf | 安全清理 | Cursor 运行日志。 | 可清理。 |
| `dev-android-avd` | `suffix` `\.android\avd` | leaf | 谨慎清理 | Android 模拟器的虚拟设备镜像与用户数据。 | 在 Android Studio 的 Device Manager 中删除不用的模拟器。 |
| `dev-android-cache` | `suffix` `\.android\cache` | leaf | 安全清理 | Android 工具链的构建/下载缓存。 | 可清理。 |
| `dev-bun-install` | `suffix` `\.bun\install` | leaf | 安全清理 | Bun 的全局包安装缓存。 | 可清理；bun install 会重新下载。 |
| `dev-bun-root` | `suffix` `\.bun` | container | 谨慎清理 | Bun 数据目录：含 bun 可执行文件与安装缓存。 | 不要整体删除；只清理 install 缓存子目录。 |
| `dev-cache-root` | `suffix` `\.cache` | container | 谨慎清理 | 用户级通用缓存根目录（.cache），各工具子目录性质不同。 | 不要整体删除；按工具子目录分别判断。 |
| `dev-cargo-root` | `suffix` `\.cargo` | container · 不可选 | 谨慎清理 | Cargo 根目录：含 cargo install 安装的二进制（bin）、registry/git 依赖缓存与配置。 | 不要整体删除；只清理其中明确标记的缓存子目录。 |
| `dev-chrome-extension-cache` | `suffix` `\AppData\Local\ChromeExtensionCache` | leaf | 安全清理 | 自动化工具下载的 Chrome 扩展缓存。 | 可清理；需要时会重新下载。 |
| `dev-chromium-snapshots` | `suffix` `\.chromium-browser-snapshots` | leaf | 安全清理 | 旧版 Puppeteer 下载的 Chromium 快照构建。 | 可清理；需要时会重新下载。 |
| `dev-deno-check` | `suffix` `\deno\check` | leaf | 安全清理 | Deno 的类型检查缓存。 | 可清理；会重新生成。 |
| `dev-deno-code-cache` | `suffix` `\deno\code_cache` | leaf | 安全清理 | Deno 的 V8 代码缓存。 | 可清理；会重新生成。 |
| `dev-deno-deps` | `suffix` `\deno\deps` | leaf | 安全清理 | Deno 下载的远程模块缓存。 | 可清理；运行时会重新下载。 |
| `dev-deno-dir` | `suffix` `\AppData\Local\deno` | container | 谨慎清理 | Deno 的默认缓存目录（DENO_DIR），含远程模块/转译/npm 缓存与站点持久数据。 | 优先用 deno clean；只清理明确标记的缓存子目录。 |
| `dev-deno-gen` | `suffix` `\deno\gen` | leaf | 安全清理 | Deno 的转译结果缓存。 | 可清理；会重新生成。 |
| `dev-deno-npm` | `suffix` `\deno\npm` | leaf | 安全清理 | Deno 的 npm 包缓存。 | 可清理；会重新下载。 |
| `dev-deno-registries` | `suffix` `\deno\registries` | leaf | 安全清理 | Deno 的注册表元数据缓存。 | 可清理；会重新生成。 |
| `dev-electron-cache` | `suffix` `\AppData\Local\electron` | leaf | 安全清理 | Electron 框架 zip 的下载缓存（electron-builder 等构建工具使用）。 | 可清理；构建 Electron 应用时会重新下载。 |
| `dev-fnm-root` | `suffix` `\AppData\Roaming\fnm` | container · 不可选 | 谨慎清理 | fnm（Fast Node Manager）根目录：含已安装的 Node.js 版本与别名配置。 | 不要整体删除；用 fnm uninstall 管理不用的 Node 版本。 |
| `dev-fnm-root-local` | `suffix` `\AppData\Local\fnm` | container · 不可选 | 谨慎清理 | fnm 根目录的 Local 位置：含已安装的 Node.js 版本与别名配置。 | 不要整体删除；用 fnm uninstall 管理不用的 Node 版本。 |
| `dev-go-build` | `suffix` `\AppData\Local\go-build` | leaf | 安全清理 | Go 编译对象与构建缓存。 | 可清理；go build 会重新生成。 |
| `dev-gradle-cache` | `suffix` `\.gradle\caches` | leaf | 安全清理 | Gradle 下载的依赖、插件与构建缓存。 | 可清理；下次构建会重新下载/生成。 |
| `dev-node-gyp` | `suffix` `\AppData\Local\node-gyp` | leaf | 安全清理 | node-gyp 下载的 Node 头文件与库缓存。 | 可清理；编译原生模块时会重新下载。 |
| `dev-ort-cache` | `suffix` `\AppData\Local\ort.pyke.io` | container | 谨慎清理 | ONNX Runtime（ort/pyke）下载的运行时二进制与模型缓存。 | 确认没有离线依赖后清理；需要时会重新下载。 |
| `dev-playwright-browsers` | `suffix` `\AppData\Local\ms-playwright` | leaf | 安全清理 | Playwright 下载的浏览器（Chromium/Firefox/WebKit）。 | 可清理；npx playwright install 会重新下载。 |
| `dev-playwright-mcp` | `suffix` `\AppData\Local\ms-playwright-mcp` | leaf | 安全清理 | Playwright MCP 下载的浏览器缓存。 | 可清理；需要时会重新下载。 |
| `dev-puppeteer-cache` | `suffix` `\.cache\puppeteer` | leaf | 安全清理 | Puppeteer 下载的 Chrome for Testing 浏览器。 | 可清理；npx puppeteer browsers install 会重新下载。 |
| `dev-rustup-downloads` | `suffix` `\.rustup\downloads` | leaf | 安全清理 | Rustup 下载工具链/组件时的临时包。 | 可清理。 |
| `dev-rustup-root` | `suffix` `\.rustup` | container · 不可选 | 谨慎清理 | Rustup 根目录：含已安装工具链（toolchains）与下载/临时缓存。 | 不要整体删除；工具链用 rustup toolchain uninstall 管理，只清理 downloads/tmp 缓存。 |
| `dev-rustup-tmp` | `suffix` `\.rustup\tmp` | leaf | 安全清理 | Rustup 安装过程中的临时文件。 | 可清理。 |
| `dev-tauri` | `suffix` `\AppData\Local\tauri` | container | 谨慎清理 | Tauri 应用的 WebView2 缓存根目录（按应用分子目录）。 | 不要整体删除；确认各应用子目录用途后再清理。 |
| `godot-temp` | `suffix` `\AppData\Local\Temp\Godot` | leaf | 安全清理 | Godot 编辑器生成的临时/缓存数据。 | 关闭 Godot 后可清理。 |
| `jetbrains-caches` | `glob` `*\AppData\Local\JetBrains\*\caches` | leaf | 安全清理 | IntelliJ IDEA/PyCharm/WebStorm 等的索引与缓存。 | 关闭对应 IDE 后清理；下次打开会重建索引。 |
| `jetbrains-logs` | `glob` `*\AppData\Local\JetBrains\*\logs` | leaf | 安全清理 | JetBrains IDE 日志。 | 可清理。 |
| `jetbrains-tmp` | `glob` `*\AppData\Local\JetBrains\*\tmp` | leaf | 安全清理 | JetBrains IDE 的临时文件。 | 关闭对应 IDE 后清理。 |
| `qoder-cache` | `suffix` `\Qoder\Cache` | leaf | 安全清理 | Qoder 的网页/扩展缓存。 | 关闭 Qoder 后清理。 |
| `qoder-cacheddata` | `suffix` `\Qoder\CachedData` | leaf | 安全清理 | Qoder 的 JavaScript 编译缓存。 | 关闭 Qoder 后清理。 |
| `qoder-code-cache` | `suffix` `\Qoder\Code Cache` | leaf | 安全清理 | Qoder 的代码编译缓存。 | 关闭 Qoder 后清理。 |
| `qoder-gpucache` | `suffix` `\Qoder\GPUCache` | leaf | 安全清理 | Qoder 的 GPU 渲染缓存。 | 关闭 Qoder 后清理。 |
| `qoder-logs` | `suffix` `\Qoder\logs` | leaf | 安全清理 | Qoder 运行日志。 | 可清理。 |
| `trae-cn-backups` | `suffix` `\Trae CN\Backups` | leaf | 谨慎清理 | Trae CN 热退出备份的未保存文件。 | 确认没有未保存的工作后清理。 |
| `trae-cn-cache` | `suffix` `\Trae CN\Cache` | leaf | 安全清理 | Trae CN 的网页/扩展缓存。 | 关闭 Trae 后清理。 |
| `trae-cn-cachedconfig` | `suffix` `\Trae CN\CachedConfigurations` | leaf | 安全清理 | Trae CN 的配置缓存。 | 关闭 Trae 后清理。 |
| `trae-cn-cacheddata` | `suffix` `\Trae CN\CachedData` | leaf | 安全清理 | Trae CN 的 JavaScript 编译缓存。 | 关闭 Trae 后清理。 |
| `trae-cn-cachedprofiles` | `suffix` `\Trae CN\CachedProfilesData` | leaf | 安全清理 | Trae CN 配置文件（Profile）的缓存数据。 | 关闭 Trae 后清理。 |
| `trae-cn-cachedvsix` | `suffix` `\Trae CN\CachedExtensionVSIXs` | leaf | 安全清理 | Trae CN 下载的扩展安装包缓存。 | 关闭 Trae 后清理。 |
| `trae-cn-code-cache` | `suffix` `\Trae CN\Code Cache` | leaf | 安全清理 | Trae CN 的代码编译缓存。 | 关闭 Trae 后清理。 |
| `trae-cn-crashpad` | `suffix` `\Trae CN\Crashpad` | leaf | 安全清理 | Trae CN 崩溃报告缓存。 | 可清理。 |
| `trae-cn-dawn-cache` | `glob` `*\Trae CN\*Dawn*Cache*` | leaf | 安全清理 | Trae CN 的 DawnGraphiteCache/DawnWebGPUCache 图形缓存。 | 关闭 Trae 后清理。 |
| `trae-cn-gpucache` | `suffix` `\Trae CN\GPUCache` | leaf | 安全清理 | Trae CN 的 GPU 渲染缓存。 | 关闭 Trae 后清理。 |
| `trae-cn-logs` | `suffix` `\Trae CN\logs` | leaf | 安全清理 | Trae CN 运行日志。 | 可清理。 |
| `vs-component-model-cache` | `glob` `*\AppData\Local\Microsoft\VisualStudio\*\ComponentModelCache` | leaf | 安全清理 | Visual Studio 的组件/扩展元数据缓存。 | 关闭 Visual Studio 后清理。 |
| `vs-designer-cache` | `glob` `*\AppData\Local\Microsoft\VisualStudio\*\DesignerCache` | leaf | 安全清理 | Visual Studio 窗体/设计器缓存。 | 关闭 Visual Studio 后清理。 |
| `vscode-cache` | `suffix` `\AppData\Roaming\Code\Cache` | leaf | 安全清理 | VS Code 的网页/扩展缓存。 | 关闭 VS Code 后清理。 |
| `vscode-cachedconfigurations` | `suffix` `\Code\CachedConfigurations` | leaf | 安全清理 | VS Code 的配置缓存。 | 关闭 VS Code 后清理。 |
| `vscode-cacheddata` | `suffix` `\AppData\Roaming\Code\CachedData` | leaf | 安全清理 | VS Code 的 JavaScript 编译缓存。 | 关闭 VS Code 后清理。 |
| `vscode-cachedextensionvsixs` | `suffix` `\Code\CachedExtensionVSIXs` | leaf | 安全清理 | VS Code 下载的扩展安装包缓存。 | 关闭 VS Code 后清理。 |
| `vscode-cachedprofilesdata` | `suffix` `\Code\CachedProfilesData` | leaf | 安全清理 | VS Code 配置文件（Profile）的缓存数据。 | 关闭 VS Code 后清理。 |
| `vscode-code-cache` | `suffix` `\AppData\Roaming\Code\Code Cache` | leaf | 安全清理 | VS Code 的代码编译缓存。 | 关闭 VS Code 后清理。 |
| `vscode-crashpad` | `suffix` `\AppData\Roaming\Code\Crashpad` | leaf | 安全清理 | VS Code 的崩溃报告缓存。 | 可清理。 |
| `vscode-gpucache` | `suffix` `\AppData\Roaming\Code\GPUCache` | leaf | 安全清理 | VS Code 的 GPU 渲染缓存。 | 关闭 VS Code 后清理。 |
| `vscode-logs` | `suffix` `\AppData\Roaming\Code\logs` | leaf | 安全清理 | VS Code 运行日志。 | 可清理。 |
| `zed-db` | `suffix` `\Zed\db` | leaf | 谨慎清理 | Zed 的工作区/最近项目数据库。 | 确认不再需要工作区状态后清理。 |
| `zed-extensions` | `suffix` `\Zed\extensions` | leaf | 谨慎清理 | Zed 已安装的扩展。 | 在 Zed 内管理扩展；直接删除会丢失扩展状态。 |
| `zed-logs` | `suffix` `\Zed\logs` | leaf | 安全清理 | Zed 编辑器运行日志。 | 可清理。 |

### 14. 包管理器缓存（29）

| ID | 匹配 | 模式 | 建议 | 说明 | 建议操作 |
| --- | --- | --- | --- | --- | --- |
| `dev-anaconda-pkgs` | `suffix` `\anaconda3\pkgs` | leaf | 安全清理 | Anaconda 下载并解压的包缓存。 | 可清理；conda clean -p 也可。 |
| `dev-bun-cache` | `suffix` `\.bun\install\cache` | leaf | 安全清理 | Bun 的包安装缓存。 | 可清理；bun install 会重新下载。 |
| `dev-cargo-git` | `suffix` `\.cargo\git` | leaf | 谨慎清理 | Cargo 从 Git 仓库拉取的依赖缓存。 | 确认没有依赖特定 Git 提交的离线构建后再清理。 |
| `dev-cargo-registry-cache` | `suffix` `\.cargo\registry\cache` | leaf | 安全清理 | Rust/Cargo 下载的 crate 压缩包缓存。 | 可清理；cargo 会重新下载。 |
| `dev-cargo-registry-src` | `suffix` `\.cargo\registry\src` | leaf | 安全清理 | Rust/Cargo 解压后的 crate 源码缓存。 | 可清理；cargo 会重新解压/下载。 |
| `dev-composer-cache` | `suffix` `\AppData\Local\Composer\cache` | leaf | 安全清理 | Composer 下载的包与元数据缓存。 | 可清理；composer install 会重新下载。 |
| `dev-conda-pkgs` | `suffix` `\.conda\pkgs` | leaf | 安全清理 | Conda 下载并解压的包缓存。 | 可清理；conda clean -p 也可。 |
| `dev-go-mod-cache` | `suffix` `\go\pkg\mod\cache` | leaf | 安全清理 | Go 下载的模块压缩包与校验缓存。 | 可清理；go mod download 会重新下载。 |
| `dev-ivy-cache` | `suffix` `\.ivy2\cache` | leaf | 安全清理 | Ivy/SBT 下载的依赖缓存。 | 可清理；下次构建会重新下载。 |
| `dev-m2-repo` | `suffix` `\.m2\repository` | leaf | 谨慎清理 | Maven 下载的依赖与本地安装的构件。 | 确认没有本地 install 的私有构件后再清理；否则会丢失本地包。 |
| `dev-miniconda-pkgs` | `suffix` `\miniconda3\pkgs` | leaf | 安全清理 | Miniconda 下载并解压的包缓存。 | 可清理；conda clean -p 也可。 |
| `dev-npm-cache-local` | `suffix` `\AppData\Local\npm-cache` | leaf | 安全清理 | 新版 npm 的全局缓存目录。 | 可清理；npm cache clean --force 也可。 |
| `dev-npm-cache-roaming` | `suffix` `\AppData\Roaming\npm-cache` | leaf · 需管理员 | 建议清理 | 旧版 npm 的全局缓存目录。 | 可清理；npm cache clean --force 也可。 |
| `dev-npm-cache-user` | `basename` `npm-cache` | leaf | 安全清理 | npm 缓存目录（用户自定义 cache 位置）。 | 可清理；npm cache clean --force 也可。 |
| `dev-npm-home` | `suffix` `\.npm` | leaf | 安全清理 | npm 的用户级缓存与日志目录。 | 可清理；npm cache clean --force 也可。 |
| `dev-nuget-packages` | `suffix` `\.nuget\packages` | leaf | 谨慎清理 | .NET 的全局 NuGet 包缓存。 | 确认没有离线构建需求后再清理；下次还原会重新下载。 |
| `dev-nuget-plugins` | `suffix` `\AppData\Local\NuGet\plugins-cache` | leaf | 安全清理 | NuGet 插件缓存。 | 可清理。 |
| `dev-nuget-v3` | `suffix` `\AppData\Local\NuGet\v3-cache` | leaf | 安全清理 | NuGet 的 HTTP/包元数据缓存。 | 可清理。 |
| `dev-pip-cache` | `suffix` `\AppData\Local\pip\Cache` | leaf | 安全清理 | pip 下载的 wheel/sdist 与 HTTP 缓存。 | 可清理；pip cache purge 也可。 |
| `dev-pip-root` | `suffix` `\AppData\Local\pip` | container | 谨慎清理 | pip 数据目录，含下载缓存。 | 只清理其中明确标记的 Cache 子目录。 |
| `dev-pnpm-cache-dir` | `suffix` `\AppData\Local\pnpm-cache` | leaf | 安全清理 | pnpm 的元数据/包缓存（cache-dir）。 | 可清理；会重新下载。 |
| `dev-pnpm-root` | `suffix` `\AppData\Local\pnpm` | container | 谨慎清理 | pnpm 数据目录，含全局存储与全局安装包。 | 只清理其中明确标记的 store 子目录（优先 pnpm store prune）。 |
| `dev-pnpm-store` | `suffix` `\AppData\Local\pnpm\store` | leaf | 谨慎清理 | pnpm 的全局包存储，已有项目的 node_modules 通过硬链接引用它。 | 优先用 pnpm store prune；直接删除可能破坏已有项目的依赖链接。 |
| `dev-pub-cache` | `suffix` `\.pub-cache` | leaf | 安全清理 | Dart/Flutter 下载的依赖包缓存。 | 可清理；flutter pub get 会重新下载。 |
| `dev-sbt-boot` | `suffix` `\.sbt\boot` | leaf | 安全清理 | SBT 启动器与 Scala 版本缓存。 | 可清理；下次启动会重新下载。 |
| `dev-uv-cache` | `suffix` `\AppData\Local\uv\cache` | leaf | 谨慎清理 | uv 的全局包/构建缓存。 | 优先用 uv cache prune（安全）或 uv cache clean；手动删除前确认没有 uv 进程。 |
| `dev-uv-data` | `suffix` `\AppData\Roaming\uv` | container | 谨慎清理 | uv 数据目录，含 uv 管理的 Python 安装。 | 不要整体删除；用 uv python uninstall 管理不用的 Python 版本。 |
| `dev-yarn-berry` | `suffix` `\AppData\Local\Yarn\Berry\cache` | leaf | 安全清理 | Yarn v2+ 的包缓存。 | 可清理。 |
| `dev-yarn-cache` | `suffix` `\AppData\Local\Yarn\Cache` | leaf | 安全清理 | Yarn v1 的包缓存。 | 可清理；yarn cache clean 也可。 |

### 15. AI/模型缓存（3）

| ID | 匹配 | 模式 | 建议 | 说明 | 建议操作 |
| --- | --- | --- | --- | --- | --- |
| `dev-huggingface-cache` | `suffix` `\.cache\huggingface` | leaf | 谨慎清理 | Hugging Face 下载的模型/数据集缓存，可能数十 GB。 | 确认不再需要离线模型后清理；重新下载可能很慢/需要网络。 |
| `dev-lmstudio-models` | `suffix` `\.lmstudio\models` | leaf | 谨慎清理 | LM Studio 下载的本地模型。 | 在 LM Studio 中删除不用的模型；直接删目录可能破坏索引。 |
| `dev-ollama-models` | `suffix` `\.ollama\models` | leaf | 谨慎清理 | Ollama 下载的本地大模型。 | 用 ollama rm <model> 删除不用的模型；直接删目录会破坏清单。 |

### 16. 项目构建产物（44）

| ID | 匹配 | 模式 | 建议 | 说明 | 建议操作 |
| --- | --- | --- | --- | --- | --- |
| `dev-angular` | `basename` `.angular` | leaf | 安全清理 | Angular CLI 的构建缓存。 | 可清理；重新构建会生成。 |
| `dev-astro` | `basename` `.astro` | leaf | 安全清理 | Astro 的生成文件与缓存。 | 可清理；重新运行会生成。 |
| `dev-aws-sam` | `basename` `.aws-sam` | leaf | 安全清理 | AWS SAM 的构建缓存与打包产物。 | 可清理；sam build 会重新生成。 |
| `dev-bower` | `basename` `bower_components` | leaf | 安全清理 | Bower 安装的前端依赖。 | 可清理；bower install 会重新下载。 |
| `dev-build` | `basename` `build` | leaf | 谨慎清理 | 项目构建输出目录，通常可重新生成。 | 确认没有需要保留的构建产物后再清理。 |
| `dev-cmake-build` | `basename` `cmake-build-*` | leaf | 谨慎清理 | CLion/CMake 的构建输出目录。 | 可清理；重新构建会生成。 |
| `dev-cmake-files` | `basename` `CMakeFiles` | leaf | 安全清理 | CMake 生成的中间构建文件。 | 可清理；重新配置/构建会生成。 |
| `dev-coverage` | `basename` `coverage` | leaf | 安全清理 | 测试覆盖率工具生成的报告目录。 | 可清理；重新跑测试会生成。 |
| `dev-cs-bin` | `basename` `bin` | leaf | 谨慎清理 | .NET 项目的编译输出目录。 | 确认没有需要保留的构建产物后再清理。 |
| `dev-cs-obj` | `basename` `obj` | leaf | 安全清理 | .NET 项目的中间编译文件。 | 可清理；重新构建会生成。 |
| `dev-dart-tool` | `basename` `.dart_tool` | leaf | 安全清理 | Dart/Flutter 项目的构建与包配置缓存。 | 可清理；flutter pub get 会重新生成。 |
| `dev-dist` | `basename` `dist` | leaf | 谨慎清理 | 打包/发布产物目录，通常可重新构建。 | 确认没有已发布版本需要保留后再清理。 |
| `dev-esbuild` | `basename` `.esbuild` | leaf | 安全清理 | esbuild 的构建缓存。 | 可清理。 |
| `dev-expo` | `basename` `.expo` | leaf | 谨慎清理 | Expo 项目的本地缓存与开发配置。 | 确认没有需要保留的本地开发配置后再清理。 |
| `dev-gradle-project` | `basename` `.gradle` | leaf | 谨慎清理 | 项目根目录下的 Gradle 配置/文件哈希缓存。 | 可清理；下次构建会重新生成。 |
| `dev-htmlcov` | `basename` `htmlcov` | leaf | 安全清理 | pytest-cov 生成的 HTML 覆盖率报告。 | 可清理；重新跑测试会生成。 |
| `dev-jspm` | `basename` `jspm_packages` | leaf | 安全清理 | JSPM 安装的前端依赖。 | 可清理；jspm install 会重新下载。 |
| `dev-mypy-cache` | `basename` `.mypy_cache` | leaf | 安全清理 | mypy 类型检查的增量缓存。 | 可清理；下次检查会重新生成。 |
| `dev-next` | `basename` `.next` | leaf | 安全清理 | Next.js 的开发/构建缓存。 | 可清理；next dev/build 会重新生成。 |
| `dev-node-modules` | `basename` `node_modules` | leaf | 安全清理 | npm/pnpm/yarn 安装的项目依赖，通常包含大量小文件。 | 可清理；在项目根目录重新 npm install / pnpm install / yarn 即可恢复（建议有锁文件）。 |
| `dev-nox` | `basename` `.nox` | leaf | 安全清理 | nox 创建的测试虚拟环境。 | 可清理；nox 会重新创建。 |
| `dev-nuxt` | `basename` `.nuxt` | leaf | 安全清理 | Nuxt 的开发/构建缓存。 | 可清理；重新运行会生成。 |
| `dev-nuxt-output` | `basename` `.output` | leaf | 谨慎清理 | Nuxt/Nitro 的构建输出。 | 确认没有需要保留的部署产物后再清理。 |
| `dev-nyc` | `basename` `.nyc_output` | leaf | 安全清理 | nyc/Istanbul 生成的覆盖率中间数据。 | 可清理；重新跑测试会生成。 |
| `dev-out` | `basename` `out` | leaf | 谨慎清理 | 项目输出目录，通常是构建/运行产物。 | 确认没有需要保留的输出后再清理。 |
| `dev-parcel` | `basename` `.parcel-cache` | leaf | 安全清理 | Parcel 的构建缓存。 | 可清理；重新构建会生成。 |
| `dev-pods` | `basename` `Pods` | leaf | 谨慎清理 | iOS 项目的 CocoaPods 依赖副本。 | 可清理；pod install 会重新生成。 |
| `dev-pycache` | `basename` `__pycache__` | leaf | 安全清理 | Python 导入模块时生成的 .pyc 缓存。 | 可清理；下次导入会重新生成。 |
| `dev-pytest-cache` | `basename` `.pytest_cache` | leaf | 安全清理 | pytest 的测试结果与上次失败缓存。 | 可清理。 |
| `dev-rollup` | `basename` `.rollup.cache` | leaf | 安全清理 | Rollup 的构建缓存。 | 可清理。 |
| `dev-ruff-cache` | `basename` `.ruff_cache` | leaf | 安全清理 | ruff 的增量检查缓存。 | 可清理。 |
| `dev-serverless` | `basename` `.serverless` | leaf | 安全清理 | Serverless Framework 的构建缓存与打包产物。 | 可清理；重新部署会生成。 |
| `dev-svelte-kit` | `basename` `.svelte-kit` | leaf | 安全清理 | SvelteKit 的生成文件与缓存。 | 可清理；重新运行会生成。 |
| `dev-target` | `basename` `target` | leaf | 谨慎清理 | Rust/Maven 的编译输出目录，通常可重新生成。 | 确认没有需要保留的构建产物后再清理。 |
| `dev-terraform` | `basename` `.terraform` | leaf | 安全清理 | Terraform 下载的 provider/module 缓存（state 通常在目录外的 .tfstate）。 | 可清理；terraform init 会重新下载。 |
| `dev-terragrunt` | `basename` `.terragrunt-cache` | leaf | 安全清理 | Terragrunt 生成的临时工作目录。 | 可清理。 |
| `dev-tox` | `basename` `.tox` | leaf | 安全清理 | tox 创建的测试虚拟环境。 | 可清理；tox 会重新创建。 |
| `dev-turbo` | `basename` `.turbo` | leaf | 安全清理 | Turborepo 的本地任务缓存。 | 可清理；下次任务会重新执行。 |
| `dev-vendor` | `basename` `vendor` | leaf | 谨慎清理 | PHP Composer 或 Go 的依赖副本。 | 确认有锁文件、可以重新下载后再清理。 |
| `dev-venv` | `basename` `.venv` | leaf | 安全清理 | Python 项目的虚拟环境（含解释器与已安装依赖）。 | 可清理；用 uv sync / python -m venv 重新创建。 |
| `dev-venv-env` | `basename` `env` | leaf | 安全清理 | Python 项目的虚拟环境（env 命名，含 pyvenv.cfg）。 | 可清理；重新创建即可。 |
| `dev-venv-plain` | `basename` `venv` | leaf | 安全清理 | Python 项目的虚拟环境（venv 命名）。 | 可清理；重新创建即可。 |
| `dev-vs` | `basename` `.vs` | leaf | 安全清理 | Visual Studio 的 .vs 隐藏缓存目录。 | 关闭 Visual Studio 后可清理；重新打开会生成。 |
| `dev-webpack` | `basename` `.webpack` | leaf | 安全清理 | webpack 的持久化缓存（部分脚手架使用）。 | 可清理；重新构建会生成。 |

### 17. 项目配置（保留）（4）

| ID | 匹配 | 模式 | 建议 | 说明 | 建议操作 |
| --- | --- | --- | --- | --- | --- |
| `dev-git` | `basename` `.git` | skip | 保留 | Git 版本库的提交历史、分支与配置。 | 禁止删除；删除会丢失全部本地历史。 |
| `dev-idea` | `basename` `.idea` | skip | 保留 | IntelliJ/PyCharm 等项目的配置与运行配置。 | 保留；通常需要入库或复用。 |
| `dev-vscode-dir` | `basename` `.vscode` | skip | 保留 | 项目的 VS Code 配置（任务、调试、推荐扩展）。 | 保留；通常需要入库。 |
| `obsidian-vault-config` | `basename` `.obsidian` | leaf | 保留 | Obsidian vault 内的配置：热键、主题、社区插件与工作区。 | 保留；随 vault 一起备份。 |

### 18. 凭据/配置（保留）（18）

| ID | 匹配 | 模式 | 建议 | 说明 | 建议操作 |
| --- | --- | --- | --- | --- | --- |
| `app-wps-kaccountsdk` | `suffix` `\kingsoft\kaccountsdk` | leaf | 保留 | WPS 账号 SDK 的登录态与本地存储。 | 禁止删除。 |
| `app-zcode-credentials` | `suffix` `\.zcode\v2\credentials` | leaf | 保留 | ZCode 的登录凭据。 | 禁止删除。 |
| `app-zed-settings` | `suffix` `\AppData\Roaming\Zed` | leaf | 保留 | Zed 编辑器的设置（settings.json/keymap.json/tasks.json）。 | 保留。 |
| `gog-storage` | `suffix` `\GOG.com\Galaxy\storage` | leaf | 保留 | GOG Galaxy 的登录会话、设置与游戏库数据库。 | 禁止删除。 |
| `secret-1password` | `suffix` `\AppData\Local\1Password` | leaf | 保留 | 1Password 的加密本地库与应用数据。 | 禁止删除。 |
| `secret-1password-roaming` | `suffix` `\AppData\Roaming\1Password` | leaf | 保留 | 1Password 的设置与缓存。 | 禁止删除。 |
| `secret-aws` | `basename` `.aws` | skip | 保留 | AWS CLI 的配置与访问密钥。 | 禁止删除。 |
| `secret-azure` | `basename` `.azure` | skip | 保留 | Azure CLI 的配置与登录状态。 | 禁止删除。 |
| `secret-bitwarden` | `suffix` `\AppData\Roaming\Bitwarden` | leaf | 保留 | Bitwarden 的加密库（data.json）与设置。 | 禁止删除。 |
| `secret-composer-home` | `suffix` `\AppData\Roaming\Composer` | leaf | 保留 | Composer 全局配置与 auth.json（私有仓库凭据）。 | 禁止删除。 |
| `secret-docker` | `basename` `.docker` | skip | 保留 | Docker CLI 的配置与 registry 凭据。 | 禁止删除。 |
| `secret-gnupg` | `basename` `.gnupg` | skip | 保留 | GPG 密钥环与配置。 | 禁止删除。 |
| `secret-kube` | `basename` `.kube` | skip | 保留 | kubeconfig 与集群凭据。 | 禁止删除。 |
| `secret-ms-credentials` | `suffix` `\Microsoft\Credentials` | leaf | 保留 | Windows 凭据管理器保存的凭据。 | 禁止删除。 |
| `secret-ms-tokenbroker` | `suffix` `\Microsoft\TokenBroker` | leaf | 保留 | Windows 令牌代理（Web 账户令牌）缓存。 | 禁止删除。 |
| `secret-ms-vault` | `suffix` `\Microsoft\Vault` | leaf | 保留 | Windows Vault 的凭据存储。 | 禁止删除。 |
| `secret-ssh` | `basename` `.ssh` | skip | 保留 | SSH 私钥、公钥与 known_hosts。 | 禁止删除。 |
| `secret-telegram-tdata` | `suffix` `\Telegram Desktop\tdata` | leaf | 保留 | Telegram 的加密账号授权密钥、设置与本地消息缓存。 | 禁止删除；清理缓存请用 Telegram 内置功能。 |

### 19. 游戏平台（30）

| ID | 匹配 | 模式 | 建议 | 说明 | 建议操作 |
| --- | --- | --- | --- | --- | --- |
| `app-epic-games` | `suffix` `\AppData\Local\Epic Games` | container | 谨慎清理 | Epic Games 数据目录，可能含游戏本体与启动器数据。 | 不要整体删除；卸载游戏请用启动器。 |
| `app-hoyoplay` | `suffix` `\AppData\Roaming\HoYoPlay` | container | 谨慎清理 | HoYoPlay 启动器数据目录。 | 不要整体删除；只清理缓存/临时子目录。 |
| `app-hoyoverse` | `suffix` `\AppData\Local\HoYoverse` | container | 谨慎清理 | HoYoverse 各游戏/启动器数据目录，含登录令牌与缓存。 | 不要整体删除；确认子目录用途后再清理。 |
| `app-krlauncher` | `suffix` `\AppData\Roaming\KRLauncher` | container | 谨慎清理 | 库洛游戏启动器（KRLauncher）数据目录。 | 不要整体删除；确认子目录用途后再清理。 |
| `battlenet-cache` | `suffix` `\AppData\Local\Battle.net\Cache` | leaf | 安全清理 | Battle.net 客户端缓存。 | 退出 Battle.net 后清理。 |
| `battlenet-cache2` | `suffix` `\AppData\Local\Blizzard Entertainment\Battle.net\Cache` | leaf | 安全清理 | Blizzard Battle.net 客户端缓存。 | 退出 Battle.net 后清理。 |
| `ea-cache` | `suffix` `\Electronic Arts\EA Desktop\cache` | leaf | 安全清理 | EA Desktop 客户端缓存。 | 退出 EA 后清理。 |
| `ea-cef-cache` | `suffix` `\Electronic Arts\EA Desktop\CEF\BrowserCache` | leaf | 安全清理 | EA Desktop 内置浏览器缓存。 | 退出 EA 后清理。 |
| `ea-igocache` | `suffix` `\Electronic Arts\EA Desktop\IGOCache` | leaf | 安全清理 | EA Desktop 游戏内覆盖（IGO）缓存。 | 退出 EA 后清理。 |
| `ea-logs` | `suffix` `\Electronic Arts\EA Desktop\Logs` | leaf | 安全清理 | EA Desktop 日志。 | 可清理。 |
| `epic-logs` | `suffix` `\AppData\Local\EpicGamesLauncher\Saved\Logs` | leaf | 安全清理 | Epic Games 启动器日志。 | 可清理。 |
| `epic-webcache` | `suffix` `\AppData\Local\EpicGamesLauncher\Saved\webcache` | leaf | 安全清理 | Epic Games 启动器的网页缓存。 | 退出启动器后清理。 |
| `game-com-proximabeta` | `suffix` `\AppData\LocalLow\com_proximabeta` | container | 谨慎清理 | NIKKE 发行商（Proxima Beta）的 LocalLow 数据目录。 | 不要整体删除；只清理明确标记的资源缓存子目录。 |
| `game-hypergryph` | `suffix` `\AppData\LocalLow\Hypergryph` | container | 谨慎清理 | 鹰角网络（明日方舟等）游戏 LocalLow 数据目录。 | 不要整体删除；确认子目录用途后再清理。 |
| `game-nikke-saus` | `suffix` `\com_proximabeta\NIKKE\saus` | leaf | 安全清理 | NIKKE 的语言/资源缓存（如韩语资源），可重新下载。 | 退出游戏后清理。 |
| `game-nikke-unity-cache` | `suffix` `\Unity\com_proximabeta_NIKKE` | leaf | 安全清理 | NIKKE（胜利女神）Unity 侧的哈希分片资源缓存（__data/__info），可重新下载。 | 退出游戏后清理。 |
| `game-unity-locallow` | `suffix` `\AppData\LocalLow\Unity` | container | 谨慎清理 | Unity 游戏/引擎的 LocalLow 数据目录，可能含游戏存档与资源缓存。 | 不要整体删除；确认各游戏子目录用途后再清理。 |
| `gog-logs` | `suffix` `\GOG.com\Galaxy\logs` | leaf | 安全清理 | GOG Galaxy 日志。 | 可清理。 |
| `gog-webcache` | `suffix` `\GOG.com\Galaxy\webcache` | leaf | 安全清理 | GOG Galaxy 商店/界面网页资源缓存（ProgramData 或 Local）。 | 退出 Galaxy 后清理。 |
| `hoyoplay-cache` | `suffix` `\HoYoPlay\Cache` | leaf | 安全清理 | HoYoPlay 启动器缓存。 | 退出启动器后清理。 |
| `hoyoplay-temp` | `suffix` `\HoYoPlay\Temp` | leaf | 安全清理 | HoYoPlay 启动器临时文件。 | 退出启动器后清理。 |
| `rockstar-launcher-cache` | `suffix` `\Rockstar Games\Launcher\Cache` | leaf | 安全清理 | Rockstar Games 启动器缓存（Documents 下）。 | 退出启动器后清理。 |
| `rockstar-socialclub-cache` | `suffix` `\Rockstar Games\Social Club\Cache` | leaf | 安全清理 | Rockstar Social Club 缓存。 | 退出 Social Club 后清理。 |
| `steam-common` | `suffix` `\AppData\Local\Steam\steamapps\common` | skip | 保留 | Steam 游戏本体安装目录。 | 保留；卸载游戏请用 Steam 客户端。 |
| `steam-downloading` | `suffix` `\AppData\Local\Steam\steamapps\downloading` | leaf | 安全清理 | Steam 游戏下载/更新中的临时文件。 | 确认没有正在下载/更新的游戏后清理。 |
| `steam-htmlcache` | `suffix` `\AppData\Local\Steam\htmlcache` | leaf | 安全清理 | Steam 客户端的网页缓存。 | 退出 Steam 后清理。 |
| `steam-temp` | `suffix` `\AppData\Local\Steam\steamapps\temp` | leaf | 安全清理 | Steam 安装/更新过程的临时文件。 | 确认没有正在下载/更新的游戏后清理。 |
| `steam-workshop` | `suffix` `\AppData\Local\Steam\steamapps\workshop` | leaf | 谨慎清理 | 已订阅的 Steam 创意工坊模组/地图。 | 在 Steam 中取消订阅后再清理；直接删除可能被重新下载。 |
| `ubisoft-cache` | `suffix` `\Ubisoft Game Launcher\cache` | leaf | 安全清理 | Ubisoft Connect 客户端缓存。 | 退出 Ubisoft Connect 后清理。 |
| `xboxgames` | `suffix` `\AppData\Local\Microsoft\XboxGames` | skip | 保留 | Xbox 应用安装的游戏。 | 保留；卸载游戏请用 Xbox 应用/设置。 |

### 20. 虚拟机/容器（3）

| ID | 匹配 | 模式 | 建议 | 说明 | 建议操作 |
| --- | --- | --- | --- | --- | --- |
| `docker-vhdx` | `glob` `*\AppData\Local\Docker\wsl\*\*.vhdx` | leaf · 文件 · 不可选 | 保留 | Docker Desktop 的 WSL2 数据盘，镜像/容器/卷都存在这里，文件只增不减。 | 先 docker system prune，再关闭 Docker 并 wsl --shutdown，最后用 Optimize-VHD/diskpart 压缩；不要直接删 VHDX。 |
| `wsl-vhdx` | `glob` `*\AppData\Local\Packages\*\LocalState\*.vhdx` | leaf · 文件 · 不可选 | 保留 | WSL 发行版的虚拟磁盘，包含该发行版的整个文件系统。 | 保留；需要回收空间时先清理发行版内部文件，再 wsl --shutdown 后压缩 VHDX。 |
| `wsl-vhdx-nested` | `glob` `*\AppData\Local\Packages\*\LocalState\*\*.vhdx` | leaf · 文件 · 不可选 | 保留 | 部分 WSL 发行版将 VHDX 放在 LocalState 的子目录中。 | 保留；用 WSL 命令清理/压缩。 |

### 21. 运行时/安装（保留）（29）

工具自带运行时与已安装组件：内部的 `node_modules` 是运行时依赖，不是项目依赖，通用项目缓存规则不得将其标为安全清理。子路径 glob 规则（优先级高于 basename）用于直接以子路径为根的扫描兜底。

| ID | 匹配 | 模式 | 建议 | 说明 | 建议操作 |
| --- | --- | --- | --- | --- | --- |
| `app-jianying-apps` | `suffix` `\JianyingPro\Apps` | leaf | 保留 | 剪映专业版的程序版本安装目录。 | 禁止删除；卸载请走系统设置。 |
| `helium-application` | `suffix` `\imput\Helium\Application` | leaf | 保留 | Helium 浏览器程序本体（chrome.exe 等）。 | 禁止删除；卸载请走系统设置。 |
| `rt-bun-bin` | `suffix` `\.bun\bin` | leaf | 保留 | Bun 运行时可执行文件（bun.exe）。 | 禁止删除。 |
| `rt-cargo-bin` | `suffix` `\.cargo\bin` | leaf · 不可选 | 保留 | cargo install 安装的可执行文件（rustup 代理也在其中）。 | 禁止删除；用 cargo uninstall 管理不用的命令。 |
| `rt-claude-3p-code` | `suffix` `\Claude-3p\claude-code` | leaf | 保留 | Claude-3p 内置的 claude-code 运行时（按版本存放）。 | 禁止删除；由应用自行管理。 |
| `rt-claude-3p-code-vm` | `suffix` `\Claude-3p\claude-code-vm` | leaf | 保留 | Claude-3p 内置的 claude-code 沙箱运行时。 | 禁止删除；由应用自行管理。 |
| `rt-codex-node-modules` | `glob` `*\.cache\codex-runtimes\*\node_modules` | leaf · 不可选 | 保留 | Codex 运行时自带的 node_modules，是运行时依赖而非项目依赖。 | 禁止删除。 |
| `rt-codex-runtimes` | `suffix` `\.cache\codex-runtimes` | leaf · 不可选 | 保留 | Codex CLI 自带的 Node/Python 运行时及依赖，可能并存 previous-* 旧版本。 | 禁止删除；运行时由 Codex 自行下载与更新。 |
| `rt-fnm-node-modules` | `glob` `*\fnm\node-versions\*\node_modules` | leaf · 不可选 | 保留 | fnm 安装的 Node.js 版本内的 node_modules（含全局包）。 | 禁止删除。 |
| `rt-fnm-node-versions` | `suffix` `\fnm\node-versions` | leaf · 不可选 | 保留 | fnm 安装的各版本 Node.js 运行时，installation 内含全局 node_modules。 | 禁止整体删除；用 fnm uninstall <version> 管理不用的版本。 |
| `rt-nodejs-bundled` | `suffix` `\nodejs\node_modules` | leaf · 不可选 | 保留 | Node.js 安装目录自带的 npm/corepack 等依赖。 | 禁止删除；随 Node.js 安装器管理。 |
| `rt-npm-global` | `suffix` `\AppData\Roaming\npm\node_modules` | leaf · 不可选 | 保留 | npm i -g 全局安装的包，不是项目依赖。 | 禁止整体删除；用 npm uninstall -g <pkg> 管理不用的包。 |
| `rt-nvm-windows` | `suffix` `\AppData\Roaming\nvm` | leaf · 不可选 | 保留 | nvm-windows 安装的各版本 Node.js 与设置。 | 禁止整体删除；用 nvm uninstall <version> 管理不用的版本。 |
| `rt-openai-codex-bin` | `suffix` `\OpenAI\Codex\bin` | leaf | 保留 | OpenAI Codex 桌面版的可执行文件目录。 | 禁止删除；由应用自行管理。 |
| `rt-openai-codex-node-modules` | `glob` `*\OpenAI\Codex\runtimes\*\node_modules` | leaf · 不可选 | 保留 | OpenAI Codex 桌面版运行时自带的 node_modules。 | 禁止删除。 |
| `rt-openai-codex-runtimes` | `suffix` `\AppData\Local\OpenAI\Codex\runtimes` | leaf · 不可选 | 保留 | OpenAI Codex 桌面版自带运行时（cua_node 等）。 | 禁止删除；由应用自行管理。 |
| `rt-pandoc` | `suffix` `\AppData\Local\Pandoc` | leaf | 保留 | Pandoc 安装器的程序目录（pandoc.exe）。 | 禁止删除；卸载请走系统设置。 |
| `rt-python-user-site` | `suffix` `\AppData\Roaming\Python` | leaf | 保留 | pip --user 安装的包（用户级 site-packages，运行时依赖）。 | 禁止整体删除；用 pip uninstall 管理。 |
| `rt-rustup-toolchains` | `suffix` `\.rustup\toolchains` | leaf · 不可选 | 保留 | 已安装的 Rust 工具链（编译器、标准库、组件）。 | 禁止整体删除；用 rustup toolchain uninstall 管理不用的工具链。 |
| `rt-typescript-sdk` | `suffix` `\AppData\Local\Microsoft\TypeScript` | leaf · 不可选 | 保留 | Visual Studio/MSBuild 使用的 TypeScript SDK 各版本安装目录。 | 禁止删除；由 Visual Studio 安装器管理。 |
| `rt-uv-python` | `suffix` `\uv\python` | leaf | 保留 | uv python install 安装的 Python 运行时。 | 禁止整体删除；用 uv python uninstall 管理。 |
| `rt-volta` | `suffix` `\AppData\Local\Volta` | leaf | 保留 | Volta 管理的 Node/npm/pnpm/yarn 运行时、shim 与全局包。 | 禁止删除；用 volta uninstall 管理工具链。 |
| `rt-workbuddy-app` | `suffix` `\.workbuddy\app` | leaf · 不可选 | 保留 | WorkBuddy 应用本体文件。 | 禁止删除；卸载请走应用自身流程。 |
| `rt-workbuddy-binaries` | `suffix` `\.workbuddy\binaries` | leaf · 不可选 | 保留 | WorkBuddy 自带的 Node 等运行时及依赖。 | 禁止删除；由 WorkBuddy 自行管理。 |
| `rt-workbuddy-connector` | `suffix` `\.workbuddy\cli-connector-packages` | leaf · 不可选 | 保留 | WorkBuddy CLI 连接器的依赖包（含 node_modules）。 | 禁止删除；由 WorkBuddy 自行管理。 |
| `rt-workbuddy-external` | `suffix` `\.workbuddy\external-packages` | leaf · 不可选 | 保留 | WorkBuddy 下载的外部依赖包。 | 禁止删除；由 WorkBuddy 自行管理。 |
| `rt-workbuddy-node-modules` | `glob` `*\.workbuddy\binaries\*\node_modules` | leaf · 不可选 | 保留 | WorkBuddy 自带 Node 运行时的 node_modules。 | 禁止删除。 |
| `rt-workbuddy-vendor` | `suffix` `\.workbuddy\vendor` | leaf · 不可选 | 保留 | WorkBuddy 内置的第三方依赖副本。 | 禁止删除；由 WorkBuddy 自行管理。 |
| `rt-zcode-plugin-node-modules` | `glob` `*\.zcode\cli\plugins\cache\*\node_modules` | leaf · 不可选 | 保留 | ZCode CLI 已安装插件自带的 node_modules，是插件运行时依赖。 | 禁止删除。 |

## 5. 维护与校验

1. 只改 `assets/rules.json`；字段：`id`（唯一）、`title`、`category`、`scope`、`match`、`mode`、`recommendation`、`method`、`description`、`action`、`risk`，可选 `target`、`requires_admin`、`selectable`、`priority`。
2. `match.type` 支持 `exact` / `suffix` / `basename` / `glob` / `prefix` / `regex`；`basename` 可带 `requires_inside` 或 `requires_sibling_any`。
3. 运行 `windows-disk-cleanup rules --check --json`（退出码 0 才通过），再跑 `python -m unittest discover -s tests`。
4. 新增/修改规则时同步本文件的表格；JSON 更新日期写当天。
5. 规则变更属于行为变化：按仓库规范升次位版本，并在 `docs/TESTS.md` 增加回归场景。

## 6. 来源与核对日期

以下来源用于核对“哪些目录可以删、正确做法是什么”；各工具缓存位置以官方文档为准。核对日期：**2026-10-27**（2026-11-15 增补运行时保护与主流软件批次）。

- Microsoft Learn — [Clean Up the WinSxS Folder](https://learn.microsoft.com/en-us/windows-hardware/manufacture/desktop/clean-up-the-winsxs-folder)：WinSxS 不得手动删除；用 DISM/磁盘清理。
- Microsoft Learn — [Additional resources for Windows Update](https://learn.microsoft.com/en-us/troubleshoot/windows-client/installing-updates-features-roles/additional-resources-for-windows-update)：重置更新组件时停止 wuauserv/bits、重命名/清理 SoftwareDistribution。
- Microsoft Q&A — [Can I delete the data in the prefetch folder?](https://learn.microsoft.com/en-us/answers/questions/2432551/can-i-delete-the-data-in-the-prefetch-folder)：Prefetch 自维护，不建议删除。
- Microsoft Q&A — [Safe to delete Previous Windows Installation?](https://learn.microsoft.com/en-us/answers/questions/4012932/)：Windows.old 可用磁盘清理删除，删除后不可回滚。
- Microsoft Support — *Free up drive space in Windows* / *Manage drive space with Storage Sense*（2026-10-27 检索）：临时文件、回收站、以前的 Windows 安装、清理建议等系统工具路径。
- uv — [Caching](https://docs.astral.sh/uv/concepts/cache/) / [Storage reference](https://docs.astral.sh/uv/reference/storage/)：Windows 默认 `%LOCALAPPDATA%\uv\cache`，优先 `uv cache prune/clean`。
- pip — [Caching](https://pip.pypa.io/en/stable/topics/caching/)：Windows 默认 `%LocalAppData%\pip\Cache`。
- npm — [npm-cache](https://docs.npmjs.com/cli/commands/npm-cache)：缓存位置与 `npm cache clean --force`。
- pnpm — [Store settings](https://pnpm.io/settings/store)：Windows 默认 `AppData\Local\pnpm\store`，优先 `pnpm store prune`。
- Gradle — [Directory layout](https://docs.gradle.org/current/userguide/directory_layout.html)：`caches/` 下的依赖/转换缓存。
- Go — [Build and test caching](https://pkg.go.dev/cmd/go#hdr-Build_and_test_caching)：Windows 默认 `%LocalAppData%\go-build`。
- Docker — [Docker Desktop docs](https://docs.docker.com/desktop/)：WSL2 数据盘 / `docker system prune` / 压缩 VHDX 的官方背景；本工具不直接删 VHDX。
- fnm — [fnm README](https://github.com/Schniz/fnm)：`node-versions/<version>/installation` 为已安装 Node 运行时（2026-11-15 本机实测 `%APPDATA%\fnm`）。
- nvm-windows — [nvm-windows README](https://github.com/coreybutler/nvm-windows)：`%APPDATA%\nvm` 存放各版本 Node.js 与 settings.txt。
- Rustup — [The rustup book](https://rust-lang.github.io/rustup/)：`~/.rustup/toolchains` 为已安装工具链，`downloads`/`tmp` 为缓存；Cargo `~/.cargo/bin` 为已安装命令。
- npm — [npm-folders](https://docs.npmjs.com/cli/configuring-npm/folders)：全局包安装在 prefix 的 `node_modules`（Windows 默认 `%APPDATA%\npm`），与项目依赖不同。
- 本机实测（2026-11-15 扫描样本）：`.cache\codex-runtimes`、`AppData\Local\OpenAI\Codex\runtimes`、`.workbuddy\{app,binaries,vendor,external-packages,cli-connector-packages}`、`.zcode\cli\plugins\cache` 的目录结构与运行时依赖形态。
- 本机实测（2026-11-15 第二批勘察）：`Roaming\ZCode\session`、`Local\NetEase\CloudMusic`、`Local\QuarkCloudDrive\User Data`、`Roaming\Trae CN`、`Roaming\CodeBuddy CN`、`Local\CodeBuddyExtension`、`Roaming\Listary\UserProfile`、`Roaming\bilibili`、`Local\imput\Helium`（Helium 浏览器）、`Local\Claude-3p`（含 claude-code 运行时）、`LocalLow\NVIDIA\DXCache`、`Roaming\kingsoft\office6`、`Local\JianyingPro\User Data\CEF`、`Roaming\Tencent\xwechat` 的目录结构。
- Zed — [paths.rs](https://github.com/zed-industries/zed/blob/main/crates/paths/src/paths.rs) / [Troubleshooting](https://zed.dev/docs/troubleshooting)：设置 `%APPDATA%\Zed`，数据/日志 `%LOCALAPPDATA%\Zed`。
- Deno — [Environment variables](https://docs.deno.com/runtime/reference/cli/env_variables) / [deno clean](https://docs.deno.com/runtime/reference/cli/clean/)：DENO_DIR 默认 `%LOCALAPPDATA%\deno`，deps/gen/npm 等为可再生缓存，location_data 为站点持久数据。
- Volta — [volta-layout](https://github.com/volta-cli/volta/blob/main/crates/volta-layout/src/v3.rs) / [Reference](https://docs.volta.sh/reference/setup)：`tools\image` 为已解包运行时，整体保留。
- Composer — [Config](https://getcomposer.org/doc/06-config.md)：COMPOSER_HOME 默认 `%APPDATA%\Composer`（auth.json 凭据），缓存 `%LOCALAPPDATA%\Composer\cache`。
- Godot — [Data paths](https://docs.godotengine.org/en/stable/tutorials/io/data_paths.html)：编辑器数据 `%APPDATA%\Godot`，临时缓存 `%TEMP%\Godot` 关闭后可删。
- Adobe — [Clear cache](https://helpx.adobe.com/premiere-pro/kb/clear-cache.html) / [Media Cache](https://helpx.adobe.com/premiere-pro/using/media-cache.html)：`Adobe\Common\Media Cache Files`/`Media Cache`/`Peak Files` 按需重建。
- Figma — [Clear desktop cache](https://help.figma.com/hc/en-us/articles/22380853110551-Clear-the-Figma-desktop-app-cache)：`DesktopProfile` 下 Cache/Code Cache/GPUCache 可清。
- Cherry Studio — [存储设置](https://docs.cherry-ai.com/pre-basic/personalization-settings/storage)：数据目录 `%APPDATA%\CherryStudio`。
- Obsidian — [How Obsidian stores data](https://obsidian.md/help/advanced-topics/how-obsidian-stores-data)：全局配置 `%APPDATA%\Obsidian`，vault 内 `.obsidian` 为插件/配置（保留）。
- 1Password — [Deploy](https://support.1password.com/deploy-1password/)；Bitwarden — [Data storage](https://bitwarden.com/help/data-storage/)：本地加密库/凭据，保留。
- Telegram — [tdesktop](https://github.com/telegramdesktop/tdesktop)：`tdata` 含加密授权密钥与本地消息，保留；清缓存用内置 Storage Usage。
- 微信 — [腾讯客服 FAQ](https://kf.qq.com/faq/250710MraIZj250710QniyAr.html)：4.x 存储目录 `xwechat_files` 可自定义（默认文档）；子目录结构为社区共识。
- 钉钉 — [帮助中心](https://help.dingtalk.com/)：官方仅提供应用内清理缓存；`%APPDATA%\DingTalk` 子目录为社区共识。
- EA — [Clear cache](https://help.ea.com/en/articles/technical-issues/clear-cache/)；Ubisoft — [Emptying the cache](https://www.ubisoft.com/en-us/help/connectivity-and-performance/article/emptying-the-cache-of-ubisoft-connect-pc/000061966)；Rockstar — [Launcher error logs](https://support.rockstargames.com/articles/7GenyC6ECNn16P1CtmhVGk/rockstar-games-launcher-error-logs)：各启动器缓存可清，存档保留。
- GOG — [Galaxy 论坛缓存帖](https://www.gog.com/forum/general_de/cache_loschen)：`webcache` 可清，`storage` 含登录态/游戏库（保留）。
- HoYoverse — [启动器缓存](https://support.hoyoverse.com/hc/en-us/articles/49686177121689)：官方确认清缓存；AppData 具体路径为社区共识。
- DaVinci Resolve — [Reference Manual](https://documents.blackmagicdesign.com/UserManuals/DaVinci_Resolve_18_Reference_Manual.pdf)：CacheClip 建在首个媒体存储路径（非固定 AppData），工程库在 `Support`。
- Microsoft Learn — [Delivery Optimization reference](https://learn.microsoft.com/en-us/windows/deployment/do/waas-delivery-optimization-reference) / [Delete-DeliveryOptimizationCache](https://learn.microsoft.com/en-us/powershell/module/deliveryoptimization/delete-deliveryoptimizationcache)：DO 缓存可用系统工具清理，按需重建。
- Microsoft Q&A — [$WinREAgent 讨论](https://learn.microsoft.com/en-us/answers/questions/4016297/navigating-windows-bt-and-winreagent-folders-how-c)：WinRE 更新临时目录，更新完成后方可清理（社区共识，标 caution）。

## 7. 已知限制

- 规则是**保守默认值**，不是系统工具的替代品：WinSxS、Installer、System32、驱动存储、搜索索引、Defender、系统还原、页面/休眠文件一律不建议直接删。
- 逻辑大小会重复计算硬链接、压缩与稀疏文件；WinSxS 的“大小”尤其容易误导。
- 目录用途可能被用户自定义（例如把 `D:\Downloads` 当作项目目录）；报告中的 `review` 项必须人工确认。
- 规则不覆盖所有软件；未命中的目录以“未识别的大型目录/顶层目录”形式出现，默认不勾选。
- 系统级删除通常需要管理员权限；回收站模式需要 Windows PowerShell 5.1+。
