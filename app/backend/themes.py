#!/usr/bin/env python3
"""
PPT Master SaaS - Builtin theme seeds

Five hand-written generic themes plus themes scanned from the PPT Master
skill's template assets — brand design_spec files, deck (full-organization)
styles, and layout (structure-only) styles — all seeded at startup
(idempotent, keyed by name). Each theme is a ``style_md`` block injected
verbatim into the executor system prompt; ``category`` marks its origin
(generic|brand|deck|layout). ``MOCK_COLORS`` gives the mock executor a
palette per theme so the no-LLM pipeline still renders on-theme SVGs.

See docs/saas/ARCHITECTURE.md §5.

Dependencies:
    None (only uses standard library)
"""

import json
import re
from pathlib import Path
from typing import Optional

_FONT_STACK = "PingFang SC, Microsoft YaHei, Noto Sans CJK SC, Source Han Sans SC, sans-serif"

_BUSINESS_BLUE = f"""# 主题：商务蓝（business-blue）

清爽 SaaS 商务风，浅色背景，蓝色主调，专业克制。

## 配色
- 背景：#F5F8FC（浅蓝灰）
- 主色：#1B6AC9（商务蓝，用于标题、强调、关键数据）
- 辅色：#0E3A6E（深蓝，用于大标题或深色卡片）
- 点缀：#4FB3F6（浅蓝，用于图标、分割线、次级强调）
- 正文：#2B3445；次要文字：#6B7A90
- 卡片底：#FFFFFF，卡片边线：#DCE6F2

## 字体
- font-family: "{_FONT_STACK}"
- 页面标题 34-40px 加粗，主色或深蓝；正文 18-22px；注释/来源 14-16px 次要色

## 版式规则
- 顶部或左上角放置 6-8px 高的主色装饰条；标题下方一条 60×4px 主色短线
- 内容以白色圆角卡片（rx=12）承载，卡片 1px 浅蓝描边，不用阴影
- 关键数据用大号主色数字（48-64px）+ 小号说明文字
- Do：大量留白、左对齐、网格统一；Don't：渐变背景、深色整页、超过 3 种彩色
"""

_TECH_DARK = f"""# 主题：科技暗色（tech-dark）

深色科技风，暗底 + 霓虹点缀，适合 AI / 前沿技术议题。

## 配色
- 背景：#0B1220（深海军蓝黑）
- 主色：#22D3EE（青蓝霓虹，用于强调、数据、图标）
- 辅色：#7C8CF8（蓝紫，次级强调）
- 正文：#E5ECF5；次要文字：#8DA0BC
- 卡片底：#131D33，卡片边线：#24334F

## 字体
- font-family: "{_FONT_STACK}"
- 页面标题 34-40px 加粗白色；强调数字 48-64px 主色；正文 18-22px

## 版式规则
- 标题左侧 6px 宽主色竖条；分割线用 1px #24334F
- 卡片用深色底 + 1px 边线，可用主色 8%-12% 透明度做高亮块
- 允许极少量线性渐变（深蓝→深青）用于封面背景，其余页面纯平
- Do：高对比、克制的霓虹点缀；Don't：纯白大面积块、暖色、阴影堆叠
"""

_CONSULT_RED = f"""# 主题：咨询红（consult-red）

咨询报告风，红色标题 + 浅色底，中式商务审美，信息密度高。

## 配色
- 背景：#FAFAF7（暖白）
- 主色：#C00000（正红，仅用于标题、关键强调）
- 辅色：#003366（藏青，用于正文标题、数据）
- 点缀：#D4A843（哑金，用于分割线、序号、次级强调）
- 正文：#2A2A2A；次要文字：#7A7A72
- 卡片底：#FFFFFF，卡片边线：#E5E1D8

## 字体
- font-family: "{_FONT_STACK}"
- 页面标题 32-38px 加粗正红；正文 18-22px；来源注释 14px 次要色

## 版式规则
- 页面顶部一条 4px 正红细线贯穿；标题下一短条（50×4px）哑金或藏青
- 卡片左侧 5px 彩色竖条（红/金/藏青轮换），直角或小圆角（rx≤6），扁平无阴影
- 三色协奏：红做标题、藏青做数据、哑金做点缀，单页不超此三色
- Do：严谨网格、序号列表、来源标注；Don't：红底大面积铺色、圆角过大、花哨图标
"""

_FRESH_GREEN = f"""# 主题：护眼绿（fresh-green）

柔和护眼的浅绿风，适合教育、健康、可持续发展议题。

## 配色
- 背景：#F4F9F4（极浅绿白）
- 主色：#2E8B57（海绿，用于标题、强调）
- 辅色：#1F5C3D（深绿，用于大标题、深色卡片）
- 点缀：#8FCDA9（浅绿，用于图标、分隔、进度条）
- 正文：#2C3A33；次要文字：#6E837A
- 卡片底：#FFFFFF，卡片边线：#D9EADF

## 字体
- font-family: "{_FONT_STACK}"
- 页面标题 34-40px 加粗主色；正文 18-22px；注释 14-16px 次要色

## 版式规则
- 左上角主色小圆点或短竖条 + 标题组合；标题下 60×4px 浅绿短线
- 白色圆角卡片（rx=14）+ 1px 浅绿描边，无阴影
- 数据可视化优先用主色/点缀绿两档，避免引入第三个彩色
- Do：圆润亲和、留白充足；Don't：荧光绿、深绿整页、红橙撞色
"""

_MINIMAL_WHITE = f"""# 主题：极简白（minimal-white）

近白极简风，单一强调色，杂志式大留白。

## 配色
- 背景：#FCFCFC（近白）
- 主色：#111111（近黑，标题与正文主体）
- 强调色：#E4572E（单一橙红强调，仅用于关键数字、标记、一处装饰）
- 次要文字：#8A8A8A
- 卡片底：#FFFFFF，卡片边线：#ECECEC

## 字体
- font-family: "{_FONT_STACK}"
- 页面标题 36-44px 加粗近黑；正文 18-22px；注释 14px 次要色

## 版式规则
- 无顶栏无色块装饰；靠字重、字号、留白建立层级
- 强调色每页至多出现 3 处；分割线 1px #ECECEC
- 卡片仅白底 + 细边线，无阴影无圆角（rx=0）
- Do：大字号对比、严格左对齐网格；Don't：多彩、渐变、装饰性图形堆砌
"""

BUILTIN_THEMES: list[dict[str, str]] = [
    {"name": "商务蓝", "style_md": _BUSINESS_BLUE},
    {"name": "科技暗色", "style_md": _TECH_DARK},
    {"name": "咨询红", "style_md": _CONSULT_RED},
    {"name": "护眼绿", "style_md": _FRESH_GREEN},
    {"name": "极简白", "style_md": _MINIMAL_WHITE},
]

# Palette per builtin theme name, used by the mock executor (llm.py).
MOCK_COLORS: dict[str, dict[str, str]] = {
    "商务蓝": {"bg": "#F5F8FC", "accent": "#1B6AC9", "deep": "#0E3A6E",
               "text": "#2B3445", "muted": "#6B7A90", "card": "#FFFFFF"},
    "科技暗色": {"bg": "#0B1220", "accent": "#22D3EE", "deep": "#131D33",
                 "text": "#E5ECF5", "muted": "#8DA0BC", "card": "#131D33"},
    "咨询红": {"bg": "#FAFAF7", "accent": "#C00000", "deep": "#003366",
               "text": "#2A2A2A", "muted": "#7A7A72", "card": "#FFFFFF"},
    "护眼绿": {"bg": "#F4F9F4", "accent": "#2E8B57", "deep": "#1F5C3D",
               "text": "#2C3A33", "muted": "#6E837A", "card": "#FFFFFF"},
    "极简白": {"bg": "#FCFCFC", "accent": "#E4572E", "deep": "#111111",
               "text": "#111111", "muted": "#8A8A8A", "card": "#FFFFFF"},
}

DEFAULT_MOCK_COLORS = MOCK_COLORS["商务蓝"]


# ---------------------------------------------------------------------------
# Brand themes from the skill's design_spec files
# ---------------------------------------------------------------------------

# (design_spec path relative to skill_dir/templates, friendly theme name)
BRAND_THEME_FILES: list[tuple[str, str]] = [
    ("brands/anthropic/design_spec.md", "Anthropic"),
    ("brands/doubao/design_spec.md", "豆包风格"),
    ("brands/google/design_spec.md", "Google"),
    ("brands/huawei/design_spec.md", "华为品牌"),
    ("brand-doubao-huawei/design_spec.md", "豆包×华为红"),
]

# Chinese one-liners shown on the style-picker card; the frontmatter
# ``summary`` in the spec files is English, which reads oddly in a Chinese UI.
BRAND_THEME_DESCRIPTIONS: dict[str, str] = {
    "Anthropic": "Anthropic 品牌风 —— 暖橙强调色 + 编辑级排版，适合 AI/技术分享与产品发布。",
    "豆包风格": "豆包品牌风 —— 现代明快、卡片式版式，青绿 + 蓝 + 暖金多色协奏。",
    "Google": "Google 品牌风 —— 四色体系、简洁友好，适合教育培训与开发者议题。",
    "华为品牌": "华为品牌风 —— 华为红主色 + 深蓝辅色，正式稳重的企业汇报气质。",
    "豆包×华为红": "豆包风格 × 华为红 —— 浅色底 + 华为红标题 + 三色协奏，高信息密度的中式商务风。",
}

# ---------------------------------------------------------------------------
# Deck themes (kind=deck, full organization styles) and layout themes
# (kind=layout, structure-only) scanned from the skill's template indexes.
# ---------------------------------------------------------------------------

# Chinese one-liners for deck themes; decks_index.json summaries are English
# for most entries. Keyed by the friendly Chinese name (= index id).
DECK_THEME_DESCRIPTIONS: dict[str, str] = {
    "中国电信": "中国电信机构风 —— 电信红主色，适合政企数字化方案、转型规划与内部汇报。",
    "中国电建": "中国电建工程风 —— 工程蓝主色，适合工程项目报告、技术方案与年度总结。",
    "中汽研": "中汽研检测认证风 —— 深蓝主色，适合产品认证展示、测评汇报与技术推介。",
    "招商银行": "招商银行品牌风 —— 招行红主色，适合交易银行方案汇报、客户案例拆解与分行培训。",
    "重庆大学": "重庆大学学术风 —— 重大蓝主色，适合学术答辩、科研报告与教学演示。",
}

# layouts/<id>/ → friendly Chinese theme name.
LAYOUT_THEME_NAMES: dict[str, str] = {
    "academic_defense": "学术答辩",
    "ai_ops": "电信AI运维",
    "government_blue": "政务蓝",
    "government_red": "政务红",
    "medical_university": "医学院",
    "pixel_retro": "像素复古",
    "psychology_attachment": "心理学",
}

# Chinese one-liners for layout themes; layouts_index.json summaries are English.
LAYOUT_THEME_DESCRIPTIONS: dict[str, str] = {
    "academic_defense": "学术答辩版式 —— 论文答辩、学术汇报、研究进展与基金申请结构。",
    "ai_ops": "电信AI运维版式 —— 运维架构、IT 系统总览、数字化转型方案结构。",
    "government_blue": "政务蓝版式 —— 重点项目汇报、五年规划、工作总结与政策解读结构。",
    "government_red": "政务红版式 —— 政府简报、政策解读、工作总结与项目推介结构。",
    "medical_university": "医学院版式 —— 医学学术报告、病例讨论、医院工作报告与教学培训结构。",
    "pixel_retro": "像素复古版式 —— 技术分享、编程教程、游戏介绍与极客风展示结构。",
    "psychology_attachment": "心理学版式 —— 心理治疗培训、学术讲座、咨询案例分析与专业分享结构。",
}

# Appended to structure-only layout specs: they carry no color/font rules.
_LAYOUT_COLOR_NOTE = "配色与字体由你按主题气质自由设计，保持全 deck 统一。"


def _read_index(skill_dir: Path, kind: str) -> dict:
    """Parse templates/<kind>s/<kind>s_index.json; {} when missing/invalid."""
    index_path = skill_dir / "templates" / f"{kind}s" / f"{kind}s_index.json"
    if not index_path.is_file():
        return {}
    try:
        data = json.loads(index_path.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return {}
    return data if isinstance(data, dict) else {}


def load_deck_themes(skill_dir: Optional[Path]) -> list[dict[str, str]]:
    """Scan decks/decks_index.json → one theme per deck directory.

    style_md = the deck's design_spec.md; palette = the index's
    primary_color followed by hex colors found in the spec.
    """
    if not skill_dir:
        return []
    themes = []
    for deck_id, meta in _read_index(skill_dir, "deck").items():
        spec_path = skill_dir / "templates" / "decks" / deck_id / "design_spec.md"
        if not spec_path.is_file():
            continue
        style_md = spec_path.read_text(encoding="utf-8")
        primary = str((meta or {}).get("primary_color") or "").upper()
        palette = extract_palette(style_md)
        if _HEX_RE.fullmatch(primary) and primary not in palette:
            palette.insert(0, primary)
        name = deck_id  # index ids are already friendly Chinese names
        themes.append({
            "name": name,
            "style_md": style_md,
            "description": (DECK_THEME_DESCRIPTIONS.get(name)
                            or str((meta or {}).get("summary") or "")),
            "palette": json.dumps(palette[:5], ensure_ascii=False),
            "category": "deck",
        })
    return themes


def load_layout_themes(skill_dir: Optional[Path]) -> list[dict[str, str]]:
    """Scan layouts/layouts_index.json → one theme per layout directory.

    Layouts are structure-only (no color spec), so a note is appended
    telling the executor to design a consistent palette itself; palette is
    whatever hex colors the spec happens to mention (often none).
    """
    if not skill_dir:
        return []
    themes = []
    for layout_id, meta in _read_index(skill_dir, "layout").items():
        spec_path = (skill_dir / "templates" / "layouts" / layout_id
                     / "design_spec.md")
        if not spec_path.is_file():
            continue
        style_md = (spec_path.read_text(encoding="utf-8").rstrip()
                    + "\n\n" + _LAYOUT_COLOR_NOTE + "\n")
        themes.append({
            "name": LAYOUT_THEME_NAMES.get(layout_id, layout_id),
            "style_md": style_md,
            "description": (LAYOUT_THEME_DESCRIPTIONS.get(layout_id)
                            or str((meta or {}).get("summary") or "")),
            "palette": json.dumps(extract_palette(style_md),
                                  ensure_ascii=False),
            "category": "layout",
        })
    return themes

_HEX_RE = re.compile(r"#[0-9A-Fa-f]{6}\b")


def extract_palette(text: str, limit: int = 5) -> list[str]:
    """First ``limit`` unique #RRGGBB values found in ``text`` (uppercased)."""
    palette: list[str] = []
    for match in _HEX_RE.finditer(text or ""):
        color = match.group(0).upper()
        if color not in palette:
            palette.append(color)
        if len(palette) >= limit:
            break
    return palette


def _frontmatter_value(text: str, keys: tuple[str, ...]) -> str:
    """First non-empty ``key: value`` among ``keys`` in the YAML frontmatter."""
    if not text.startswith("---"):
        return ""
    end = text.find("\n---", 3)
    if end < 0:
        return ""
    for line in text[3:end].splitlines():
        key, sep, value = line.partition(":")
        if sep and key.strip() in keys and value.strip():
            return value.strip().strip('"').strip("'")
    return ""


def _first_heading(text: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip()
    return ""


def _first_paragraph(text: str) -> str:
    """First non-empty, non-heading, non-frontmatter line (the vibe line)."""
    for line in text.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith(("#", "---")):
            return stripped
    return ""


def load_brand_themes(skill_dir: Optional[Path]) -> list[dict[str, str]]:
    """Read brand design_spec files into theme dicts; skips missing files.

    description comes from the frontmatter ``summary``/``description``
    field, falling back to the first Markdown heading.
    """
    if not skill_dir:
        return []
    themes = []
    for rel_path, name in BRAND_THEME_FILES:
        spec_path = skill_dir / "templates" / rel_path
        if not spec_path.is_file():
            continue
        style_md = spec_path.read_text(encoding="utf-8")
        description = (BRAND_THEME_DESCRIPTIONS.get(name)
                       or _frontmatter_value(style_md, ("summary", "description"))
                       or _first_heading(style_md))
        themes.append({
            "name": name,
            "style_md": style_md,
            "description": description,
            "palette": json.dumps(extract_palette(style_md),
                                  ensure_ascii=False),
            "category": "brand",
        })
    return themes


def seed_builtin_themes(db, skill_dir: Optional[Path] = None) -> None:
    """Insert builtin themes if not already present (idempotent by name)."""
    from .db import utcnow

    themes = [
        {
            "name": theme["name"],
            "style_md": theme["style_md"],
            "description": _first_paragraph(theme["style_md"]),
            "palette": json.dumps(extract_palette(theme["style_md"]),
                                  ensure_ascii=False),
            "category": "generic",
        }
        for theme in BUILTIN_THEMES
    ] + load_brand_themes(skill_dir) + load_deck_themes(skill_dir) \
        + load_layout_themes(skill_dir)

    for theme in themes:
        existing = db.query_one(
            "SELECT id FROM themes WHERE builtin = 1 AND name = ?", (theme["name"],)
        )
        if existing:
            db.execute(
                "UPDATE themes SET style_md = ?, description = ?, palette = ?,"
                " category = ? WHERE id = ?",
                (theme["style_md"], theme["description"], theme["palette"],
                 theme["category"], existing["id"]),
            )
        else:
            db.execute(
                "INSERT INTO themes(name, builtin, owner_id, style_md,"
                " description, palette, category, created_at)"
                " VALUES (?, 1, NULL, ?, ?, ?, ?, ?)",
                (theme["name"], theme["style_md"], theme["description"],
                 theme["palette"], theme["category"], utcnow()),
            )
