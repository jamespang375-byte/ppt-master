#!/usr/bin/env python3
"""
PPT Master SaaS - Server entry point

Usage:
    python3 app/backend/run.py

Reads PPTSAAS_HOST / PPTSAAS_PORT (and every other PPTSAAS_* var, see
docs/saas/ARCHITECTURE.md §3) and starts uvicorn.

Dependencies:
    uvicorn
"""

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from app.backend.config import get_settings  # noqa: E402
from app.backend.main import app  # noqa: E402


def main() -> int:
    import uvicorn

    settings = get_settings()
    # 传 app 对象而非 "app.backend.main:app" 字符串：PyInstaller 冻结后
    # uvicorn 的字符串动态 import 找不到模块，对象引用则由静态分析收集。
    uvicorn.run(
        app,
        host=settings.host,
        port=settings.port,
        log_level="info",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
