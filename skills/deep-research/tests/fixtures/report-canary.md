# 中文标题 · 机制对标调研报告

> 版本说明：canary 样张，覆盖 deep-research 报告的全部受控语法。

## 摘要

- **结论一**：Plan 管动手前，Goal 管收尾，强制力完全不同<sup>[S1], [S2]</sup>。
- 结论二：TODO 是零副作用的回声工具（单源）<sup>[S3]</sup>。
- 结论三：静态阅读推断的运行时行为需标注（推断）<sup>[S1]</sup>。

## 一、机制分析

### 1.1 官方口径

正文段落，含行内代码 `update_plan` 与中文标点。结论放段首，证据在后。

| 维度 | Plan | TODO |
| --- | --- | --- |
| 强制力 | 执行层门禁 | 纯提示词 |
| 状态载体 | 计划文件 | 内存列表 |

> 注意：块引用作为 callout 呈现。

### 1.2 代码证据

代码结论用固定 SHA 永久链接：[C1·plan.rs:42](https://github.com/example/repo/blob/0123456789abcdef0123456789abcdef01234567/codex-rs/plan.rs#L42)。

```python
def handler():
    return "Plan updated"
```

## 未覆盖与不确定

- 运行时行为未实测。

## 附录 A · 来源与证据

### 官方

| 编号 | 来源 | 类型 | 访问日期 | 语言 | 时效 |
| --- | --- | --- | --- | --- | --- |
| S1 | [权限模式文档](https://example.com/permission-modes) | 官方 | 2026-11-17 | en | 常青 |
| S2 | [PlanHandler 源码](https://example.com/plan.rs) | 官方仓库 | 2026-11-17 | en | 常青 |

### 社区观点

| 编号 | 来源 | 类型 | 访问日期 | 语言 | 时效 |
| --- | --- | --- | --- | --- | --- |
| S3 | [echo 工具分析](https://example.com/agents-are-hard) | 社区观点 | 2026-11-17 | en | 近期 |

### 证据摘要与反向索引

- **S1**（官方 · en · 常青）：权限模式决定 Plan 的门禁强度。支撑：§1.1。
- **S2**（官方仓库 · en · 常青）：PlanHandler 在执行层拦截。支撑：§1.1。
- **S3**（社区观点 · en · 近期）：TODO 仅回声，无副作用。支撑：§1.2。

### 排除留痕

| 编号 | 来源 | 排除原因 |
| --- | --- | --- |
| S4 | [过期转载](https://example.com/stale) | 被 S1 推翻（版本过期） |

### 源码快照

| 编号 | 仓库 | 本地路径 | 固定 commit | 版本 / 标签 | 获取日期 | 分析范围 | 状态 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| C1 | https://github.com/example/repo | sources/repo/ | 0123456789abcdef0123456789abcdef01234567 | — | 2026-11-17 | codex-rs/plan.rs | 在用 |

## 附录 B · 调研元信息

附录 B 字段为粗体标签行（渲染器页脚消费前四个）；格式示例：`**标签**：值`。

- **日期**：2026-11-17
- **模型**：claude-opus-4-6
- **平台**：Claude Code
- **工具组合**：WebSearch 搜索 / WebFetch 抓取
- **调研目标**：对比 Plan 与 TODO 的强制力差异
- **输出目录**：/tmp/example/261117-机制对标/
- **假设声明**：无
- **确认来源**：结构化提问结果（两屏：环境屏 + 计划屏）
- **源码基线**：C1 @ 0123456
- **实际投入**：3 个子问题 / 约 6 轮搜索 / 单线程

<!-- 链接定义区：供正文上标引用跳转，渲染时隐藏 -->
[S1]: https://example.com/permission-modes "权限模式文档 · 官方 · 访问 2026-11-17"
[S2]: https://example.com/plan.rs "PlanHandler 源码 · 官方仓库 · 访问 2026-11-17"
[S3]: https://example.com/agents-are-hard "echo 工具分析 · 社区观点 · 访问 2026-11-17"