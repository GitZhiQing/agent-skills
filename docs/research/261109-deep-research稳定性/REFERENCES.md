## 素材登记簿 · deep-research 稳定性（2026-11-09，档位 中，工具 ddgs-web-access 搜索 / WebFetch 抓取）

| 编号 | 链接 | 标题 | 摘要 | 类型 | 访问日期 | 语言 | 时效 | 支撑结论 | 状态 | 排除原因 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| S1 | https://docs.langchain.com/oss/python/langgraph/interrupts | LangGraph Interrupts | interrupt 依赖 checkpointer 与 thread_id 保存/恢复状态；恢复会重跑所在节点，因此批准前副作用应可重放或后置，resume 输入可用 schema 校验。 | 官方 | 2026-11-09 | en | 近期 | 流程状态机、确认门与恢复 | 在用 | — |
| S2 | https://openai.github.io/openai-agents-python/human_in_the_loop/ | OpenAI Agents SDK Human-in-the-loop | RunState 可序列化并恢复；允许只处理部分 interruptions，未决项会再次暂停；快照需可信存储并防并发/重放，批准不等于 exactly-once。 | 官方 | 2026-11-09 | en | 近期 | 显式审批状态、部分回答、取消与恢复 | 在用 | — |
| S3 | https://www.anthropic.com/research/multi-agent-research-system | How we built our multi-agent research system | 建议检查点续跑、完整 tracing、外部记忆与大产物引用；开放式研究可并行分工，但多 Agent 高 token 成本且不适合强共享上下文任务。 | 官方 | 2026-11-09 | en | 常青 | 检查点恢复、来源质量、并行取舍与生产追踪 | 在用 | — |
| S4 | https://www.anthropic.com/research/demystifying-evals-for-ai-agents | Demystifying evals for AI agents | 建议能力集与回归集分开；每任务多次试验，以 pass@1 衡量单次成功率、pass^k 衡量连续一致性；结合确定性检查、模型评分与 transcript 失败分析。 | 官方 | 2026-11-09 | en | 近期 | 稳定性指标、重复试验与评测设计 | 在用 | — |
| S5 | https://agentskills.io/skill-creation/best-practices | Best practices for skill creators | 强调从真实执行与失败案例提炼规则，按脆弱性校准约束强度，提供默认值、检查清单、验证循环和渐进披露；过度全面反而分散注意力。 | 官方 | 2026-11-09 | en | 常青 | 提示词协议、验证循环与渐进披露 | 在用 | — |
| S6 | https://claude.com/resources/articles/improving-skill-creator-test-measure-and-refine-agent-skills | Improving skill-creator: Test, measure, and refine Agent Skills | 独立 Agent 干净上下文并行评测，分别记录 token 与耗时；支持 benchmark 和盲测 A/B，防止上下文串扰并比较版本收益。 | 官方 | 2026-11-09 | en | 近期 | skill 评测隔离、版本对照与成本指标 | 在用 | — |
| S7 | https://agentskills.io/skill-creation/evaluating-skills | Evaluating skill output quality | 建议 evals.json、with/without 或新旧版本对照、干净上下文、客观断言与具体证据；记录通过率/耗时/token 均值和标准差，多次运行定位不一致。 | 官方 | 2026-11-09 | en | 常青 | skill 可执行评测、重复试验与版本对比 | 在用 | — |
| S8 | https://cheatsheetseries.owasp.org/cheatsheets/AI_Agent_Security_Cheat_Sheet.html | OWASP AI Agent Security Cheat Sheet | 预防控制包括只读最小权限、执行层工具校验、精确绑定的一次性审批、记忆隔离与限额、熔断和回滚；日志与异常检测用于审计而非替代预防。 | 官方 | 2026-11-09 | en | 近期 | 工具权限、状态、审批与故障 containment | 在用 | — |
| S9 | https://cheatsheetseries.owasp.org/cheatsheets/LLM_Prompt_Injection_Prevention_Cheat_Sheet.html | OWASP LLM Prompt Injection Prevention Cheat Sheet | 外部内容应标为数据而非指令，但定界并非安全边界；授权必须由执行代码校验，需用真实抓取渠道做注入与误报回归。 | 官方 | 2026-11-09 | en | 近期 | 网页内容隔离、工具限制与注入测试 | 在用 | — |
| S10 | https://github.com/assafelovic/gpt-researcher | GPT Researcher 公开仓库 | 搜索连续空结果，已知公开仓库直连亦超时，未获得可核验正文。 | 社区项目 | 2026-11-09 | en | — | — | 已排除 | 搜索与直连均失败，未核验，不据此形成结论 |
| S11 | https://arxiv.org/abs/2506.11763 | DeepResearch Bench | 100 个跨 22 领域专家任务；报告质量与检索/引用分开评价，后者使用 effective citation count 与 overall citation accuracy。 | 论文 | 2026-11-09 | en | 常青 | 研究质量与引用质量分层评测 | 在用 | — |
| S12 | https://deepresearch-bench.github.io/ | DeepResearch Bench 项目页 | RACE 评价完整性、深度、指令遵循、可读性；FACT 评价引用准确性和有效引用数；任务中英各 50，可借鉴分维度评价而非只看总分。 | 官方项目 | 2026-11-09 | en | 近期 | 深度研究评价维度、双语任务与基准复用 | 在用 | — |
| S13 | https://exa.ai/pricing | Exa Pricing | 官方页载明注册免费额度为每月重置的 10 美元，约覆盖 2500 次 Lite 搜索，无需支付方式但需 API key；搜索和 contents 分开计费。 | 官方 | 2026-11-09 | en | 快速变化 | Exa 免费额度、计费与接入成本 | 在用 | — |
| S14 | https://docs.exa.ai/reference/search | Exa Search API | 支持 lite/auto/deep、域名与日期过滤、正文/highlights/summary、缓存与 livecrawlTimeout；401/402/429/5xx 语义明确，429 数值限额未在该页给出。 | 官方 | 2026-11-09 | en | 快速变化 | Exa 搜索能力、结构化结果、错误与超时处理 | 在用 | — |
| S15 | https://docs.exa.ai/reference/contents | Exa Contents API | 按 URL 提取 Markdown、highlights 或 summary；支持缓存新鲜度和超时，批量请求须逐 URL 检查 statuses，内容视图分别计费。 | 官方 | 2026-11-09 | en | 快速变化 | Exa 正文抓取、缓存与部分失败处理 | 在用 | — |
| S16 | https://www.tavily.com/pricing | Tavily Pricing | Researcher 免费计划每月 1000 API credits，无需信用卡但需注册和 API key；额度每月一日重置，耗尽后停止至重置或升级。 | 官方 | 2026-11-09 | en | 快速变化 | Tavily 免费额度、配额耗尽与接入成本 | 在用 | — |
| S17 | https://docs.tavily.com/documentation/api-reference/endpoint/search | Tavily Search API | basic/fast/ultra-fast 每次 1 credit，advanced 2；支持域名/日期/语言过滤、Markdown raw content、缓存控制、request_id，以及 429/432/433/434 等明确错误。 | 官方 | 2026-11-09 | en | 快速变化 | Tavily 搜索能力、计费、限速与错误处理 | 在用 | — |
| S18 | https://docs.tavily.com/documentation/api-reference/endpoint/extract | Tavily Extract API | 单批 1~20 URL，输出 Markdown/文本；basic 默认 10 秒、advanced 30 秒，HTTP 200 也须检查 failed_results，按成功提取数累计计费。 | 官方 | 2026-11-09 | en | 快速变化 | Tavily 正文抓取、超时与部分失败处理 | 在用 | — |
| S19 | https://api-dashboard.search.brave.com/app/documentation/web-search/get-started | Brave Web Search API Get Started | Brave 官方 Web Search API 入门文档，直连超时，未获得正文。 | 官方 | 2026-11-09 | en | — | — | 已排除 | 直连超时；改用 S22 快速入门与 S23 查询文档 |
| S20 | https://pypi.org/project/ddgs/ | ddgs Python package | 9.16.1 发布于 2026-10-23；文本搜索覆盖 Bing、Brave、DuckDuckGo、Google 等多后端，extract 支持 Markdown 等格式；默认 HTTP 超时 5 秒，页面未承诺重试或限速保障。 | 官方包发布 | 2026-11-09 | en | 快速变化 | 当前 ddgs 多后端能力、维护与运行时约束 | 在用 | — |
| S21 | https://api-dashboard.search.brave.com/app/plans | Brave Search API Pricing | Search 为预付制，5 美元/1000 请求，每月自动赠送 5 美元 credits，标称容量 50 请求/秒；包含 Web Search 与面向模型的 LLM Context。 | 官方 | 2026-11-09 | en | 快速变化 | Brave 免费额度、计费、容量与产品边界 | 在用 | — |
| S22 | https://api-dashboard.search.brave.com/documentation/quickstart | Brave Search API Quickstart | 注册需有效邮箱，激活计划需信用卡，再创建 API key；Search plan 含 LLM Context 与 Web Search，LLM Context 返回提取文本和来源元数据。 | 官方 | 2026-11-09 | en | 快速变化 | Brave 接入门槛、密钥与正文能力 | 在用 | — |
| S23 | https://api-dashboard.search.brave.com/documentation/services/web-search | Brave Web Search | 支持 freshness、国家/语言、extra snippets、Goggles、搜索运算符与分页；面向 Agent 官方建议改用 LLM Context。 | 官方 | 2026-11-09 | en | 快速变化 | Brave 搜索过滤、分页与 Agent 接入 | 在用 | — |
| S24 | https://api-dashboard.search.brave.com/documentation/guides/rate-limiting | Brave API Rate Limiting | 以 1 秒滑动窗口限速，响应头给出限额、剩余量与重置秒数；429 应依据 reset 等待并退避，只有成功请求计入配额和计费。 | 官方 | 2026-11-09 | en | 快速变化 | Brave 可观测配额、重试与计费语义 | 在用 | — |
| S25 | https://openai.github.io/openai-agents-python/zh/human_in_the_loop/ | OpenAI Agents SDK 人工参与 | 官方中文文档与 S2 一致：审批中断、可信 RunState 序列化、批准/拒绝后恢复，以及部分审批未决项再次暂停。 | 官方 | 2026-11-09 | zh | 近期 | S2 的中文交叉验证 | 在用 | — |
| S26 | https://learn.microsoft.com/zh-cn/azure/architecture/ai-ml/guide/ai-agent-design-patterns | AI 代理编排模式 | 中文官方架构指南：采用满足要求的最低复杂度；外置持久化任务进度与中间结果，设置超时/重试/熔断、输出验证和迭代上限，并明确人工批准与修改反馈的区别。 | 官方 | 2026-11-09 | zh | 近期 | 状态恢复、故障降级、HITL 与复杂度控制 | 在用 | — |
| S27 | https://www.anthropic.com/zh-cn/research/multi-agent-research-system | Anthropic 多智能体研究系统中文镜像候选 | 直接核验返回 HTTP 404，未获得中文页面。 | 官方 | 2026-11-09 | zh | — | — | 已排除 | 页面不存在；保留英文原文 S3 |

## 检索轮次台账

| 轮次 | 查询 | 新增 / 更新来源 |
| --- | --- | --- |
| 1 | LangGraph official human-in-the-loop interrupts persistence durability checkpointer | 新增 S1 |
| 2 | site:openai.github.io/openai-agents-python human in the loop sessions interruptions approval | 搜索超时，自动重试仍失败；按纪律退避后换后端重试 |
| 3 | OpenAI Agents SDK human in the loop approvals sessions official documentation | 新增 S2 |
| 4 | site:anthropic.com engineering multi-agent research system evaluation orchestrator worker | 新增 S3 |
| 5 | Agent Skills official best practices evaluation testing skill reliability Anthropic | 新增 S4、S5、S6；S5 外链新增 S7 |
| 6 | GPT Researcher official documentation architecture citations source aggregation scraping | 搜索超时/后端错误，待退避换后端重试 |
| 7 | GPT Researcher docs architecture report citations scraper official | 空结果；连续失败后按要求退避，准备最后一次简化查询 |
| 8 | GPT Researcher GitHub | 仍为空结果，停止该搜索路径；直接核验仓库亦超时，登记排除 S10 |
| 9 | OWASP official agentic AI prompt injection least privilege tools security guide | 新增 S8、S9 |
| 10 | deep research agent benchmark citation correctness completeness evaluation official paper | 新增 S11、S12 |
| 11 | site:docs.exa.ai pricing free credits search contents API rate limits | 搜索超时，待退避后简化重试 |
| 12 | Exa API pricing free credits official | 搜索空结果；直接抓取官方价格页成功，新增 S13；官方文档外链新增 S14、S15 |
| 13 | Tavily API pricing free credits search extract official | 搜索空结果；直接抓取官方价格页成功，新增 S16；官方文档新增 S17、S18 |
| 14 | Brave Search API free plan official pricing queries month | 搜索空结果，官方价格页直连超时；改试官方文档入口，登记 S19；另直接登记 ddgs 包页 S20 |
| 15 | site:api-dashboard.search.brave.com web search API free plan pricing | 新增 S21、S22、S23；S20 已核验；达到中档查询上限，停止新增 query；备用抓取补登 S24 |
| 补充抓取（不计 query） | 官方中文镜像与架构指南直连 | 新增 S25、S26；S27 因 404 排除；中英文证据交叉验证完成 |
