# PPT Master Agent

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Release](https://img.shields.io/github/v/release/jamespang375-byte/ppt-master?include_prereleases&color=blue)](https://github.com/jamespang375-byte/ppt-master/releases)
[![CI](https://img.shields.io/github/actions/workflow/status/jamespang375-byte/ppt-master/build-pptsaas.yml?label=build)](https://github.com/jamespang375-byte/ppt-master/actions)

English | [中文](./README_CN.md)

**Upload a document or paste a brief — get a natively editable PowerPoint, from your browser, on your own machine.**

[⬇ Download (Windows / Linux)](https://github.com/jamespang375-byte/ppt-master/releases) · [🎬 Demo video (5:45)](docs/saas/demo/ppt-master-agent-demo.mp4) · [Quickstart](app/README.md) · [中文手册](docs/zh/saas/)

---

## Why we rebuilt a Skill as an Agent

### The insight: skills, as executed today, have structural problems

Over the past year, both research and engineering practice have been asking
the same question: how should LLM skills be executed *reliably*? Work on
skill runtimes and execution efficiency — including SkillRT (Shanghai Jiao
Tong University, April 2026) — together with our own experience building
MYGEM (an internal deep-research and content-generation platform), led us to
the same observation:

**Letting an LLM free-wheel its way through a complex skill, step by step,
has three unavoidable problems:**

1. **Inefficiency** — at every step the model re-reasons "what should I do
   next", spending tokens on process decisions instead of content. To make
   one deck, the model re-reads specs, picks templates, invents layouts, and
   writes coordinates — all inside its context, over and over.
2. **Token waste** — long skill specifications (ours runs to thousands of
   lines) are re-injected into the context every round. The same constraints
   are read and reasoned over again and again; cost grows linearly, sometimes
   super-linearly, with page count.
3. **Instability** — free execution means free-form failure: drifting
   coordinates, overlapping elements, truncated JSON, broken exports. The
   same input fails in three different ways across ten runs. That is not
   something you can ship to non-technical users.

### The idea: Compiled Skill — collapse uncertainty to the few decisions that need it

Our answer is to **"compile" the skill into a fixed pipeline**: the way a
compiler lowers a high-level language into deterministic instructions, we
decompose skill execution into stages and keep the LLM only at the few
decision points where it is irreplaceable (understanding material, planning
the outline, authoring page content). Everything else — parsing, template
injection, image acquisition, quality checks, format conversion, export —
goes to deterministic code.

```
upload → [code] parse (source_to_md)
       → [LLM ] one call → outline JSON (strict contract + auto-repair)
       → [human] confirm/edit in the browser (a product, not a black box)
       → [code] concurrent image acquisition (Pexels/Wikimedia, license-aware)
       → [LLM ] per-page generation, concurrent (theme spec + layout catalog
                injected, hard density floor)
       → [code] quality check → native PPTX export (svg_to_pptx)
```

The payoff is measurable: DeepSeek-class small models produce solid decks
(no flagship model required); token usage is predictable, metered, and
quota-able per user; and failure collapses from "any step, at random" to
"two retryable LLM stages" — so a failed project can self-heal with one
click.

### The build: internal practice × great open source

We extracted the PPT Agent practice from MYGEM and forked the excellent
[PPT Master](https://github.com/hugohe3/ppt-master) skill — whose
SVG→native-PPTX converter, 22 brand/institution/layout template assets, and
document parsers are first-class — then **rewrote the whole pipeline** on
top of those assets, and packaged it as a single-box Windows / Linux
application: embedded Python runtime, multi-user with token quotas, a visual
settings UI, ready to run.

## Features

- **Two ways in** — upload Markdown / Word / PDF / PPTX, or paste a brief of
  up to ~100k characters. The outline is grounded in your material.
- **22 visual themes** — 5 brand specs (Anthropic / Doubao / Google / Huawei
  / Doubao×Huawei-red), 5 institutional decks (China Telecom, CMB, CATARC…),
  7 layouts, 5 generic. Hard density floor: ≥20 visual elements per content
  page, native SVG charts.
- **Confirm before generate** — edit every page of the outline (title, key
  message, summary, image query, layout hint), switch theme, then generate.
- **Online preview & editing** — click text on a slide to edit it inline,
  regenerate any page with feedback, raw-SVG mode, step back at any point.
- **Share links** — one click creates a login-free, read-only flip-through
  link for any deck (revocable).
- **SaaS essentials** — multi-user registration (first user = admin),
  per-user LLM token quotas and metering, admin console, settings UI for
  model and image-search keys (masked, hot-swappable), embedded API guides.
- **Smart image acquisition** — Pexels / Pixabay / Wikimedia / Openverse,
  concurrent batches, license provenance, per-page assigned photos embedded
  by contract.
- **Real deliverable** — native DrawingML export: text, images, and charts
  are all editable in PowerPoint.

## Quickstart

**Option A — package**: grab the Windows zip or Linux AppImage from
[Releases](https://github.com/jamespang375-byte/ppt-master/releases), run
it, open `http://localhost:8310`. The first registered user becomes admin.

**Option B — source**:

```bash
pip install -r app/backend/requirements.txt -r requirements.txt
python3 app/backend/run.py        # → http://localhost:8310 (mock demo mode)
```

Configure a model in the Settings page (admin) or `.env`:

```bash
PPTSAAS_LLM_BASE_URL=https://api.deepseek.com/v1
PPTSAAS_LLM_API_KEY=sk-xxx
PPTSAAS_LLM_MODEL=deepseek-chat
PEXELS_API_KEY=your-pexels-key    # optional, web images
```

## Docs

- [Architecture & API contract](docs/saas/ARCHITECTURE.md)
- 中文手册：[部署](docs/zh/saas/DEPLOYMENT.md) · [运维](docs/zh/saas/OPERATIONS.md) · [规格](docs/zh/saas/SPEC.md) · [API 获取](docs/zh/saas/API_KEYS.md)
- [App quickstart](app/README.md) · Original skill: [skills/ppt-master/](skills/ppt-master/SKILL.md)

## Acknowledgements

This project is a fork of [hugohe3/ppt-master](https://github.com/hugohe3/ppt-master).
Without its excellent converter, template assets, and its pioneering
"AI generates your deck — it doesn't fill in a template" philosophy, this
app would not exist. We rebuilt the pipeline and productized it on that
foundation, drawing on our internal practice.

**If you like this project, please support the original author, hugohe3** —
star his repo, or buy him a coffee ☕ through the sponsor channels in his
README (PackyCode / APIKEY.FUN / RunAPI / YouYun ZhiSuan):

- Upstream: https://github.com/hugohe3/ppt-master
- Upstream live demo: https://hugohe3.github.io/ppt-master/

## License

MIT, same as upstream.
