# video-insight

把一条视频变成可信、可回溯的结构化洞察：先把口播转成文字，做内容结构与话术分析（L1）；需要时再叠加画面帧证据，回答"画面有没有接住口播、字幕排版有没有硬伤、标注时机对不对"（L2）。纯 BGM 无口播、文案烧在画面上的视频也有完整分支：帧差定位每屏文案的起止，逐屏读图（或 OCR 回退）还原画面文案轨。

## 何时触发

- 用户要求分析一条视频的内容、结构、话术，或提出「拉片」「画面分析」「音画对齐」「节奏分析」「字幕排版检查」；
- 无口播 / 纯 BGM / 文案在画面上的视频，或点名「提取画面文案 / 画面文字」；
- 只要意图是理解或评估一条已有视频即适用——未说"分析"二字同样触发；
- 仅需转写字幕或浅摘要（不要结构化分析）、或要求生成素材 / 剪辑时不适用（见边界）。

## 工作方式

两档，成本差约 3–8 倍。执行链：`doctor.py` 自检 → **单轮开工确认门**（[SKILL.md](SKILL.md) §0：环境事实 + 理解陈述 + 交付形态 + 档位推荐与理由；回应只有确认 / 调整 / 显式委托，交互会话不存在默认执行）→ `pipeline.py` 一条命令完成机械采集（取链 / 转写 / 探测 / 无口播分支 / L2 基础证据，幂等可重跑，收尾报告带 branch / stats / ai_next）→ 模型做读图成稿、内容分析与定点取证（定帧 / 取色单步调用）。L2 长跑在中途设**拼版检查点**，方向跑偏不用等交付才发现。

| 档位 | 做什么 | 实测成本 |
| --- | --- | --- |
| L1 文案档 | 转写 → 校对 → 语义分段 → 口播数据 → 逻辑骨架 → 主张与合规核查 | 约 6–10 分钟、40–130 万 token |
| L2 画面档 | 追加抽帧拼版、帧差量化、定帧回查、局部放大、音频三层检测、区域取色，产出分级问题清单与优化动作清单 | 约 30–40 分钟（实测 27–37）、330–480 万 token |

- **无口播 / 批量**：无口播分支（帧差逐屏 + 读图 / OCR 回退）与多视频批量（清单、失败隔离、批报告、可选并发）的完整协议见 [references/no-speech-batch.md](references/no-speech-batch.md)。
- **判断纪律**：实测 / 约 / 推断三档表述、交付前自检见 [references/evidence-discipline.md](references/evidence-discipline.md)。
- **经验闭环**：判断类经验沉淀在 `memory/`，开工检索、失败先查、收尾写回，见 [SKILL.md](SKILL.md) §5 与 [memory/INDEX.md](memory/INDEX.md)。

每个脚本把运行状态与产物清单写进 `manifest.json`，归档失败会在校验中直接暴露。

## 边界

- 不做：独立于分析的转写 / 字幕服务（转写只作为内部分步）、非 B站 链接的视频下载、素材生成、剪辑、通用"图片转文字"（OCR 仅限无口播分支回退）；
- 链接支持矩阵以实测为准：B站 支持；抖音 / 小红书 / 快手 / 视频号 不支持，`fetch.py` 会拒绝并给出手动下载指引。

## 安装

把这句交给你的 Agent（它会自己安装并验证）：

```text
安装 GitHub 仓库 GitZhiQing/agent-skills 里的 video-insight skill：优先 `npx skills add "GitZhiQing/agent-skills/video-insight"`；不可用则 clone 仓库后执行 `bash scripts/skills-link.sh video-insight`，再用 `scripts/skills-doctor.sh` 验证并汇报结果。
```

插件市场与手动分发方式见[仓库 README](../../README.md#安装)。

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
- [references/no-speech-batch.md](references/no-speech-batch.md) — 无口播分支与多视频批量
- [references/output-template.md](references/output-template.md) — 报告固定骨架（L1/L2）
- [references/evidence-discipline.md](references/evidence-discipline.md) — 三档表述、硬规则与交付前自检
- [references/visual-analysis.md](references/visual-analysis.md) — 画面元素检查清单与 BGM 判断
- [memory/INDEX.md](memory/INDEX.md) — 经验层检索入口
- [docs/SPEC.md](docs/SPEC.md) — 设计规格与决策理由
- [docs/TESTS.md](docs/TESTS.md) — 行为协议断言与已知答案回归基准

许可：MIT（仓库根 [LICENSE](../../LICENSE)）。
