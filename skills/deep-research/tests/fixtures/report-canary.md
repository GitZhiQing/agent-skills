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

## 来源引用

按来源层分组；编号与登记簿一致。

### 官方

| 编号 | 来源 | 类型 | 访问日期 |
| --- | --- | --- | --- |
| S1 | [权限模式文档](https://example.com/permission-modes) | 官方 | 2026-11-17 |
| S2 | [PlanHandler 源码](https://example.com/plan.rs) | 官方仓库 | 2026-11-17 |

### 社区观点

| 编号 | 来源 | 类型 | 访问日期 |
| --- | --- | --- | --- |
| S3 | [echo 工具分析](https://example.com/agents-are-hard) | 社区观点 | 2026-11-17 |

<!-- 链接定义区：供正文上标引用跳转，渲染时隐藏 -->
[S1]: https://example.com/permission-modes "权限模式文档 · 官方 · 访问 2026-11-17"
[S2]: https://example.com/plan.rs "PlanHandler 源码 · 官方仓库 · 访问 2026-11-17"
[S3]: https://example.com/agents-are-hard "echo 工具分析 · 社区观点 · 访问 2026-11-17"
