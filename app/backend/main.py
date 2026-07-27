#!/usr/bin/env python3
"""
PPT Master SaaS - FastAPI application

All REST routes per docs/saas/ARCHITECTURE.md §7, plus static frontend
hosting (GET / → app/frontend/index.html, assets under /static/*).

Dependencies:
    fastapi, uvicorn, openai, python-multipart
"""

import json
import mimetypes
import re
import secrets
import shutil
import time
from pathlib import Path
from typing import Any, Optional

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .auth import (
    admin_user,
    create_session,
    current_user,
    delete_session,
    find_user_by_name,
    hash_password,
    new_salt,
    public_user,
    verify_password,
)
from .config import REPO_ROOT, Settings, get_settings, resolve, settings_payload
from .db import Database, utcnow
from .llm import LLMClient
from .pipeline import (
    CURRENT_STAGE,
    GenerateRegistry,
    PipelineError,
    QuotaExceeded,
    check_quota,
    generate_page_svg,
    load_outline,
    new_project_id,
    project_dir,
    run_export,
    run_ingest,
    run_strategist,
    sanitize_filename,
    save_outline,
    validate_outline,
    write_page_svg,
)
from .themes import seed_builtin_themes

FRONTEND_DIR = REPO_ROOT / "app" / "frontend"
_UNFINISHED_STATUSES = ("draft", "outline", "confirmed", "generating")
_PPTX_MEDIA = ("application/vnd.openxmlformats-officedocument"
               ".presentationml.presentation")

app = FastAPI(title="PPT Master SaaS", version="0.1.0")


@app.on_event("startup")
def _startup() -> None:
    settings = get_settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    db = Database(settings.data_dir / "app.db")
    seed_builtin_themes(db, settings.skill_dir)
    app.state.settings = settings
    app.state.db = db
    app.state.llm = LLMClient(settings, db)
    app.state.registry = GenerateRegistry(settings.max_active_projects)


def _settings(request: Request) -> Settings:
    return request.app.state.settings


def _llm(request: Request) -> LLMClient:
    return request.app.state.llm


def _registry(request: Request) -> GenerateRegistry:
    return request.app.state.registry


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

class CredentialsIn(BaseModel):
    username: str
    password: str


@app.post("/api/auth/register")
def register(body: CredentialsIn, request: Request) -> dict:
    settings, db = _settings(request), request.app.state.db
    username = body.username.strip()
    if not re.fullmatch(r"[\w一-鿿.-]{2,32}", username):
        raise HTTPException(400, "username must be 2-32 chars (letters/digits/._-)")
    if len(body.password) < 6:
        raise HTTPException(400, "password must be at least 6 characters")
    user_count = db.query_one("SELECT COUNT(*) AS c FROM users")["c"]
    if user_count > 0 and not settings.registration_open:
        raise HTTPException(409, "registration is closed")
    if find_user_by_name(db, username):
        raise HTTPException(409, "username already taken")
    salt = new_salt()
    role = "admin" if user_count == 0 else "user"
    cur = db.execute(
        "INSERT INTO users(username, password_hash, salt, role, token_quota,"
        " token_used, disabled, created_at) VALUES (?, ?, ?, ?, ?, 0, 0, ?)",
        (username, hash_password(body.password, salt), salt, role,
         settings.default_token_quota, utcnow()),
    )
    user = db.query_one("SELECT * FROM users WHERE id = ?", (cur.lastrowid,))
    token = create_session(db, user["id"], settings.session_ttl_hours)
    return {"token": token, "user": public_user(user)}


@app.post("/api/auth/login")
def login(body: CredentialsIn, request: Request) -> dict:
    settings, db = _settings(request), request.app.state.db
    user = find_user_by_name(db, body.username.strip())
    if not user or not verify_password(body.password, user["salt"],
                                       user["password_hash"]):
        raise HTTPException(401, "invalid username or password")
    if user["disabled"]:
        raise HTTPException(403, "user is disabled")
    token = create_session(db, user["id"], settings.session_ttl_hours)
    return {"token": token, "user": public_user(user)}


@app.post("/api/auth/logout")
def logout(request: Request, user: dict = Depends(current_user)) -> dict:
    delete_session(request.app.state.db, user["_token"])
    return {"ok": True}


@app.get("/api/auth/me")
def me(request: Request, user: dict = Depends(current_user)) -> dict:
    eff = resolve(_settings(request), request.app.state.db)
    return {"user": public_user(user),
            "token_used": user["token_used"],
            "token_quota": user["token_quota"],
            "mock_mode": eff.mock_llm}


# ---------------------------------------------------------------------------
# Themes
# ---------------------------------------------------------------------------

class ThemeIn(BaseModel):
    name: str
    style_md: str


def _palette_list(raw: Any) -> list[str]:
    """Decode the themes.palette JSON array column into a list."""
    try:
        value = json.loads(raw or "[]")
    except (TypeError, json.JSONDecodeError):
        return []
    return [str(c) for c in value] if isinstance(value, list) else []


@app.get("/api/themes")
def list_themes(request: Request,
                user: dict = Depends(current_user)) -> list[dict]:
    rows = request.app.state.db.query(
        "SELECT id, name, builtin, owner_id, style_md, description, palette,"
        " category, created_at FROM themes ORDER BY builtin DESC, id"
    )
    return [{
        "id": r["id"],
        "name": r["name"],
        "builtin": bool(r["builtin"]),
        "owner_id": r["owner_id"],
        "category": r["category"] or "generic",
        "description": r["description"] or "",
        "palette": _palette_list(r["palette"]),
        "summary": (r["style_md"] or "")[:200],
    } for r in rows]


@app.post("/api/themes", status_code=201)
def create_theme(body: ThemeIn, request: Request,
                 user: dict = Depends(current_user)) -> dict:
    name = body.name.strip()
    if not name or not body.style_md.strip():
        raise HTTPException(400, "name and style_md are required")
    db = request.app.state.db
    cur = db.execute(
        "INSERT INTO themes(name, builtin, owner_id, style_md, created_at)"
        " VALUES (?, 0, ?, ?, ?)",
        (name[:60], user["id"], body.style_md, utcnow()),
    )
    return db.query_one("SELECT * FROM themes WHERE id = ?", (cur.lastrowid,))


@app.get("/api/themes/{theme_id}")
def get_theme(theme_id: int, request: Request,
              user: dict = Depends(current_user)) -> dict:
    row = request.app.state.db.query_one(
        "SELECT * FROM themes WHERE id = ?", (theme_id,))
    if not row:
        raise HTTPException(404, "theme not found")
    row["description"] = row.get("description") or ""
    row["palette"] = _palette_list(row.get("palette"))
    return row


# ---------------------------------------------------------------------------
# Projects & pipeline
# ---------------------------------------------------------------------------

def _get_project(db: Database, project_id: str, user: dict) -> dict:
    row = db.query_one("SELECT * FROM projects WHERE id = ?", (project_id,))
    if not row:
        raise HTTPException(404, "project not found")
    if user["role"] != "admin" and row["user_id"] != user["id"]:
        raise HTTPException(403, "not your project")
    return row


def _project_json(row: dict, db: Database) -> dict:
    done = db.query_one(
        "SELECT COUNT(*) AS c FROM pages WHERE project_id = ? AND status = 'done'",
        (row["id"],))["c"]
    total = db.query_one(
        "SELECT COUNT(*) AS c FROM pages WHERE project_id = ?", (row["id"],))["c"]
    return {
        "id": row["id"],
        "user_id": row["user_id"],
        "title": row["title"],
        "status": row["status"],
        "theme_id": row["theme_id"],
        "slide_count": row["slide_count"],
        "style_brief": row["style_brief"],
        "error": row["error"],
        "pptx_ready": bool(row["pptx_path"] and Path(row["pptx_path"]).is_file()),
        "progress": {"done": done, "total": total},
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


@app.post("/api/projects", status_code=201)
async def create_project(
    request: Request,
    files: Optional[list[UploadFile]] = File(default=None),
    topic: str = Form(default=""),
    title: str = Form(default=""),
    theme_id: int = Form(default=1),
    slide_count: int = Form(default=10),
    style_brief: str = Form(default=""),
    user: dict = Depends(current_user),
) -> dict:
    settings = _settings(request)
    db = request.app.state.db
    llm = _llm(request)
    files = [f for f in (files or []) if f.filename]
    topic = topic.strip()
    if not files and not topic:
        raise HTTPException(400, "provide files[] or a topic")
    if len(files) > settings.upload_max_files:
        raise HTTPException(400, f"too many files (max {settings.upload_max_files})")
    slide_count = max(2, min(40, slide_count))
    if not db.query_one("SELECT id FROM themes WHERE id = ?", (theme_id,)):
        raise HTTPException(400, f"theme {theme_id} not found")
    queued = db.query_one(
        "SELECT COUNT(*) AS c FROM projects WHERE user_id = ? AND status IN"
        " ('draft','outline','confirmed','generating')", (user["id"],))["c"]
    if queued >= settings.max_queued_per_user:
        raise HTTPException(409, "too many unfinished projects for this user")
    try:
        check_quota(db, user["id"])
    except QuotaExceeded as exc:
        raise HTTPException(409, str(exc))

    project_id = new_project_id()
    proj_dir = project_dir(settings, project_id)
    (proj_dir / "sources").mkdir(parents=True, exist_ok=True)
    now = utcnow()
    db.execute(
        "INSERT INTO projects(id, user_id, title, status, theme_id, slide_count,"
        " style_brief, outline_json, error, pptx_path, created_at, updated_at)"
        " VALUES (?, ?, ?, 'draft', ?, ?, ?, NULL, NULL, NULL, ?, ?)",
        (project_id, user["id"], title.strip() or topic[:60] or "未命名演示",
         theme_id, slide_count, style_brief.strip(), now, now),
    )

    try:
        # Stage 1: ingest (skipped for topic-only).
        saved: list[Path] = []
        for upload in files:
            safe = sanitize_filename(upload.filename or "upload")
            dest = proj_dir / "sources" / safe
            if dest.exists():
                dest = dest.with_name(dest.stem + "_" + project_id + dest.suffix)
            data = await upload.read()
            if len(data) > settings.upload_max_mb * 1024 * 1024:
                raise HTTPException(
                    400, f"file too large (max {settings.upload_max_mb} MB): {safe}")
            dest.write_bytes(data)
            saved.append(dest)
        if saved:
            sources_md = await run_ingest(settings, proj_dir, saved)
        else:
            sources_md = f"# {topic}\n"
            (proj_dir / "sources.md").write_text(sources_md, encoding="utf-8")

        # Upload-only projects have no topic text; fall back to the first
        # markdown heading so the strategist gets a sensible subject.
        topic_hint = topic or title.strip()
        if not topic_hint:
            heading = re.search(r"^#\s+(.+)$", sources_md, re.MULTILINE)
            topic_hint = heading.group(1).strip() if heading else ""

        # Stage 2: strategist (inline).
        outline = await run_strategist(
            settings, db, llm, user["id"], project_id,
            topic_hint, title.strip(), slide_count,
            style_brief.strip(), sources_md,
        )
        save_outline(db, proj_dir, project_id, outline)
        final_title = title.strip() or outline["deck_title"]
        db.execute(
            "UPDATE projects SET title = ?, status = 'outline', updated_at = ?"
            " WHERE id = ?",
            (final_title, utcnow(), project_id),
        )
    except HTTPException:
        db.execute("UPDATE projects SET status = 'failed', error = 'upload rejected'"
                   " WHERE id = ?", (project_id,))
        raise
    except (PipelineError, QuotaExceeded) as exc:
        db.execute("UPDATE projects SET status = 'failed', error = ? WHERE id = ?",
                   (str(exc)[:800], project_id))
        raise HTTPException(500, str(exc))

    row = _get_project(db, project_id, user)
    return {"project": _project_json(row, db), "outline": outline}


@app.get("/api/projects")
def list_projects(request: Request,
                  user: dict = Depends(current_user)) -> list[dict]:
    db = request.app.state.db
    if user["role"] == "admin":
        rows = db.query("SELECT * FROM projects ORDER BY created_at DESC")
    else:
        rows = db.query(
            "SELECT * FROM projects WHERE user_id = ? ORDER BY created_at DESC",
            (user["id"],))
    return [_project_json(r, db) for r in rows]


@app.get("/api/projects/{project_id}")
def get_project(project_id: str, request: Request,
                user: dict = Depends(current_user)) -> dict:
    db = request.app.state.db
    row = _get_project(db, project_id, user)
    detail = _project_json(row, db)
    detail["outline"] = (json.loads(row["outline_json"])
                         if row["outline_json"] else None)
    detail["pages"] = [
        {"n": p["page_number"], "status": p["status"], "error": p["error"]}
        for p in db.query(
            "SELECT page_number, status, error FROM pages"
            " WHERE project_id = ? ORDER BY page_number", (project_id,))
    ]
    return detail


@app.delete("/api/projects/{project_id}")
def delete_project(project_id: str, request: Request,
                   user: dict = Depends(current_user)) -> dict:
    settings, db = _settings(request), request.app.state.db
    _get_project(db, project_id, user)
    if _registry(request).is_running(project_id):
        raise HTTPException(409, "generation is running; wait for it to finish")
    db.execute("DELETE FROM pages WHERE project_id = ?", (project_id,))
    db.execute("DELETE FROM projects WHERE id = ?", (project_id,))
    proj_dir = project_dir(settings, project_id)
    if proj_dir.is_dir() and proj_dir.parent == settings.data_dir / "projects":
        shutil.rmtree(proj_dir, ignore_errors=True)
    return {"ok": True}


class OutlineIn(BaseModel):
    outline: dict[str, Any]
    theme_id: int | None = None


@app.put("/api/projects/{project_id}/outline")
def put_outline(project_id: str, body: OutlineIn, request: Request,
                user: dict = Depends(current_user)) -> dict:
    settings, db = _settings(request), request.app.state.db
    _get_project(db, project_id, user)
    try:
        outline = validate_outline(body.outline)
    except PipelineError as exc:
        raise HTTPException(400, str(exc))
    save_outline(db, project_dir(settings, project_id), project_id, outline)
    if body.theme_id is not None:
        if not db.query_one("SELECT id FROM themes WHERE id = ?", (body.theme_id,)):
            raise HTTPException(400, f"theme {body.theme_id} not found")
        db.execute("UPDATE projects SET theme_id = ? WHERE id = ?",
                   (body.theme_id, project_id))
    db.execute(
        "UPDATE projects SET status = 'confirmed', error = NULL, updated_at = ?"
        " WHERE id = ?",
        (utcnow(), project_id),
    )
    return {"ok": True, "outline": outline}


@app.post("/api/projects/{project_id}/generate")
async def start_generate(project_id: str, request: Request,
                         user: dict = Depends(current_user)) -> dict:
    settings, db = _settings(request), request.app.state.db
    row = _get_project(db, project_id, user)
    try:
        check_quota(db, user["id"])
    except QuotaExceeded as exc:
        raise HTTPException(409, str(exc))
    if not row["outline_json"]:
        # Self-healing retry: the project failed at the strategist stage
        # (e.g. truncated LLM JSON). Rebuild the outline from stored sources
        # instead of forcing the user to recreate the project.
        proj_dir = project_dir(settings, project_id)
        sources_path = proj_dir / "sources.md"
        sources_md = (sources_path.read_text(encoding="utf-8")
                      if sources_path.is_file() else f"# {row['title']}\n")
        topic_hint = row["title"] or ""
        if not topic_hint:
            heading = re.search(r"^#\s+(.+)$", sources_md, re.MULTILINE)
            topic_hint = heading.group(1).strip() if heading else ""
        try:
            outline = await run_strategist(
                settings, db, _llm(request), user["id"], project_id,
                topic_hint, "", row["slide_count"] or 10,
                row["style_brief"] or "", sources_md,
            )
        except (PipelineError, QuotaExceeded) as exc:
            db.execute(
                "UPDATE projects SET status = 'failed', error = ?,"
                " updated_at = ? WHERE id = ?",
                (str(exc)[:800], utcnow(), project_id),
            )
            raise HTTPException(500, str(exc))
        save_outline(db, proj_dir, project_id, outline)
        db.execute(
            "UPDATE projects SET status = 'confirmed', error = NULL,"
            " updated_at = ? WHERE id = ?",
            (utcnow(), project_id),
        )
    ok, message = _registry(request).try_start(
        project_id, settings, db, _llm(request), user["id"])
    if not ok:
        raise HTTPException(409, message)
    return {"started": True}


@app.get("/api/projects/{project_id}/status")
def project_status(project_id: str, request: Request,
                   user: dict = Depends(current_user)) -> dict:
    db = request.app.state.db
    row = _get_project(db, project_id, user)
    pages = [
        {"n": p["page_number"], "status": p["status"], "error": p["error"]}
        for p in db.query(
            "SELECT page_number, status, error FROM pages"
            " WHERE project_id = ? ORDER BY page_number", (project_id,))
    ]
    return {
        "status": row["status"],
        "error": row["error"],
        "stage": CURRENT_STAGE.get(project_id),
        "pages": pages,
        "pptx_ready": bool(row["pptx_path"] and Path(row["pptx_path"]).is_file()),
    }


class RegenerateIn(BaseModel):
    feedback: str = ""


@app.post("/api/projects/{project_id}/pages/{page_number}/regenerate")
async def regenerate_page(project_id: str, page_number: int,
                          body: RegenerateIn, request: Request,
                          user: dict = Depends(current_user)) -> dict:
    settings, db = _settings(request), request.app.state.db
    llm = _llm(request)
    _get_project(db, project_id, user)
    try:
        outline = load_outline(db, project_id)
    except PipelineError as exc:
        raise HTTPException(409, str(exc))
    page = next((p for p in outline["pages"] if p["page_number"] == page_number),
                None)
    if not page:
        raise HTTPException(404, f"page {page_number} not in outline")
    try:
        check_quota(db, user["id"])
    except QuotaExceeded as exc:
        raise HTTPException(409, str(exc))
    theme_row = db.query_one(
        "SELECT t.name, t.style_md FROM projects p"
        " JOIN themes t ON t.id = p.theme_id WHERE p.id = ?", (project_id,))
    images_dir = project_dir(settings, project_id) / "images"
    image_files = sorted(p.name for p in images_dir.glob("*.jpg")) \
        if images_dir.is_dir() else []
    try:
        svg = await generate_page_svg(
            settings, db, llm, user["id"], project_id, outline["deck_title"],
            (theme_row or {}).get("style_md") or "",
            (theme_row or {}).get("name") or "",
            page, image_files, body.feedback.strip(),
        )
    except PipelineError as exc:
        raise HTTPException(500, str(exc))
    write_page_svg(project_dir(settings, project_id), page_number, svg)
    db.execute(
        "INSERT INTO pages(project_id, page_number, status, error)"
        " VALUES (?, ?, 'done', NULL)"
        " ON CONFLICT(project_id, page_number)"
        " DO UPDATE SET status = 'done', error = NULL",
        (project_id, page_number),
    )
    return {"svg": _svg_with_image_urls(svg, project_id, user["_token"])}


_HREF_RE = re.compile(r'(xlink:href|href)="images/')


def _svg_with_image_urls(svg: str, project_id: str, token: str) -> str:
    """Rewrite relative image hrefs to the authed image endpoint.

    Inline SVG loads images without Authorization headers, so the session
    token rides along as a query param (see auth._extract_token).
    """
    svg = _HREF_RE.sub(rf'\1="/api/projects/{project_id}/images/', svg)
    return re.sub(
        rf'(/api/projects/{project_id}/images/[^"]+?)(")',
        rf'\1?token={token}\2', svg)


@app.get("/api/projects/{project_id}/pages/{page_number}/svg")
def get_page_svg(project_id: str, page_number: int, request: Request,
                 user: dict = Depends(current_user)) -> Response:
    settings, db = _settings(request), request.app.state.db
    _get_project(db, project_id, user)
    path = (project_dir(settings, project_id) / "svg_output"
            / f"page_{page_number:02d}.svg")
    if not path.is_file():
        raise HTTPException(404, "svg not generated yet")
    svg = path.read_text(encoding="utf-8")
    svg = _svg_with_image_urls(svg, project_id, user["_token"])
    return Response(content=svg, media_type="image/svg+xml")


@app.put("/api/projects/{project_id}/pages/{page_number}/svg")
async def put_page_svg(project_id: str, page_number: int, request: Request,
                       user: dict = Depends(current_user)) -> dict:
    settings, db = _settings(request), request.app.state.db
    _get_project(db, project_id, user)
    body = await request.body()
    if len(body) > 5 * 1024 * 1024:
        raise HTTPException(400, "svg too large (max 5 MB)")
    text = body.decode("utf-8", "replace")
    if "<svg" not in text or "</svg>" not in text:
        raise HTTPException(400, "body must be a complete SVG document")
    # The on-screen SVG carries rewritten authed URLs; normalize back to the
    # relative form the exporter and re-serving expect.
    text = re.sub(
        rf'/api/projects/{project_id}/images/([^"?]+)\?token=[^"]+',
        r'images/\1', text)
    write_page_svg(project_dir(settings, project_id), page_number, text)
    db.execute(
        "INSERT INTO pages(project_id, page_number, status, error)"
        " VALUES (?, ?, 'done', NULL)"
        " ON CONFLICT(project_id, page_number)"
        " DO UPDATE SET status = 'done', error = NULL",
        (project_id, page_number),
    )
    return {"ok": True}


@app.post("/api/projects/{project_id}/export")
async def export_project(project_id: str, request: Request,
                         user: dict = Depends(current_user)) -> dict:
    db = request.app.state.db
    _get_project(db, project_id, user)
    svg_dir = project_dir(_settings(request), project_id) / "svg_output"
    if not svg_dir.is_dir() or not list(svg_dir.glob("*.svg")):
        raise HTTPException(409, "no SVG pages to export")
    try:
        await run_export(_settings(request), db, project_id)
    except PipelineError as exc:
        raise HTTPException(500, str(exc))
    db.execute("UPDATE projects SET status = 'exported', updated_at = ?"
               " WHERE id = ?", (utcnow(), project_id))
    return {"pptx_ready": True}


@app.get("/api/projects/{project_id}/download")
def download_pptx(project_id: str, request: Request,
                  user: dict = Depends(current_user)) -> FileResponse:
    db = request.app.state.db
    row = _get_project(db, project_id, user)
    if not row["pptx_path"] or not Path(row["pptx_path"]).is_file():
        raise HTTPException(404, "pptx not exported yet")
    return FileResponse(row["pptx_path"], media_type=_PPTX_MEDIA,
                        filename=Path(row["pptx_path"]).name)


@app.get("/api/projects/{project_id}/images/{name}")
def get_project_image(project_id: str, name: str, request: Request,
                      user: dict = Depends(current_user)) -> FileResponse:
    settings, db = _settings(request), request.app.state.db
    _get_project(db, project_id, user)
    safe = sanitize_filename(name)
    path = project_dir(settings, project_id) / "images" / safe
    if not path.is_file():
        raise HTTPException(404, "image not found")
    media = mimetypes.guess_type(safe)[0] or "application/octet-stream"
    return FileResponse(str(path), media_type=media)


# ---------------------------------------------------------------------------
# Share links (public, no auth; owners manage tokens per project)
# ---------------------------------------------------------------------------

def _get_shared_project(db: Database, token: str) -> dict:
    row = db.query_one("SELECT * FROM projects WHERE share_token = ?", (token,))
    if not row:
        raise HTTPException(404, "share link not found or revoked")
    return row


@app.post("/api/projects/{project_id}/share")
def create_share(project_id: str, request: Request,
                 user: dict = Depends(current_user)) -> dict:
    db = request.app.state.db
    row = _get_project(db, project_id, user)
    token = row["share_token"]
    if not token:
        token = secrets.token_urlsafe(12)
        db.execute("UPDATE projects SET share_token = ? WHERE id = ?",
                   (token, project_id))
    return {"share_url": "/share/" + token}


@app.delete("/api/projects/{project_id}/share")
def revoke_share(project_id: str, request: Request,
                 user: dict = Depends(current_user)) -> dict:
    db = request.app.state.db
    _get_project(db, project_id, user)
    db.execute("UPDATE projects SET share_token = NULL WHERE id = ?",
               (project_id,))
    return {"ok": True}


@app.get("/api/share/{token}")
def share_meta(token: str, request: Request) -> dict:
    settings, db = _settings(request), request.app.state.db
    row = _get_shared_project(db, token)
    svg_dir = project_dir(settings, row["id"]) / "svg_output"
    page_count = len(list(svg_dir.glob("*.svg"))) if svg_dir.is_dir() else 0
    theme = db.query_one("SELECT name FROM themes WHERE id = ?",
                         (row["theme_id"],))
    return {
        "title": row["title"],
        "page_count": page_count,
        "theme_name": (theme or {}).get("name") or "",
    }


@app.get("/api/share/{token}/pages/{page_number}")
def share_page_svg(token: str, page_number: int, request: Request) -> Response:
    settings, db = _settings(request), request.app.state.db
    row = _get_shared_project(db, token)
    path = (project_dir(settings, row["id"]) / "svg_output"
            / f"page_{page_number:02d}.svg")
    if not path.is_file():
        raise HTTPException(404, "project not finished exporting yet")
    svg = path.read_text(encoding="utf-8")
    svg = _HREF_RE.sub(rf'\1="/api/share/{token}/images/', svg)
    return Response(content=svg, media_type="image/svg+xml")


@app.get("/api/share/{token}/images/{name}")
def share_image(token: str, name: str, request: Request) -> FileResponse:
    settings, db = _settings(request), request.app.state.db
    row = _get_shared_project(db, token)
    safe = sanitize_filename(name)
    path = project_dir(settings, row["id"]) / "images" / safe
    if not path.is_file():
        raise HTTPException(404, "image not found")
    media = mimetypes.guess_type(safe)[0] or "application/octet-stream"
    return FileResponse(str(path), media_type=media)


# ---------------------------------------------------------------------------
# Usage & admin
# ---------------------------------------------------------------------------

@app.get("/api/usage")
def my_usage(request: Request, user: dict = Depends(current_user)) -> dict:
    db = request.app.state.db
    totals = db.query_one(
        "SELECT COALESCE(SUM(total_tokens), 0) AS total,"
        " COALESCE(SUM(prompt_tokens), 0) AS prompt,"
        " COALESCE(SUM(completion_tokens), 0) AS completion"
        " FROM token_usage WHERE user_id = ?", (user["id"],))
    per_project = db.query(
        "SELECT tu.project_id, p.title,"
        " COALESCE(SUM(tu.total_tokens), 0) AS total_tokens,"
        " COALESCE(SUM(tu.prompt_tokens), 0) AS prompt,"
        " COALESCE(SUM(tu.completion_tokens), 0) AS completion,"
        " COUNT(*) AS calls"
        " FROM token_usage tu LEFT JOIN projects p ON p.id = tu.project_id"
        " WHERE tu.user_id = ? GROUP BY tu.project_id"
        " ORDER BY total_tokens DESC",
        (user["id"],))
    recent = db.query(
        "SELECT project_id, stage, model, prompt_tokens, completion_tokens,"
        " total_tokens, created_at FROM token_usage WHERE user_id = ?"
        " ORDER BY id DESC LIMIT 20", (user["id"],))
    return {
        "token_quota": user["token_quota"],
        "token_used": user["token_used"],
        "totals": totals,
        "per_project": per_project,
        "recent": recent,
    }


@app.get("/api/admin/users")
def admin_list_users(request: Request,
                     admin: dict = Depends(admin_user)) -> list[dict]:
    rows = request.app.state.db.query(
        "SELECT * FROM users ORDER BY id")
    return [public_user(r) for r in rows]


class PatchUserIn(BaseModel):
    token_quota: Optional[int] = None
    disabled: Optional[bool] = None
    role: Optional[str] = None


@app.patch("/api/admin/users/{user_id}")
def admin_patch_user(user_id: int, body: PatchUserIn, request: Request,
                     admin: dict = Depends(admin_user)) -> dict:
    db = request.app.state.db
    target = db.query_one("SELECT * FROM users WHERE id = ?", (user_id,))
    if not target:
        raise HTTPException(404, "user not found")
    if body.role is not None and body.role not in ("admin", "user"):
        raise HTTPException(400, "role must be 'admin' or 'user'")
    if body.token_quota is not None:
        db.execute("UPDATE users SET token_quota = ? WHERE id = ?",
                   (max(0, body.token_quota), user_id))
    if body.disabled is not None:
        db.execute("UPDATE users SET disabled = ? WHERE id = ?",
                   (1 if body.disabled else 0, user_id))
    if body.role is not None:
        db.execute("UPDATE users SET role = ? WHERE id = ?", (body.role, user_id))
    return public_user(db.query_one("SELECT * FROM users WHERE id = ?", (user_id,)))


@app.get("/api/admin/stats")
def admin_stats(request: Request, admin: dict = Depends(admin_user)) -> dict:
    db = request.app.state.db
    today = utcnow()[:10]
    return {
        "users": db.query_one("SELECT COUNT(*) AS c FROM users")["c"],
        "projects": db.query_one("SELECT COUNT(*) AS c FROM projects")["c"],
        "tokens_total": db.query_one(
            "SELECT COALESCE(SUM(total_tokens), 0) AS t FROM token_usage")["t"],
        "tokens_today": db.query_one(
            "SELECT COALESCE(SUM(total_tokens), 0) AS t FROM token_usage"
            " WHERE created_at >= ?", (today,))["t"],
    }


# ---------------------------------------------------------------------------
# Admin settings (LLM + image provider keys; resolution: DB override > env)
# ---------------------------------------------------------------------------

class SettingsIn(BaseModel):
    """PUT /api/admin/settings body; any subset of the allowed keys.

    Non-empty string → stored as a DB override; empty string "" → the DB
    override is deleted (falls back to env); omitted keys are untouched.
    """

    llm_base_url: Optional[str] = None
    llm_model: Optional[str] = None
    llm_api_key: Optional[str] = None
    pexels_api_key: Optional[str] = None
    pixabay_api_key: Optional[str] = None
    image_provider: Optional[str] = None


@app.get("/api/admin/settings")
def admin_get_settings(request: Request,
                       admin: dict = Depends(admin_user)) -> dict:
    """Effective settings; secrets are only exposed as a tail (last 4 chars)."""
    return settings_payload(_settings(request), request.app.state.db)


@app.put("/api/admin/settings")
def admin_put_settings(body: SettingsIn, request: Request,
                       admin: dict = Depends(admin_user)) -> dict:
    db = request.app.state.db
    for key, raw in body.model_dump(exclude_unset=True).items():
        if raw is None:
            continue
        value = raw.strip()
        if value:
            db.execute(
                "INSERT INTO settings(k, v) VALUES (?, ?)"
                " ON CONFLICT(k) DO UPDATE SET v = excluded.v",
                (key, value),
            )
        else:
            db.execute("DELETE FROM settings WHERE k = ?", (key,))
    return settings_payload(_settings(request), db)


@app.post("/api/admin/settings/test-llm")
async def admin_test_llm(request: Request,
                         admin: dict = Depends(admin_user)) -> dict:
    """Minimal chat completion ("ping", max_tokens 16) against the effective
    LLM config. Always HTTP 200; failures are reported in the body."""
    settings, db = _settings(request), request.app.state.db
    eff = resolve(settings, db)
    if not eff.llm_api_key:
        return {"ok": False, "error": "mock mode: no api key"}
    from openai import AsyncOpenAI

    client = AsyncOpenAI(
        base_url=eff.llm_base_url,
        api_key=eff.llm_api_key,
        timeout=min(eff.llm_timeout, 60.0),
        max_retries=0,
    )
    extra_body = ({"enable_thinking": False}
                  if eff.disable_thinking_effective else None)
    started = time.monotonic()
    try:
        await client.chat.completions.create(
            model=eff.llm_model,
            messages=[{"role": "user", "content": "ping"}],
            max_tokens=16,
            extra_body=extra_body,
        )
    except Exception as exc:
        return {"ok": False, "error": str(exc)[:300]}
    return {
        "ok": True,
        "latency_ms": int((time.monotonic() - started) * 1000),
        "model": eff.llm_model,
    }


@app.post("/api/admin/settings/test-image")
def admin_test_image(body: dict, request: Request,
                     admin: dict = Depends(admin_user)) -> dict:
    """Ping the effective key of one image provider ("pexels" / "pixabay")
    with a minimal search request. Always HTTP 200; failures in the body."""
    import urllib.error
    import urllib.request

    from .config import effective_image_keys

    provider = str(body.get("provider", "")).strip().lower()
    keys = effective_image_keys(request.app.state.db)
    key = keys.get(f"{provider}_api_key", ("",))[0]
    if provider not in ("pexels", "pixabay"):
        return {"ok": False, "error": "provider must be 'pexels' or 'pixabay'"}
    if not key:
        return {"ok": False, "error": "未配置该服务商的 API Key"}
    if provider == "pexels":
        req = urllib.request.Request(
            "https://api.pexels.com/v1/search?query=nature&per_page=1",
            headers={"Authorization": key})
    else:
        req = urllib.request.Request(
            f"https://pixabay.com/api/?key={key}&q=nature&per_page=3")
    started = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            ok = resp.status == 200
            if not ok:
                return {"ok": False, "error": f"HTTP {resp.status}"}
    except urllib.error.HTTPError as exc:
        return {"ok": False, "error": f"HTTP {exc.code}（Key 无效或已过期）"}
    except OSError as exc:
        return {"ok": False, "error": str(exc)[:300]}
    return {"ok": True,
            "latency_ms": int((time.monotonic() - started) * 1000),
            "provider": provider}


# ---------------------------------------------------------------------------
# Frontend serving
# ---------------------------------------------------------------------------

@app.get("/")
def index() -> Any:
    index_path = FRONTEND_DIR / "index.html"
    if index_path.is_file():
        return FileResponse(str(index_path))
    return {"service": "ppt-master-saas", "frontend": "not installed"}


@app.get("/share/{token}")
def share_page(token: str) -> Any:
    """Public read-only deck viewer (self-contained, no login required)."""
    share_path = FRONTEND_DIR / "share.html"
    if share_path.is_file():
        return FileResponse(str(share_path))
    raise HTTPException(404, "share page not installed")


if FRONTEND_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")
