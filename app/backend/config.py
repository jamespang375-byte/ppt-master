#!/usr/bin/env python3
"""
PPT Master SaaS - Configuration

Env-driven settings for the SaaS backend. All app settings use the
``PPTSAAS_`` prefix; provider keys (PEXELS_API_KEY etc.) are read by the
reused skill scripts from the environment / repo-root ``.env``.

See docs/saas/ARCHITECTURE.md §3 for the full variable table.

Dependencies:
    None (only uses standard library)
"""

import os
import sys
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .db import Database

REPO_ROOT = Path(__file__).resolve().parents[2]


def _frozen_pkg_root() -> Path | None:
    """PyInstaller 冻结产物（桌面盒子）的包根目录，非冻结态返回 None。

    打包布局为 <pkg>/app/pptsaas[.exe]（exe 的上一级即包根，python/ 与
    data/ 都是它的子目录）。识别后用户直接双击 exe 也能跑，不必经过
    start.bat / pptsaas.sh 启动器。
    """
    if not getattr(sys, "frozen", False):
        return None
    return Path(sys.executable).resolve().parent.parent


def _frozen_python_bin() -> str | None:
    """桌面盒子里内嵌解释器的路径（未打包时 None）。"""
    root = _frozen_pkg_root()
    if root is None:
        return None
    for rel in ("python/python.exe", "python/bin/python3.12"):
        candidate = root / rel
        if candidate.is_file():
            return str(candidate)
    return None


def _load_dotenv_file(env_path: Path) -> None:
    """Load one .env file into os.environ without overriding real env vars."""
    if not env_path.is_file():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            os.environ.setdefault(key, value)


def _load_root_dotenv() -> None:
    """Load .env into os.environ without overriding real env vars.

    Two locations are tried, in order: the current working directory (so a
    packaged build picks up the .env the user placed next to the launcher)
    and the repo root (development layout). Real env vars always win.
    """
    _load_dotenv_file(Path.cwd() / ".env")
    _load_dotenv_file(REPO_ROOT / ".env")


_load_root_dotenv()


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, "") or default)
    except ValueError:
        return default


def _bool_env(name: str, default: bool) -> bool:
    raw = (os.environ.get(name) or "").strip().lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    """Runtime settings snapshot. Build via get_settings()."""

    port: int = 8310
    host: str = "0.0.0.0"
    data_dir: Path = field(default_factory=lambda: Path("./data"))
    skill_dir: Path = field(default_factory=lambda: REPO_ROOT / "skills" / "ppt-master")
    llm_base_url: str = "https://api.deepseek.com/v1"
    llm_api_key: str = ""
    llm_model: str = "deepseek-chat"
    llm_model_fallbacks: list[str] = field(default_factory=list)
    llm_timeout: float = 600.0
    llm_disable_thinking: bool = True
    max_concurrent_pages: int = 4
    max_active_projects: int = 2
    max_queued_per_user: int = 2
    default_token_quota: int = 2_000_000
    registration_open: bool = True
    session_ttl_hours: int = 72
    upload_max_mb: int = 50
    upload_max_files: int = 10
    #: Interpreter used to run skills/ppt-master scripts via subprocess.
    #: Packaged builds point this at the embedded portable Python
    #: (PPTSAAS_PYTHON); development defaults to "python3".
    python_bin: str = "python3"

    @property
    def scripts_dir(self) -> Path:
        return self.skill_dir / "scripts"

    @property
    def mock_llm(self) -> bool:
        """Mock mode: no LLM key configured, pipeline runs deterministically."""
        return not self.llm_api_key

    @property
    def disable_thinking_effective(self) -> bool:
        """Send ``extra_body={"enable_thinking": false}`` on chat calls.

        Only applies to Alibaba Bailian (DashScope) OpenAI-compatible
        endpoints — ``enable_thinking`` is a Bailian compatible-mode
        parameter that turns off the reasoning phase of thinking models
        (e.g. qwen3 family), which otherwise burns max_tokens on hidden
        reasoning and can truncate JSON output. Other providers never
        receive this parameter.
        """
        return self.llm_disable_thinking and "dashscope" in self.llm_base_url


def get_settings() -> Settings:
    """Build settings from the current environment."""
    fallbacks_raw = os.environ.get("PPTSAAS_LLM_MODEL_FALLBACKS", "")
    fallbacks = [m.strip() for m in fallbacks_raw.split(",") if m.strip()]
    # 冻结产物（桌面盒子）默认：数据目录与内嵌解释器都取包根下的路径，
    # 使直接双击 exe 与经过启动器行为一致；环境变量始终优先。
    pkg_root = _frozen_pkg_root()
    default_data = str(pkg_root / "data") if pkg_root else "./data"
    default_python = _frozen_python_bin() or "python3"
    return Settings(
        port=_int_env("PPTSAAS_PORT", 8310),
        host=os.environ.get("PPTSAAS_HOST", "0.0.0.0"),
        data_dir=Path(os.environ.get("PPTSAAS_DATA_DIR", default_data)).resolve(),
        skill_dir=Path(
            os.environ.get("PPTSAAS_SKILL_DIR", str(REPO_ROOT / "skills" / "ppt-master"))
        ).resolve(),
        llm_base_url=os.environ.get("PPTSAAS_LLM_BASE_URL", "https://api.deepseek.com/v1"),
        llm_api_key=os.environ.get("PPTSAAS_LLM_API_KEY", ""),
        llm_model=os.environ.get("PPTSAAS_LLM_MODEL", "deepseek-chat"),
        llm_model_fallbacks=fallbacks,
        llm_timeout=float(_int_env("PPTSAAS_LLM_TIMEOUT", 600)),
        llm_disable_thinking=_bool_env("PPTSAAS_LLM_DISABLE_THINKING", True),
        max_concurrent_pages=_int_env("PPTSAAS_MAX_CONCURRENT_PAGES", 4),
        max_active_projects=_int_env("PPTSAAS_MAX_ACTIVE_PROJECTS", 2),
        max_queued_per_user=_int_env("PPTSAAS_MAX_QUEUED_PER_USER", 2),
        default_token_quota=_int_env("PPTSAAS_DEFAULT_TOKEN_QUOTA", 2_000_000),
        registration_open=_bool_env("PPTSAAS_REGISTRATION_OPEN", True),
        session_ttl_hours=_int_env("PPTSAAS_SESSION_TTL_HOURS", 72),
        python_bin=os.environ.get("PPTSAAS_PYTHON", default_python),
    )


# ---------------------------------------------------------------------------
# Admin-editable settings (resolution order: non-empty DB value > env/.env)
# ---------------------------------------------------------------------------

#: Keys an admin may override at runtime via PUT /api/admin/settings.
SETTING_KEYS = (
    "llm_base_url",
    "llm_model",
    "llm_api_key",
    "pexels_api_key",
    "pixabay_api_key",
    "image_provider",
)

_ENV_FOR_SETTING = {
    "llm_base_url": "PPTSAAS_LLM_BASE_URL",
    "llm_model": "PPTSAAS_LLM_MODEL",
    "llm_api_key": "PPTSAAS_LLM_API_KEY",
    "pexels_api_key": "PEXELS_API_KEY",
    "pixabay_api_key": "PIXABAY_API_KEY",
    "image_provider": "PPTSAAS_IMAGE_PROVIDER",
}

# Pin the image search to one provider; "auto" keeps the default chain
# (keyed providers first, then openverse/wikimedia).
IMAGE_PROVIDERS = ("auto", "pexels", "pixabay", "openverse", "wikimedia")


def db_setting_overrides(db: "Database") -> dict[str, str]:
    """Non-empty admin overrides from the settings table (unknown keys ignored)."""
    rows = db.query("SELECT k, v FROM settings")
    return {
        r["k"]: r["v"]
        for r in rows
        if r["k"] in SETTING_KEYS and (r["v"] or "").strip()
    }


def resolve(settings: Settings, db: "Database") -> Settings:
    """Effective settings snapshot: non-empty DB overrides win over env.

    Cheap to call (one tiny SELECT); callers resolve per request/batch so
    admin edits apply without a restart.
    """
    overrides = db_setting_overrides(db)
    kwargs = {
        key: overrides[key]
        for key in ("llm_base_url", "llm_model", "llm_api_key")
        if key in overrides
    }
    return replace(settings, **kwargs) if kwargs else settings


def effective_image_keys(db: "Database") -> dict[str, tuple[str, str]]:
    """Effective image provider keys: {setting_key: (value, source)}.

    source is "db" (admin override), "env" (.env / environment), or "none".
    """
    overrides = db_setting_overrides(db)
    result: dict[str, tuple[str, str]] = {}
    for key in ("pexels_api_key", "pixabay_api_key"):
        db_val = overrides.get(key, "")
        if db_val:
            result[key] = (db_val, "db")
        else:
            env_val = os.environ.get(_ENV_FOR_SETTING[key], "")
            result[key] = (env_val, "env" if env_val else "none")
    return result


def effective_image_provider(db: "Database") -> tuple[str, str]:
    """Effective pinned image provider: (value, source).

    "auto" (default) keeps image_search.py's provider chain; any other value
    in IMAGE_PROVIDERS pins the search to that provider. Invalid values
    degrade to "auto".
    """
    overrides = db_setting_overrides(db)
    if "image_provider" in overrides:
        value, src = overrides["image_provider"], "db"
    else:
        env_val = os.environ.get("PPTSAAS_IMAGE_PROVIDER", "")
        value, src = env_val, ("env" if env_val else "none")
    value = (value or "auto").strip().lower()
    if value not in IMAGE_PROVIDERS:
        value = "auto"
    return value, (src if value != "auto" or src == "db" else "none")

def image_search_env(db: "Database") -> dict[str, str]:
    """os.environ copy with effective PEXELS/PIXABAY keys injected.

    Passed to the image_search.py subprocess so admin key edits take effect
    without a server restart. Keys with no effective value are removed so a
    deleted env key cannot leak through from the parent process.
    """
    env = os.environ.copy()
    for key, (value, _src) in effective_image_keys(db).items():
        env_name = _ENV_FOR_SETTING[key]
        if value:
            env[env_name] = value
        else:
            env.pop(env_name, None)
    return env


def settings_payload(settings: Settings, db: "Database") -> dict:
    """Admin GET/PUT response shape; secrets are only exposed as a tail."""
    eff = resolve(settings, db)
    overrides = db_setting_overrides(db)

    def source(key: str) -> str:
        return "db" if key in overrides else "env"

    def secret_fields(key: str, value: str, src: str) -> dict:
        return {
            f"{key}_set": bool(value),
            f"{key}_tail": ("…" + value[-4:]) if value else None,
            f"{key}_source": src,
        }

    payload = {
        "llm_base_url": eff.llm_base_url,
        "llm_model": eff.llm_model,
        "llm_base_url_source": source("llm_base_url"),
        "llm_model_source": source("llm_model"),
        "mock_mode": eff.mock_llm,
    }
    payload.update(secret_fields("llm_api_key", eff.llm_api_key,
                                 source("llm_api_key") if eff.llm_api_key
                                 else "none"))
    for key, (value, src) in effective_image_keys(db).items():
        payload.update(secret_fields(key, value, src))
    provider, provider_src = effective_image_provider(db)
    payload["image_provider"] = provider
    payload["image_provider_source"] = provider_src
    return payload
