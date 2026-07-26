# PPT Master Agent

> 🎬 全流程演示视频（登录 → 新建 → 选风格 → 大纲 → 生成 → 在线编辑 → 导出，5 分 45 秒）：[`docs/saas/demo/ppt-master-agent-demo.mp4`](../docs/saas/demo/ppt-master-agent-demo.mp4) SaaS

把 PPT Master 技能变成可部署的多用户 Web 应用：上传资料（md/docx/pdf/pptx/txt）或输入主题 → AI 规划大纲 → 你在页面上确认/修改 → 逐页生成 SVG 幻灯片并预览 → 一键导出原生可编辑的 PPTX。

技术栈：FastAPI + SQLite + 零构建静态前端（vanilla HTML/JS/CSS），后台任务用 asyncio，无 Redis、无 Node 工具链。架构与 API 契约见 [`docs/saas/ARCHITECTURE.md`](../docs/saas/ARCHITECTURE.md)。

---

## 5 分钟跑起来

### 第一步：安装（约 2 分钟）

在**仓库根目录**执行（Python 3.10+）：

```bash
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r app/backend/requirements.txt -r requirements.txt
```

### 第二步 A：mock 模式直接演示（0 配置）

什么都不用配，直接启动：

```bash
python3 app/backend/run.py
```

浏览器打开 `http://localhost:8310`，注册一个账号（**首个注册用户自动成为 admin**），新建项目：输入一个主题或上传一份文档，走完「大纲确认 → 生成 → 预览 → 导出 PPTX」全流程。

未配置 `PPTSAAS_LLM_API_KEY` 时即为 mock 演示模式：大纲用内置样例、页面生成占位 SVG，不消耗任何 token，用来验证部署与演示流程。

### 第二步 B：接真实模型（1 分钟）

在仓库根目录建 `.env`：

```ini
PPTSAAS_LLM_BASE_URL=https://api.deepseek.com/v1
PPTSAAS_LLM_API_KEY=sk-你的key
PPTSAAS_LLM_MODEL=deepseek-chat

# 可选：图片搜索，不配则自动回退 Openverse+Wikimedia 免费源
PEXELS_API_KEY=你的pexels-key
```

重启 `python3 app/backend/run.py`，再建一个项目即为真实生成。任何 OpenAI 兼容端点都行（DeepSeek / GLM / Qwen / 本机 Ollama），本机模型接入见 [`docs/zh/saas/DEPLOYMENT.md`](../docs/zh/saas/DEPLOYMENT.md) 第 4 章。

---

## 常用配置（全部可选，均有默认值）

| 环境变量 | 默认值 | 说明 |
|---|---|---|
| `PPTSAAS_PORT` / `PPTSAAS_HOST` | `8310` / `0.0.0.0` | 监听地址 |
| `PPTSAAS_DATA_DIR` | `./data` | 数据目录（SQLite + 项目文件） |
| `PPTSAAS_LLM_TIMEOUT` | `600` | 单次 LLM 调用超时（秒） |
| `PPTSAAS_MAX_ACTIVE_PROJECTS` | `2` | 全局并发生成任务数 |
| `PPTSAAS_MAX_CONCURRENT_PAGES` | `4` | 单项目页面生成并发 |
| `PPTSAAS_DEFAULT_TOKEN_QUOTA` | `2000000` | 每用户 token 配额（0 = 不限） |
| `PPTSAAS_REGISTRATION_OPEN` | `true` | 是否开放注册 |

完整配置表见 ARCHITECTURE.md 第 3 节。

## 数据在哪

```
data/
├── app.db              # 用户、会话、项目、token 计量、主题
└── projects/<id>/      # sources.md、outline.json、images/、svg_output/、exports/*.pptx
```

备份整个 `data/` 目录即备份全部数据。

## 打包分发

- Windows 单机 exe：`app/packaging/build_windows.ps1`
- Linux AppImage：`app/packaging/build_linux.sh`

详见部署手册。

## 文档

- API 获取与配置指南（DeepSeek / GLM / 百炼 / 本地模型 / Pexels / Pixabay 申请与填写）：[`docs/zh/saas/API_KEYS.md`](../docs/zh/saas/API_KEYS.md)
- 部署手册（源码 / exe / AppImage / 本地模型）：[`docs/zh/saas/DEPLOYMENT.md`](../docs/zh/saas/DEPLOYMENT.md)
- 运维手册（用户管理、计量、备份、排错、升级）：[`docs/zh/saas/OPERATIONS.md`](../docs/zh/saas/OPERATIONS.md)
- 规格与容量规划（并发档位、硬件、token 成本）：[`docs/zh/saas/SPEC.md`](../docs/zh/saas/SPEC.md)
