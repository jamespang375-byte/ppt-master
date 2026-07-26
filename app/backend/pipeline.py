#!/usr/bin/env python3
"""
PPT Master SaaS - Pipeline

Stages: ingest → strategist → images → executor → export, all delegating
heavy lifting to skills/ppt-master/scripts via subprocess (cwd=repo root).
Background generate tasks are bounded by a registry enforcing
PPTSAAS_MAX_ACTIVE_PROJECTS; per-page LLM concurrency is bounded by
PPTSAAS_MAX_CONCURRENT_PAGES.

See docs/saas/ARCHITECTURE.md §2 and §8.

Dependencies:
    openai (via llm.py)
"""

import asyncio
import json
import os
import re
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from .config import (REPO_ROOT, Settings, effective_image_provider,
                     image_search_env)
from .db import Database, utcnow
from .llm import LLMClient, mock_outline, mock_svg, repair_json
from .prompts import (
    STRATEGIST_SYSTEM,
    executor_system,
    executor_user,
    strategist_user,
)

MAX_SOURCES_EXCERPT = 24_000


class PipelineError(Exception):
    """A pipeline stage failed; message is user-presentable."""


class QuotaExceeded(Exception):
    """User token quota exhausted."""


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def new_project_id() -> str:
    return uuid.uuid4().hex[:12]


def project_dir(settings: Settings, project_id: str) -> Path:
    return settings.data_dir / "projects" / project_id


def sanitize_filename(name: str, default: str = "file") -> str:
    """Strip path components and unsafe characters from an upload filename."""
    base = Path(name or "").name
    base = re.sub(r"[^\w.一-鿿-]+", "_", base).strip("._")
    return (base or default)[:120]


def sanitize_title(title: str) -> str:
    cleaned = re.sub(r"[^\w一-鿿 -]+", "_", title or "").strip()
    return cleaned[:60] or "deck"


def clean_image_query(raw: str) -> str:
    """Reduce a free-form query to 2-5 lowercase English keywords."""
    words = re.sub(r"[^a-zA-Z0-9\s-]", " ", raw or "").lower().split()
    words = [w for w in words if len(w) >= 2][:5]
    return " ".join(words) if len(words) >= 2 else ""


def dump_raw_debug(proj_dir: Path, stage: str, raw: str) -> Path:
    """Write a failed LLM stage's raw output to <proj_dir>/debug/ for triage."""
    debug_dir = proj_dir / "debug"
    debug_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = debug_dir / f"{stage}_raw_{stamp}.txt"
    path.write_text(raw or "", encoding="utf-8")
    return path


async def run_script(settings: Settings, script: str, args: list[str],
                     timeout: float = 300.0,
                     env: Optional[dict[str, str]] = None) -> tuple[int, str, str]:
    """Run a skills/ppt-master script via subprocess; return (rc, out, err).

    ``env`` replaces the subprocess environment when given (default: inherit
    the parent process environment).
    """
    cmd = [settings.python_bin, str(settings.scripts_dir / script), *args]
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        cwd=str(REPO_ROOT),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=env,
    )
    try:
        out, err = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        return 124, "", f"script timed out after {timeout}s: {script}"
    return (proc.returncode or 0,
            out.decode("utf-8", "replace"), err.decode("utf-8", "replace"))


def check_quota(db: Database, user_id: int) -> None:
    """Raise QuotaExceeded when the user is over budget (0 = unlimited)."""
    user = db.query_one("SELECT token_quota, token_used FROM users WHERE id = ?",
                        (user_id,))
    if user and user["token_quota"] > 0 and user["token_used"] >= user["token_quota"]:
        raise QuotaExceeded(
            f"token quota exceeded ({user['token_used']}/{user['token_quota']})"
        )


# ---------------------------------------------------------------------------
# Stage 1: ingest
# ---------------------------------------------------------------------------

async def run_ingest(settings: Settings, proj_dir: Path,
                     source_files: list[Path]) -> str:
    """source_to_md.py over the uploaded files → merged sources.md."""
    md_dir = proj_dir / "sources_md"
    md_dir.mkdir(parents=True, exist_ok=True)
    inputs = [str(p) for p in source_files]
    if len(inputs) == 1:
        out_arg = str(md_dir / (Path(inputs[0]).stem + ".md"))
    else:
        out_arg = str(md_dir)
    rc, _out, err = await run_script(
        settings, "source_to_md.py", [*inputs, "-o", out_arg], timeout=600.0
    )
    md_files = sorted(md_dir.glob("*.md"))
    if rc != 0 or not md_files:
        raise PipelineError(f"source_to_md failed (rc={rc}): {err[-500:]}")
    merged = "\n\n".join(
        f"<!-- source: {p.name} -->\n\n" + p.read_text(encoding="utf-8", errors="replace")
        for p in md_files
    )
    (proj_dir / "sources.md").write_text(merged, encoding="utf-8")
    return merged


# ---------------------------------------------------------------------------
# Stage 2: strategist
# ---------------------------------------------------------------------------

_LAYOUT_HINTS = {"cover", "toc", "content", "data", "closing"}


def validate_outline(data: Any) -> dict[str, Any]:
    """Validate/normalize an outline against the contract schema."""
    if not isinstance(data, dict):
        raise PipelineError("outline must be a JSON object")
    deck_title = str(data.get("deck_title") or "").strip() or "未命名演示"
    raw_pages = data.get("pages")
    if not isinstance(raw_pages, list) or not raw_pages:
        raise PipelineError("outline.pages must be a non-empty list")
    pages = []
    for idx, raw in enumerate(raw_pages, start=1):
        if not isinstance(raw, dict):
            raise PipelineError(f"outline.pages[{idx}] must be an object")
        layout = str(raw.get("layout_hint") or "content")
        pages.append({
            "page_number": idx,
            "title": str(raw.get("title") or f"第 {idx} 页")[:60],
            "key_message": str(raw.get("key_message") or ""),
            "content_summary": str(raw.get("content_summary") or ""),
            "visual_suggestion": str(raw.get("visual_suggestion") or ""),
            "image_query": str(raw.get("image_query") or ""),
            "layout_hint": layout if layout in _LAYOUT_HINTS else "content",
            "bullets": [str(b) for b in (raw.get("bullets") or [])][:8]
            if isinstance(raw.get("bullets"), list) else [],
        })
    return {"deck_title": deck_title, "pages": pages}


def save_outline(db: Database, proj_dir: Path, project_id: str,
                 outline: dict[str, Any]) -> None:
    """Persist outline.json and (re)create page rows as pending."""
    (proj_dir / "outline.json").write_text(
        json.dumps(outline, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    db.execute(
        "UPDATE projects SET outline_json = ?, slide_count = ?, updated_at = ?"
        " WHERE id = ?",
        (json.dumps(outline, ensure_ascii=False), len(outline["pages"]),
         utcnow(), project_id),
    )
    db.execute("DELETE FROM pages WHERE project_id = ?", (project_id,))
    for page in outline["pages"]:
        db.execute(
            "INSERT INTO pages(project_id, page_number, status, error)"
            " VALUES (?, ?, 'pending', NULL)",
            (project_id, page["page_number"]),
        )


def load_outline(db: Database, project_id: str) -> dict[str, Any]:
    row = db.query_one("SELECT outline_json FROM projects WHERE id = ?",
                       (project_id,))
    if not row or not row["outline_json"]:
        raise PipelineError("project has no outline")
    return json.loads(row["outline_json"])


async def run_strategist(settings: Settings, db: Database, llm: LLMClient,
                         user_id: int, project_id: str, topic: str,
                         title: str, slide_count: int, style_brief: str,
                         sources_md: str) -> dict[str, Any]:
    """One LLM call (or mock) → validated outline JSON."""
    check_quota(db, user_id)
    if llm.is_mock:
        outline = mock_outline(topic, title, slide_count, style_brief)
        llm.record_usage(user_id, project_id, "strategist", "mock", 0, 0)
        return validate_outline(outline)
    max_tokens = min(32768, max(8192, 300 * slide_count + 3000))
    raw = await llm.complete(
        user_id=user_id, project_id=project_id, stage="strategist",
        system=STRATEGIST_SYSTEM,
        user=strategist_user(topic, title, slide_count, style_brief,
                             sources_md[:MAX_SOURCES_EXCERPT]),
        temperature=0.4, max_tokens=max_tokens,
    )
    try:
        repaired = repair_json(raw)
        return validate_outline(json.loads(repaired))
    except (ValueError, json.JSONDecodeError) as exc:
        dump_path = dump_raw_debug(project_dir(settings, project_id),
                                   "strategist", raw)
        raise PipelineError(
            f"strategist returned invalid JSON: {exc};"
            f" raw output (first 200 chars): {raw[:200]!r};"
            f" full dump: {dump_path}"
        ) from exc


# ---------------------------------------------------------------------------
# Stage 4: images (advisory per page; failures never block the deck)
# ---------------------------------------------------------------------------

async def run_image_stage(settings: Settings, db: Database, proj_dir: Path,
                          outline: dict[str, Any]) -> list[str]:
    """image_search.py per page.image_query; returns downloaded filenames.

    Effective provider keys (DB admin override > env) are injected into the
    subprocess environment so admin key edits apply without a restart.
    """
    images_dir = proj_dir / "images"
    images_dir.mkdir(parents=True, exist_ok=True)
    img_env = image_search_env(db)
    items: list[dict[str, str]] = []
    for page in outline["pages"]:
        query = clean_image_query(str(page.get("image_query") or ""))
        if not query:
            continue
        n = page["page_number"]
        items.append({
            "filename": f"page_{n:02d}.jpg",
            "query": query,
            "status": "Pending",
            "slide": f"{n:02d}",
            "orientation": "landscape",
        })
    if not items:
        return []
    # One batch invocation: image_search.py runs the queries concurrently
    # (threads) and keeps image_sources.json provenance consistent — far
    # faster than one subprocess per page on multi-page decks.
    manifest = images_dir / "image_queries.json"
    manifest.write_text(json.dumps({"items": items}, ensure_ascii=False,
                                   indent=2),
                        encoding="utf-8")
    provider, _src = effective_image_provider(db)
    args = ["--batch", str(manifest), "-o", str(images_dir),
            "--concurrency", "3"]
    if provider != "auto":
        args += ["--provider", provider]
    await run_script(
        settings, "image_search.py", args,
        timeout=600.0,
        env=img_env,
    )
    return [it["filename"] for it in items
            if (images_dir / it["filename"]).is_file()]


# ---------------------------------------------------------------------------
# Stage 5: executor
# ---------------------------------------------------------------------------

def extract_svg(raw: str) -> Optional[str]:
    """Pull the <svg>…</svg> document out of an LLM response."""
    text = raw or ""
    start = text.find("<svg")
    end = text.rfind("</svg>")
    if start < 0 or end < 0 or end <= start:
        return None
    return text[start:end + len("</svg>")]


async def generate_page_svg(settings: Settings, db: Database, llm: LLMClient,
                            user_id: int, project_id: str, deck_title: str,
                            style_md: str, theme_name: str, page: dict,
                            image_files: list[str], feedback: str = "") -> str:
    """Produce one page's SVG (mock or LLM); does not touch the DB."""
    if llm.is_mock:
        svg = mock_svg(deck_title, page, theme_name)
        llm.record_usage(user_id, project_id, "executor", "mock", 0, 0)
        return svg
    raw = await llm.complete(
        user_id=user_id, project_id=project_id, stage="executor",
        system=executor_system(style_md),
        user=executor_user(deck_title, page, image_files, feedback),
        temperature=0.3, max_tokens=16384,
    )
    svg = extract_svg(raw)
    if not svg:
        raise PipelineError(f"executor returned no SVG for page {page['page_number']}")
    return svg


def write_page_svg(proj_dir: Path, page_number: int, svg: str) -> Path:
    out_dir = proj_dir / "svg_output"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"page_{page_number:02d}.svg"
    path.write_text(svg, encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Stage 6: export
# ---------------------------------------------------------------------------

async def run_export(settings: Settings, db: Database, project_id: str) -> Path:
    """svg_to_pptx.py → exports/<title>.pptx; updates pptx_path."""
    proj_dir = project_dir(settings, project_id)
    row = db.query_one("SELECT title FROM projects WHERE id = ?", (project_id,))
    title = sanitize_title((row or {}).get("title") or "deck")
    exports_dir = proj_dir / "exports"
    exports_dir.mkdir(parents=True, exist_ok=True)
    out_path = exports_dir / f"{title}.pptx"
    rc, _out, err = await run_script(
        settings, "svg_to_pptx.py",
        [str(proj_dir), "-o", str(out_path)], timeout=600.0,
    )
    if rc != 0 or not out_path.is_file():
        raise PipelineError(f"svg_to_pptx failed (rc={rc}): {err[-500:]}")
    db.execute(
        "UPDATE projects SET pptx_path = ?, updated_at = ? WHERE id = ?",
        (str(out_path), utcnow(), project_id),
    )
    return out_path


# ---------------------------------------------------------------------------
# Background generate task (stages 4-6) + registry
# ---------------------------------------------------------------------------

# Live stage of each running generate task ("images" | "pages" | "export").
# In-memory by design: only meaningful while a task is running.
CURRENT_STAGE: dict[str, str] = {}


def _set_status(db: Database, project_id: str, status: str,
                error: Optional[str] = None) -> None:
    db.execute(
        "UPDATE projects SET status = ?, error = ?, updated_at = ? WHERE id = ?",
        (status, error, utcnow(), project_id),
    )


async def generate_project(settings: Settings, db: Database, llm: LLMClient,
                           user_id: int, project_id: str) -> None:
    """Background task body: images → executor (concurrent) → check → export."""
    proj_dir = project_dir(settings, project_id)
    _set_status(db, project_id, "generating")
    try:
        outline = load_outline(db, project_id)
        theme_row = db.query_one(
            "SELECT t.name, t.style_md FROM projects p"
            " JOIN themes t ON t.id = p.theme_id WHERE p.id = ?",
            (project_id,),
        )
        style_md = (theme_row or {}).get("style_md") or ""
        theme_name = (theme_row or {}).get("name") or ""

        try:
            CURRENT_STAGE[project_id] = "images"
            image_files = await run_image_stage(settings, db, proj_dir, outline)
        except PipelineError:
            image_files = []

        check_quota(db, user_id)
        CURRENT_STAGE[project_id] = "pages"
        sem = asyncio.Semaphore(settings.max_concurrent_pages)

        async def one_page(page: dict) -> None:
            n = page["page_number"]
            db.execute(
                "UPDATE pages SET status = 'generating', error = NULL"
                " WHERE project_id = ? AND page_number = ?",
                (project_id, n),
            )
            try:
                async with sem:
                    svg = await generate_page_svg(
                        settings, db, llm, user_id, project_id,
                        outline["deck_title"], style_md, theme_name, page,
                        image_files,
                    )
                write_page_svg(proj_dir, n, svg)
                db.execute(
                    "UPDATE pages SET status = 'done', error = NULL"
                    " WHERE project_id = ? AND page_number = ?",
                    (project_id, n),
                )
            except Exception as exc:  # page failure must not kill siblings
                db.execute(
                    "UPDATE pages SET status = 'failed', error = ?"
                    " WHERE project_id = ? AND page_number = ?",
                    (str(exc)[:500], project_id, n),
                )

        await asyncio.gather(*(one_page(p) for p in outline["pages"]))

        failed = db.query(
            "SELECT page_number, error FROM pages"
            " WHERE project_id = ? AND status = 'failed'", (project_id,),
        )
        if failed:
            detail = "; ".join(f"p{r['page_number']}: {r['error']}" for r in failed)
            raise PipelineError(f"{len(failed)} page(s) failed: {detail[:400]}")

        # Advisory quality check — never blocks the pipeline.
        rc, out, err = await run_script(
            settings, "svg_quality_checker.py", [str(proj_dir)], timeout=300.0
        )
        report = f"exit={rc}\n{out}\n{err}".strip()
        (proj_dir / "quality_report.txt").write_text(report, encoding="utf-8")

        CURRENT_STAGE[project_id] = "export"
        await run_export(settings, db, project_id)
        _set_status(db, project_id, "exported")
    except Exception as exc:
        _set_status(db, project_id, "failed", str(exc)[:800])
    finally:
        CURRENT_STAGE.pop(project_id, None)


class GenerateRegistry:
    """Tracks running generate tasks; enforces the global concurrency cap."""

    def __init__(self, max_active: int) -> None:
        self._sem = asyncio.Semaphore(max_active)
        self._tasks: dict[str, asyncio.Task] = {}

    def is_running(self, project_id: str) -> bool:
        task = self._tasks.get(project_id)
        return bool(task and not task.done())

    def try_start(self, project_id: str, settings: Settings, db: Database,
                  llm: LLMClient, user_id: int) -> tuple[bool, str]:
        if self.is_running(project_id):
            return False, "generation already running for this project"
        if self._sem.locked():
            return False, ("server busy: too many active generations, "
                           "try again later")

        async def runner() -> None:
            async with self._sem:
                await generate_project(settings, db, llm, user_id, project_id)

        task = asyncio.create_task(runner())
        self._tasks[project_id] = task
        task.add_done_callback(lambda _t: self._tasks.pop(project_id, None))
        return True, ""
