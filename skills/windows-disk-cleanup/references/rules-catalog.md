# Windows 目录规则库

版本：v1　更新：2026-10-27　规则数：226

本文件是 [`assets/rules.json`](../assets/rules.json) 的可读目录；**JSON 是权威数据**，本表用于人工审阅与解释。修改规则后运行 `windows-disk-cleanup rules --check`，并同步本表。

## 目录

- [1. 这份规则库解决什么问题](#1-这份规则库解决什么问题)
- [2. 安全等级](#2-安全等级)
- [3. 扫描模式与判定](#3-扫描模式与判定)
- [4. 规则明细](#4-规则明细)
  - [系统升级残留（7）](#系统升级残留7)
  - [Windows 更新（4）](#windows-更新4)
  - [系统临时文件（3）](#系统临时文件3)
  - [系统日志与转储（13）](#系统日志与转储13)
  - [系统性能缓存（2）](#系统性能缓存2)
  - [系统组件（保留）（26）](#系统组件保留26)
  - [系统托管（6）](#系统托管6)
  - [回收站（1）](#回收站1)
  - [用户数据（6）](#用户数据6)
  - [用户临时文件（4）](#用户临时文件4)
  - [浏览器缓存（18）](#浏览器缓存18)
  - [应用缓存（24）](#应用缓存24)
  - [开发工具缓存（20）](#开发工具缓存20)
  - [包管理器缓存（23）](#包管理器缓存23)
  - [AI/模型缓存（3）](#ai模型缓存3)
  - [项目构建产物（44）](#项目构建产物44)
  - [项目配置（保留）（3）](#项目配置保留3)
  - [凭据/配置（保留）（6）](#凭据配置保留6)
  - [游戏平台（10）](#游戏平台10)
  - [虚拟机/容器（3）](#虚拟机容器3)
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
| `sys-windows-bt` | `suffix` `\$Windows.~BT` | leaf · 需管理员 | 建议清理 | 功能更新下载/安装过程中产生的临时安装文件。 | 升级完成后可删；优先用磁盘清理的「临时 Windows 安装文件」。 |
| `sys-windows-q` | `suffix` `\$Windows.~Q` | leaf · 需管理员 | 建议清理 | Windows 升级过程中的临时工作目录。 | 升级完成后可删。 |
| `sys-windows-ws` | `suffix` `\$Windows.~WS` | leaf · 需管理员 | 建议清理 | Windows 升级安装器留下的临时下载目录。 | 升级完成后可删。 |
| `sys-esd` | `suffix` `\ESD` | leaf · 需管理员 | 建议清理 | Windows 升级/安装器下载的 ESD 镜像缓存。 | 确认没有正在进行的升级后可删。 |
| `sys-inplace-tr` | `suffix` `\$INPLACE.~TR` | leaf · 需管理员 | 建议清理 | 就地升级（in-place upgrade）留下的临时文件。 | 升级完成后可删。 |
| `sys-windows-old` | `suffix` `\Windows.old` | leaf · 需管理员 | 建议清理 | 系统升级后保留的上一版 Windows，通常 10–25 GB，用于回滚。 | 建议用「磁盘清理 → 清理系统文件 → 以前的 Windows 安装」删除；删除后无法回滚系统版本。 |
| `sys-sysreset` | `suffix` `\$SysReset` | leaf · 需管理员 | 建议清理 | 系统重置/恢复过程留下的日志与回滚数据。 | 重置完成后可删。 |

### 2. Windows 更新（4）

| ID | 匹配 | 模式 | 建议 | 说明 | 建议操作 |
| --- | --- | --- | --- | --- | --- |
| `win-update-datastore` | `suffix` `\Windows\SoftwareDistribution\DataStore` | leaf · 需管理员 | 保留 | Windows Update 的更新历史与配置数据库。 | 保留；只有重置 Windows Update 时才按官方步骤重命名/重建。 |
| `win-update-root` | `suffix` `\Windows\SoftwareDistribution` | container · 需管理员 | 保留 | Windows Update 服务的工作目录，包含下载缓存、历史数据库与状态。 | 不要整体删除；只清理其中的 Download 子目录。 |
| `win-update-download` | `suffix` `\Windows\SoftwareDistribution\Download` | leaf · 需管理员 | 建议清理 | Windows Update 下载的更新包缓存，更新完成后通常不再需要。 | 建议先停止 wuauserv/bits 再清理，或用磁盘清理；服务运行中部分文件会被占用。 |
| `programdata-bits` | `suffix` `\ProgramData\Microsoft\Network\Downloader` | leaf · 需管理员 | 谨慎清理 | 后台智能传输服务（BITS）的下载队列与缓存。 | 确认没有正在进行的更新/下载后清理。 |

### 3. 系统临时文件（3）

| ID | 匹配 | 模式 | 建议 | 说明 | 建议操作 |
| --- | --- | --- | --- | --- | --- |
| `win-temp` | `suffix` `\Windows\Temp` | leaf · 需管理员 | 安全清理 | 系统与安装程序共用的临时目录。 | 关闭正在安装的程序后清理；被占用的文件会自动跳过。 |
| `win-systemtemp` | `suffix` `\Windows\SystemTemp` | leaf · 需管理员 | 安全清理 | Windows 11 引入的系统级临时目录，供服务和安装程序使用。 | 关闭正在安装的程序后清理。 |
| `programdata-retaildemo` | `suffix` `\ProgramData\Microsoft\Windows\RetailDemo` | leaf · 需管理员 | 安全清理 | 零售演示模式使用的示例内容。 | 普通用户可删。 |

### 4. 系统日志与转储（13）

| ID | 匹配 | 模式 | 建议 | 说明 | 建议操作 |
| --- | --- | --- | --- | --- | --- |
| `win-livekernel` | `suffix` `\Windows\LiveKernelReports` | leaf · 需管理员 | 安全清理 | Windows 记录的内核/驱动异常转储。 | 不排查蓝屏/驱动问题时可以删除。 |
| `perflogs` | `suffix` `\PerfLogs` | leaf · 需管理员 | 安全清理 | Windows 性能监视器/数据收集器留下的日志，通常为空或很小。 | 可以清理；正在做性能采集时保留。 |
| `user-wer` | `suffix` `\AppData\Local\Microsoft\Windows\WER` | leaf | 安全清理 | 当前用户的 Windows 错误报告队列与存档。 | 可清理。 |
| `user-crashdumps` | `suffix` `\AppData\Local\CrashDumps` | leaf | 安全清理 | 应用程序崩溃时生成的转储文件。 | 不排查崩溃问题时可删。 |
| `win-minidump` | `suffix` `\Windows\Minidump` | leaf · 需管理员 | 安全清理 | 蓝屏时生成的小型内存转储，用于分析崩溃原因。 | 不排查蓝屏问题时可删。 |
| `programdata-wer` | `suffix` `\ProgramData\Microsoft\Windows\WER` | leaf · 需管理员 | 安全清理 | Windows 错误报告（WER）的队列与存档。 | 可清理；正在排查崩溃时保留。 |
| `win-memorydmp` | `suffix` `\Windows\MEMORY.DMP` | leaf · 文件 · 需管理员 | 谨慎清理 | 完整内存转储，单文件通常数百 MB 到数 GB。 | 不排查蓝屏问题时可删；正在排查则先保留。 |
| `win-panther` | `suffix` `\Windows\Panther` | leaf · 需管理员 | 谨慎清理 | Windows 安装/升级过程日志。 | 安装完成后可清理；排查升级失败时保留。 |
| `win-logs-wu` | `suffix` `\Windows\Logs\WindowsUpdate` | leaf · 需管理员 | 谨慎清理 | Windows Update 客户端日志。 | 可清理；更新故障排查时保留。 |
| `win-logs` | `suffix` `\Windows\Logs` | leaf · 需管理员 | 谨慎清理 | Windows 各组件的日志汇总目录。 | 只清理确认无用的旧日志；排障期间保留。 |
| `file-memorydmp` | `suffix` `\MEMORY.DMP` | leaf · 文件 · 需管理员 | 谨慎清理 | 蓝屏后生成的完整内存转储，单文件可能很大。 | 不排查蓝屏问题时可删。 |
| `win-system32-logfiles` | `suffix` `\Windows\System32\LogFiles` | leaf · 需管理员 | 谨慎清理 | 部分系统组件（如网络、打印）写入的日志。 | 确认没有排障需求后再清理。 |
| `win-logs-cbs` | `suffix` `\Windows\Logs\CBS` | leaf · 需管理员 | 谨慎清理 | Windows 组件服务（CBS）日志，长期积累可能很大。 | 可清理旧日志；排查系统更新/组件问题时保留。 |

### 5. 系统性能缓存（2）

| ID | 匹配 | 模式 | 建议 | 说明 | 建议操作 |
| --- | --- | --- | --- | --- | --- |
| `win-prefetch` | `suffix` `\Windows\Prefetch` | leaf · 需管理员 | 保留 | 记录程序启动轨迹以加速冷启动，Windows 会自行维护。 | 保留；Microsoft 的说明是无需清理，删除后启动会暂时变慢。 |
| `sys-fontcache` | `suffix` `\Windows\ServiceProfiles\LocalService\AppData\Local\FontCache` | leaf · 需管理员 | 安全清理 | 系统字体缓存，Windows 会按需重建。 | 停止 FontCache 服务后清理更彻底；也可以直接删除缓存文件。 |

### 6. 系统组件（保留）（26）

| ID | 匹配 | 模式 | 建议 | 说明 | 建议操作 |
| --- | --- | --- | --- | --- | --- |
| `win-assembly` | `suffix` `\Windows\assembly` | skip · 需管理员 | 保留 | 旧版 .NET 全局程序集缓存（GAC）。 | 保留。 |
| `win-dotnet` | `suffix` `\Windows\Microsoft.NET` | skip · 需管理员 | 保留 | .NET Framework 运行时与配置。 | 保留。 |
| `sys-program-files-x86` | `exact` `%SystemDrive%\Program Files (x86)` | container · 需管理员 | 保留 | 32 位程序的默认安装目录。 | 不要整体删除；卸载程序请用设置/卸载器。 |
| `programdata-defender` | `suffix` `\ProgramData\Microsoft\Windows Defender` | skip · 需管理员 | 保留 | Defender 的定义、扫描历史与隔离区。 | 保留；用 Windows 安全中心管理。 |
| `win-syswow64` | `suffix` `\Windows\SysWOW64` | skip · 需管理员 | 保留 | 64 位 Windows 上的 32 位系统组件。 | 禁止删除。 |
| `win-installer` | `suffix` `\Windows\Installer` | skip · 需管理员 | 保留 | MSI 安装包的缓存，用于程序修复、卸载和更新。 | 保留；不要用第三方清理工具批量删除。 |
| `win-boot` | `suffix` `\Windows\Boot` | skip · 需管理员 | 保留 | 启动管理器与启动相关资源。 | 禁止删除。 |
| `programdata-search` | `suffix` `\ProgramData\Microsoft\Search` | skip · 需管理员 | 保留 | Windows Search 的索引数据库。 | 保留；需要重建时用「索引选项 → 高级 → 重建」。 |
| `win-servicing` | `suffix` `\Windows\servicing` | skip · 需管理员 | 保留 | Windows 更新/组件服务使用的离线组件与 LCU 数据。 | 保留；组件清理用 DISM。 |
| `win-root` | `exact` `%SystemDrive%\Windows` | container · 需管理员 | 保留 | Windows 操作系统目录，包含系统组件、驱动、更新缓存与日志。 | 不要整体删除；本工具只深入其中明确标记的可清理子目录。 |
| `win-system32` | `suffix` `\Windows\System32` | skip · 需管理员 | 保留 | Windows 核心系统文件与驱动目录。 | 禁止删除；本工具只会在其中清理明确标记的日志子目录。 |
| `win-winsxs` | `suffix` `\Windows\WinSxS` | skip · 需管理员 | 保留 | Windows 组件存储，包含系统文件的硬链接与旧组件。资源管理器显示的大小会因硬链接而失真。 | 禁止手动删除；需要清理时用 DISM /Online /Cleanup-Image /StartComponentCleanup。 |
| `sys-programdata-env` | `exact` `%ProgramData%` | container · 需管理员 | 保留 | 系统登记的共享应用数据目录。 | 不要整体删除。 |
| `sys-boot-dir` | `exact` `%SystemDrive%\Boot` | skip · 需管理员 | 保留 | 启动配置与启动管理器文件。 | 禁止删除。 |
| `programdata-package-cache` | `suffix` `\ProgramData\Package Cache` | skip · 需管理员 | 保留 | Visual Studio / 安装器保存的安装包缓存，用于修复与卸载。 | 保留；用 Visual Studio Installer 或对应卸载器清理。 |
| `windowsapps` | `suffix` `\AppData\Local\Microsoft\WindowsApps` | skip | 保留 | Windows 商店应用与命令别名。 | 保留。 |
| `sys-recovery` | `exact` `%SystemDrive%\Recovery` | skip · 需管理员 | 保留 | Windows 恢复环境（WinRE）与恢复脚本。 | 保留。 |
| `sys-programdata` | `exact` `%SystemDrive%\ProgramData` | container · 需管理员 | 保留 | 所有用户共享的应用数据、配置与缓存。 | 不要整体删除；只清理其中明确标记的缓存子目录。 |
| `win-catroot2` | `suffix` `\Windows\System32\catroot2` | skip · 需管理员 | 保留 | Windows 更新使用的目录签名数据库。 | 保留；只有按官方步骤重置更新组件时才重建。 |
| `win-config` | `suffix` `\Windows\System32\config` | skip · 需管理员 | 保留 | Windows 注册表文件与事务日志。 | 禁止删除或移动。 |
| `local-programs` | `suffix` `\AppData\Local\Programs` | skip | 保留 | 只对当前用户安装的程序（VS Code、Cursor 等）。 | 保留；卸载程序请用设置/卸载器。 |
| `sys-program-files` | `exact` `%SystemDrive%\Program Files` | container · 需管理员 | 保留 | 64 位程序的默认安装目录。 | 不要整体删除；卸载程序请用设置/卸载器。 |
| `sys-program-files-env` | `exact` `%ProgramFiles%` | container · 需管理员 | 保留 | 系统登记的 64 位程序安装目录（可能不在系统盘）。 | 不要整体删除。 |
| `win-fonts` | `suffix` `\Windows\Fonts` | skip · 需管理员 | 保留 | 系统已安装字体。 | 保留；卸载字体请用设置/字体管理。 |
| `win-csc` | `suffix` `\Windows\CSC` | skip · 需管理员 | 保留 | 脱机文件/同步中心的本地缓存。 | 保留；用同步中心管理脱机文件。 |
| `win-driverstore` | `suffix` `\Windows\System32\DriverStore` | skip · 需管理员 | 保留 | Windows 驱动包的集中存储，包含正在使用和可回滚的驱动。 | 保留；驱动管理用 pnputil / 设备管理器。 |

### 7. 系统托管（6）

| ID | 匹配 | 模式 | 建议 | 说明 | 建议操作 |
| --- | --- | --- | --- | --- | --- |
| `sys-config-msi` | `exact` `%SystemDrive%\Config.Msi` | skip · 需管理员 | 保留 | Windows Installer 安装/回滚期间使用的临时目录。 | 保留；安装程序运行期间尤其不要删除。 |
| `file-swapfile` | `suffix` `\swapfile.sys` | leaf · 文件 | 保留 | UWP 应用使用的交换文件，由系统管理。 | 保留。 |
| `file-hiberfil` | `suffix` `\hiberfil.sys` | leaf · 文件 | 保留 | 休眠/快速启动使用的内存镜像文件，通常与物理内存同量级。 | 如需移除，管理员运行 powercfg /h off（会关闭休眠）；不要直接删文件。 |
| `sys-volume-info` | `suffix` `\System Volume Information` | skip · 需管理员 | 保留 | 卷影副本、系统还原点与索引数据。 | 保留；用「系统保护」或 vssadmin 管理还原点。 |
| `file-pagefile` | `suffix` `\pagefile.sys` | leaf · 文件 | 保留 | Windows 虚拟内存页面文件，由系统管理。 | 保留；如需调整，用「系统属性 → 高级 → 性能 → 虚拟内存」。 |
| `file-dumpstack` | `suffix` `\DumpStack.log.tmp` | leaf · 文件 | 保留 | 系统崩溃转储相关的小型日志。 | 保留。 |

### 8. 回收站（1）

| ID | 匹配 | 模式 | 建议 | 说明 | 建议操作 |
| --- | --- | --- | --- | --- | --- |
| `sys-recycle-bin` | `suffix` `\$Recycle.Bin` | skip · 不可选 | 谨慎清理 | 各用户删除的文件先进入这里；清空后才真正释放磁盘空间。 | 右键回收站 → 清空回收站，或 PowerShell Clear-RecycleBin；不要手动删除目录。 |

### 9. 用户数据（6）

| ID | 匹配 | 模式 | 建议 | 说明 | 建议操作 |
| --- | --- | --- | --- | --- | --- |
| `sys-appdata-locallow` | `regex` `^[a-z]:\\users\\[^\\]+\\appdata\\locallow$` | container | 保留 | 低权限/沙盒应用的数据目录，通常较小。 | 保留；不要整体删除。 |
| `sys-appdata` | `regex` `^[a-z]:\\users\\[^\\]+\\appdata$` | container | 保留 | 应用保存配置与缓存的根目录，分为 Local / Roaming / LocalLow。 | 不要整体删除；只清理其中明确标记的缓存子目录。 |
| `sys-appdata-local` | `regex` `^[a-z]:\\users\\[^\\]+\\appdata\\local$` | container | 保留 | 本机专用应用数据与缓存（不随漫游配置同步）。 | 不要整体删除；只清理其中明确标记的缓存子目录。 |
| `sys-appdata-roaming` | `regex` `^[a-z]:\\users\\[^\\]+\\appdata\\roaming$` | container | 保留 | 应用配置、账户信息与可漫游数据。 | 保留；不要整体删除。 |
| `sys-users` | `exact` `%SystemDrive%\Users` | container · 需管理员 | 保留 | 所有用户配置文件的根目录，包含桌面、文档、下载、AppData 等。 | 不要整体删除；只清理用户明确选择的具体目录。 |
| `user-downloads` | `suffix` `\Downloads` | leaf | 谨慎清理 | 浏览器/应用默认的下载目录，通常包含安装包、文档与临时下载。 | 建议在资源管理器中逐项筛选，只删除确认不再需要的文件；不要整体清理。 |

### 10. 用户临时文件（4）

| ID | 匹配 | 模式 | 建议 | 说明 | 建议操作 |
| --- | --- | --- | --- | --- | --- |
| `onedrivetemp` | `suffix` `\OneDriveTemp` | leaf | 安全清理 | OneDrive 同步过程使用的临时目录。 | 暂停同步后可清理。 |
| `user-wincaches` | `suffix` `\AppData\Local\Microsoft\Windows\Caches` | leaf | 安全清理 | Windows shell 与部分系统组件的小型缓存。 | 可清理。 |
| `user-temp` | `suffix` `\AppData\Local\Temp` | leaf | 安全清理 | 当前用户与各程序写入的临时文件；关闭程序后大部分可删除。 | 关闭常用程序后清理；被占用的文件会自动跳过。 |
| `user-explorer-cache` | `suffix` `\AppData\Local\Microsoft\Windows\Explorer` | leaf | 谨慎清理 | Windows 资源管理器的缩略图、图标与视图缓存。 | 可清理；资源管理器会重建，文件夹视图设置可能重置。 |

### 11. 浏览器缓存（18）

| ID | 匹配 | 模式 | 建议 | 说明 | 建议操作 |
| --- | --- | --- | --- | --- | --- |
| `brave-cache` | `glob` `*\AppData\Local\BraveSoftware\Brave-Browser\User Data\*\Cache` | leaf | 安全清理 | Brave 各配置文件的网页缓存。 | 关闭 Brave 后清理。 |
| `firefox-startupcache` | `glob` `*\AppData\Local\Mozilla\Firefox\Profiles\*\startupCache` | leaf | 安全清理 | Firefox 的启动缓存。 | 关闭 Firefox 后清理。 |
| `firefox-cache2` | `glob` `*\AppData\Local\Mozilla\Firefox\Profiles\*\cache2` | leaf | 安全清理 | Firefox 各配置文件的网页缓存。 | 关闭 Firefox 后清理。 |
| `chrome-gpucache` | `glob` `*\AppData\Local\Google\Chrome\User Data\*\GPUCache` | leaf | 安全清理 | Chrome 的 GPU 着色器/渲染缓存。 | 关闭 Chrome 后清理。 |
| `chrome-grshadercache` | `suffix` `\AppData\Local\Google\Chrome\User Data\GrShaderCache` | leaf | 安全清理 | Chrome 的 GPU 着色器缓存。 | 关闭 Chrome 后清理。 |
| `chrome-sw-cache` | `glob` `*\AppData\Local\Google\Chrome\User Data\*\Service Worker\CacheStorage` | leaf | 安全清理 | Chrome 的 Service Worker 离线缓存。 | 关闭 Chrome 后清理。 |
| `chrome-shadercache` | `suffix` `\AppData\Local\Google\Chrome\User Data\ShaderCache` | leaf | 安全清理 | Chrome 的着色器缓存。 | 关闭 Chrome 后清理。 |
| `chrome-code-cache` | `glob` `*\AppData\Local\Google\Chrome\User Data\*\Code Cache` | leaf | 安全清理 | Chrome 的 JavaScript/WebAssembly 编译缓存。 | 关闭 Chrome 后清理。 |
| `chrome-cache` | `glob` `*\AppData\Local\Google\Chrome\User Data\*\Cache` | leaf | 安全清理 | Chrome 各配置文件的网页缓存。 | 关闭 Chrome 后清理；不要删除 User Data 下的其他目录。 |
| `user-inetcache` | `suffix` `\AppData\Local\Microsoft\Windows\INetCache` | leaf · 需管理员 | 建议清理 | Internet Explorer / 部分系统组件使用的网页缓存。 | 可清理。 |
| `edge-gpucache` | `glob` `*\AppData\Local\Microsoft\Edge\User Data\*\GPUCache` | leaf | 安全清理 | Edge 的 GPU 着色器/渲染缓存。 | 关闭 Edge 后清理。 |
| `edge-sw-cache` | `glob` `*\AppData\Local\Microsoft\Edge\User Data\*\Service Worker\CacheStorage` | leaf | 安全清理 | Edge 的 Service Worker 离线缓存。 | 关闭 Edge 后清理。 |
| `edge-code-cache` | `glob` `*\AppData\Local\Microsoft\Edge\User Data\*\Code Cache` | leaf | 安全清理 | Edge 的 JavaScript/WebAssembly 编译缓存。 | 关闭 Edge 后清理。 |
| `edge-cache` | `glob` `*\AppData\Local\Microsoft\Edge\User Data\*\Cache` | leaf | 安全清理 | Edge 各配置文件的网页缓存。 | 关闭 Edge 后清理；不要删除 User Data 下的其他目录。 |
| `opera-cache` | `suffix` `\AppData\Local\Opera Software\Opera Stable\Cache` | leaf | 安全清理 | Opera 的网页缓存。 | 关闭 Opera 后清理。 |
| `vivaldi-cache` | `glob` `*\AppData\Local\Vivaldi\User Data\*\Cache` | leaf | 安全清理 | Vivaldi 各配置文件的网页缓存。 | 关闭 Vivaldi 后清理。 |
| `user-temporary-internet-files` | `suffix` `\AppData\Local\Microsoft\Windows\Temporary Internet Files` | leaf · 需管理员 | 建议清理 | 旧版 Windows/IE 的临时 Internet 文件目录。 | 可清理。 |
| `user-webcache` | `suffix` `\AppData\Local\Microsoft\Windows\WebCache` | leaf · 需管理员 | 建议清理 | 旧版 IE/系统组件的 Web 缓存数据库。 | 关闭浏览器与相关程序后清理；文件常被占用。 |

### 12. 应用缓存（24）

| ID | 匹配 | 模式 | 建议 | 说明 | 建议操作 |
| --- | --- | --- | --- | --- | --- |
| `amd-dxcache` | `suffix` `\AppData\Local\AMD\DxCache` | leaf | 安全清理 | AMD 驱动的 DirectX 着色器缓存。 | 可清理。 |
| `amd-glcache` | `suffix` `\AppData\Local\AMD\GLCache` | leaf | 安全清理 | AMD 驱动的 OpenGL 着色器缓存。 | 可清理。 |
| `d3dscache` | `suffix` `\AppData\Local\D3DSCache` | leaf | 安全清理 | DirectX 游戏的着色器编译缓存。 | 可清理；游戏会重新编译着色器。 |
| `discord-gpucache` | `suffix` `\AppData\Roaming\Discord\GPUCache` | leaf | 安全清理 | Discord 的 GPU 渲染缓存。 | 退出 Discord 后清理。 |
| `discord-code-cache` | `suffix` `\AppData\Roaming\Discord\Code Cache` | leaf | 安全清理 | Discord 的 JavaScript 编译缓存。 | 退出 Discord 后清理。 |
| `discord-cache` | `suffix` `\AppData\Roaming\Discord\Cache` | leaf | 安全清理 | Discord 的网页/媒体缓存。 | 退出 Discord 后清理。 |
| `intel-shadercache` | `suffix` `\AppData\Local\Intel\ShaderCache` | leaf | 安全清理 | Intel 显卡驱动的着色器缓存。 | 可清理。 |
| `onedrive-ms-logs` | `suffix` `\AppData\Local\Microsoft\OneDrive\logs` | leaf | 安全清理 | Microsoft Store 版 OneDrive 日志。 | 可清理。 |
| `teams-gpucache` | `suffix` `\AppData\Roaming\Microsoft\Teams\GPUCache` | leaf | 安全清理 | Teams 的 GPU 渲染缓存。 | 退出 Teams 后清理。 |
| `teams-code-cache` | `suffix` `\AppData\Roaming\Microsoft\Teams\Code Cache` | leaf | 安全清理 | Teams 的 JavaScript 编译缓存。 | 退出 Teams 后清理。 |
| `teams-cache` | `suffix` `\AppData\Roaming\Microsoft\Teams\Cache` | leaf | 安全清理 | Teams 的网页/媒体缓存。 | 退出 Teams 后清理。 |
| `nvidia-dxcache` | `suffix` `\AppData\Local\NVIDIA\DXCache` | leaf | 安全清理 | NVIDIA 驱动的 DirectX 着色器缓存。 | 可清理；驱动会重新生成。 |
| `nvidia-glcache` | `suffix` `\AppData\Local\NVIDIA\GLCache` | leaf | 安全清理 | NVIDIA 驱动的 OpenGL 着色器缓存。 | 可清理。 |
| `programdata-nvidia-downloader` | `suffix` `\ProgramData\NVIDIA Corporation\Downloader` | leaf · 需管理员 | 安全清理 | NVIDIA 驱动安装器下载的安装包缓存。 | 驱动安装完成后可删；再次安装会重新下载。 |
| `office-diagnostics` | `glob` `*\AppData\Local\Microsoft\Office\*\Diagnostics` | leaf | 安全清理 | Office 诊断日志。 | 可清理。 |
| `onedrive-setup-logs` | `suffix` `\AppData\Local\Microsoft\OneDrive\setup\logs` | leaf | 安全清理 | OneDrive 安装/更新日志。 | 可清理。 |
| `onedrive-logs` | `suffix` `\AppData\Local\OneDrive\logs` | leaf | 安全清理 | OneDrive 客户端日志。 | 可清理；同步故障排查时保留。 |
| `slack-gpucache` | `suffix` `\AppData\Roaming\Slack\GPUCache` | leaf | 安全清理 | Slack 的 GPU 渲染缓存。 | 退出 Slack 后清理。 |
| `slack-cache` | `suffix` `\AppData\Roaming\Slack\Cache` | leaf | 安全清理 | Slack 的网页/媒体缓存。 | 退出 Slack 后清理。 |
| `uwp-ac-temp` | `glob` `*\AppData\Local\Packages\*\AC\Temp` | leaf | 安全清理 | UWP 应用兼容层使用的临时文件。 | 关闭对应应用后可清理。 |
| `uwp-tempstate` | `glob` `*\AppData\Local\Packages\*\TempState` | leaf | 安全清理 | Windows 商店应用的临时状态目录。 | 关闭对应应用后可清理。 |
| `office-file-cache` | `glob` `*\AppData\Local\Microsoft\Office\*\OfficeFileCache` | leaf | 谨慎清理 | Office 文档的本地缓存，可能包含未同步的编辑。 | 关闭 Office 并确认文档已保存/同步后清理。 |
| `spotify-storage` | `suffix` `\AppData\Local\Spotify\Storage` | leaf | 谨慎清理 | Spotify 的离线歌曲与封面缓存，可能很大。 | 确认不需要离线收听后清理；重新下载会消耗流量。 |
| `uwp-localcache` | `glob` `*\AppData\Local\Packages\*\LocalCache` | leaf | 谨慎清理 | Windows 商店应用（UWP）的本地缓存，可能包含离线数据。 | 关闭对应应用后清理；重要离线内容先确认。 |

### 13. 开发工具缓存（20）

| ID | 匹配 | 模式 | 建议 | 说明 | 建议操作 |
| --- | --- | --- | --- | --- | --- |
| `dev-android-cache` | `suffix` `\.android\cache` | leaf | 安全清理 | Android 工具链的构建/下载缓存。 | 可清理。 |
| `cursor-logs` | `suffix` `\AppData\Roaming\Cursor\logs` | leaf | 安全清理 | Cursor 运行日志。 | 可清理。 |
| `cursor-cacheddata` | `suffix` `\AppData\Roaming\Cursor\CachedData` | leaf | 安全清理 | Cursor 的 JavaScript 编译缓存。 | 关闭 Cursor 后清理。 |
| `cursor-cache` | `suffix` `\AppData\Roaming\Cursor\Cache` | leaf | 安全清理 | Cursor 编辑器的网页/扩展缓存。 | 关闭 Cursor 后清理。 |
| `dev-go-build` | `suffix` `\AppData\Local\go-build` | leaf | 安全清理 | Go 编译对象与构建缓存。 | 可清理；go build 会重新生成。 |
| `dev-gradle-cache` | `suffix` `\.gradle\caches` | leaf | 安全清理 | Gradle 下载的依赖、插件与构建缓存。 | 可清理；下次构建会重新下载/生成。 |
| `jetbrains-tmp` | `glob` `*\AppData\Local\JetBrains\*\tmp` | leaf | 安全清理 | JetBrains IDE 的临时文件。 | 关闭对应 IDE 后清理。 |
| `jetbrains-logs` | `glob` `*\AppData\Local\JetBrains\*\logs` | leaf | 安全清理 | JetBrains IDE 日志。 | 可清理。 |
| `jetbrains-caches` | `glob` `*\AppData\Local\JetBrains\*\caches` | leaf | 安全清理 | IntelliJ IDEA/PyCharm/WebStorm 等的索引与缓存。 | 关闭对应 IDE 后清理；下次打开会重建索引。 |
| `dev-rustup-downloads` | `suffix` `\.rustup\downloads` | leaf | 安全清理 | Rustup 下载工具链/组件时的临时包。 | 可清理。 |
| `dev-rustup-tmp` | `suffix` `\.rustup\tmp` | leaf | 安全清理 | Rustup 安装过程中的临时文件。 | 可清理。 |
| `vscode-gpucache` | `suffix` `\AppData\Roaming\Code\GPUCache` | leaf | 安全清理 | VS Code 的 GPU 渲染缓存。 | 关闭 VS Code 后清理。 |
| `vscode-code-cache` | `suffix` `\AppData\Roaming\Code\Code Cache` | leaf | 安全清理 | VS Code 的代码编译缓存。 | 关闭 VS Code 后清理。 |
| `vscode-crashpad` | `suffix` `\AppData\Roaming\Code\Crashpad` | leaf | 安全清理 | VS Code 的崩溃报告缓存。 | 可清理。 |
| `vscode-logs` | `suffix` `\AppData\Roaming\Code\logs` | leaf | 安全清理 | VS Code 运行日志。 | 可清理。 |
| `vscode-cacheddata` | `suffix` `\AppData\Roaming\Code\CachedData` | leaf | 安全清理 | VS Code 的 JavaScript 编译缓存。 | 关闭 VS Code 后清理。 |
| `vscode-cache` | `suffix` `\AppData\Roaming\Code\Cache` | leaf | 安全清理 | VS Code 的网页/扩展缓存。 | 关闭 VS Code 后清理。 |
| `vs-component-model-cache` | `glob` `*\AppData\Local\Microsoft\VisualStudio\*\ComponentModelCache` | leaf | 安全清理 | Visual Studio 的组件/扩展元数据缓存。 | 关闭 Visual Studio 后清理。 |
| `vs-designer-cache` | `glob` `*\AppData\Local\Microsoft\VisualStudio\*\DesignerCache` | leaf | 安全清理 | Visual Studio 窗体/设计器缓存。 | 关闭 Visual Studio 后清理。 |
| `dev-android-avd` | `suffix` `\.android\avd` | leaf | 谨慎清理 | Android 模拟器的虚拟设备镜像与用户数据。 | 在 Android Studio 的 Device Manager 中删除不用的模拟器。 |

### 14. 包管理器缓存（23）

| ID | 匹配 | 模式 | 建议 | 说明 | 建议操作 |
| --- | --- | --- | --- | --- | --- |
| `dev-anaconda-pkgs` | `suffix` `\anaconda3\pkgs` | leaf | 安全清理 | Anaconda 下载并解压的包缓存。 | 可清理；conda clean -p 也可。 |
| `dev-bun-cache` | `suffix` `\.bun\install\cache` | leaf | 安全清理 | Bun 的包安装缓存。 | 可清理；bun install 会重新下载。 |
| `dev-cargo-registry-src` | `suffix` `\.cargo\registry\src` | leaf | 安全清理 | Rust/Cargo 解压后的 crate 源码缓存。 | 可清理；cargo 会重新解压/下载。 |
| `dev-cargo-registry-cache` | `suffix` `\.cargo\registry\cache` | leaf | 安全清理 | Rust/Cargo 下载的 crate 压缩包缓存。 | 可清理；cargo 会重新下载。 |
| `dev-conda-pkgs` | `suffix` `\.conda\pkgs` | leaf | 安全清理 | Conda 下载并解压的包缓存。 | 可清理；conda clean -p 也可。 |
| `dev-pub-cache` | `suffix` `\.pub-cache` | leaf | 安全清理 | Dart/Flutter 下载的依赖包缓存。 | 可清理；flutter pub get 会重新下载。 |
| `dev-go-mod-cache` | `suffix` `\go\pkg\mod\cache` | leaf | 安全清理 | Go 下载的模块压缩包与校验缓存。 | 可清理；go mod download 会重新下载。 |
| `dev-ivy-cache` | `suffix` `\.ivy2\cache` | leaf | 安全清理 | Ivy/SBT 下载的依赖缓存。 | 可清理；下次构建会重新下载。 |
| `dev-miniconda-pkgs` | `suffix` `\miniconda3\pkgs` | leaf | 安全清理 | Miniconda 下载并解压的包缓存。 | 可清理；conda clean -p 也可。 |
| `dev-nuget-v3` | `suffix` `\AppData\Local\NuGet\v3-cache` | leaf | 安全清理 | NuGet 的 HTTP/包元数据缓存。 | 可清理。 |
| `dev-nuget-plugins` | `suffix` `\AppData\Local\NuGet\plugins-cache` | leaf | 安全清理 | NuGet 插件缓存。 | 可清理。 |
| `dev-sbt-boot` | `suffix` `\.sbt\boot` | leaf | 安全清理 | SBT 启动器与 Scala 版本缓存。 | 可清理；下次启动会重新下载。 |
| `dev-yarn-berry` | `suffix` `\AppData\Local\Yarn\Berry\cache` | leaf | 安全清理 | Yarn v2+ 的包缓存。 | 可清理。 |
| `dev-yarn-cache` | `suffix` `\AppData\Local\Yarn\Cache` | leaf | 安全清理 | Yarn v1 的包缓存。 | 可清理；yarn cache clean 也可。 |
| `dev-npm-home` | `suffix` `\.npm` | leaf | 安全清理 | npm 的用户级缓存与日志目录。 | 可清理；npm cache clean --force 也可。 |
| `dev-npm-cache-local` | `suffix` `\AppData\Local\npm-cache` | leaf | 安全清理 | 新版 npm 的全局缓存目录。 | 可清理；npm cache clean --force 也可。 |
| `dev-npm-cache-roaming` | `suffix` `\AppData\Roaming\npm-cache` | leaf · 需管理员 | 建议清理 | 旧版 npm 的全局缓存目录。 | 可清理；npm cache clean --force 也可。 |
| `dev-pip-cache` | `suffix` `\AppData\Local\pip\Cache` | leaf | 安全清理 | pip 下载的 wheel/sdist 与 HTTP 缓存。 | 可清理；pip cache purge 也可。 |
| `dev-cargo-git` | `suffix` `\.cargo\git` | leaf | 谨慎清理 | Cargo 从 Git 仓库拉取的依赖缓存。 | 确认没有依赖特定 Git 提交的离线构建后再清理。 |
| `dev-m2-repo` | `suffix` `\.m2\repository` | leaf | 谨慎清理 | Maven 下载的依赖与本地安装的构件。 | 确认没有本地 install 的私有构件后再清理；否则会丢失本地包。 |
| `dev-nuget-packages` | `suffix` `\.nuget\packages` | leaf | 谨慎清理 | .NET 的全局 NuGet 包缓存。 | 确认没有离线构建需求后再清理；下次还原会重新下载。 |
| `dev-pnpm-store` | `suffix` `\AppData\Local\pnpm\store` | leaf | 谨慎清理 | pnpm 的全局包存储，已有项目的 node_modules 通过硬链接引用它。 | 优先用 pnpm store prune；直接删除可能破坏已有项目的依赖链接。 |
| `dev-uv-cache` | `suffix` `\AppData\Local\uv\cache` | leaf | 谨慎清理 | uv 的全局包/构建缓存。 | 优先用 uv cache prune（安全）或 uv cache clean；手动删除前确认没有 uv 进程。 |

### 15. AI/模型缓存（3）

| ID | 匹配 | 模式 | 建议 | 说明 | 建议操作 |
| --- | --- | --- | --- | --- | --- |
| `dev-huggingface-cache` | `suffix` `\.cache\huggingface` | leaf | 谨慎清理 | Hugging Face 下载的模型/数据集缓存，可能数十 GB。 | 确认不再需要离线模型后清理；重新下载可能很慢/需要网络。 |
| `dev-lmstudio-models` | `suffix` `\.lmstudio\models` | leaf | 谨慎清理 | LM Studio 下载的本地模型。 | 在 LM Studio 中删除不用的模型；直接删目录可能破坏索引。 |
| `dev-ollama-models` | `suffix` `\.ollama\models` | leaf | 谨慎清理 | Ollama 下载的本地大模型。 | 用 ollama rm <model> 删除不用的模型；直接删目录会破坏清单。 |

### 16. 项目构建产物（44）

| ID | 匹配 | 模式 | 建议 | 说明 | 建议操作 |
| --- | --- | --- | --- | --- | --- |
| `dev-cs-obj` | `basename` `obj` | leaf | 安全清理 | .NET 项目的中间编译文件。 | 可清理；重新构建会生成。 |
| `dev-aws-sam` | `basename` `.aws-sam` | leaf | 安全清理 | AWS SAM 的构建缓存与打包产物。 | 可清理；sam build 会重新生成。 |
| `dev-angular` | `basename` `.angular` | leaf | 安全清理 | Angular CLI 的构建缓存。 | 可清理；重新构建会生成。 |
| `dev-astro` | `basename` `.astro` | leaf | 安全清理 | Astro 的生成文件与缓存。 | 可清理；重新运行会生成。 |
| `dev-bower` | `basename` `bower_components` | leaf | 安全清理 | Bower 安装的前端依赖。 | 可清理；bower install 会重新下载。 |
| `dev-cmake-files` | `basename` `CMakeFiles` | leaf | 安全清理 | CMake 生成的中间构建文件。 | 可清理；重新配置/构建会生成。 |
| `dev-dart-tool` | `basename` `.dart_tool` | leaf | 安全清理 | Dart/Flutter 项目的构建与包配置缓存。 | 可清理；flutter pub get 会重新生成。 |
| `dev-htmlcov` | `basename` `htmlcov` | leaf | 安全清理 | pytest-cov 生成的 HTML 覆盖率报告。 | 可清理；重新跑测试会生成。 |
| `dev-jspm` | `basename` `jspm_packages` | leaf | 安全清理 | JSPM 安装的前端依赖。 | 可清理；jspm install 会重新下载。 |
| `dev-next` | `basename` `.next` | leaf | 安全清理 | Next.js 的开发/构建缓存。 | 可清理；next dev/build 会重新生成。 |
| `dev-node-modules` | `basename` `node_modules` | leaf | 安全清理 | npm/pnpm/yarn 安装的项目依赖，通常包含大量小文件。 | 可清理；在项目根目录重新 npm install / pnpm install / yarn 即可恢复（建议有锁文件）。 |
| `dev-nuxt` | `basename` `.nuxt` | leaf | 安全清理 | Nuxt 的开发/构建缓存。 | 可清理；重新运行会生成。 |
| `dev-parcel` | `basename` `.parcel-cache` | leaf | 安全清理 | Parcel 的构建缓存。 | 可清理；重新构建会生成。 |
| `dev-pycache` | `basename` `__pycache__` | leaf | 安全清理 | Python 导入模块时生成的 .pyc 缓存。 | 可清理；下次导入会重新生成。 |
| `dev-venv` | `basename` `.venv` | leaf | 安全清理 | Python 项目的虚拟环境（含解释器与已安装依赖）。 | 可清理；用 uv sync / python -m venv 重新创建。 |
| `dev-venv-env` | `basename` `env` | leaf | 安全清理 | Python 项目的虚拟环境（env 命名，含 pyvenv.cfg）。 | 可清理；重新创建即可。 |
| `dev-venv-plain` | `basename` `venv` | leaf | 安全清理 | Python 项目的虚拟环境（venv 命名）。 | 可清理；重新创建即可。 |
| `dev-rollup` | `basename` `.rollup.cache` | leaf | 安全清理 | Rollup 的构建缓存。 | 可清理。 |
| `dev-serverless` | `basename` `.serverless` | leaf | 安全清理 | Serverless Framework 的构建缓存与打包产物。 | 可清理；重新部署会生成。 |
| `dev-svelte-kit` | `basename` `.svelte-kit` | leaf | 安全清理 | SvelteKit 的生成文件与缓存。 | 可清理；重新运行会生成。 |
| `dev-terraform` | `basename` `.terraform` | leaf | 安全清理 | Terraform 下载的 provider/module 缓存（state 通常在目录外的 .tfstate）。 | 可清理；terraform init 会重新下载。 |
| `dev-terragrunt` | `basename` `.terragrunt-cache` | leaf | 安全清理 | Terragrunt 生成的临时工作目录。 | 可清理。 |
| `dev-turbo` | `basename` `.turbo` | leaf | 安全清理 | Turborepo 的本地任务缓存。 | 可清理；下次任务会重新执行。 |
| `dev-vs` | `basename` `.vs` | leaf | 安全清理 | Visual Studio 的 .vs 隐藏缓存目录。 | 关闭 Visual Studio 后可清理；重新打开会生成。 |
| `dev-esbuild` | `basename` `.esbuild` | leaf | 安全清理 | esbuild 的构建缓存。 | 可清理。 |
| `dev-mypy-cache` | `basename` `.mypy_cache` | leaf | 安全清理 | mypy 类型检查的增量缓存。 | 可清理；下次检查会重新生成。 |
| `dev-nox` | `basename` `.nox` | leaf | 安全清理 | nox 创建的测试虚拟环境。 | 可清理；nox 会重新创建。 |
| `dev-nyc` | `basename` `.nyc_output` | leaf | 安全清理 | nyc/Istanbul 生成的覆盖率中间数据。 | 可清理；重新跑测试会生成。 |
| `dev-pytest-cache` | `basename` `.pytest_cache` | leaf | 安全清理 | pytest 的测试结果与上次失败缓存。 | 可清理。 |
| `dev-ruff-cache` | `basename` `.ruff_cache` | leaf | 安全清理 | ruff 的增量检查缓存。 | 可清理。 |
| `dev-tox` | `basename` `.tox` | leaf | 安全清理 | tox 创建的测试虚拟环境。 | 可清理；tox 会重新创建。 |
| `dev-webpack` | `basename` `.webpack` | leaf | 安全清理 | webpack 的持久化缓存（部分脚手架使用）。 | 可清理；重新构建会生成。 |
| `dev-coverage` | `basename` `coverage` | leaf | 安全清理 | 测试覆盖率工具生成的报告目录。 | 可清理；重新跑测试会生成。 |
| `dev-cs-bin` | `basename` `bin` | leaf | 谨慎清理 | .NET 项目的编译输出目录。 | 确认没有需要保留的构建产物后再清理。 |
| `dev-cmake-build` | `basename` `cmake-build-*` | leaf | 谨慎清理 | CLion/CMake 的构建输出目录。 | 可清理；重新构建会生成。 |
| `dev-pods` | `basename` `Pods` | leaf | 谨慎清理 | iOS 项目的 CocoaPods 依赖副本。 | 可清理；pod install 会重新生成。 |
| `dev-expo` | `basename` `.expo` | leaf | 谨慎清理 | Expo 项目的本地缓存与开发配置。 | 确认没有需要保留的本地开发配置后再清理。 |
| `dev-nuxt-output` | `basename` `.output` | leaf | 谨慎清理 | Nuxt/Nitro 的构建输出。 | 确认没有需要保留的部署产物后再清理。 |
| `dev-target` | `basename` `target` | leaf | 谨慎清理 | Rust/Maven 的编译输出目录，通常可重新生成。 | 确认没有需要保留的构建产物后再清理。 |
| `dev-gradle-project` | `basename` `.gradle` | leaf | 谨慎清理 | 项目根目录下的 Gradle 配置/文件哈希缓存。 | 可清理；下次构建会重新生成。 |
| `dev-vendor` | `basename` `vendor` | leaf | 谨慎清理 | PHP Composer 或 Go 的依赖副本。 | 确认有锁文件、可以重新下载后再清理。 |
| `dev-dist` | `basename` `dist` | leaf | 谨慎清理 | 打包/发布产物目录，通常可重新构建。 | 确认没有已发布版本需要保留后再清理。 |
| `dev-build` | `basename` `build` | leaf | 谨慎清理 | 项目构建输出目录，通常可重新生成。 | 确认没有需要保留的构建产物后再清理。 |
| `dev-out` | `basename` `out` | leaf | 谨慎清理 | 项目输出目录，通常是构建/运行产物。 | 确认没有需要保留的输出后再清理。 |

### 17. 项目配置（保留）（3）

| ID | 匹配 | 模式 | 建议 | 说明 | 建议操作 |
| --- | --- | --- | --- | --- | --- |
| `dev-git` | `basename` `.git` | skip | 保留 | Git 版本库的提交历史、分支与配置。 | 禁止删除；删除会丢失全部本地历史。 |
| `dev-idea` | `basename` `.idea` | skip | 保留 | IntelliJ/PyCharm 等项目的配置与运行配置。 | 保留；通常需要入库或复用。 |
| `dev-vscode-dir` | `basename` `.vscode` | skip | 保留 | 项目的 VS Code 配置（任务、调试、推荐扩展）。 | 保留；通常需要入库。 |

### 18. 凭据/配置（保留）（6）

| ID | 匹配 | 模式 | 建议 | 说明 | 建议操作 |
| --- | --- | --- | --- | --- | --- |
| `secret-aws` | `basename` `.aws` | skip | 保留 | AWS CLI 的配置与访问密钥。 | 禁止删除。 |
| `secret-azure` | `basename` `.azure` | skip | 保留 | Azure CLI 的配置与登录状态。 | 禁止删除。 |
| `secret-docker` | `basename` `.docker` | skip | 保留 | Docker CLI 的配置与 registry 凭据。 | 禁止删除。 |
| `secret-gnupg` | `basename` `.gnupg` | skip | 保留 | GPG 密钥环与配置。 | 禁止删除。 |
| `secret-kube` | `basename` `.kube` | skip | 保留 | kubeconfig 与集群凭据。 | 禁止删除。 |
| `secret-ssh` | `basename` `.ssh` | skip | 保留 | SSH 私钥、公钥与 known_hosts。 | 禁止删除。 |

### 19. 游戏平台（10）

| ID | 匹配 | 模式 | 建议 | 说明 | 建议操作 |
| --- | --- | --- | --- | --- | --- |
| `steam-common` | `suffix` `\AppData\Local\Steam\steamapps\common` | skip | 保留 | Steam 游戏本体安装目录。 | 保留；卸载游戏请用 Steam 客户端。 |
| `xboxgames` | `suffix` `\AppData\Local\Microsoft\XboxGames` | skip | 保留 | Xbox 应用安装的游戏。 | 保留；卸载游戏请用 Xbox 应用/设置。 |
| `battlenet-cache` | `suffix` `\AppData\Local\Battle.net\Cache` | leaf | 安全清理 | Battle.net 客户端缓存。 | 退出 Battle.net 后清理。 |
| `battlenet-cache2` | `suffix` `\AppData\Local\Blizzard Entertainment\Battle.net\Cache` | leaf | 安全清理 | Blizzard Battle.net 客户端缓存。 | 退出 Battle.net 后清理。 |
| `epic-logs` | `suffix` `\AppData\Local\EpicGamesLauncher\Saved\Logs` | leaf | 安全清理 | Epic Games 启动器日志。 | 可清理。 |
| `epic-webcache` | `suffix` `\AppData\Local\EpicGamesLauncher\Saved\webcache` | leaf | 安全清理 | Epic Games 启动器的网页缓存。 | 退出启动器后清理。 |
| `steam-downloading` | `suffix` `\AppData\Local\Steam\steamapps\downloading` | leaf | 安全清理 | Steam 游戏下载/更新中的临时文件。 | 确认没有正在下载/更新的游戏后清理。 |
| `steam-temp` | `suffix` `\AppData\Local\Steam\steamapps\temp` | leaf | 安全清理 | Steam 安装/更新过程的临时文件。 | 确认没有正在下载/更新的游戏后清理。 |
| `steam-htmlcache` | `suffix` `\AppData\Local\Steam\htmlcache` | leaf | 安全清理 | Steam 客户端的网页缓存。 | 退出 Steam 后清理。 |
| `steam-workshop` | `suffix` `\AppData\Local\Steam\steamapps\workshop` | leaf | 谨慎清理 | 已订阅的 Steam 创意工坊模组/地图。 | 在 Steam 中取消订阅后再清理；直接删除可能被重新下载。 |

### 20. 虚拟机/容器（3）

| ID | 匹配 | 模式 | 建议 | 说明 | 建议操作 |
| --- | --- | --- | --- | --- | --- |
| `docker-vhdx` | `glob` `*\AppData\Local\Docker\wsl\*\*.vhdx` | leaf · 文件 · 不可选 | 保留 | Docker Desktop 的 WSL2 数据盘，镜像/容器/卷都存在这里，文件只增不减。 | 先 docker system prune，再关闭 Docker 并 wsl --shutdown，最后用 Optimize-VHD/diskpart 压缩；不要直接删 VHDX。 |
| `wsl-vhdx` | `glob` `*\AppData\Local\Packages\*\LocalState\*.vhdx` | leaf · 文件 · 不可选 | 保留 | WSL 发行版的虚拟磁盘，包含该发行版的整个文件系统。 | 保留；需要回收空间时先清理发行版内部文件，再 wsl --shutdown 后压缩 VHDX。 |
| `wsl-vhdx-nested` | `glob` `*\AppData\Local\Packages\*\LocalState\*\*.vhdx` | leaf · 文件 · 不可选 | 保留 | 部分 WSL 发行版将 VHDX 放在 LocalState 的子目录中。 | 保留；用 WSL 命令清理/压缩。 |

## 5. 维护与校验

1. 只改 `assets/rules.json`；字段：`id`（唯一）、`title`、`category`、`scope`、`match`、`mode`、`recommendation`、`method`、`description`、`action`、`risk`，可选 `target`、`requires_admin`、`selectable`、`priority`。
2. `match.type` 支持 `exact` / `suffix` / `basename` / `glob` / `prefix` / `regex`；`basename` 可带 `requires_inside` 或 `requires_sibling_any`。
3. 运行 `windows-disk-cleanup rules --check --json`（退出码 0 才通过），再跑 `python -m unittest discover -s tests`。
4. 新增/修改规则时同步本文件的表格；JSON 更新日期写当天。
5. 规则变更属于行为变化：按仓库规范升次位版本，并在 `docs/TESTS.md` 增加回归场景。

## 6. 来源与核对日期

以下来源用于核对“哪些目录可以删、正确做法是什么”；各工具缓存位置以官方文档为准。核对日期：**2026-10-27**。

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

## 7. 已知限制

- 规则是**保守默认值**，不是系统工具的替代品：WinSxS、Installer、System32、驱动存储、搜索索引、Defender、系统还原、页面/休眠文件一律不建议直接删。
- 逻辑大小会重复计算硬链接、压缩与稀疏文件；WinSxS 的“大小”尤其容易误导。
- 目录用途可能被用户自定义（例如把 `D:\Downloads` 当作项目目录）；报告中的 `review` 项必须人工确认。
- 规则不覆盖所有软件；未命中的目录以“未识别的大型目录/顶层目录”形式出现，默认不勾选。
- 系统级删除通常需要管理员权限；回收站模式需要 Windows PowerShell 5.1+。
