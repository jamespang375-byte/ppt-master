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
      (with a warning) instead of crashing.
    - Once the server answers HTTP, opens the UI automatically: prefers a
      chromeless ``--app=`` window (Edge/Chrome) so it feels like a native
      app, falling back to the default browser. Set PPTSAAS_NO_BROWSER=1
      to disable (headless servers, CI).

Dependencies:
    uvicorn
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


def _maybe_autopen(url: str, port: int) -> None:
    raw = (os.environ.get("PPTSAAS_NO_BROWSER") or "").strip().lower()
    if raw in {"1", "true", "yes", "on"}:
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
