# video-insight

把一条视频变成可信、可回溯的结构化洞察：先把口播转成文字，做内容结构与话术分析（L1）；需要时再叠加画面帧证据，回答"画面有没有接住口播、字幕排版有没有硬伤、标注时机对不对"（L2）。纯 BGM 无口播、文案烧在画面上的视频也有完整分支：帧差定位每屏文案的起止，逐屏读图（或 OCR 回退）还原画面文案轨。

## 何时触发

- 用户要求分析一条视频的内容、结构、话术，或提出「拉片」「画面分析」「音画对齐」「节奏分析」「字幕排版检查」；
- 无口播 / 纯 BGM / 文案在画面上的视频，或点名「提取画面文案 / 画面文字」；
- 只要意图是理解或评估一条已有视频即适用——未说"分析"二字同样触发；
- 仅需转写字幕或浅摘要（不要结构化分析）、或要求生成素材 / 剪辑时不适用（见边界）。

## 工作方式

两档，成本差约 3–8 倍。开工前先跑 `doctor.py` 自检并把环境事实并入**单轮开工确认门**（SKILL.md §0：环境一句话 + 理解 + 交付形态 + 档位推荐与理由；回应只有确认 / 调整 / 显式委托三种，交互会话不存在默认执行）；子代理 / 批处理免问，取 L1 并声明"档位未确认"。L2 长跑在中途设**拼版检查点**（呈报拼版 + 事件表 + 精读节点，可显式跳过），方向跑偏不用等交付才发现：

| 档位 | 做什么 | 实测成本 |
| --- | --- | --- |
| L1 文案档 | 转写 → 校对 → 语义分段 → 口播数据 → 逻辑骨架 → 主张与合规核查 | 约 6–10 分钟、40–130 万 token |
| L2 画面档 | 追加抽帧拼版、帧差量化、定帧回查、局部放大、音频三层检测、区域取色，产出分级问题清单与优化动作清单 | 约 30–40 分钟（实测 27–37）、330–480 万 token |

无口播视频（无音轨或 ASR 零文本）走画面文案分支（SKILL.md §2.1）：pipeline 按客观信号直通切换——帧差事件/静止期合成逐屏区间（时间轴为帧差实测）→ 每屏定帧精读（`--screen-mode frames`：抓每屏一帧由模型读图；`--screen-mode ocr`：无读图能力时 `screen_ocr.py` 回退 + 组装器自动成稿，纯标准库直连官方托管 PaddleOCR API）→ 产出 `transcript.screen.*` 画面文案稿。

执行链：`doctor` 自检 → **单轮开工确认门** → `pipeline.py --tier <档位>` 一条命令完成全部机械采集（取链/转写/探测/无口播分支/L2 基础证据，幂等可重跑，收尾报告带 branch / stats / ai_next 指路）→ 模型做确认门、读图成稿、内容分析与定点取证（定帧/取色单步调用）。每个脚本把运行状态与产物清单写进 `manifest.json`，归档失败会在校验中直接暴露。

多视频（SKILL.md §2.2）：一次给多条时同一条命令直接批量——`pipeline.py <输入1> <输入2> ... --tier <档位>` 或 `--batch 清单.txt`；每条独立归档 `<批根>/<slug>/`，单条失败不阻塞其余，收尾批报告一屏总览（落盘 `batch-report.json`），`--jobs N` 可选并发（默认串行）；对比类需求产跨视频对比文档落批根。

经验闭环（SKILL.md §5）：判断类经验沉淀在 `memory/`（INDEX.md 检索入口 + lessons 单条 JSON，git 追踪跨机共享）——开工 doctor 后按平台/形态检索并入确认门；任一步骤失败先查历史教训再诊断；分段统计与目检矛盾时由模型决策重分段（`screen_segments --mode` 三态 + `events_in_segment` 锚点 + `grab_frames --range` 扫窗定点补齐）；收尾自检三问写回新发现，反复验证的经验毕业进代码或文档。脚本层只做能力开关，场景判断一律归模型。

## 边界

- 不做：独立于分析的转写/字幕服务（转写只作为内部分步）、非 B站 链接的视频下载、素材生成、剪辑、通用"图片转文字"（OCR 仅限无口播分支回退）；
- 链接支持矩阵以实测为准：B站 支持；抖音 / 小红书 / 快手 / 视频号 不支持，`fetch.py` 会拒绝并给出手动下载指引。

## 安装

随仓库任一方式安装（skills CLI / Claude Code 插件市场 / 手动链接），见[仓库 README](../../README.md#安装)。

运行时依赖：

- Python 3.9+，`ffmpeg` / `ffprobe` 在 PATH 中可用；
- B站链接下载需要 `yt-dlp`（或 `uvx`）。

### API Key 配置

两个可选 Key、同一套读取规则（**环境变量 > skill 目录 `.env`**，脚本与 doctor 一致；`.env` 已 gitignore，模板见 `.env.example`）：

| Key | 用在哪 | 哪些场景可以不配 | 获取方式 |
| --- | --- | --- | --- |
| `VOLC_BIGMODEL_API_KEY` | 口播视频 L1 转写（内置火山引擎 Seed ASR 托管 API，纯标准库直连，默认模型 `volc.seedasr.auc`） | 无口播分支 / 已有转写稿 / L2 画面档 | [火山控制台 > API Key 管理](https://console.volcengine.com/speech/new/setting/apikeys) |
| `PADDLEOCR_ACCESS_TOKEN` | 无读图能力 agent 的 OCR 回退 | 多模态 agent（能直接读图） | [星河社区访问令牌页](https://aistudio.baidu.com/token)（免费） |

配置步骤（以转写 Key 为例）：

```bash
cd skills/video-insight
cp .env.example .env   # 然后编辑 .env，填入 VOLC_BIGMODEL_API_KEY
```

也可直接设环境变量；`VOLC_BIGMODEL_RESOURCE_ID` / `VOLC_BIGMODEL_API_BASE` 保持默认即可。OCR 回退不用 token 的替代路径：本地安装 `paddleocr`（或 `uv run --with paddleocr --with paddlepaddle` 临时运行）。

验证：`python scripts/doctor.py --workdir <工作目录>`——Key 未配置只降级为 warn（exit 0，会列出对应的弱可用场景与获取指引），ffmpeg 等硬依赖缺失才是 missing。

## 文档

- [SKILL.md](SKILL.md) — 流程与判断（权威正文）
- [docs/需求与设计文档.md](docs/需求与设计文档.md) — 设计规格与决策理由
- [docs/测试集.md](docs/测试集.md) — 行为协议断言与已知答案回归基准
- [references/](references/) — 输出模板 / 证据纪律 / 画面分析手册
- [memory/INDEX.md](memory/INDEX.md) — 经验层检索入口

许可：MIT（仓库根 [LICENSE](../../LICENSE)）。
