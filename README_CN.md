# PPT Master Agent

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Release](https://img.shields.io/github/v/release/jamespang375-byte/ppt-master?include_prereleases&color=blue)](https://github.com/jamespang375-byte/ppt-master/releases)
[![CI](https://img.shields.io/github/actions/workflow/status/jamespang375-byte/ppt-master/build-pptsaas.yml?label=build)](https://github.com/jamespang375-byte/ppt-master/actions)

[English](./README.md) | 中文

**上传文档或粘贴需求，在浏览器里得到一份原生可编辑的 PowerPoint。自部署、无 IDE、无提示词门槛。**

[⬇ 下载安装包（Windows / Linux）](https://github.com/jamespang375-byte/ppt-master/releases) · [🎬 演示视频（5 分 45 秒）](docs/saas/demo/ppt-master-agent-demo.mp4) · [快速上手](app/README.md) · [中文手册](docs/zh/saas/)

---

## 来龙去脉：为什么把 Skill 重写成 Agent

### 洞察：Skill 的执行方式存在结构性问题

过去一年，学术界和工业界都在追问同一个问题：大模型技能（Skill）应该怎样被可靠地执行？包括 SkillRT（上海交通大学，2026 年 4 月）在内的关于 skill 运行时与执行效率的研究，以及我们自己在大模型应用项目（MYGEM，内部深度研究与内容生成平台）中的工程实践，让我们观察到同一个事实——

**让 LLM 以"自由发挥"的方式逐步骤执行一个复杂 skill，存在三个绕不开的问题：**

1. **效率低下**：每一步都要重新推理"下一步该做什么"，大量 token 消耗在流程决策而非内容生产上；生成一份 PPT，模型要把"读规范、选模板、想版式、写坐标"全部在上下文里滚一遍。
2. **Token 浪费**：skill 的长篇规范文档（我们的 PPT skill 规范超过数千行）每轮都要注入上下文；同样的约束被反复读取、反复推理，成本随页数线性甚至超线性膨胀。
3. **稳定性差**：自由执行意味着自由出错——坐标漂移、元素重叠、JSON 截断、导出失败，同一份输入跑十次可能有三种失败方式，无法作为产品交付给非技术用户。

### 思路：Compiled Skill —— 把不确定性收敛到最小必要决策点

我们的答案是**把 skill"编译"成固定管线**：像编译器把高级语言落成确定性指令一样，我们把 skill 的执行过程拆解成阶段，**LLM 只保留在它不可替代的少数决策点上**（理解材料、规划大纲、创作页面内容），其余全部交给确定性代码——解析、模板注入、图片获取、质量检查、格式转换、导出。

```
上传材料 → [代码] 解析(source_to_md)
        → [LLM] 一次调用产出大纲 JSON（严格契约 + 自动修复）
        → [人]   浏览器确认/编辑（这是产品，不是黑盒）
        → [代码] 并发批量配图（Pexels/Wikimedia，许可溯源）
        → [LLM] 逐页并发生成（主题规范与版式目录注入，密度硬约束）
        → [代码] 质量检查 → 导出原生 PPTX（svg_to_pptx）
```

这套"compiled skill"带来的收益是可测量的：DeepSeek 级别的小模型即可稳定产出（不需要旗舰模型）；token 消耗可预测、可按用户计量配额；失败点从"随机的每一步"收敛到"可重试的两个 LLM 阶段"，pipeline 级重试让失败项目可以一键自愈。

### 落地：内部实践 × 优秀开源

我们把 MYGEM 项目中的 PPT Agent 实践抽离出来，fork 了上游优秀的 [PPT Master](https://github.com/hugohe3/ppt-master) skill——它的 SVG→原生 PPTX 转换器、22 套品牌/机构/版式模板资产、文档解析脚本都是一流水准——在其资产之上**重写了整条管线**，封装成一个 Windows / Linux 单包交付的应用盒子：内嵌 Python 运行时、多用户与 token 配额、可视化设置、开箱即用。

## 功能特性

- **两种输入**：上传 Markdown / Word / PDF / PPTX，或粘贴最长 10 万字的详细提示词；大纲基于材料，不是凭空编造。
- **22 套视觉主题**：5 品牌规范（Anthropic / 豆包 / Google / 华为 / 豆包×华为红）、5 机构模板（中国电信 / 招商银行 / 中汽研……）、7 版式、5 通用；内容页 ≥20 视觉元素、原生 SVG 图表的密度硬约束。
- **先确认再生成**：大纲逐页可编辑（标题/要点/摘要/配图词/版式），可换主题，确认后再生成。
- **在线预览与编辑**：点击页面文字直接改、按反馈单页重生成、SVG 源码模式、任意步骤可回退。
- **分享链接**：一键生成免登录只读翻页链接（可撤销），deck 发给任何人在线看。
- **SaaS 基础**：多用户注册（首个即管理员）、按用户 token 配额与计量、管理后台、模型与搜图 key 设置界面（脱敏、热生效）、内嵌 API 申请引导。
- **智能配图**：Pexels / Pixabay / Wikimedia / Openverse 并发批量下载、许可溯源、每页专属配图强制嵌入。
- **真实交付物**：原生 DrawingML 形状导出，文字、图片、图表在 PowerPoint 里全部可编辑。

## 快速开始

**方式 A —— 安装包**：从 [Releases](https://github.com/jamespang375-byte/ppt-master/releases) 下载 Windows zip 或 Linux AppImage，解压运行，打开 `http://localhost:8310`，首个注册用户即管理员。

**方式 B —— 源码**：

```bash
pip install -r app/backend/requirements.txt -r requirements.txt
python3 app/backend/run.py        # → http://localhost:8310（mock 演示模式）
```

模型在「设置」界面或 `.env` 中配置（DeepSeek / GLM / 通义 / 本地 Ollama 均可）：

```bash
PPTSAAS_LLM_BASE_URL=https://api.deepseek.com/v1
PPTSAAS_LLM_API_KEY=sk-xxx
PPTSAAS_LLM_MODEL=deepseek-chat
PEXELS_API_KEY=你的pexels-key     # 可选，网络配图
```

## 文档

- [架构与 API 契约](docs/saas/ARCHITECTURE.md)
- 中文手册：[部署](docs/zh/saas/DEPLOYMENT.md) · [运维](docs/zh/saas/OPERATIONS.md) · [规格与容量规划](docs/zh/saas/SPEC.md) · [API 获取指南](docs/zh/saas/API_KEYS.md)
- [应用快速上手](app/README.md) · 原版技能文档：[skills/ppt-master/](skills/ppt-master/SKILL.md)

## 致谢

本项目是 [hugohe3/ppt-master](https://github.com/hugohe3/ppt-master) 的 fork——没有它优秀的转换器、模板资产和开创性的"AI 生成而非套模板"理念，就没有这个应用。我们只是在它的地基上，结合内部实践做了管线重构与产品化。

**如果你觉得这个项目不错，请去支持原作者 hugohe3**——给他的仓库点 Star，或通过他 README 里的赞助渠道（PackyCode / APIKEY.FUN / RunAPI / 优云智算）请他喝杯咖啡 ☕：

- 上游仓库：https://github.com/hugohe3/ppt-master
- 上游在线演示：https://hugohe3.github.io/ppt-master/

## 许可证

MIT，与上游一致。
