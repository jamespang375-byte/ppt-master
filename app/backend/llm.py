#!/usr/bin/env python3
"""
PPT Master SaaS - LLM client, JSON repair, metering, mock mode

OpenAI-compatible async client with a fallback model chain (5xx/timeout
retries, max 3 attempts), token metering into token_usage, and a
deterministic mock mode used when PPTSAAS_LLM_API_KEY is empty so the
full pipeline runs without a key.

See docs/saas/ARCHITECTURE.md §6.

Dependencies:
    openai
"""

import json
import re
from typing import Any, Optional
from xml.sax.saxutils import escape

from .config import Settings, resolve
from .db import Database, utcnow
from .themes import DEFAULT_MOCK_COLORS, MOCK_COLORS

_FULLWIDTH_QUOTES = str.maketrans({
    "“": '"', "”": '"', "„": '"', "‟": '"',
    "‘": "'", "’": "'", "‚": "'", "‛": "'",
    "：": ":", "，": ",",
})
_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)
_FENCE_RE = re.compile(r"```(?:json|svg|xml)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)


def repair_json(raw: str) -> str:
    """Repair common LLM JSON defects and return a parseable JSON string.

    Strips think tags / code fences, normalizes full-width quotes, drops
    trailing commas, truncates to the outermost balanced object. Raises
    ValueError if no balanced object can be recovered.
    """
    text = _THINK_RE.sub("", raw or "").strip()
    fence = _FENCE_RE.search(text)
    if fence and fence.group(1).strip().startswith(("{", "[")):
        text = fence.group(1).strip()
    start = text.find("{")
    if start < 0:
        raise ValueError("no JSON object found in LLM output")
    text = text[start:]
    # Balance brackets, tracking string state so braces inside strings
    # do not count.
    depth = 0
    in_str = False
    escaped = False
    end = -1
    for idx, ch in enumerate(text):
        if in_str:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                end = idx
                break
    text = text[:end + 1] if end >= 0 else text
    # Try strict parse first — repair passes below corrupt valid JSON whose
    # string values contain full-width punctuation (common in Chinese decks).
    try:
        json.loads(text)
        return text
    except json.JSONDecodeError:
        pass
    text = re.sub(r",\s*([}\]])", r"\1", text)
    try:
        json.loads(text)
        return text
    except json.JSONDecodeError:
        pass
    # Last resort: normalize full-width quotes/punctuation (also rewrites
    # punctuation inside string values, so it must stay the final attempt).
    text = text.translate(_FULLWIDTH_QUOTES)
    try:
        json.loads(text)
        return text
    except json.JSONDecodeError:
        pass
    # Last resort: drop content after the last complete top-level value.
    if end >= 0:
        raise ValueError("unrecoverable JSON in LLM output")
    raise ValueError("unbalanced JSON in LLM output")


class LLMClient:
    """OpenAI-compatible async chat client with fallback chain + metering.

    The effective config is resolved per call (DB admin overrides win over
    env). The underlying AsyncOpenAI client is cached and rebuilt whenever
    (base_url, api_key, model) changes, so admin edits to the LLM settings
    apply to new requests without a server restart.
    """

    def __init__(self, settings: Settings, db: Database) -> None:
        self.base_settings = settings
        self.db = db
        self._client: Any = None
        self._client_key: Optional[tuple[str, str, str]] = None

    def effective_settings(self) -> Settings:
        """Current effective settings: DB overrides win over env."""
        return resolve(self.base_settings, self.db)

    @property
    def is_mock(self) -> bool:
        return self.effective_settings().mock_llm

    def _get_client(self, eff: Settings) -> Any:
        """Cached AsyncOpenAI, rebuilt when (base_url, api_key, model) changes."""
        from openai import AsyncOpenAI

        key = (eff.llm_base_url, eff.llm_api_key, eff.llm_model)
        if self._client is None or self._client_key != key:
            self._client = AsyncOpenAI(
                base_url=eff.llm_base_url,
                api_key=eff.llm_api_key,
                timeout=eff.llm_timeout,
                max_retries=0,
            )
            self._client_key = key
        return self._client

    def record_usage(self, user_id: int, project_id: Optional[str], stage: str,
                     model: str, prompt_tokens: int, completion_tokens: int) -> None:
        """Write a token_usage row and increment users.token_used."""
        total = prompt_tokens + completion_tokens
        self.db.execute(
            "INSERT INTO token_usage(user_id, project_id, stage, model,"
            " prompt_tokens, completion_tokens, total_tokens, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (user_id, project_id, stage, model, prompt_tokens,
             completion_tokens, total, utcnow()),
        )
        if total:
            self.db.execute(
                "UPDATE users SET token_used = token_used + ? WHERE id = ?",
                (total, user_id),
            )

    async def complete(self, *, user_id: int, project_id: Optional[str],
                       stage: str, system: str, user: str,
                       temperature: float, max_tokens: int) -> str:
        """One chat completion with fallback models; returns message content.

        Fallback chain: primary model, then PPTSAAS_LLM_MODEL_FALLBACKS in
        order, max 3 attempts total, only on 5xx / timeout / connection
        errors. Other API errors raise immediately.
        """
        from openai import APIConnectionError, APIStatusError

        eff = self.effective_settings()
        client = self._get_client(eff)
        models = [eff.llm_model] + eff.llm_model_fallbacks
        # Bailian compatible-mode only: kill the thinking phase so reasoning
        # tokens cannot eat max_tokens and truncate JSON (see config.py).
        extra_body = ({"enable_thinking": False}
                      if eff.disable_thinking_effective else None)
        last_error: Optional[Exception] = None
        for attempt in range(min(3, len(models))):
            model = models[attempt]
            try:
                resp = await client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    temperature=temperature,
                    max_tokens=max_tokens,
                    extra_body=extra_body,
                )
            except APIStatusError as exc:
                last_error = exc
                if exc.status_code >= 500 and attempt < min(3, len(models)) - 1:
                    continue
                raise
            except APIConnectionError as exc:
                last_error = exc
                if attempt < min(3, len(models)) - 1:
                    continue
                raise
            usage = getattr(resp, "usage", None)
            prompt_tokens = int(getattr(usage, "prompt_tokens", 0) or 0)
            completion_tokens = int(getattr(usage, "completion_tokens", 0) or 0)
            self.record_usage(user_id, project_id, stage, model,
                              prompt_tokens, completion_tokens)
            return resp.choices[0].message.content or ""
        raise RuntimeError(f"LLM call failed after retries: {last_error}")


# ---------------------------------------------------------------------------
# Mock mode: deterministic outline + SVG so the pipeline runs without a key.
# ---------------------------------------------------------------------------

_CONTENT_SEEDS = [
    ("行业现状与驱动力", "技术成熟度与市场需求形成共振，行业进入规模化落地前夜。"),
    ("关键技术突破", "核心指标持续跃升，成本曲线快速下探，工程化瓶颈逐步消解。"),
    ("典型应用场景", "头部场景率先验证商业价值，长尾场景呈现多点开花态势。"),
    ("竞争格局与生态", "产业链上下游加速整合，开放生态成为竞争分水岭。"),
    ("挑战与风险", "算力、数据、合规三重约束仍需系统性应对。"),
    ("趋势研判与建议", "未来两年是窗口期，建议以小步快跑的方式卡位布局。"),
]


def mock_outline(topic: str, title: str, slide_count: int,
                 style_brief: str) -> dict[str, Any]:
    """Deterministic sample outline for mock mode."""
    n = max(2, int(slide_count))
    deck_title = (title or topic or "未命名演示").strip()[:40]
    brief = (style_brief or "").strip()
    pages: list[dict[str, Any]] = []
    content_idx = 0
    for i in range(1, n + 1):
        if i == 1:
            pages.append({
                "page_number": 1,
                "title": deck_title,
                "key_message": f"{deck_title}——核心观点与行动建议",
                "content_summary": (
                    f"封面页。主题：{deck_title}。"
                    + (f"风格要求：{brief}。" if brief else "")
                    + "本演示围绕主题的背景、现状、关键趋势与行动建议展开，"
                      "面向决策者提供结构化的判断依据。"
                ),
                "visual_suggestion": "居中大标题 + 副标题 + 主题色装饰条",
                "image_query": "",
                "layout_hint": "cover",
                "bullets": [deck_title, "核心观点 · 数据支撑 · 行动建议"],
            })
        elif i == n:
            pages.append({
                "page_number": i,
                "title": "总结与展望",
                "key_message": "把握窗口期，小步快跑、持续迭代。",
                "content_summary": (
                    "结尾页。回顾全篇核心结论：行业处于关键窗口期，"
                    "建议从试点场景切入，建立数据与人才的长期壁垒，"
                    "以季度为节奏复盘进展并动态调整路线图。"
                ),
                "visual_suggestion": "结论要点 + 致谢语，简洁收尾",
                "image_query": "",
                "layout_hint": "closing",
                "bullets": ["核心结论回顾", "行动建议", "谢谢观看"],
            })
        elif i == 2 and n >= 4:
            toc_titles = [t for t, _ in _CONTENT_SEEDS][:max(2, n - 3)]
            pages.append({
                "page_number": i,
                "title": "目录",
                "key_message": "全篇结构一览",
                "content_summary": "目录页，列出本演示的章节结构："
                                   + "；".join(toc_titles) + "。",
                "visual_suggestion": "编号列表式目录",
                "image_query": "",
                "layout_hint": "toc",
                "bullets": toc_titles,
            })
        else:
            seed_title, seed_msg = _CONTENT_SEEDS[content_idx % len(_CONTENT_SEEDS)]
            content_idx += 1
            pages.append({
                "page_number": i,
                "title": seed_title,
                "key_message": seed_msg,
                "content_summary": (
                    f"{seed_title}。{seed_msg}"
                    "从市场规模、增速、渗透率三个维度看，相关指标均保持两位数增长；"
                    "供给侧技术成熟度持续提升，需求侧付费意愿显著增强；"
                    "政策与资本的双重加持进一步缩短了从试点到规模化的周期。"
                    "建议关注头部企业的实践路径，并警惕同质化竞争风险。"
                ),
                "visual_suggestion": "标题 + 要点列表 + 关键数据卡片",
                "image_query": "",
                "layout_hint": "content",
                "bullets": [
                    seed_msg,
                    "市场规模与增速保持两位数增长",
                    "供给侧与需求侧形成正向循环",
                    "政策与资本双轮驱动",
                    "警惕同质化竞争与合规风险",
                ],
            })
    return {"deck_title": deck_title, "pages": pages}


def _mock_bullets_svg(bullets: list[str], colors: dict[str, str],
                      x: int, y: int, width: int, line_h: int = 46,
                      max_items: int = 6, font_size: int = 20) -> str:
    parts = []
    for idx, bullet in enumerate(bullets[:max_items]):
        by = y + idx * line_h
        parts.append(
            f'<rect x="{x}" y="{by + 6}" width="10" height="10" fill="{colors["accent"]}"/>'
            f'<text x="{x + 24}" y="{by + 16}" font-size="{font_size}" '
            f'fill="{colors["text"]}" font-family="PingFang SC, Microsoft YaHei, '
            f'Noto Sans CJK SC, Source Han Sans SC, sans-serif">'
            f'{escape(str(bullet))[:38]}</text>'
        )
    return "".join(parts)


def mock_svg(deck_title: str, page: dict, theme_name: str) -> str:
    """Deterministic 1280×720 SVG for mock mode, themed by palette."""
    colors = MOCK_COLORS.get(theme_name, DEFAULT_MOCK_COLORS)
    font = ("PingFang SC, Microsoft YaHei, Noto Sans CJK SC, "
            "Source Han Sans SC, sans-serif")
    layout = str(page.get("layout_hint", "content"))
    title = escape(str(page.get("title", ""))[:24])
    message = escape(str(page.get("key_message", ""))[:42])
    bullets = page.get("bullets") or []
    page_no = int(page.get("page_number", 1))
    footer = (
        f'<text x="1200" y="696" font-size="14" text-anchor="end" '
        f'fill="{colors["muted"]}" font-family="{font}">{page_no:02d}</text>'
    )
    bg = f'<rect width="1280" height="720" fill="{colors["bg"]}"/>'

    if layout == "cover":
        body = (
            f'<rect x="0" y="0" width="1280" height="10" fill="{colors["accent"]}"/>'
            f'<rect x="560" y="330" width="160" height="6" fill="{colors["accent"]}"/>'
            f'<text x="640" y="300" font-size="56" font-weight="bold" text-anchor="middle" '
            f'fill="{colors["deep"]}" font-family="{font}">{title}</text>'
            f'<text x="640" y="380" font-size="24" text-anchor="middle" '
            f'fill="{colors["muted"]}" font-family="{font}">{message}</text>'
        )
    elif layout == "closing":
        body = (
            f'<rect x="0" y="0" width="1280" height="10" fill="{colors["accent"]}"/>'
            f'<text x="640" y="300" font-size="48" font-weight="bold" text-anchor="middle" '
            f'fill="{colors["deep"]}" font-family="{font}">{title}</text>'
            f'<text x="640" y="370" font-size="24" text-anchor="middle" '
            f'fill="{colors["accent"]}" font-family="{font}">谢谢观看</text>'
            f'<text x="640" y="420" font-size="20" text-anchor="middle" '
            f'fill="{colors["muted"]}" font-family="{font}">{message}</text>'
        )
    else:
        body = (
            f'<rect x="0" y="0" width="1280" height="6" fill="{colors["accent"]}"/>'
            f'<text x="80" y="96" font-size="36" font-weight="bold" '
            f'fill="{colors["deep"]}" font-family="{font}">{title}</text>'
            f'<rect x="80" y="116" width="60" height="4" fill="{colors["accent"]}"/>'
            f'<text x="80" y="164" font-size="20" fill="{colors["muted"]}" '
            f'font-family="{font}">{message}</text>'
            f'<rect x="80" y="196" width="1120" height="430" rx="12" '
            f'fill="{colors["card"]}" stroke="#DCE0E6" stroke-width="1"/>'
            + _mock_bullets_svg(bullets, colors, 120, 250, 1040)
        )
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 720" '
        'width="1280" height="720">'
        + bg + body + footer + "</svg>"
    )
