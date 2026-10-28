# theme-commit 失败处理

按需加载：预检或提交中出现异常时读取。原则是**停止并报告，不自动修复、不改写历史**；任何涉及删除、重置、丢弃暂存状态的操作都必须先获得用户同意。

| 场景 | 处理 |
| --- | --- |
| 已有 staged 改动 | 列出并询问；未处理前暂停，不静默混入 |
| 主题为空 | `git diff --cached --quiet` 命中，跳过并说明 |
| 快速检查失败 | 停止；修复后重新暂存并重跑 |
| hook 失败 | 停止；commit-msg 格式问题按规范修正后重试；不使用 `--no-verify` |
| hook 修改文件 | 重新暂存并重试本次提交 |
| 提交中途失败 | 报告已提交 / 剩余 / index 状态；不自动 reset / amend |
| 批次后完整测试失败 | 报告失败摘要与已提交内容；不自动改写历史 |
| 敏感 / 大文件 | 停止并询问；不强行提交 |
| 合并 / 变基 / 冲突 / detached HEAD | 停止并报告 |

## 报告格式

失败时向用户说明：

1. 已成功提交的内容（hash / subject / files）；
2. 未完成或无归属的主题；
3. 当前 index 与 worktree 状态（`git status --short`）；
4. 建议的下一步（修复检查 / 处理敏感文件 / 让用户决定暂存区），但不要替用户执行破坏性操作。

## 不做的事

- `git reset --hard`、`git checkout --`、`git restore`（未经同意）、`git clean`。
- `git commit --amend`、`git rebase`、`git push --force`。
- 为让检查通过而跳过 hook（`--no-verify`）或删除测试。
