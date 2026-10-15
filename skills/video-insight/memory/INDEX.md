# memory/INDEX.md · video-insight 经验层检索入口

一行一条；检索时 `grep -i <关键词>` 本文件与 `lessons/*.json`（trigger/finding/action 字段）。
条目实际改变了动作时把该条 `used` +1；同一经验多次验证稳定后毕业（进代码或 SKILL.md 一行），
条目转 `graduated`。entry schema 与写回/毕业规则见 `docs/需求与设计文档.md`「记忆层」节。

| id | trigger（可检索信号） | finding（一句话结论） | status |
| --- | --- | --- | --- |
| L-001 | stills: 0 且事件密集 / 分段屏数明显少于 overview 目检 | 微动画背景吃掉静止期，event 锚点合并塌缩成极少数屏 | active |
| L-002 | uniform 采样后拼版屏数 > n_screens / dwell_s 异常长段 | 短于采样间隔的屏可能整屏被跳过 | active |
| L-003 | grab_frames 报 Non full-range YUV / mjpeg 编码错误 | 新版 ffmpeg mjpeg 拒绝有限色域 YUV | graduated |
| L-004 | python -c 内联 CJK 引号脚本在 Git Bash 报错 | shell 转义破坏中文引号与多字节字符 | active |
