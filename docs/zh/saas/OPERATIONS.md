# PPT Master Agent SaaS 运维手册

本文档面向系统管理员，覆盖日常运维：管理员职责、用户管理、token 计量、数据目录、备份恢复、日志排错与升级流程。所有行为以契约文档 [`docs/saas/ARCHITECTURE.md`](../../saas/ARCHITECTURE.md) 为准；部署方式见 [`DEPLOYMENT.md`](DEPLOYMENT.md)。

---

## 1. 管理员职责

- **首个注册的用户自动成为 admin**（`users.role = 'admin'`，之后注册的用户均为 `user`）。请部署完成后**第一时间注册管理员账号**，避免被他人抢占；若对内网开放，建议注册完成后在 `.env` 设 `PPTSAAS_REGISTRATION_OPEN=false` 并重启。
- admin 拥有以下专属能力：
  - `GET /api/admin/users` — 查看全部用户；
  - `PATCH /api/admin/users/{id}` — 调整用户 `token_quota`、`disabled`、`role`；
  - `GET /api/admin/stats` — 全局统计（用户数、项目数、今日/累计 token）；
  - `GET /api/projects` 返回全部用户的项目（普通用户只见自己的）。
- admin 的日常职责：开通/回收账号、盯全局 token 消耗、定期备份 `data/`、跟进失败项目（`status = 'failed'`）。

---

## 2. 用户管理

### 2.1 注册与关闭注册

- 默认开放自助注册（`PPTSAAS_REGISTRATION_OPEN=true`），注册接口 `POST /api/auth/register`。
- 关闭注册后，新注册请求返回 409；已有用户不受影响。
- v1 没有「管理员代建账号」接口；需要加人时临时打开注册、让对方注册后再关，或直接操作 SQLite（不推荐，见 2.4）。

### 2.2 配额管理

- 每个用户有 LLM token 预算 `token_quota`（默认值来自 `PPTSAAS_DEFAULT_TOKEN_QUOTA=2000000`），已用量记在 `token_used`。
- `token_quota = 0` 表示**不限量**。
- 配额在 strategist 调用前与每个 executor 批次前强制检查，超限的项目 `generate` 返回 409。
- 调整配额（前端管理页或 curl）：

  ```bash
  curl -X PATCH http://localhost:8310/api/admin/users/2 \
    -H "Authorization: Bearer <admin-token>" \
    -H "Content-Type: application/json" \
    -d '{"token_quota": 5000000}'
  ```

### 2.3 禁用用户

```bash
curl -X PATCH http://localhost:8310/api/admin/users/2 \
  -H "Authorization: Bearer <admin-token>" \
  -H "Content-Type: application/json" \
  -d '{"disabled": 1}'
```

禁用后该用户的会话不应再可用；恢复设 `"disabled": 0`。禁用不删除其项目数据。

### 2.4 直接改库（仅限应急）

所有用户数据在 SQLite `<DATA_DIR>/app.db` 的 `users` 表。服务停止后可用 `sqlite3` 修改（如紧急把某用户提为 admin：`UPDATE users SET role='admin' WHERE id=2;`）。改前务必备份（见第 5 章），改完重启服务。

---

## 3. token 计量与用量查看

### 3.1 计量口径

- 每次 LLM 调用（strategist 大纲规划、executor 逐页 SVG 生成，含 fallback 模型的每一次尝试）都会把 `usage` 写入 `token_usage` 表：`user_id / project_id / stage / model / prompt_tokens / completion_tokens / total_tokens / created_at`，并累加到 `users.token_used`。
- 主模型失败按 `PPTSAAS_LLM_MODEL_FALLBACKS` 顺序重试（5xx/超时，最多 3 次），**每次尝试独立计量**——排障时若发现 token 消耗异常偏高，先查是否大量重试。

### 3.2 查看用量

- 普通用户：`GET /api/usage` → 本人总用量 + 按项目拆分 + 最近明细记录；`GET /api/auth/me` 返回 `token_used` / `token_quota`。
- 管理员：`GET /api/admin/stats` → 全局用户数、项目数、今日/累计 token。
- 命令行直查（服务可不停）：

  ```bash
  sqlite3 data/app.db "SELECT username, token_used, token_quota FROM users;"
  sqlite3 data/app.db "SELECT stage, model, SUM(total_tokens) FROM token_usage GROUP BY stage, model;"
  ```

---

## 4. 数据目录结构

`PPTSAAS_DATA_DIR`（默认 `./data`）下：

```
data/
├── app.db                        # SQLite：users / sessions / projects / pages / token_usage / themes
└── projects/
    └── <project_id>/             # uuid hex 12
        ├── sources/              # 上传的原始文件（md/docx/pdf/pptx/txt）
        ├── sources.md            # 阶段 1 ingest 合并后的 Markdown
        ├── outline.json          # 阶段 2/3 大纲（用户可编辑）
        ├── images/               # image_search.py 下载的图 + image_sources.json
        ├── svg_output/
        │   └── page_01.svg … page_NN.svg   # 阶段 5 产物，svg_to_pptx 的源
        └── exports/
            └── <title>.pptx      # 阶段 6 导出产物
```

- 项目元数据（状态、标题、页数、错误信息）在 `projects` 表；每页状态在 `pages` 表。
- 内置主题在首次启动时幂等写入 `themes` 表（business-blue / tech-dark / consult-red / fresh-green / minimal-white）。
- 磁盘占用量级：`app.db` 通常 < 50 MB；单个项目目录（图片 + SVG + PPTX）约 5–30 MB。定期清理已删除项目残留目录可控制膨胀。

---

## 5. 备份与恢复

**备份 = 备份整个 `data/` 目录**，无其他状态。

### 5.1 备份（推荐停机或低峰执行）

```bash
# 方式一：整目录打包（最简单，适合每日定时）
tar czf backup/pptsaas-$(date +%F).tar.gz data/

# 方式二：SQLite 在线备份（不停机，安全拷贝 app.db）
sqlite3 data/app.db ".backup 'backup/app-$(date +%F).db'"
tar czf backup/projects-$(date +%F).tar.gz data/projects/
```

注意：直接 `cp app.db` 在服务写入中可能拷出不一致的库，务必用 `.backup` 命令或在停机时拷贝；`projects/` 目录无此限制，可随时 rsync/tar。

建议 cron 每日一次，保留最近 14 份。

### 5.2 恢复

```bash
systemctl stop pptsaas            # 或停掉对应进程
mv data data.bak                  # 保留现场
mkdir data
cp backup/app-2026-07-25.db data/app.db
tar xzf backup/projects-2026-07-25.tar.gz -C data/   # 恢复 projects/
systemctl start pptsaas
```

恢复后抽查：登录正常、`GET /api/projects` 列表完整、任选一个 `ready` 项目能下载 PPTX。

---

## 6. 日志与排错

### 6.1 日志位置

- 源码部署（前台 / systemd）：stdout，systemd 下用 `journalctl -u pptsaas -f`。
- exe / AppImage：控制台窗口输出。
- 项目级错误会写入 `projects.error` 与 `pages.error` 字段，前端项目详情页可见；`GET /api/projects/{id}/status` 返回每页状态与错误。

### 6.2 常见错误表

| 现象 | 可能原因 | 处理 |
|---|---|---|
| 项目创建 / 生成失败，错误含 `401 Unauthorized` | `PPTSAAS_LLM_API_KEY` 错误、过期或欠费；或 `PPTSAAS_LLM_BASE_URL` 指错端点 | 用 `curl $PPTSAAS_LLM_BASE_URL/models -H "Authorization: Bearer $KEY"` 验证 key；本地 Ollama 确认服务已启动 |
| LLM 调用超时（默认 `PPTSAAS_LLM_TIMEOUT=600` 秒） | 端点过载；本地小模型生成 SVG 慢；网络抖动 | 系统已按 fallback 链重试（最多 3 次）；仍失败则调大超时、换更快模型或降低 `PPTSAAS_MAX_CONCURRENT_PAGES` 减轻端点压力 |
| 大纲 JSON 解析失败 | 模型未按 strict-JSON 契约输出（本地小模型常见） | 系统内置 JSON 修复（去 think 标签/代码围栏/全角引号/尾逗号/括号配平）；仍失败说明模型能力不足，换模型 |
| 图片阶段静默无图 | 未配 `PEXELS_API_KEY` 且 Openverse/Wikimedia 也无结果 | 这是**设计内回退**：无 Pexels key 自动走 Openverse+Wikimedia，查不到就跳过该图，页面照常生成，不算错误；需要更稳的配图就配 `PEXELS_API_KEY` / `PIXABAY_API_KEY` |
| 导出失败（`svg_to_pptx` 阶段） | 某页 SVG 非法（LLM 输出越界元素、外部引用等）；依赖缺失 | 看 `pages.error` 定位页码 → 用 `POST /api/projects/{id}/pages/{n}/regenerate` 重生成该页或 `PUT .../pages/{n}/svg` 手改 → `POST /api/projects/{id}/export` 重新导出；确认已安装 `requirements.txt` 依赖 |
| `generate` 返回 409 | 已有 `PPTSAAS_MAX_ACTIVE_PROJECTS`（默认 2）个生成任务在跑；或用户 token 配额超限；或项目已在 generating | 稍后重试；管理员调大 `PPTSAAS_MAX_ACTIVE_PROJECTS` 或用户配额 |
| 上传被拒 | 单文件超 50 MB 或超过 10 个文件 | 压缩/拆分源文件后重传（v1 硬上限） |
| 磁盘满（写入失败、SQLite `database or disk is full`） | `data/projects/` 膨胀 | 删除无用项目（`DELETE /api/projects/{id}`）并清理残留目录；把 `PPTSAAS_DATA_DIR` 迁到大容量磁盘；建立第 5 章的定期清理 |
| 注册返回 409 | `PPTSAAS_REGISTRATION_OPEN=false` | 管理员临时开启注册后再关闭 |
| 会话失效需重新登录 | 会话过期（`PPTSAAS_SESSION_TTL_HOURS=72`） | 正常现象，重新登录；可按需调长 |

---

## 7. 升级流程

### 7.1 源码部署升级

```bash
systemctl stop pptsaas
tar czf backup/pre-upgrade-$(date +%F).tar.gz data/    # 先备份
git pull                                                # 或替换为新版本代码
source .venv/bin/activate
pip install -r app/backend/requirements.txt -r requirements.txt   # 依赖可能有新增
systemctl start pptsaas
```

- 内置主题在启动时幂等播种，升级自动补齐；数据库表结构变更（如有）随启动迁移，**升级前备份 `app.db` 是底线**。
- 升级后按 DEPLOYMENT.md 第 5 章自检清单跑一遍（mock 模式建一个项目走全流程）。

### 7.2 exe / AppImage 升级

1. 备份旧版旁的 `data/` 目录；
2. 解压/替换为新版产物，把 `data/` 和 `.env` 放回原位置（保持 `PPTSAAS_DATA_DIR` 指向不变）；
3. 启动新版，抽查历史项目可打开、可下载。

### 7.3 回滚

恢复升级前的代码（`git checkout <旧版本>` 或换回旧包）+ 按第 5.2 节恢复备份的 `data/`。若新版已写入过数据，注意旧代码可能不认识新字段——回滚前优先用升级前的完整备份。
