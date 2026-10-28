# AI 深化分析协议（enrichment）

本文定义 scan 之后的可选「深化分析」阶段：Agent 对未命中规则的条目做受限只读探索，把结论写成 `enrichment.json`，由 `enrich` 子命令校验、合并进扫描条目并重新渲染增强报告。规则库覆盖常见目录；深化分析覆盖长尾——不认识的应用缓存、新工具产物。

## 1. 安全边界（先读）

1. **AI 只在「待定」上定档**：`confidence: high` 时，可把 `review` 提升为 `safe` / `caution` / `keep`；提升后该条目不再需要 `--allow-review`。非 `review` 档位的条目，`advice` 只作展示，不改档。
2. **只收紧、不放宽**：AI 永远不能把规则判为「建议保留」的项变成可删（`selectable: false → true` 被禁止），不能把任何条目改成 `suggest`（最高档只由规则授予）。`advice: keep` 会把条目设为不可选。
3. **可修正分类**：`group`（归属）/ `nature`（性质）/ `language`（生态）只能取受控词表中的值；自由造词会被校验拒绝。
4. **探索是只读的**：`ls` 一到两层、看文件名；不递归全树、不读文件内容、不执行任何东西。
5. **诚实标注**：没分析到的条目就是没有 enrichment；证据不足时 `confidence` 写 `low`，不要硬给结论。
6. **可审计**：档位来源写入 `tier_source: "ai"`，原 `review` 可从 `enrichment.json` 回溯；报告用「AI 定档」徽章区分。

## 2. enrichment.json 结构

```json
{
  "skill": "windows-disk-cleanup",
  "schema": 1,
  "scan_id": "20261028-220958-d264",
  "generated_at": "2026-10-28T23:00:00+08:00",
  "analyzer": "ai-agent",
  "budget": { "max_items": 50, "max_depth": 2, "max_seconds": 120, "analyzed": 37 },
  "entries": [
    {
      "path": "C:\\Users\\<user>\\AppData\\LocalLow\\Unity",
      "category": "游戏引擎缓存",
      "language": "",
      "title": "Unity 编辑器缓存",
      "description": "Unity 编辑器的着色器与资产缓存，删除后重新打开工程会重新导入。",
      "advice": "caution",
      "confidence": "high",
      "evidence": ["Cache", "Unity", "ShaderCache"]
    }
  ]
}
```

字段规则：

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `skill` | 建议 | 固定 `windows-disk-cleanup`；其他值拒绝 |
| `schema` | 是 | 当前为 `1` |
| `scan_id` | 是 | 必须与 `scan.json` 一致；跨扫描的分析作废 |
| `analyzer` / `generated_at` / `budget` | 否 | 审计信息；`budget` 记录实际预算消耗 |
| `entries[].path` | 是 | 必须是本次 `scan.json` 中的条目路径；不存在的路径整份拒绝 |
| `category` / `title` / `description` / `language` / `advice` | 至少一个 | 非空字段覆盖条目展示值；`language` 受控枚举（同规则库），`advice` ∈ safe/caution/keep |
| `group` | 否 | 归属，受控：`system` / `app` / `dev` / `user` / `virtual` |
| `nature` | 否 | 性质，受控：`cache` / `log` / `build` / `installer` / `temp` / `content` / `config` / `other` |
| `confidence` | 建议 | `high` / `medium` / `low`；**只有 high 才会改档** |
| `evidence` | 建议 | 字符串数组：判断依据的文件/子目录名，报告徽章悬浮可见 |

## 3. Agent 分析流程

1. **选对象**：`scan.json` 中没有 `rule_id` 的条目（规则命中的已有结论），按大小排序取 top 30~50；总数少可全做。
2. **受限探索**：每条 `ls` 一层（必要时再下一层）；结合目录名、已知软件常识判断；证据（文件名）记入 `evidence`。
3. **预算**：总时长约 2 分钟；超限立即停止，未分析的条目不写进 entries（报告自然保持原样）。
4. **落盘**：写 `$OUT/enrichment.json`（UTF-8）。
5. **校验应用**：先 `enrich --check`，报错就修文件再试；通过后去掉 `--check` 应用。
6. **交付**：增强报告在 `<scan 目录>/enriched/report.html`；向用户说明哪些是 AI 补充的、置信度如何。

## 4. 与经验闭环的衔接

高置信（`confidence: high`）且不同会话反复出现的结论，按 `scope=rule` 记录经验（`mem record`），`used >= 3` 后走人工毕业流程沉淀进 `rules.json`——深化分析是规则库的候选来源，**不要**因为一次分析直接改规则库。

## 5. 命令速查

```bash
S="<skill 目录>"; OUT="<扫描输出目录>"

# 只校验不应用
bash "$S/bin/windows-disk-cleanup" enrich \
  --scan "$OUT/scan.json" --enrichment "$OUT/enrichment.json" --check --json

# 应用并重渲染（默认输出 $OUT/enriched/，可覆盖重跑）
bash "$S/bin/windows-disk-cleanup" enrich \
  --scan "$OUT/scan.json" --enrichment "$OUT/enrichment.json" --json
```

退出码：`0` 成功；`2` 校验失败（schema/scan_id/path/枚举值非法）。增强后的 `scan.json` 与原始扫描 `scan_id` 一致，后续 selection → delete 流程不受影响。
