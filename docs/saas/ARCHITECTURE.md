# PPT Master Agent (SaaS) — Architecture & API Contract

This document is the **build contract** for the SaaS-ified PPT Master Agent
(`app/` at repo root). It pins down the pipeline, config, DB schema, and REST
API so backend, frontend, docs, and packaging can be built in parallel.

> Branch intent: turn the agent-driven *skill* (`skills/ppt-master/`) into a
> deployable *application* — upload sources → confirm outline → per-page
> preview/edit → export PPTX — with multi-user auth, token metering, themes,
> and one-file packaging (Windows exe / Linux AppImage).

## 1. Design principles

1. **Reuse, don't reinvent.** All heavy lifting delegates to the existing,
   battle-tested scripts under `skills/ppt-master/scripts/` via subprocess:
   - `source_to_md.py` — MD/DOCX/PDF/PPTX/URL → Markdown
   - `image_search.py` — Pexels / Pixabay / Openverse / Wikimedia image
     acquisition (this is the MYGEM-proven capability, already vendored here)
   - `svg_quality_checker.py` — per-page SVG lint
   - `svg_to_pptx.py` — SVG → natively-editable PPTX (reads
     `<project>/svg_output/*.svg` by default)
2. **LLM only does what LLMs must do**: outline planning and per-page SVG
   authoring. Everything else is deterministic code.
3. **OpenAI-compatible LLM endpoint** — works with DeepSeek-class small
   models, GLM, Qwen, or a co-located local model (llama.cpp / vLLM / Ollama).
4. **Zero-build frontend** — a static SPA (vanilla HTML/JS/CSS) served by
   FastAPI. No Node toolchain required at deploy time.
5. **Low barrier deployment** — SQLite only, no Redis/broker; background work
   via asyncio tasks; single config via env vars or `.env`.

## 2. Fixed pipeline

```
upload (md/docx/pdf/pptx/txt or topic text)
  → 1. ingest:    source_to_md.py → sources.md            (skipped for topic-only; topic-only may optionally web-expand later — out of scope v1)
  → 2. strategist: 1 LLM call → outline JSON (deck title + pages[])
  → 3. confirm:   user edits outline / theme / font / density in UI (blocking stage)
  → 4. images:    image_search.py per page.image_query (Pexels key → pexels+pixabay chain; else openverse+wikimedia)
  → 5. executor:  concurrent per-page LLM → SVG 1280×720 (theme style guide injected) → svg_quality_checker.py (advisory)
  → 6. export:    svg_to_pptx.py → downloadable .pptx
```

Stages 1–2 run synchronously on project creation request `outline`;
stage 3 waits for the user; stages 4–6 run as a background task
(`generate`). Users may regenerate a single page with feedback, or save a
hand-edited SVG, then re-export.

### Project directory layout (under `<DATA_DIR>/projects/<project_id>/`)

```
sources/            uploaded originals
sources.md          merged markdown (stage 1)
outline.json        strategist output, user-editable (stage 3)
images/             image_search.py output + image_sources.json
svg_output/page_01.svg … page_NN.svg   (stage 5; svg_to_pptx native source)
exports/<title>.pptx                   (stage 6)
```

This mirrors what `svg_to_pptx.py` expects (native source = `svg_output/`).

## 3. Configuration (env, all prefixed `PPTSAAS_` except provider keys)

| Var | Default | Meaning |
|---|---|---|
| `PPTSAAS_PORT` | `8310` | listen port |
| `PPTSAAS_HOST` | `0.0.0.0` | listen host |
| `PPTSAAS_DATA_DIR` | `./data` | SQLite DB + projects + uploads |
| `PPTSAAS_SKILL_DIR` | auto: `<repo>/skills/ppt-master` | where scripts live |
| `PPTSAAS_PYTHON` | `python3` | interpreter for the skill-script subprocesses; packaged launchers point this at the embedded portable Python |
| `PPTSAAS_LLM_BASE_URL` | `https://api.deepseek.com/v1` | OpenAI-compatible endpoint |
| `PPTSAAS_LLM_API_KEY` | — | required |
| `PPTSAAS_LLM_MODEL` | `deepseek-chat` | primary model |
| `PPTSAAS_LLM_MODEL_FALLBACKS` | `` | comma-separated fallback models on same endpoint |
| `PPTSAAS_LLM_TIMEOUT` | `600` | per-call seconds |
| `PPTSAAS_LLM_DISABLE_THINKING` | `true` | DashScope (Bailian) endpoints only: send `extra_body={"enable_thinking": false}` so thinking models skip the reasoning phase (faster, reasoning tokens can't eat `max_tokens`) |
| `PPTSAAS_MAX_CONCURRENT_PAGES` | `4` | per-project page-generation concurrency |
| `PPTSAAS_MAX_ACTIVE_PROJECTS` | `2` | global concurrent `generate` tasks |
| `PPTSAAS_MAX_QUEUED_PER_USER` | `2` | per-user unfinished project cap |
| `PPTSAAS_DEFAULT_TOKEN_QUOTA` | `2000000` | per-user LLM token budget (0 = unlimited) |
| `PPTSAAS_REGISTRATION_OPEN` | `true` | open self-registration |
| `PPTSAAS_SESSION_TTL_HOURS` | `72` | session expiry |
| `PEXELS_API_KEY` / `PIXABAY_API_KEY` | — | image search providers (no key → openverse+wikimedia) |
| `PPTSAAS_IMAGE_PROVIDER` | `auto` | pin image search to one provider: `auto`/`pexels`/`pixabay`/`openverse`/`wikimedia` (admin UI may override) |

`.env` at repo root is loaded if present (pexels keys already live there).

### Runtime overrides (admin-editable)

Five keys can be overridden at runtime from the admin UI without a restart;
they are stored in the `settings` table (§4):

`llm_base_url` → `PPTSAAS_LLM_BASE_URL`, `llm_model` → `PPTSAAS_LLM_MODEL`,
`llm_api_key` → `PPTSAAS_LLM_API_KEY`, `pexels_api_key` → `PEXELS_API_KEY`,
`pixabay_api_key` → `PIXABAY_API_KEY`, `image_provider` → `PPTSAAS_IMAGE_PROVIDER`.

**Resolution order: a non-empty DB value always wins over env/.env.**
Consumers never read the raw env snapshot directly: LLM calls go through
`config.resolve(settings, db)` (per call; the `LLMClient`'s cached
`AsyncOpenAI` is rebuilt whenever `(base_url, api_key, model)` changes), and
the image stage injects `config.image_search_env(db)` into the
`image_search.py` subprocess environment. `config.settings_payload()`
builds the admin GET/PUT response — secrets are only ever exposed as a
`"…"`-prefixed last-4-chars tail, never in full.

## 4. Database (SQLite, `<DATA_DIR>/app.db`)

```sql
users(id INTEGER PK, username TEXT UNIQUE, password_hash TEXT, salt TEXT,
      role TEXT DEFAULT 'user',           -- 'admin' | 'user'; first registered = admin
      token_quota INTEGER DEFAULT 2000000, token_used INTEGER DEFAULT 0,
      disabled INTEGER DEFAULT 0, created_at TEXT)
sessions(token TEXT PK, user_id INTEGER, created_at TEXT, expires_at TEXT)
projects(id TEXT PK,                      -- uuid hex 12
         user_id INTEGER, title TEXT, status TEXT,   -- draft|outline|confirmed|generating|ready|exported|failed
         theme_id INTEGER, slide_count INTEGER, style_brief TEXT,
         outline_json TEXT, error TEXT, pptx_path TEXT,
         share_token TEXT,                -- public share link token (NULL = not shared)
         created_at TEXT, updated_at TEXT)
pages(project_id TEXT, page_number INTEGER, status TEXT,  -- pending|generating|done|failed
      error TEXT, PRIMARY KEY(project_id, page_number))
token_usage(id INTEGER PK, user_id INTEGER, project_id TEXT, stage TEXT,
            model TEXT, prompt_tokens INTEGER, completion_tokens INTEGER,
            total_tokens INTEGER, created_at TEXT)
themes(id INTEGER PK, name TEXT, builtin INTEGER DEFAULT 0, owner_id INTEGER,
       style_md TEXT, description TEXT, palette TEXT,  -- palette = JSON array of hex colors
       category TEXT,                     -- generic|brand|deck|layout
       created_at TEXT)
settings(k TEXT PRIMARY KEY, v TEXT)   -- admin runtime overrides, see §3
```

Passwords: PBKDF2-HMAC-SHA256 (stdlib `hashlib`), per-user salt.
Sessions: `secrets.token_urlsafe(32)`, Bearer header `Authorization: Bearer <token>`.

## 5. Themes

Builtin themes are seeded at startup (idempotent, keyed by name), each a
`style_md` block (palette hex codes, font stack, background, card/divider
rules, do/don't) injected verbatim into the executor system prompt. 22
builtins in four categories (`category` column, returned by
`GET /api/themes`):

| category | count | source | themes |
|---|---|---|---|
| `generic` | 5 | hand-written in `themes.py` | 商务蓝, 科技暗色, 咨询红, 护眼绿, 极简白 |
| `brand` | 5 | `templates/brands/*/design_spec.md` + `templates/brand-doubao-huawei/` | Anthropic, 豆包风格, Google, 华为品牌, 豆包×华为红 |
| `deck` | 5 | `templates/decks/decks_index.json` + each deck's `design_spec.md` | 中国电信, 中国电建, 中汽研, 招商银行, 重庆大学 |
| `layout` | 7 | `templates/layouts/layouts_index.json` + each layout's `design_spec.md` | 学术答辩, 电信AI运维, 政务蓝, 政务红, 医学院, 像素复古, 心理学 |

The five hand-written generic themes:

| key | name | vibe |
|---|---|---|
| `business-blue` | 商务蓝 | clean SaaS blue, light bg |
| `tech-dark` | 科技暗色 | dark bg, neon accent |
| `consult-red` | 咨询红 | Huawei-style red headings, light bg |
| `fresh-green` | 护眼绿 | soft green, light bg |
| `minimal-white` | 极简白 | near-white, single accent |

Users with any role may create custom themes (owner-scoped + visible to all
in v1 — keep it simple; custom themes report `category` as `generic`).

Scanned themes (brand/deck/layout) use friendly Chinese names, full
`style_md` = file content, `description` from a Chinese mapping table in
`themes.py` (falling back to the index/frontmatter summary), and `palette`
= up to 5 unique `#RRGGBB` values (decks: the index's `primary_color`
first, then spec hexes). Layouts are structure-only (no color spec), so a
note is appended to their `style_md` telling the executor to design a
consistent palette itself, and their `palette` is whatever hexes the spec
mentions (possibly empty — the frontend has a fallback).
`GET /api/themes` and `GET /api/themes/{id}` return `category`,
`description` and `palette` (array).

## 6. LLM prompting

- **Strategist** (temp 0.4, max_tokens = min(32768, max(8192, 300×N+3000))):
  system = role + narrative-arc guidance + density rules + strict-JSON
  contract; user = topic/title, slide count, style brief, sources.md excerpt
  (≤24000 chars). Output JSON:
  ```json
  {"deck_title":"…","pages":[{"page_number":1,"title":"…","key_message":"…",
   "content_summary":"…(300-800字)…","visual_suggestion":"…",
   "image_query":"2-5 english keywords or empty",
   "chart_hint":"optional, e.g. 'bar: 2022-2026 市场规模'",
   "layout_hint":"cover|toc|content|data|closing",
   "bullets":["…","…"]}]}
  ```
  Density rules: content pages must carry structured elements (data points /
  comparisons / steps / lists) in `content_summary`; page types must vary
  across the deck (KPI big-number, table, timeline, comparison, process — at
  least 2 kinds); `chart_hint` is optional and tolerated by outline
  validation.
- **Executor per page** (temp 0.3, max_tokens 16384):
  system = theme.style_md + condensed SVG rules (see below) + layout pattern
  catalog (~14 patterns: centered/left-text cover, toc grid, chapter
  divider, KPI big-number cards, card grids, image-text splits, comparison
  columns, table, timeline, process arrows, pyramid, quote, closing) +
  density floor (content pages ≥20 visual elements, no sparse
  "title + 3 lines" pages, data pages should draw native
  rect/polyline/circle charts, honoring `chart_hint`) + "output ONLY the
  SVG"; user = deck context + this page's outline JSON + available image
  filenames (if any) with `images/<file>` hrefs + user feedback when
  regenerating. Output: one `<svg viewBox="0 0 1280 720">…</svg>`.
- **Condensed SVG rules** (distilled from
  `skills/ppt-master/references/shared-standards.md` — backend hardcodes a
  ~40-line summary: 1280×720 viewBox, no external fonts/scripts, explicit
  font-family stack, text length discipline, no overflow beyond canvas,
  images via relative `images/…` href, flat shapes, legible contrast).
- **JSON repair**: strip think tags / code fences, normalize full-width
  quotes, drop trailing commas, balance brackets (port of MYGEM
  `llm_utils.repair_json`). On unrecoverable JSON the raw output is dumped
  to `<project>/debug/<stage>_raw_<timestamp>.txt` and the error message
  carries the first 200 chars.
- **Token metering**: every call records `usage` into `token_usage` and
  increments `users.token_used`; quota enforced before strategist and before
  each executor batch (`token_quota == 0` means unlimited).

## 7. REST API (all JSON unless noted; auth via Bearer except register/login)

### Auth
- `POST /api/auth/register` `{username, password}` → `{token, user}` (first user becomes admin; 409 if closed)
- `POST /api/auth/login` `{username, password}` → `{token, user}`
- `POST /api/auth/logout`
- `GET  /api/auth/me` → `{user, token_used, token_quota}`

### Themes
- `GET  /api/themes` → `[{id, key|name, builtin, category, description, palette, summary}]` (`category` = generic|brand|deck|layout)
- `POST /api/themes` `{name, style_md}` → theme (custom)
- `GET  /api/themes/{id}` → full incl. `style_md`

### Projects & pipeline
- `POST /api/projects` multipart: `files[]` (0..n) **or** form `topic` text;
  plus `title?`, `theme_id`, `slide_count` (default 10), `style_brief?`
  → creates project, runs ingest+strategist inline → `{project, outline}`
- `GET  /api/projects` → caller's projects (admin: all) with status/progress
- `GET  /api/projects/{id}` → detail incl. outline_json + per-page status
- `DELETE /api/projects/{id}`
- `PUT  /api/projects/{id}/outline` `{outline}` (validated vs schema) → saved, status→`confirmed`
- `POST /api/projects/{id}/generate` → starts background stages 4–6 (409 if already running / quota exceeded) → `{started: true}`
- `GET  /api/projects/{id}/status` → `{status, pages:[{n,status,error}], pptx_ready}`
- `POST /api/projects/{id}/pages/{n}/regenerate` `{feedback?}` → regenerates one page (inline, synchronous) → `{svg}` 
- `GET  /api/projects/{id}/pages/{n}/svg` → `image/svg+xml`
- `PUT  /api/projects/{id}/pages/{n}/svg` (raw SVG body) → save hand edit
- `POST /api/projects/{id}/export` → re-run svg_to_pptx → `{pptx_ready:true}`
- `GET  /api/projects/{id}/download` → `application/vnd…presentation` file
- `GET  /api/projects/{id}/images/{name}` → image file (for SVG preview rendering)

### Share links (public, no auth)
- `POST /api/projects/{id}/share` (owner) → idempotent `{"share_url": "/share/<token>"}` (`secrets.token_urlsafe(12)`)
- `DELETE /api/projects/{id}/share` (owner) → revoke (token set to NULL)
- `GET  /api/share/{token}` → `{"title", "page_count", "theme_name"}`; 404 when unknown/revoked
- `GET  /api/share/{token}/pages/{n}` → `image/svg+xml` with `images/…` hrefs rewritten to `/api/share/{token}/images/…`; 404 until the project has SVG output
- `GET  /api/share/{token}/images/{name}` → image file
- `GET  /share/{token}` → `app/frontend/share.html` (self-contained read-only viewer)

### Usage & admin
- `GET /api/usage` → caller's totals + per-project breakdown + recent records
- `GET /api/admin/users` / `PATCH /api/admin/users/{id}` `{token_quota?, disabled?, role?}` / `GET /api/admin/stats` (users, projects, tokens today/total) — admin only

### Admin settings (all admin only; resolution order in §3)
- `GET /api/admin/settings` → effective LLM + image-provider config.
  Secrets are never returned in full — only a tail:
  ```json
  {"llm_base_url":"https://...","llm_model":"qwen3.7-max",
   "llm_api_key_set":true,"llm_api_key_tail":"…a1b2","llm_api_key_source":"db|env|none",
   "pexels_api_key_set":true,"pexels_api_key_tail":"…c3d4","pexels_api_key_source":"db|env|none",
   "pixabay_api_key_set":false,"pixabay_api_key_tail":null,"pixabay_api_key_source":"none",
   "llm_base_url_source":"db|env","llm_model_source":"db|env",
   "image_provider":"auto|pexels|pixabay|openverse|wikimedia",
   "image_provider_source":"db|env|none",
   "mock_mode":false}
  ```
- `PUT /api/admin/settings` — body: any subset of `{"llm_base_url","llm_model","llm_api_key","pexels_api_key","pixabay_api_key","image_provider"}`.
  Non-empty string → stored as a DB override; empty string `""` → the DB
  override is deleted (falls back to env); omitted fields are untouched.
  Returns the same shape as GET.
- `POST /api/admin/settings/test-llm` → minimal chat completion
  (`max_tokens` 16, `"ping"`) against the effective config →
  `{"ok":true,"latency_ms":123,"model":"..."}` or
  `{"ok":false,"error":"..."}` (always HTTP 200). Mock mode (no key) →
  `{"ok":false,"error":"mock mode: no api key"}`.

### Frontend serving
- `GET /` → `app/frontend/index.html`; static assets under `/static/*`.
  SVG preview pages must rewrite relative `images/…` hrefs to
  `/api/projects/{id}/images/…` when serving (backend does the rewrite on GET svg).

## 8. Concurrency & limits (v1)

- asyncio; page generation bounded by `asyncio.Semaphore(PPTSAAS_MAX_CONCURRENT_PAGES)` per project;
  global `generate` tasks bounded by `PPTSAAS_MAX_ACTIVE_PROJECTS` (extra requests get 409 with message).
- LLM calls via `openai.AsyncOpenAI`; fallback models tried in order on
  5xx/timeout (max 3 attempts), 600s timeout.
- Upload cap 50 MB/file, 10 files.

## 9. Packaging (target deliverables documented, scripts provided)

- `.github/workflows/build-pptsaas.yml`: tag (`v*`) / manual builds, matrix
  ubuntu (Docker) + windows; both jobs smoke-test the artifact (HTTP 200 +
  register + themes) before upload; tag builds publish a GitHub Release.
- Linux: `app/packaging/Dockerfile.linux-build` (wrapped by
  `build_linux.sh`) — pip deps → PyInstaller one-dir (spec
  `app/packaging/pptsaas.spec`, entry `app/backend/run.py`, datas embed
  `app/frontend` + `skills/ppt-master/{scripts,templates}`) → assemble with
  the build container's CPython 3.12 (`/usr/local`) as the embedded runtime →
  `pptsaas-linux-x86_64.tar.gz` (+ AppImage when appimagetool downloads).
- Windows: `app/packaging/build_windows.ps1` (must run on Windows) — same
  one-dir build + python-build-standalone embedded runtime →
  `pptsaas-windows-x86_64.zip` with `start.bat`.
- Embedded Python is required because the backend shells out to the
  skills/ppt-master scripts; launchers export `PPTSAAS_PYTHON` (and
  `LD_LIBRARY_PATH` on Linux) so `pipeline.run_script` uses the bundled
  interpreter on machines without Python.
- Model is **not** embedded; point `PPTSAAS_LLM_BASE_URL` at a co-located
  local server (Ollama/llama.cpp/vLLM) or a cloud endpoint. Manual documents
  both.

## 10. Out of scope (v1)

AI text-to-image generation (no capability yet — web image search only),
web research expansion for topic-only decks, collaborative editing, billing.
