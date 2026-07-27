# Windows 打包操作指南（自己构建 exe 发行包）

本文面向**没有 Python 基础也能照着做**的打包人员：在一台 Windows 电脑上，把 PPT Master Agent 构建成一个可以随便分发的 zip 包。最终拿到手的用户**不需要安装 Python、不需要任何开发环境**，解压双击即可使用。

> 只想「用」不想「打包」的人请直接看 [DEPLOYMENT.md](DEPLOYMENT.md) 形态 B——从 GitHub Release 下载现成的 zip 即可，无需阅读本文。

---

## 0. 你会得到什么

构建成功后得到一个文件：

```
dist\pptsaas-windows-x86_64.zip     （约 250–350 MB）
```

把它发给任何人，对方解压后双击 `start.bat` 就能用。包内已包含：

- `app\pptsaas.exe` —— 后端服务主程序（PyInstaller 冻结，带品牌图标）
- `python\` —— 内嵌便携 Python 3.12（生成 PPTX 的技能脚本运行时，用户无感知）
- `start.bat` —— 一键启动器（自动弹应用窗口）
- `.env.example` —— 配置模板（可选，全部配置也能在界面里完成）

---

## 1. 构建机要求（一次性的）

| 项目 | 要求 |
|---|---|
| 操作系统 | Windows 10 / 11，64 位 |
| 磁盘空间 | 至少 3 GB 空闲 |
| 网络 | 能访问 GitHub 和 PyPI（构建时要下载依赖和内嵌 Python） |
| 软件 | Python 3.12（仅构建用）、Git（或直接下载源码 zip） |

> 最终产物的使用机器**没有这些要求**，普通 Win10/11 即可。

---

## 2. 准备构建环境（约 5 分钟）

### 2.1 安装 Python 3.12

1. 打开 https://www.python.org/downloads/release/python-31210/ （或任意 3.12.x 版本页）
2. 下载页面底部的 **Windows installer (64-bit)**
3. 安装时**务必勾选** `Add python.exe to PATH`，然后点 Install Now
4. 验证：按 `Win+R` 输入 `cmd` 回车，执行：

```bat
python --version
```

显示 `Python 3.12.x` 即成功。如果提示"不是内部或外部命令"，说明没勾选 PATH，卸载重装。

> 注意：只要 3.12 大版本对，小版本不限。不要装 3.13/3.14——内嵌运行时固定用 3.12，保持构建宿主一致最稳。

### 2.2 获取源码

二选一：

```bat
:: 方式一：git（推荐，方便以后更新）
git clone https://github.com/jamespang375-byte/ppt-master.git
cd ppt-master
git checkout doubao-custom
```

方式二：浏览器打开仓库页 → 绿色 `Code` 按钮 → `Download ZIP` → 解压到任意目录（路径建议纯英文，如 `D:\ppt-master`），然后用 `cd` 进入该目录。

---

## 3. 一键构建（约 5–15 分钟）

在源码根目录（能看到 `app`、`skills` 目录的位置）执行：

```bat
powershell -ExecutionPolicy Bypass -File app\packaging\build_windows.ps1
```

脚本会自动完成 5 个阶段，每步都有中文进度输出：

| 阶段 | 做什么 |
|---|---|
| [1/5] | 给构建用 Python 安装依赖和 PyInstaller |
| [2/5] | PyInstaller 把后端冻结成 `dist\pptsaas\`（onedir） |
| [3/5] | 下载内嵌便携 Python 3.12 并装入技能管线依赖 |
| [4/5] | 组装完整包目录，并**自动冒烟验证**（启动服务、请求首页、期望 HTTP 200） |
| [5/5] | 压缩出 `dist\pptsaas-windows-x86_64.zip` |

**成功标志**：最后输出 `完成：dist\pptsaas-windows-x86_64.zip` 且中间出现过 `冒烟验证通过（HTTP 200）`。

冒烟验证不通过脚本会主动报错退出——这时打出来的包不要发给别人，先把报错解决掉（见第 6 章）。

---

## 4. 发出去之前，自己先验一遍

模拟最终用户的真实场景：

1. 把 `dist\pptsaas-windows-x86_64.zip` 复制到一个**干净的目录**（如 `D:\test\`），解压
2. 进入解压出的 `pptsaas` 目录，双击 `start.bat`
3. 预期：黑色控制台窗口打印启动横幅 → 几秒后自动弹出应用窗口（有 Edge/Chrome 是无边框应用窗口，没有则打开默认浏览器）
4. 在界面里注册一个账号 → 进入首次配置向导 → 随便填或跳过 → 创建一个演示项目
5. 能走通「输入主题 → 大纲 → 生成 → 下载 PPTX」即合格

验证完把测试目录整个删掉即可，无残留。

---

## 5. 分发给更多人：对方怎么用

发给对方一个 zip，附带三句话：

1. 解压到**纯英文路径**（如 `D:\pptsaas`），**不要在 zip 里直接双击运行**，必须完整解压
2. 双击 `start.bat`，等几秒会自动弹出应用窗口
3. 首次打开跟着向导填模型 Key（界面里有获取教程链接），不填也能先体验演示模式

对方侧常见提示的应对：

- **Windows SmartScreen 蓝色警告**：exe 没有付费代码签名证书时会出现，点「更多信息 → 仍要运行」即可。分发量大时可考虑购买 OV 代码签名证书消除。
- **杀毒软件报毒**：PyInstaller + 内嵌 Python 是常见误报对象，让对方对解压目录加白名单（详见 DEPLOYMENT.md）。
- **防火墙弹窗**：包默认只监听本机回环（127.0.0.1），一般不弹；若对方要局域网共享使用，在 `.env` 设 `PPTSAAS_HOST=0.0.0.0` 后放行。
- **端口被占用**：程序会自动换用 8311–8319 中的空闲端口并打印提示，无需处理。

---

## 6. 构建常见问题

| 现象 | 原因与解决 |
|---|---|
| `无法加载文件 ... 因为在此系统上禁止运行脚本` | 没用 `-ExecutionPolicy Bypass` 参数，按第 3 章完整命令执行 |
| [3/5] 下载 python-build-standalone 失败 / 超时 | 网络到 GitHub 不稳。重跑脚本即可（前序产物会复用）；公司网需配代理时先 `set HTTPS_PROXY=http://代理:端口` 再执行 |
| pip 安装依赖报 SSL / 超时 | PyPI 网络问题，重试；或换镜像：`pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple` 后重跑 |
| 冒烟验证失败，日志提示端口占用 | 构建机上 8399 端口被占，关掉占用程序后重跑（冒烟端口固定 8399） |
| 报毒导致 exe 被删 | 构建机上先对源码目录加杀毒白名单再重跑 |
| `python --version` 不是 3.12 | 不影响成功率上限，但请换回 3.12 再构建，避免冻结产物与内嵌运行时行为差异 |

---

## 7. 可选增强

- **原生桌面窗口**（关窗即退出、独立任务栏图标）：当前发行包未包含 pywebview（Windows 侧未经充分验证）。想实验的话，在第 3 章构建前执行 `pip install pywebview` 并自行验证 —— 相关说明见 `app/backend/requirements-desktop.txt`。
- **改默认端口 / 默认模型**：编辑仓库 `app/backend/config.py` 的默认值后再构建。
- **自动构建（无需本机 Windows）**：给仓库打 `v*` tag 推送，或在 GitHub Actions 页手动触发 `build-pptsaas` 工作流，Windows 包会作为构建产物/Release 附件产出。见 DEPLOYMENT.md §2.1。

---

相关文档：[DEPLOYMENT.md](DEPLOYMENT.md)（部署与运维）、[API_KEYS.md](API_KEYS.md)（各类 Key 获取教程）、[SPEC.md](SPEC.md)（规格与容量规划）。
