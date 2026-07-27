# PPT Master Agent

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Release](https://img.shields.io/github/v/release/jamespang375-byte/ppt-master?include_prereleases&color=blue)](https://github.com/jamespang375-byte/ppt-master/releases)
[![CI](https://img.shields.io/github/actions/workflow/status/jamespang375-byte/ppt-master/build-pptsaas.yml?label=build)](https://github.com/jamespang375-byte/ppt-master/actions)

English | [中文](./README_CN.md)

**Upload a document or paste a brief — get a natively editable PowerPoint, from your browser, on your own machine.**
PPT Master Agent is a self-hostable web app: no IDE, no prompt engineering, no platform lock-in. Every element of the exported `.pptx` is a real PowerPoint shape you can edit.

[⬇ Download (Windows / Linux)](https://github.com/jamespang375-byte/ppt-master/releases) · [🎬 Demo video (5:45)](docs/saas/demo/ppt-master-agent-demo.mp4) · [Quickstart](app/README.md) · [中文手册](docs/zh/saas/)

---

## What is this

This repository was forked from the excellent [PPT Master](https://github.com/hugohe3/ppt-master) — an AI-IDE *skill* that generates decks inside Claude Code / Cursor. We rebuilt that skill into a **product**:

- **From skill to app** — the original workflow requires an AI IDE and prompt-driving. The Agent wraps the same proven pipeline (outline → per-page SVG → native PPTX) in a fixed, guided web flow anyone can use.
- **Lowered barrier** — one package with an embedded Python runtime; model runs against any OpenAI-compatible endpoint (DeepSeek / GLM / Qwen / local Ollama); a built-in mock mode demos the full flow with zero keys.
- **Battle-tested ideas from MYGEM** — our sister project's PPT Agent contributed the fixed-pipeline design, small-model-friendly JSON contracts, Pexels/Wikimedia image acquisition, and per-page regeneration.

## Features

- **Two ways in** — upload Markdown / Word / PDF / PPTX, or paste a long brief (up to ~100k characters). The outline is grounded in your material, not hallucinated.
- **22 visual themes** — 5 brand specs (Anthropic / Doubao / Google / Huawei / Doubao×Huawei-red), 5 institutional decks (China Telecom, CMB, CATARC…), 7 layout styles, 5 generic — grouped in a visual picker. Density is enforced: ≥20 visual elements per content page, native SVG charts.
- **Confirm before generate** — edit the outline (title, key message, per-page content, image queries, layout hints), switch theme, then generate.
- **Online preview & editing** — click text on a slide to edit it inline, regenerate any page with feedback, raw-SVG mode, go back to any step.
- **Share links** — one click creates a login-free, read-only flip-through link for a deck (revocable).
- **SaaS essentials** — multi-user registration (first user = admin), per-user LLM token quotas and metering, admin console, settings UI for model endpoint and image-search keys (masked, hot-swappable), embedded "how to get an API key" guides.
- **Smart image acquisition** — Pexels / Pixabay / Wikimedia / Openverse, concurrent batch download with license provenance; each page's assigned photo is embedded by contract.
- **Real deliverable** — export via the original `skills/ppt-master` converter: native DrawingML shapes, editable text, images, charts.

## Quickstart

**Option A — download a package** (Windows zip / Linux AppImage): unzip, run, open `http://localhost:8310`. First registered user becomes admin.

**Option B — from source**:

```bash
pip install -r app/backend/requirements.txt -r requirements.txt
python3 app/backend/run.py        # → http://localhost:8310 (mock demo mode)
```

Then configure a model in **Settings** (admin) or `.env`:

```bash
PPTSAAS_LLM_BASE_URL=https://api.deepseek.com/v1
PPTSAAS_LLM_API_KEY=sk-xxx
PPTSAAS_LLM_MODEL=deepseek-chat
PEXELS_API_KEY=your-pexels-key    # optional, web images
```

## Docs

- [Architecture & API contract](docs/saas/ARCHITECTURE.md)
- [中文手册：部署](docs/zh/saas/DEPLOYMENT.md) · [运维](docs/zh/saas/OPERATIONS.md) · [规格与容量规划](docs/zh/saas/SPEC.md) · [API 获取指南](docs/zh/saas/API_KEYS.md)
- [App quickstart](app/README.md)

## The original skill

The upstream PPT Master skill still lives in [`skills/ppt-master/`](skills/ppt-master/SKILL.md) and works exactly as before inside AI IDEs — the Agent reuses its converters and template assets rather than replacing them. Original user docs: [docs/](docs/), upstream: [hugohe3/ppt-master](https://github.com/hugohe3/ppt-master).

## License

MIT, same as upstream. Sponsor credits for the upstream project: see [original README history](https://github.com/hugohe3/ppt-master).
