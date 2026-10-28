# zero-coding

从零启动一个个人项目的轻量工作流：先判规模分路——小活一轮对齐直接做，立项走 SPEC 范围契约 + 垂直切片。核心信念是 agent 能力越强，过多的文档越是束缚——只维护代码与 git 历史推导不出的信息，方案确认尽量委托平台自带能力（Plan Mode、子 Agent 调研）。

## 何时触发

- 用户带着新想法从空目录开始（"我想做个……"）、需要固化需求或搭建项目骨架；
- 不触发：项目已有成熟的文档体系与开发规范，或用户只是临时求助并不打算立项。

## 工作方式

首次触发先判路并告知（用户可改判），判据是会话容量——当前上下文窗口装得下从想法到交付的全过程，就走小活路线：

| 路线 | 适用 | 怎么走 | 完成标志 |
| --- | --- | --- | --- |
| 小活 | 一个会话能做完（小工具、脚本、单页面） | 对齐一轮 → 平台 Plan Mode（没有则 3~5 句方案）→ 直接实现；不建项目文档，仅不可逆选择记 DECISIONS | 交付可用 |
| 立项 | 需要多会话的 MVP | 对齐 → SPEC 确认（硬门槛：确认前不写产品代码，原型除外）→ 骨架（AGENTS.md 每条命令真实执行过）→ 逐片实现（不显然的片动工前走 Plan Mode / 方案对齐）→ 收敛收尾 | MVP 全程可演示 |

## 最小文档集（3 个，不增不减）

| 文件 | 一句话定位 | 生命周期 |
| --- | --- | --- |
| docs/SPEC.md | 范围契约，只综合已定决策 | MVP 交付后删除 |
| docs/DECISIONS.md | 轻量 ADR，条目一行式，只追加 | 永久 |
| AGENTS.md | 会话级上下文，保持克制（<100 行） | 持续维护 |

README.md 是常规惯例，骨架期写最小版自然长成，不作为工作流管理对象。

三条核心原则：

- **按规模分路**：小活跳过全部仪式，立项才建文档——判断标准是"一个会话能否做完"，而非项目重要程度；
- **拷问先于书写**：对齐阶段事实自查（必要时派子 Agent）、决策问人（每题带推荐答案）、说不清的做一次性原型；SPEC 只综合已定决策，不做新决定；
- **一条走通的路**：MVP 是端到端最薄路径 + 垂直切片，每片独立可验证、一片一提交；收尾对照走通路径收敛核验后再删 SPEC。

## 安装

**让 Agent 代装（推荐）**：把下面这段原样发给你的 Agent。

```text
安装 https://github.com/GitZhiQing/agent-skills 仓库中的 zero-coding skill：
1) 先执行 `npx skills add "GitZhiQing/agent-skills/zero-coding"`，按输出完成安装；
2) 该方式不可用时，克隆仓库后执行 `bash scripts/skills-link.sh zero-coding`，再跑 `bash scripts/skills-doctor.sh` 确认链接健康；
3) 汇报安装位置与验证结果；失败时说明原因，不要跳过验证。
```

**Claude Code 插件市场**：`/plugin marketplace add GitZhiQing/agent-skills`，然后 `/plugin install zero-coding@agent-skills`。

**仓库内手动分发**（Windows junction / Unix symlink，单一来源，`git pull` 后全端生效）：

```bash
git clone https://github.com/GitZhiQing/agent-skills.git
cd agent-skills
bash scripts/skills-link.sh zero-coding    # 全部 skill 用 --all；卸载用 scripts/skills-unlink.sh zero-coding
bash scripts/skills-doctor.sh
```

纯提示词 skill，无运行时依赖；链接完成后，Agent 依据 `SKILL.md` 的 description 自动触发。


## 文档

- [SKILL.md](SKILL.md) — 协议正文（权威来源，含 SPEC 模板与各文档标准）
- [docs/测试集.md](docs/测试集.md) — 行为断言

许可：MIT（仓库根 [LICENSE](../../LICENSE)）。
