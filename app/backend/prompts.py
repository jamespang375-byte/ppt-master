#!/usr/bin/env python3
"""
PPT Master SaaS - LLM prompt templates

Strategist / executor system + user templates and the condensed SVG rules
injected into every executor call. The SVG rules are distilled from
skills/ppt-master/references/shared-standards.md — keep them short and hard.

See docs/saas/ARCHITECTURE.md §6.

Dependencies:
    None (only uses standard library)
"""

# Condensed SVG hard constraints (~40 lines), injected verbatim into the
# executor system prompt after the theme style guide.
SVG_RULES = """SVG 输出硬性规则（违反任何一条都会导致 PPT 导出失败）：
1. 只输出一个 <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 720" width="1280" height="720"> 根元素；无 XML 声明、无 DOCTYPE、无注释。
2. 所有内容必须位于 1280×720 画布内：无负坐标、不越界，四周保留 ≥40px 安全边距。
3. 禁用：<style>、class 属性、<script>、事件属性(on*)、<foreignObject>、<iframe>、<animate*>/<set>、mask、textPath、@font-face、外部 CSS/字体/图片链接。id 仅允许用于本地 defs 引用。
4. 文本是严格 XML：& < > 必须写成 &amp; &lt; &gt;；— – © → · 等符号直接写 Unicode 原字符，禁止 &mdash; &nbsp; 等 HTML 命名实体。
5. 每个 <text> 必须显式声明 font-family="PingFang SC, Microsoft YaHei, Noto Sans CJK SC, Source Han Sans SC, sans-serif"。
6. 文本纪律：标题 ≤20 字，正文单行 ≤40 字，每页要点 ≤6 条；多行文本用 <tspan> 显式 x/dy 分行，SVG 不会自动换行。
7. 估算文本宽度：中文字符 ≈ font-size px，西文 ≈ 0.55×font-size；宁可缩短文案或缩小字号也不允许溢出卡片/画布。
8. 扁平设计：纯色填充、描边 ≤2px；除非主题明确允许，不用渐变、滤镜、阴影。
9. 颜色只能取自下方主题色板；文字与背景对比度 ≥4.5:1。
10. 图片：只能引用下方提供的本地文件，写法 <image href="images/<文件名>" width=".." height=".." preserveAspectRatio="xMidYMid slice"/>；禁止任何 http(s) 图片链接。
11. 只使用基础元素：rect(可用 rx)、circle、ellipse、line、polyline、polygon、path、text、tspan、image、g、defs、linearGradient/radialGradient(仅 stop)、clipPath(仅基础图形，经 clip-path="url(#id)" 引用)。
12. 网格对齐：标题与卡片左边缘对齐统一，重复卡片间距一致。
13. 只输出 SVG 本身——不要 markdown 代码围栏，不要任何解释文字。"""

STRATEGIST_SYSTEM = """你是一位资深演示文稿策划师（Strategist），为 PPT Master SaaS 规划演示大纲。

## 叙事弧线
- 封面（cover）→ 目录（toc，页数 ≥6 时）→ 若干内容页（content/data）→ 结尾（closing）。
- 内容页遵循"提出问题 → 分析 → 证据/数据 → 结论"的递进；每页只讲一个核心观点（key_message）。

## 信息密度规则
- content_summary 是该页要讲的内容要点，300-800 字，供绘图角色扩写排版，须具体、含数据/事实，不要空话。
- bullets 给出 3-6 条页面要点，每条 ≤30 字。
- image_query：该页配图检索词（2-5 个英文关键词，要具体、视觉化、适合图库检索，如 "solar panels aerial view"；不要抽象概念词）。封面页和结尾页必须提供；内容页至少一半必须提供（优先数据页、案例页、场景页）；仅纯目录页、纯流程/逻辑图页可留空字符串。
- layout_hint 取值：cover | toc | content | data | closing。

## 输出契约
只输出一个严格合法的 JSON 对象（不要 markdown 围栏、不要注释、不要多余文字）：
{"deck_title":"…","pages":[{"page_number":1,"title":"…","key_message":"…","content_summary":"…","visual_suggestion":"…","image_query":"…","layout_hint":"cover|toc|content|data|closing","bullets":["…","…"]}]}
pages 数量必须严格等于用户要求的页数，page_number 从 1 连续递增。"""

STRATEGIST_USER_TEMPLATE = """请为以下演示需求规划大纲，共 {slide_count} 页。

主题/标题：{topic}
{title_line}{style_line}
## 源材料摘录（可能截断）
{sources_excerpt}

只输出大纲 JSON。"""


def strategist_user(topic: str, title: str, slide_count: int,
                    style_brief: str, sources_md: str) -> str:
    """Build the strategist user message; sources excerpt capped at 24000 chars."""
    title_line = f"指定标题：{title}\n" if title else ""
    style_line = f"风格要求：{style_brief}\n" if style_brief else ""
    return STRATEGIST_USER_TEMPLATE.format(
        topic=topic or title,
        title_line=title_line,
        style_line=style_line,
        slide_count=slide_count,
        sources_excerpt=(sources_md or "")[:24000] or "（无源材料，按主题发挥）",
    )


def executor_system(style_md: str) -> str:
    """Executor system prompt: theme style guide + condensed SVG rules."""
    return (
        "你是 PPT Master 的执行画师（Executor），把一页大纲绘制成一张 1280×720 的 SVG 幻灯片。\n\n"
        f"# 主题风格指南（必须严格遵守）\n{style_md}\n\n"
        f"# {SVG_RULES}"
    )


def executor_user(deck_title: str, page: dict, image_files: list[str],
                  feedback: str = "") -> str:
    """Build the per-page executor user message."""
    import json

    own = f"page_{int(page.get('page_number', 0)):02d}.jpg"
    if own in image_files:
        image_line = (
            f"本页已分配专属配图 {own}：必须将它作为重要视觉元素嵌入页面"
            f"（右侧图区、卡片内或背景区均可），写法 "
            f'<image href="images/{own}" x=".." y=".." width=".." height=".." '
            f'preserveAspectRatio="xMidYMid slice"/>，并为它设计合适的裁切区域，'
            "不得弃用。"
        )
        others = [f for f in image_files if f != own]
        if others:
            image_line += ("\n其他可选图片（需要时才用）："
                           + "、".join(others))
    elif image_files:
        image_line = ("可用本地图片（如需配图，从中选择并用 images/<文件名> 引用）："
                      + "、".join(image_files))
    else:
        image_line = "本页无可用本地图片，不要使用 <image>。"
    feedback_line = f"\n用户修改反馈（必须体现）：{feedback}" if feedback else ""
    page_json = json.dumps(page, ensure_ascii=False, indent=2)
    return (
        f"演示文稿总标题：{deck_title}\n"
        f"本页大纲 JSON：\n{page_json}\n\n"
        f"{image_line}{feedback_line}\n\n"
        "请输出本页的完整 SVG。"
    )
