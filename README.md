# skills — 个人 AI Agent Skills 集合

存放供 AI coding agent（ZCode / Claude Code / Agents 等）使用的 skills。每个一级子目录是一个独立 skill，以 SKILL.md 为入口；通过链接（Windows junction / Unix symlink）分发到本机各 agent 的 skills 目录，做到单一来源、改一处全端生效。

开发与维护标准（目录结构、frontmatter、版本规则、台账格式、分发与回归流程）见 [docs/开发与维护规范.md](docs/开发与维护规范.md)。

## Skills 一览

各 skill 的完整元信息（版本、依赖、分发链接、文档索引、状态）见 [SKILLS.md](SKILLS.md)。

| Skill | 版本 | 类型 | 说明 |
| --- | --- | --- | --- |
| [ddgs-web-access](ddgs-web-access/) | 0.2.0 | Python CLI | 基于 ddgs 的联网搜索与网页抓取工具（`ddgs-web-search` / `ddgs-web-fetch`） |
| [theme-commit](theme-commit/) | 0.1.0 | 纯提示词 | 分析混杂变更，按逻辑主题分组提交 git |
| [deep-research](deep-research/) | 0.1.0 | 纯提示词 | 先校准问题再调研：环境检查→预检索校准→选项式澄清→档位推荐→增量登记→报告 + 素材登记簿双文档 |

## 快速使用

以 ddgs-web-access 为例（需 [uv](https://docs.astral.sh/uv/) >= 0.5，首次调用自动安装依赖）：

```bash
bash ddgs-web-access/bin/ddgs-web-search "python 3.13 asyncio" -m 5
bash ddgs-web-access/bin/ddgs-web-fetch "https://example.com"
```

各 skill 的调用方法、参数与排障见其目录内的 SKILL.md / README.md。

## 安装与分发

仓库级脚本把指定 skill 链接到本机已发现的 agent skills 目录（Windows junction / Unix symlink，幂等，可重复执行）：

```bash
bash scripts/skills-link.sh --all                  # 分发全部 skill（或指定名称：skills-link.sh theme-commit）
bash scripts/skills-doctor.sh                      # 巡检链接健康（linked/missing/foreign/broken）
bash scripts/skills-unlink.sh --all                # 卸载（只删指向本仓库的链接）
```

新增 skill 用脚手架生成规范骨架，改动后跑校验：

```bash
bash scripts/skills-new.sh my-skill                # SKILL.md + docs/测试集.md 骨架
bash scripts/skills-lint.sh                        # 结构与元数据一致性校验
```

ddgs-web-access 另自带 `scripts/install.sh` / `uninstall.sh`，供把该 skill 目录单独拷走使用的场景；在本仓库内分发统一用上面的根脚本。

## 许可

本仓库以 [MIT](LICENSE) 发布（ddgs-web-access 目录内另附一份，供该 skill 单独拷走使用）。注意上游 ddgs 声明"仅供教育目的使用"，使用时请遵守目标网站服务条款与 robots 协议。
