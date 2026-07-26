# PPT Master Agent SaaS 规格设计（容量规划）

本文档回答三个问题：**开多大并发、要什么硬件、烧多少 token / 钱**。配置项与默认值以 [`docs/saas/ARCHITECTURE.md`](../../saas/ARCHITECTURE.md) 第 3、8 节为准；部署见 [`DEPLOYMENT.md`](DEPLOYMENT.md)，运维见 [`OPERATIONS.md`](OPERATIONS.md)。

---

## 1. 容量估算的基础假设

- **单页生成**（executor 一次调用）：input 约 3–6K token（主题 style_md + SVG 规则 + 大纲 + 图片清单），output 约 2–4K token（一页 1280×720 SVG）。
- **一份 10 页 deck 全管线**：strategist 大纲（input 含 sources.md 摘录，较大）+ 10 页 executor + 失败重试（fallback 链每次尝试独立计量），合计约 **8–15 万 token**。
- 重生成单页 / 手改 SVG 后重导出只增加单页量级消耗，重导出（svg_to_pptx）本身**不消耗 token**。
- 单页 wall-clock 主要由 LLM 输出速度决定：云端模型约 20–60 秒/页，本地 8B 模型（消费级 GPU）约 1–3 分钟/页。一份 10 页 deck 在默认 `PPTSAAS_MAX_CONCURRENT_PAGES=4` 下约 2–5 分钟（云端）。

> 以下为规划参考值，实际消耗随主题复杂度、页数、重试率浮动；**token 单价以各厂商实时定价为准**。

---

## 2. 并发档位与推荐配置

两个关键旋钮（ARCHITECTURE.md 第 8 节）：

- `PPTSAAS_MAX_ACTIVE_PROJECTS` — 全局同时进行的 `generate` 任务数（默认 2，超出返回 409）。
- `PPTSAAS_MAX_CONCURRENT_PAGES` — 每个项目内部的页面并发（默认 4，asyncio 信号量）。

| 档位 | 典型规模 | `PPTSAAS_MAX_ACTIVE_PROJECTS` | `PPTSAAS_MAX_CONCURRENT_PAGES` | 峰值同时在途的 LLM 调用 | 说明 |
|---|---|---|---|---|---|
| 个人 | 1–2 人，1–2 并发项目 | 2（默认） | 4（默认） | ≈ 8 | 默认值即为个人档调优结果；本地小模型可降到 2 减抖 |
| 小团队 | 5–15 人，4–8 并发项目 | 6 | 4 | ≈ 24 | 提高项目并发、页面并发不动——瓶颈在 LLM 端点限流，不在本机 |
| 部门 | 30+ 人，16+ 并发项目 | 16 | 8 | ≈ 128 | 前提是云端端点配额/限流撑得住；本地模型单机基本到不了此档 |

调参原则：

- 先确认 **LLM 端点的 RPM/并发上限**——它是真正的天花板。本机只是转发请求，`MAX_ACTIVE_PROJECTS × MAX_CONCURRENT_PAGES` 超过端点限额只会换来大量 429/超时重试，反而烧 token。
- `PPTSAAS_MAX_QUEUED_PER_USER`（默认 2）限制单用户未完成项目数，防止个人刷爆全局队列，部门档可按需放宽。
- 每用户配额 `PPTSAAS_DEFAULT_TOKEN_QUOTA`（默认 200 万 token ≈ 15–25 份 10 页 deck）按档位人均需求量调整，0 = 不限。

---

## 3. 硬件需求

核心结论：**瓶颈在 LLM API 等待，不在本机算力**。本机 CPU 主要消耗在导出阶段的 `svg_to_pptx` 转换（单线程，单核即可），其余时间进程都在等网络。

| 档位 | CPU | 内存 | 磁盘 | 备注 |
|---|---|---|---|---|
| 个人 | 2 核 | 1 GB | 20 GB | 内存 = Python 进程基线 ~300 MB + 每并发任务 ~50 MB；随便一台旧机器/入门 VPS 即可 |
| 小团队 | 4 核 | 2–4 GB | 100 GB | 峰值并发任务多，内存按 ~300 MB + 50 MB × 峰值任务数估算；磁盘大头是 `data/projects/`（单项目 5–30 MB） |
| 部门 | 8 核 | 8 GB | 500 GB+，建议 SSD | CPU 富余是因为多项目同时跑 `svg_to_pptx` 转换；磁盘 IO 几乎无要求，SSD 主要为 SQLite 写入与项目目录读写体验 |

补充说明：

- **不需要 GPU**（LLM 在云端时）。本地模型场景的显存需求见第 4 章。
- 网络：出方向到 LLM 端点与图片源（Pexels/Openverse 等）稳定即可，带宽要求低（图片下载单页几张、每张几百 KB–2 MB）。
- SQLite 单文件足够支撑部门档；v1 无 Redis/broker，无水平扩展设计，更大规模请拆分多实例按团队隔离。

---

## 4. token 消耗与云端成本估算

按第 1 章假设（一份 10 页 deck ≈ 8–15 万 token），按团队规模估算每日消耗：

| 团队规模 | 假设日产出 | 每日 token 消耗 | 每月（22 工作日） | DeepSeek/GLM 小模型成本量级* |
|---|---|---|---|---|
| 个人（1–2 人） | 3–5 份 deck | ≈ 30–70 万 | ≈ 700–1500 万 | 每日几角到 1–2 元 |
| 小团队（10 人） | 15–30 份 deck | ≈ 150–450 万 | ≈ 0.3–1 亿 | 每日数元到十几元 |
| 部门（50 人） | 80–150 份 deck | ≈ 800–2200 万 | ≈ 2–5 亿 | 每日几十元量级 |

\* 按 DeepSeek `deepseek-chat` / GLM 小模型 2026 年前后的公开定价量级估算（input 每百万 token 元级、output 每百万 token 十元级），仅用于预算拍脑袋；**实际费用以各厂商实时定价为准**，注意缓存命中、阶梯价、夜间折扣会显著拉低单价。

控制成本的手段：

- 用配额兜底：`PPTSAAS_DEFAULT_TOKEN_QUOTA` + 管理员按人调整（OPERATIONS.md 第 2 章）。
- 降重试损耗：fallback 链每次尝试独立计费，端点不稳时重试占消耗大头——选稳定端点比选便宜模型更省钱。
- 页数即成本：成本与页数近似线性，20 页 deck ≈ 两份 10 页。
- 盯 `GET /api/admin/stats` 的今日 token，异常飙升先查是否大量失败重试（OPERATIONS.md 第 3、6 章）。

---

## 5. 本地模型硬件速查

把 LLM 放在同一台机器时（部署方式见 DEPLOYMENT.md 第 4 章），按模型规模估算资源（GGUF Q4 量化 + 32K 上下文；FP16 约 ×2.5–3）：

| 模型规模 | 显存（GPU 推理） | 纯 CPU 内存 | 适用性评估 |
|---|---|---|---|
| 8B（如 Qwen3-8B） | ≈ 6–8 GB | ≈ 8–12 GB | 能跑通全流程；JSON/SVG 遵循度一般，页面排版质量明显弱于云端，适合演示与草稿 |
| 14B（如 Qwen3-14B） | ≈ 10–14 GB | ≈ 16–20 GB | 质量接近可用，个人本地档推荐起点 |
| 32B（如 Qwen3-32B） | ≈ 20–24 GB | ≈ 36–40 GB | 质量好但单机吞吐低，页面并发建议降到 2；需要 RTX 4090/5090 级单卡或 Apple Silicon 大内存统一内存 |

注意：

- 上下文要留足：strategist 的 input 含 sources.md 摘录（上限 24000 字符），建议模型上下文 ≥ 32K。
- Ollama / llama.cpp 在 CPU-only 时 8B 约 5–15 token/s，单页生成要数分钟——纯 CPU 只适合 mock 之外的体验验证，不建议生产。
- Apple Silicon（M 系列）按统一内存估算，64 GB 机型跑 32B Q4 体验良好。
