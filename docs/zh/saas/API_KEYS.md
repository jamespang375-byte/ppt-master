# API 获取与配置指南

PPT Master Agent 需要两类外部 API：**大模型**（必需，生成大纲和页面）和**网络搜图**（可选但强烈建议，为页面配真实图片）。本文说明每个 API 怎么申请、怎么配进系统。

配置有两种方式，优先级为 **界面配置 > 环境变量**：

- **界面配置（推荐）**：管理员登录 → 顶栏「设置」→ 直接填写，保存即生效，无需重启。key 只显示后 4 位。
- **环境变量**：写在仓库根目录 `.env` 文件中，重启服务生效。适合源码部署和打包分发时预置。

不配置任何模型 key 时系统进入 **mock 演示模式**：全流程可走通，但大纲和页面内容是内置模板，不是 AI 生成。不配置搜图 key 时自动回退到 Wikimedia / Openverse 免费图源（无需 key，但国内可达性和图片质量不稳定）。

---

## 一、大模型 API（必需）

系统兼容任何 **OpenAI 兼容接口**（`/v1/chat/completions`）。推荐以下几家，小模型即可获得高质量输出：

### 方案 A：DeepSeek（推荐，便宜）

| 项 | 值 |
|---|---|
| 申请地址 | https://platform.deepseek.com |
| base_url | `https://api.deepseek.com/v1` |
| 推荐模型 | `deepseek-chat` |

1. 注册并登录 DeepSeek 开放平台。
2. 左侧「API keys」→「创建 API key」，复制保存（只显示一次）。
3. 充值：按量计费，生成一份 12 页 PPT 约消耗 8-15 万 token，成本在几毛钱量级（以官网实时定价为准）。

### 方案 B：智谱 GLM

| 项 | 值 |
|---|---|
| 申请地址 | https://open.bigmodel.cn |
| base_url | `https://open.bigmodel.cn/api/paas/v4` |
| 推荐模型 | `glm-5.2`（或其他 glm 系列） |

注册 → 控制台「API 密钥」→ 新建密钥。新用户通常有免费额度。

### 方案 C：阿里百炼（Qwen 系列）

| 项 | 值 |
|---|---|
| 申请地址 | https://bailian.console.aliyun.com |
| base_url | `https://dashscope.aliyuncs.com/compatible-mode/v1` |
| 推荐模型 | `qwen3.7-max`、`qwen-plus` 等 |

开通百炼服务 → 右上角头像 →「API-KEY」→ 创建。注意百炼按模型分别计费/给额度。

> 百炼的 thinking 模型 reasoning 会消耗 token 额度。系统默认对百炼端点关闭 thinking（`PPTSAAS_LLM_DISABLE_THINKING=true`）以提速省费；如需最强推理可在 `.env` 设为 `false`。

### 方案 D：本地模型（离线/一体机部署）

在部署机器上跑一个 OpenAI 兼容服务，base_url 指向本机即可，api_key 随便填一个非空字符串：

| 工具 | 启动示例 | base_url |
|---|---|---|
| Ollama | `ollama run qwen3:8b` | `http://127.0.0.1:11434/v1` |
| llama.cpp | `llama-server -m model.gguf --jinja` | `http://127.0.0.1:8080/v1` |
| vLLM | `vllm serve Qwen/Qwen3-8B` | `http://127.0.0.1:8000/v1` |

本地模型建议 8B 以上，显存/内存需求见《规格设计》（SPEC.md）§5。

### 配置方式

界面：管理员「设置」→「模型配置」→ 填 base_url / model / api_key →「测试连接」确认绿色通过后保存。

`.env`：

```bash
PPTSAAS_LLM_BASE_URL=https://api.deepseek.com/v1
PPTSAAS_LLM_API_KEY=sk-xxxxxxxx
PPTSAAS_LLM_MODEL=deepseek-chat
# 可选：同端点的备用模型，失败自动降级
PPTSAAS_LLM_MODEL_FALLBACKS=deepseek-reasoner
```

---

## 二、网络搜图 API（可选，建议配置）

### Pexels（首选，质量高、国内可达性好）

| 项 | 值 |
|---|---|
| 申请地址 | https://www.pexels.com/api/ |
| 环境变量 | `PEXELS_API_KEY` |
| 免费额度 | 200 次/小时、20,000 次/月（一般团队够用） |

1. 打开 https://www.pexels.com/api/ ，点「Get Started」注册账号。
2. 邮箱验证后进入 API 页面，点「Your API Key」即可看到 key（随时可查，不会过期）。
3. 许可：Pexels License，可免费商用、无需署名。

### Pixabay（备选）

| 项 | 值 |
|---|---|
| 申请地址 | https://pixabay.com/api/docs/ |
| 环境变量 | `PIXABAY_API_KEY` |

注册 Pixabay 账号 → 打开 API 文档页 → 页面中即显示你的 key。

### 不配置时（零成本）

自动使用 Wikimedia Commons 和 Openverse，无需任何 key。系统会按 `pexels → pixabay → openverse → wikimedia` 的顺序自动降级，并过滤许可（优先免署名图库）。

### 配置方式

界面：管理员「设置」→「搜图配置」→ 粘贴 key 保存，立即生效；「图源提供方」下拉可选择：自动（优先 Pexels/Pixabay，无 key 用免费源）、仅 Pexels、仅 Pixabay、仅 Wikimedia、仅 Openverse。

`.env`：

```bash
PEXELS_API_KEY=your-pexels-key
PIXABAY_API_KEY=your-pixabay-key
# 可选：固定使用单一图源（auto/pexels/pixabay/openverse/wikimedia）
PPTSAAS_IMAGE_PROVIDER=auto
```

---

## 三、验证与排错

- 界面「设置」页的「测试连接」会真实调用一次模型接口并返回延迟，是验证配置最快的办法。
- 生成失败时先看项目卡片上的错误原因：
  - `401` / `invalid api key` → key 填错或已删除，重新粘贴（注意别带空格）。
  - `insufficient balance` / `quota` → 平台欠费，去对应控制台充值。
  - 超时 → 网络到该 base_url 不通（海外端点需代理），或换一家。
- 配图始终不出现：到「用量」页确认生成流程跑到了搜图阶段；搜图失败不会阻塞生成（设计如此），日志 `/tmp` 或服务输出里可见 `image_search.py` 的报错。
- 管理员在界面改过配置后，`.env` 里的同名配置即被覆盖；在界面点「清除覆盖」即恢复使用 `.env` 值。

相关文档：[部署手册](DEPLOYMENT.md) · [运维手册](OPERATIONS.md) · [规格设计](SPEC.md)
