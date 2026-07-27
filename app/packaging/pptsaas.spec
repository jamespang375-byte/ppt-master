# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec — PPT Master Agent SaaS
#
# 入口：app/backend/run.py（启动 uvicorn 并打开浏览器）
# 打包内容：后端 + 零构建前端 app/frontend + 技能管线 skills/ppt-master/{scripts,templates}
# 不内嵌任何模型；LLM 端点由 .env / 环境变量 PPTSAAS_LLM_* 指定。
#
# 用法（在仓库根目录）：
#   pyinstaller app/packaging/pptsaas.spec --distpath dist --workpath build
# 或直接跑 app/packaging/build_linux.sh / build_windows.ps1。

import os

from PyInstaller.utils.hooks import collect_submodules

# spec 文件位于 <repo>/app/packaging/，向上两级即仓库根目录
REPO_ROOT = os.path.abspath(os.path.join(SPECPATH, "..", ".."))


def repo_path(*parts):
    return os.path.join(REPO_ROOT, *parts)


# (源路径, 打包内相对目录)。运行期后端按 <exe>/app/frontend、
# <exe>/skills/ppt-master 定位这些资源。
datas = [
    (repo_path("app", "frontend"), "app/frontend"),
    (repo_path("skills", "ppt-master", "scripts"), "skills/ppt-master/scripts"),
    (repo_path("skills", "ppt-master", "templates"), "skills/ppt-master/templates"),
]

# uvicorn 的 loop / protocol / lifespan 实现是运行时按字符串动态 import 的，
# PyInstaller 静态分析抓不到，必须全量收集；python-multipart / dotenv 同理。
# （python-multipart 新版同时提供 multipart / python_multipart 两个导入名。）
# app.backend 各模块由 run.py 静态导入 app.backend.main 递归收集，这里再
# 显式列出兜底（模块经 Analysis 的 pathex=[REPO_ROOT] 解析）。
hiddenimports = collect_submodules("uvicorn") + [
    "app.backend.auth",
    "app.backend.config",
    "app.backend.db",
    "app.backend.llm",
    "app.backend.main",
    "app.backend.pipeline",
    "app.backend.prompts",
    "app.backend.themes",
    "multipart",
    "python_multipart",
    "dotenv",
]

a = Analysis(
    [repo_path("app", "backend", "run.py")],
    pathex=[REPO_ROOT],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="pptsaas",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,  # 保留控制台窗口：日志可见、Ctrl+C 可停
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    # Windows 资源管理器/任务栏图标（Linux 构建时 PyInstaller 忽略此参数）
    icon=repo_path("app", "packaging", "assets", "pptsaas.ico"),
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="pptsaas",
)
