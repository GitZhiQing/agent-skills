# find-my-xp

成人向深度访谈 skill：带用户看清自己真正被什么打动（XP / 心仪类型 / 性癖）、以及为什么。产出多份并存原型档案 + 一份元地图报告，适度标签化且有血肉细节与深层解读。不是固定题库测试、不是玄学许愿、不是"你配不配"的市场评估。

## 何时触发

- 想探索自己的性癖、心仪类型、理想型或恋爱/性偏好："测测我的XP""我到底喜欢什么类型""帮我理清择偶偏好""find my xp""ideal type"。
- 困惑于反复被同一类人吸引、或审美与身体/依恋错位，想搞懂自己。
- 不触发：分析两个人是否合适/配对兼容性；心理治疗或危机干预；固定题库娱乐测试；创作角色卡；市场可行性评估。

## 工作方式

老练松弛的同行者人格，约 20-30 问 / 30-45 分钟，可中断续访。标本先行 → 三元对比提双极标签 → 阶梯下钻情感需求 → 强制取舍 → 反差探针（瓦解条件/雷区）→ 性脚本与情感基调 → 可选深挖 → 聚类成 2-4 个并存原型 + 回映验证。交付元地图 + N 原型档案（各含表面/互动/内核三层、层间错位、激活情境、XP 链、角色卡），可选私密档案风单文件离线 HTML。

具体描写（外貌/语言/行为/角色卡语气示例）**从人类创作文本提取并署名**，模型只选择匹配不发明，避免 AI 味。来源分级：官方档案/语音 > 百科wiki（萌百/百科/HoYoWiki/米游社）> 论坛深析（NGA/贴吧/豆瓣/知乎/PTT/bilibili），避免百家号等低质自媒体；网文优先可确认原文（百科引原著/赏析直引）。内置**四介质角色档案库**（网文/日漫/虚拟歌手/RPG，约 100 条目：原始描写短引用+社区评价+反差/XP 标签+来源指针）与**深度角色赏析来源**，作认知辅助与借喻来源；未检索到原文者标"待补"不仿写。见 references/corpus-sourcing.md 与 corpus-*.md。

成人 gate 前置（确认成年+自愿+知情）；未成年/非自愿/违法硬拒绝，合法成人癖好正常探索；非评判非诊断；危机信号切安全协议；日志与报告本地落盘、提醒避开 git/云同步。完整协议见 SKILL.md，安全细则见 references/safety.md。

可选 HTML 渲染需 uv >= 0.5（自动装 markdown-it-py）；缺失自动降级为纯 Markdown，不阻塞交付。

## 安装

把下面这段原样发给你的 Agent：

```text
安装 GitHub 仓库 GitZhiQing/agent-skills 里的 find-my-xp skill：优先执行 `npx skills add "GitZhiQing/agent-skills/find-my-xp"`；不可用则克隆仓库后执行 `bash scripts/skills-link.sh find-my-xp`，再跑 `bash scripts/skills-doctor.sh` 验证并汇报结果。
```

其他分发方式见仓库根 README；本 skill 可独立安装和使用，不要求同时安装其他 skill。

## 文档

- [SKILL.md](SKILL.md) — 协议正文（权威来源）
- [references/safety.md](references/safety.md) — 成人 gate、硬拒绝、危机协议、隐私
- [references/interview-guide.md](references/interview-guide.md) — 分阶段题库与探针
- [references/methodology.md](references/methodology.md) — 方法论依据与四成分
- [references/xp-dimensions.md](references/xp-dimensions.md) — 备用探针词表
- [references/corpus-sourcing.md](references/corpus-sourcing.md) — 描写语料来源、提取协议、反 AI 味、公版兜底、档案库指路
- [references/corpus-novel.md](references/corpus-novel.md) / [corpus-anime.md](references/corpus-anime.md) / [corpus-virtual.md](references/corpus-virtual.md) / [corpus-game.md](references/corpus-game.md) — 四介质角色档案库
- [references/report-template.md](references/report-template.md) — 元地图 / 原型档案 / 角色卡模板
- [references/html-render.md](references/html-render.md) — HTML 渲染调用、质量门与降级
- [docs/TESTS.md](docs/TESTS.md) — 行为断言与触发校准
- [docs/SPEC.md](docs/SPEC.md) — 设计决策与依据
- [LICENSE](LICENSE) — MIT

许可：MIT。