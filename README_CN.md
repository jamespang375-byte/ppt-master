# PPT Master Agent

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Release](https://img.shields.io/github/v/release/jamespang375-byte/ppt-master?include_prereleases&color=blue)](https://github.com/jamespang375-byte/ppt-master/releases)
[![CI](https://img.shields.io/github/actions/workflow/status/jamespang375-byte/ppt-master/build-pptsaas.yml?label=build)](https://github.com/jamespang375-byte/ppt-master/actions)

[English](./README.md) | 中文

**上传一份文档或粘贴一段需求，在浏览器里得到一份原生可编辑的 PowerPoint——自部署、无 IDE、无提示词门槛、数据不出你的机器。**
导出的 `.pptx` 里每个元素都是真实的 PowerPoint 形状，随处可改。

[⬇ 下载安装包（Windows / Linux）](https://github.com/jamespang375-byte/ppt-master/releases) · [🎬 演示视频（5 分 45 秒）](docs/saas/demo/ppt-master-agent-demo.mp4) · [快速上手](app/README.md) · [中文手册](docs/zh/saas/)

---

## 这是什么

本仓库 fork 自优秀的开源项目 [PPT Master](https://github.com/hugohe3/ppt-master)（在 AI IDE 里运行的 PPT 生成*技能*）。我们把它重构成了一个**产品**：

- **从技能到应用**——原版工作流需要 AI IDE 和提示词驱动；Agent 把同一条久经验证的管线（大纲 → 逐页 SVG → 原生 PPTX）包装成固定、可引导的 Web 流程，任何人都会用。
- **降低门槛**——单包交付、内嵌 Python 运行时；模型支持任何 OpenAI 兼容端点（DeepSeek / GLM / 通义 / 本地 Ollama）；不配任何 key 也有 mock 演示模式跑通全流程。
- **吸收 MYGEM 的实战经验**——我们的姊妹项目 MYGEM 的 PPT Agent 贡献了固定管线设计、对小模型友好的 JSON 契约、Pexels/Wikimedia 搜图配图与单页重生成机制。

## 功能特性

- **两种输入**——上传 Markdown / Word / PDF / PPTX，或直接粘贴最长 10 万字的详细提示词；大纲基于你的材料生成，不是凭空编造。
- **22 套视觉主题**——5 品牌规范（Anthropic / 豆包 / Google / 华为 / 豆包×华为红）、5 机构模板（中国电信 / 招商银行 / 中汽研……）、7 版式风格、5 通用主题，分组卡片选择；密度硬约束：内容页 ≥20 个视觉元素、原生 SVG 图表。
- **先确认再生成**——大纲可逐页编辑（标题、要点、内容摘要、配图检索词、版式），可换主题，确认后再生成。
- **在线预览与编辑**——点击页面文字直接修改、按反馈单页重生成、SVG 源码模式、任意步骤可回退重来。
- **分享链接**——一键生成免登录只读翻页链接，把 deck 发给任何人在线看（可撤销）。
- **SaaS 基础能力**——多用户注册（首个用户即管理员）、按用户 token 配额与计量、管理后台、模型与搜图 key 设置界面（脱敏、热生效）、内嵌"API key 怎么申请"引导。
- **智能配图**——Pexels / Pixabay / Wikimedia / Openverse 并发批量下载、许可溯源，每页专属配图按契约强制嵌入。
- **真实交付物**——经原版 `skills/ppt-master` 转换器导出：原生 DrawingML 形状、可编辑文字、图片与图表。

## 快速开始

**方式 A —— 下载安装包**（Windows zip / Linux AppImage）：解压运行，打开 `http://localhost:8310`，首个注册用户自动成为管理员。

**方式 B —— 源码运行**：

```bash
pip install -r app/backend/requirements.txt -r requirements.txt
python3 app/backend/run.py        # → http://localhost:8310（mock 演示模式）
```

然后在「设置」（管理员）或 `.env` 中配置模型：

```bash
PPTSAAS_LLM_BASE_URL=https://api.deepseek.com/v1
PPTSAAS_LLM_API_KEY=sk-xxx
PPTSAAS_LLM_MODEL=deepseek-chat
PEXELS_API_KEY=你的pexels-key     # 可选，网络配图
```

## 文档

- [架构与 API 契约](docs/saas/ARCHITECTURE.md)
- 中文手册：[部署](docs/zh/saas/DEPLOYMENT.md) · [运维](docs/zh/saas/OPERATIONS.md) · [规格与容量规划](docs/zh/saas/SPEC.md) · [API 获取指南](docs/zh/saas/API_KEYS.md)
- [应用快速上手](app/README.md)

## 原版技能

上游 PPT Master 技能仍完整保留在 [`skills/ppt-master/`](skills/ppt-master/SKILL.md)，在 AI IDE 中照常可用——Agent 复用的是它的转换器与模板资产，而不是取代它。原版文档见 [docs/](docs/)，上游仓库：[hugohe3/ppt-master](https://github.com/hugohe3/ppt-master)。

## 许可证

MIT，与上游一致。上游项目的赞助方致谢见其[原始 README](https://github.com/hugohe3/ppt-master)。
