#!/usr/bin/env python3
"""
PPT Master SaaS - Server entry point

Usage:
    python3 app/backend/run.py

Reads PPTSAAS_HOST / PPTSAAS_PORT (and every other PPTSAAS_* var, see
docs/saas/ARCHITECTURE.md §3) and starts uvicorn.

Desktop behavior (packaged boxes and local runs alike):
    - Prints a startup banner with the access URL.
    - If the configured port is already taken, falls back to a free port
      (with a warning) instead of crashing. If the occupying service is
      another PPT Master Agent instance, the window attaches to it
      instead of starting a second server (single-instance feel).
    - UI presentation, best first:
      1. Native desktop window via pywebview (real window, dock/taskbar
         entry, closing it quits the app). Enabled automatically when
         pywebview is installed; force with PPTSAAS_DESKTOP=1, disable
         with PPTSAAS_DESKTOP=0.
      2. Chromeless ``--app=`` window (Edge/Chrome).
      3. Default browser tab.
      Set PPTSAAS_NO_BROWSER=1 to disable UI opening entirely
      (headless servers, CI).

Dependencies:
    uvicorn (required), pywebview (optional, native window)
"""

import os
import socket
import subprocess
import sys
import threading
import urllib.request
import webbrowser
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from app.backend.config import get_settings  # noqa: E402
from app.backend.main import app  # noqa: E402

# Windows 上 stdout 被重定向到文件/管道时编码退化为 cp1252，中文启动横幅会
# 触发 UnicodeEncodeError 直接崩掉冻结程序（CI windows 冒烟实测）。保持原编码
# 只对不可编码字符做替换：交互终端（GBK 控制台）中文显示不受影响。
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(errors="replace")  # type: ignore[union-attr]
    except Exception:
        pass


def _port_in_use(host: str, port: int) -> bool:
    bind_host = "127.0.0.1" if host in {"0.0.0.0", "::"} else host
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(1)
        return sock.connect_ex((bind_host, port)) == 0


def _pick_port(host: str, preferred: int) -> tuple[int, bool]:
    """优先用配置端口；被占用时顺序尝试其后 9 个（与 splash 轮询范围一致），
    仍全满才退回系统随机端口。返回 (port, 是否发生了回退)。"""
    for port in range(preferred, preferred + 10):
        if not _port_in_use(host, port):
            return port, port != preferred
    return _free_port(host), True


def _free_port(host: str) -> int:
    bind_host = "127.0.0.1" if host in {"0.0.0.0", "::"} else host
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((bind_host, 0))
        return sock.getsockname()[1]


def _splash_path() -> Path | None:
    """启动页 splash.html：冻结产物在 _MEIPASS 的 datas 里，开发态在仓库内。"""
    if getattr(sys, "frozen", False):
        path = Path(sys._MEIPASS) / "app" / "frontend" / "splash.html"  # type: ignore[attr-defined]
    else:
        path = _REPO_ROOT / "app" / "frontend" / "splash.html"
    return path if path.is_file() else None


def _app_window_candidates() -> list[list[str]]:
    """Per-OS commands that open URL in a chromeless app window."""
    if sys.platform == "win32":
        candidates = []
        for env_name, tail in (
            ("ProgramFiles(x86)", r"Microsoft\Edge\Application\msedge.exe"),
            ("ProgramFiles", r"Microsoft\Edge\Application\msedge.exe"),
            ("LOCALAPPDATA", r"Microsoft\Edge\Application\msedge.exe"),
            ("ProgramFiles", r"Google\Chrome\Application\chrome.exe"),
            ("ProgramFiles(x86)", r"Google\Chrome\Application\chrome.exe"),
            ("LOCALAPPDATA", r"Google\Chrome\Application\chrome.exe"),
        ):
            base = os.environ.get(env_name)
            if base:
                exe = Path(base) / tail
                if exe.is_file():
                    candidates.append([str(exe), "--app={url}"])
        return candidates
    if sys.platform == "darwin":
        candidates = []
        for name in ("Google Chrome", "Microsoft Edge", "Chromium"):
            if Path(f"/Applications/{name}.app").is_dir():
                candidates.append(["open", "-na", name, "--args", "--app={url}"])
        return candidates
    # Linux / other unix
    candidates = []
    import shutil

    for exe in ("google-chrome", "google-chrome-stable", "microsoft-edge",
                "chromium", "chromium-browser"):
        if shutil.which(exe):
            candidates.append([exe, "--app={url}"])
    return candidates


def _open_ui(url: str) -> None:
    """Open the UI, preferring a chromeless app window over a browser tab."""
    for cmd in _app_window_candidates():
        try:
            subprocess.Popen(
                [part.format(url=url) for part in cmd],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return
        except OSError:
            continue
    try:
        webbrowser.open(url)
    except webbrowser.Error:
        pass


def _open_ui_when_ready(url: str, timeout: float = 60.0) -> None:
    """Daemon thread target: poll until the server answers, then open the UI."""
    import time

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2):
                break
        except OSError:
            time.sleep(0.3)
    else:
        return
    _open_ui(url)


def _env_flag(name: str) -> bool | None:
    raw = (os.environ.get(name) or "").strip().lower()
    if raw in {"1", "true", "yes", "on"}:
        return True
    if raw in {"0", "false", "no", "off"}:
        return False
    return None


def _no_browser() -> bool:
    return _env_flag("PPTSAAS_NO_BROWSER") is True


def _desktop_mode_enabled() -> bool:
    """原生桌面窗口（pywebview）是否可用：显式开关优先，默认装了就用。"""
    forced = _env_flag("PPTSAAS_DESKTOP")
    if forced is not None:
        return forced
    try:
        import webview  # noqa: F401
    except Exception:
        return False
    if sys.platform.startswith("linux") and not (
        os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")
    ):
        return False
    return True


def _existing_instance(port: int) -> bool:
    """端口上已跑着另一个 PPT Master Agent（桌面模式复用它，避免双开两个服务）。"""
    try:
        with urllib.request.urlopen(f"http://localhost:{port}/", timeout=2) as resp:
            return b"PPT Master" in resp.read(65536)
    except (OSError, ValueError):
        return False


def _run_desktop(host: str, port: int, reuse_existing: bool) -> int:
    """原生窗口模式：uvicorn 跑后台线程，pywebview 窗口占主线程（macOS 要求），
    关窗即退出整个应用。"""
    import time

    import uvicorn
    import webview

    url = f"http://localhost:{port}"
    splash = _splash_path()
    splash_html = splash.read_text(encoding="utf-8") if splash else ""

    window = webview.create_window(
        "PPT Master Agent",
        html=splash_html,
        width=1440,
        height=900,
        min_size=(1024, 640),
    )

    def _ensure_app_page() -> None:
        # splash 自带轮询跳转；若其 fetch 被 WebView 策略拦截，这里兜底跳转。
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            try:
                with urllib.request.urlopen(url, timeout=2):
                    break
            except OSError:
                time.sleep(0.3)
        else:
            return
        time.sleep(1.0)
        try:
            if not (window.get_current_url() or "").startswith(url):
                window.load_url(url)
        except Exception:
            pass

    if not reuse_existing:
        config = uvicorn.Config(app, host=host, port=port, log_level="info")
        server = uvicorn.Server(config)
        threading.Thread(target=server.run, daemon=True).start()

    threading.Thread(target=_ensure_app_page, daemon=True).start()
    try:
        webview.start()
    finally:
        # 关窗 = 退出应用（窗口是主线程，uvicorn 是 daemon 线程，随之结束）。
        os._exit(0)
    return 0


def _maybe_autopen(url: str, port: int) -> None:
    if _no_browser():
        return
    splash = _splash_path()
    if splash is not None:
        # 立即打开启动页（无需等服务就绪）：它自带轮询，就绪后自动跳转。
        splash_url = f"{splash.as_uri()}?port={port}"
        threading.Thread(target=_open_ui, args=(splash_url,), daemon=True).start()
    else:
        threading.Thread(target=_open_ui_when_ready, args=(url,), daemon=True).start()


def main() -> int:
    import uvicorn

    settings = get_settings()
    desktop = _desktop_mode_enabled() and not _no_browser()
    reuse = desktop and _existing_instance(settings.port)
    if reuse:
        port, fell_back = settings.port, False
    else:
        port, fell_back = _pick_port(settings.host, settings.port)
    if fell_back:
        print(
            f"[pptsaas] 警告：端口 {settings.port} 已被占用，改用 {port}。"
            "（如需固定端口请关闭占用进程或设置 PPTSAAS_PORT）",
            flush=True,
        )

    url = f"http://localhost:{port}"
    mode = "mock 演示模式（未配置 LLM key）" if settings.mock_llm else f"模型 {settings.llm_model}"
    print("=" * 56, flush=True)
    print("  PPT Master Agent 已启动", flush=True)
    print(f"  访问地址：{url}", flush=True)
    print(f"  运行模式：{mode}", flush=True)
    print("  停止服务：关闭本窗口或按 Ctrl+C", flush=True)
    print("=" * 56, flush=True)

    if desktop:
        if reuse:
            print(f"[pptsaas] 检测到已有实例运行在 {url}，窗口将直接接入。", flush=True)
        return _run_desktop(settings.host, port, reuse)

    _maybe_autopen(url, port)

    # 传 app 对象而非 "app.backend.main:app" 字符串：PyInstaller 冻结后
    # uvicorn 的字符串动态 import 找不到模块，对象引用则由静态分析收集。
    uvicorn.run(
        app,
        host=settings.host,
        port=port,
        log_level="info",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
