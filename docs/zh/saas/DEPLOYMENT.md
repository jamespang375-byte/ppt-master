# PPT Master Agent SaaS 部署手册

本文档面向部署人员，介绍 PPT Master Agent SaaS（代码位于仓库 `app/` 目录）的三种部署形态：

- **形态 A：源码部署**（Linux / macOS / Windows，推荐开发与服务器场景）
- **形态 B：Windows 单机 zip**（解压即用，免 Python 环境，内嵌便携 Python）
- **形态 C：Linux tar.gz / AppImage**（免安装分发，内嵌便携 Python）

末尾附「模型部署在同一台机器」章节，介绍如何用 Ollama / llama.cpp / vLLM 在本机起 OpenAI 兼容端点，以及不配 LLM key 时的 mock 演示模式。

所有配置项、默认值、目录结构均以契约文档 [`docs/saas/ARCHITECTURE.md`](../../saas/ARCHITECTURE.md) 为准。

---

## 0. 部署前须知

- 服务默认监听 `0.0.0.0:8310`（`PPTSAAS_HOST` / `PPTSAAS_PORT`）。
- 全部数据落在 `PPTSAAS_DATA_DIR`（默认 `./data`）下：SQLite 库 `app.db` + 项目目录 `projects/`。**备份这一个目录即备份全部数据。**
- LLM 不内嵌。必须有一个 OpenAI 兼容端点：云端（DeepSeek / GLM / Qwen 等）或本机（Ollama / llama.cpp / vLLM）。未配置 `PPTSAAS_LLM_API_KEY` 时进入 mock 演示模式（见第 4 章）。
- 图片搜索：配置 `PEXELS_API_KEY` / `PIXABAY_API_KEY` 走 Pexels+Pixabay 链；不配则自动回退到 Openverse+Wikimedia 免费源，无需 key。
- `.env` 自动加载位置：**当前工作目录**（打包形态即启动器所在目录）与仓库根目录（源码形态）；真实环境变量优先于 `.env`。

---

## 1. 形态 A：源码部署

适用于 Linux 服务器、macOS、Windows（Python 3.10+）。

### 1.1 获取代码并建虚拟环境

```bash
git clone <repo-url> ppt-master
cd ppt-master

python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
```

### 1.2 安装依赖

后端依赖与 PPT Master 技能依赖分开安装，两个 requirements 都要装：

```bash
pip install -r app/backend/requirements.txt -r requirements.txt
```

- `app/backend/requirements.txt`：FastAPI、uvicorn、openai、python-multipart、python-dotenv 等 Web 层依赖。
- `requirements.txt`（仓库根目录，内含 `skills/ppt-master/requirements.txt`）：`source_to_md.py` / `image_search.py` / `svg_to_pptx.py` 等管线脚本依赖（python-pptx、PyMuPDF、mammoth、Pillow、requests 等）。

> 如需 Office 兼容模式（老版本 Office 打开 PPTX 时的 PNG 回退），建议额外安装 CairoSVG：
>
> ```bash
> pip install cairosvg        # macOS 需先 brew install cairo
> ```

### 1.3 配置 `.env`

在仓库根目录创建 `.env`（不存在则新建，已存在则追加）：

```ini
# —— LLM（OpenAI 兼容端点）——
PPTSAAS_LLM_BASE_URL=https://api.deepseek.com/v1
PPTSAAS_LLM_API_KEY=sk-你的key
PPTSAAS_LLM_MODEL=deepseek-chat
# 可选：同一端点上的备用模型，逗号分隔，主模型 5xx/超时时按序重试
PPTSAAS_LLM_MODEL_FALLBACKS=

# —— 图片搜索（可选；不配则回退 Openverse+Wikimedia）——
PEXELS_API_KEY=你的pexels-key
# PIXABAY_API_KEY=你的pixabay-key

# —— 常用可选项（均为默认值，按需修改）——
# PPTSAAS_PORT=8310
# PPTSAAS_HOST=0.0.0.0
# PPTSAAS_DATA_DIR=./data
# PPTSAAS_MAX_ACTIVE_PROJECTS=2
# PPTSAAS_MAX_CONCURRENT_PAGES=4
# PPTSAAS_MAX_QUEUED_PER_USER=2
# PPTSAAS_DEFAULT_TOKEN_QUOTA=2000000
# PPTSAAS_REGISTRATION_OPEN=true
# PPTSAAS_SESSION_TTL_HOURS=72
# PPTSAAS_LLM_TIMEOUT=600
```

完整配置项说明见 ARCHITECTURE.md 第 3 节。

### 1.4 启动

```bash
python3 app/backend/run.py
```

启动后浏览器访问 `http://localhost:8310`。首个注册的用户自动成为 admin（详见运维手册）。

### 1.5 systemd 常驻（Linux 服务器）

新建 `/etc/systemd/system/pptsaas.service`：

```ini
[Unit]
Description=PPT Master Agent SaaS
After=network.target

[Service]
Type=simple
User=pptsaas
WorkingDirectory=/opt/ppt-master
EnvironmentFile=/opt/ppt-master/.env
ExecStart=/opt/ppt-master/.venv/bin/python3 app/backend/run.py
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

启用并启动：

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now pptsaas
sudo systemctl status pptsaas
journalctl -u pptsaas -f        # 查看日志
```

注意：`WorkingDirectory` 决定相对路径 `./data` 的实际位置（上例为 `/opt/ppt-master/data`）；生产环境建议显式设置 `PPTSAAS_DATA_DIR` 为绝对路径。

---

## 2. 形态 B：Windows 单机 zip

面向无 Python 环境的 Windows（x86_64）用户。产物 `pptsaas-windows-x86_64.zip` 解压即用，**内嵌便携 Python 3.12 运行时**（python-build-standalone），目标机无需安装任何软件。

### 2.1 获取产物（推荐：CI Release）

打 tag（`v*`）推送到 GitHub 后，工作流 `.github/workflows/build-pptsaas.yml` 的 `windows` job 自动完成构建 + 启动冒烟验证，并把 zip 上传到 Release；也可在 Actions 页手动 `workflow_dispatch` 触发后从 Artifacts 下载。

### 2.2 手动打包（必须在 Windows 构建机上执行）

PyInstaller 不能交叉编译，Windows 产物只能在 Windows 上构建。**零基础的逐步操作指南（含构建环境安装、验证、分发说明、常见问题）见 [BUILD_WINDOWS.md](BUILD_WINDOWS.md)**，此处仅列命令：

```powershell
git clone <repo-url> ppt-master
cd ppt-master
# 需要本机 Python 3.12（仅作构建宿主，产物不依赖它）
powershell -ExecutionPolicy Bypass -File app\packaging\build_windows.ps1
```

脚本流程与 CI 一致：pip 依赖 → `pyinstaller app/packaging/pptsaas.spec`（onedir）→ 下载 python-build-standalone 内嵌运行时并装入技能依赖 → 组装 `pkg\pptsaas\` → 启动冒烟验证（HTTP 200）→ 压缩 `dist\pptsaas-windows-x86_64.zip`。

产物目录结构：

```
pptsaas\
  start.bat          启动器（设置 PPTSAAS_PYTHON 指向内嵌解释器后拉起服务）
  .env.example       配置模板，复制为 .env 使用
  app\               PyInstaller onedir 后端（pptsaas.exe + _internal\）
  python\            内嵌便携 Python 3.12（含 python-pptx / PyMuPDF / Pillow 等全部管线依赖）
  data\              首次启动自动创建（SQLite + 项目文件）
```

> 为什么需要内嵌 Python：后端本体是 PyInstaller 冻结的 exe，但生成管线中的重活
> （`source_to_md.py` / `image_search.py` / `svg_to_pptx.py` 等 skills 脚本）是后端以
> subprocess 调 `python` 执行的，目标机没有 Python，所以包内带一份解释器。
> 后端通过环境变量 `PPTSAAS_PYTHON` 定位解释器（默认 `python3`，见
> `app/backend/config.py`），`start.bat` 已自动设置，**不要单独双击 `app\pptsaas.exe`**。

### 2.3 终端用户使用

1. 解压 `pptsaas-windows-x86_64.zip` 到任意目录，例如 `D:\pptsaas\`。
2. 把 `.env.example` 复制为 `.env`，至少写入 LLM 配置（格式同 1.3 节）；不配则进入 mock 演示模式（界面内也可随时配置，见「设置」页与首次启动向导）。
3. 双击 `start.bat`：先弹出**品牌启动页**（splash），服务就绪后自动切换进应用窗口（Edge/Chrome 的无边框 `--app` 模式，看起来就是独立应用；找不到这两种浏览器时退回默认浏览器标签页）。
4. 停止：直接关闭黑色控制台窗口（或 Ctrl+C）。数据存放在解压目录的 `data\`（或 `.env` 中 `PPTSAAS_DATA_DIR` 指定路径）。

> 桌面体验细节（`app/backend/run.py` / `app/backend/config.py`）：
> - exe 带品牌图标（`app/packaging/assets/pptsaas.ico`，由 `make_icons.py` 生成），任务栏/资源管理器均显示。
> - 启动页轮询 8310-8319 端口，服务在哪个端口起来就跳进哪个；90 秒未就绪会显示排查提示。
> - 端口被占用时按顺序自动改用下一个空闲端口（8310→8319，全满再随机），横幅中提示实际地址；需要固定端口可在 `.env` 设 `PPTSAAS_PORT`。
> - 直接双击 `app\pptsaas.exe` 也能正常运行（自动识别同包的 `python\` 内嵌解释器与 `data\` 目录），但推荐仍用 `start.bat`（默认仅监听本机回环，避免防火墙弹窗）。
> - 不想自动打开界面（纯服务器部署、远程终端）时设 `PPTSAAS_NO_BROWSER=1`。

### 2.4 防火墙、杀毒软件与端口

- `start.bat` 默认仅监听 `127.0.0.1`（本机回环），因此**首次启动不会弹防火墙提示**，局域网也无法访问。需要局域网内同事访问时，在 `.env` 中设 `PPTSAAS_HOST=0.0.0.0`，并在防火墙弹窗中勾选「专用网络」允许。
- **杀毒软件误报**：PyInstaller 冻结的 exe 与内嵌 `python\` 目录（自包含解释器 + 大量第三方库）是常见的启发式杀软误报对象。产物未做代码签名，遇误报请将解压目录加入杀软白名单；企业环境可分发给 IT 做哈希登记（CI 同时产出 `SHA256SUMS.txt`）。
- 端口冲突无需手动处理（自动避让）；确需固定端口时在 `.env` 改 `PPTSAAS_PORT`，例如 `8600`。

---

## 3. 形态 C：Linux tar.gz / AppImage

面向 Linux 桌面 / 无 root 环境。两种产物内容相同（onedir 后端 + 内嵌便携 Python 3.12），只是一个是解压包、一个是单文件 AppImage。均在 Debian 12（glibc 2.36）容器内构建，多数现代发行版可直接运行。

### 3.1 获取产物（推荐：CI Release 或本机 Docker 构建）

- CI：同 2.1 节，`linux` job 产出 `pptsaas-linux-x86_64.tar.gz` 与 `pptsaas-x86_64.AppImage`（附 `SHA256SUMS.txt`）。
- 本地构建（任何装了 Docker 的机器，含 macOS，无需本地 Python）：

  ```bash
  git clone <repo-url> ppt-master
  cd ppt-master
  bash app/packaging/build_linux.sh
  ```

  该脚本只做两件事：`docker build -f app/packaging/Dockerfile.linux-build --output type=local,dest=dist .`，然后在干净的 debian 容器里冒烟验证产物（HTTP 200 + 注册 + 主题接口 + 内嵌解释器依赖自检）。Dockerfile 内完成：pip 全量依赖 → PyInstaller onedir → 拷贝容器内 CPython 3.12（`/usr/local`）作为内嵌运行时 → 组装 + 启动器 → tar.gz，appimagetool 可下载时再产出 AppImage。

tar.gz 解压后的目录结构与 2.2 节相同（`pptsaas.sh` 对应 `start.bat`）。

### 3.2 tar.gz 使用

```bash
tar -xzf pptsaas-linux-x86_64.tar.gz
cd pptsaas
cp .env.example .env      # 填入 PPTSAAS_LLM_API_KEY 等；不配为 mock 演示模式
./pptsaas.sh              # 启动后先显示品牌启动页，就绪自动进入应用窗口（无桌面/浏览器的环境设 PPTSAAS_NO_BROWSER=1，再手动访问 http://localhost:8310）
```

- 数据目录默认在解压目录的 `data/`，可用 `PPTSAAS_DATA_DIR` 改到别处。
- 内嵌解释器位于 `python/`，启动器已导出 `PPTSAAS_PYTHON` 与 `LD_LIBRARY_PATH`；**请始终用 `pptsaas.sh` 启动**，不要直接跑 `app/pptsaas`（少了这两个变量，管线脚本阶段会失败）。

### 3.3 AppImage 使用

```bash
chmod +x pptsaas-x86_64.AppImage
./pptsaas-x86_64.AppImage
```

- AppImage 为只读挂载，数据目录默认落在 `$HOME/.local/share/pptsaas`（可用 `PPTSAAS_DATA_DIR` 覆盖）；`.env` 从**当前工作目录**读取，在 AppImage 旁放 `.env` 时请在同目录启动。
- 依赖 FUSE；无 FUSE 的极简/容器环境加 `--appimage-extract-and-run` 运行：

  ```bash
  ./pptsaas-x86_64.AppImage --appimage-extract-and-run
  ```

- 与 Windows 侧同理，AppImage 未签名，个别安全软件可能告警，属误报。

---

## 4. 模型部署在同一台机器（本地 LLM）

把 LLM 端点和 PPT SaaS 部署在同一台机器，可完全离线运行。三种常见方式任选其一，都提供 OpenAI 兼容端点。

### 4.1 Ollama（最省事，推荐个人/小团队）

```bash
# 安装：https://ollama.com/download
ollama pull qwen3:8b
ollama run qwen3:8b        # 或 ollama serve 常驻
```

`.env` 配置：

```ini
PPTSAAS_LLM_BASE_URL=http://127.0.0.1:11434/v1
PPTSAAS_LLM_API_KEY=ollama          # Ollama 不校验，非空即可
PPTSAAS_LLM_MODEL=qwen3:8b
```

### 4.2 llama.cpp server（GGUF 模型，资源占用低）

```bash
llama-server -m /path/to/qwen3-8b-q4_k_m.gguf \
  --jinja \
  --port 8080 \
  -ngl 99                           # 有 GPU 时层数全 offload
```

`.env` 配置：

```ini
PPTSAAS_LLM_BASE_URL=http://127.0.0.1:8080/v1
PPTSAAS_LLM_API_KEY=local
PPTSAAS_LLM_MODEL=qwen3-8b          # 与 llama-server 汇报的模型名一致
```

### 4.3 vLLM（GPU 服务器，高吞吐）

```bash
pip install vllm
vllm serve Qwen/Qwen3-14B --port 8000 --max-model-len 32768
```

`.env` 配置：

```ini
PPTSAAS_LLM_BASE_URL=http://127.0.0.1:8000/v1
PPTSAAS_LLM_API_KEY=local
PPTSAAS_LLM_MODEL=Qwen/Qwen3-14B
```

本地模型显存/内存需求速查见 [`SPEC.md`](SPEC.md) 第 4 章。注意 PPT 生成要求模型具备**长 JSON 输出 + SVG 代码能力**，8B 级模型可用但排版质量明显弱于 DeepSeek/GLM 云端模型，14B+ 更接近可用水平。

### 4.4 mock 演示模式（不配 LLM key）

`.env` 中**不设置 `PPTSAAS_LLM_API_KEY`** 时，后端进入 mock 演示模式：strategist 返回内置样例大纲、executor 生成占位 SVG，全流程（上传 → 大纲确认 → 逐页生成 → 导出 PPTX）都可以走通，不产生任何 token 消耗。用于：

- 部署后自检管线是否打通；
- 向用户演示产品流程；
- 无网络 / 无 LLM 额度时验证打包产物。

正式使用时务必配置真实的 `PPTSAAS_LLM_*`。

---

## 5. 部署后自检清单

1. `curl http://localhost:8310/` 返回前端页面（SPA 由 FastAPI 直接托管）。
2. 注册第一个账号 → 应自动获得 admin 角色（`GET /api/auth/me` 可见）。
3. mock 模式下创建一个 10 页项目 → 走完确认大纲 → 生成 → 导出，验证 `data/projects/<id>/exports/` 下产出 `.pptx`。
4. 配置真实 LLM 后重建项目，观察 `data/app.db` 的 `token_usage` 表有计量记录。
5. 未配 `PEXELS_API_KEY` 时确认图片阶段自动回退 Openverse+Wikimedia，不报错中断。

运维细节（备份、排错、升级）见 [`OPERATIONS.md`](OPERATIONS.md)。
