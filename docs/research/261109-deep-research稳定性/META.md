# META

- 档位：中
- 日期：2026-11-09
- 执行环境：ZCode + kimi-code-cn/k3.1-pro
- 工具组合：ddgs-web-access 搜索；WebFetch 抓取；Brave 官方站在 WebFetch 超时后使用 ddgs-web-fetch 备用通道
- 调研目标：调研社区资料，寻找提升本仓库 deep-research skill 全面稳定性的方法，覆盖流程遵循、故障恢复、证据可靠性、回归评测，以及 Exa、Tavily 等带免费额度搜索 API 的接入评估。
- 输出目录（绝对路径）：E:\code\ai\skills\docs\research\261109-deep-research稳定性
- 假设声明：无
- 确认来源：结构化提问结果 + 用户文本（在 Q4 追加“考虑引入其他有免费额度的搜索 API，如 Exa、Tavily”）
- 查询预算与实际：8~15 / 15 个 query；另有明确标注的直连抓取，不计 query
- 来源登记：27 条，其中 24 条在用、3 条已排除
- 语言策略：中英官方资料交叉验证；OpenAI 中英文页互证，Azure 中文架构指南提供独立中文证据
- 源码基线：不涉及（未做外部源码调研）
- 执行边界：未配置或调用需注册服务的 API key；API 价格、额度与能力仅做官方文档核验，未做调用实测；未修改 deep-research skill
