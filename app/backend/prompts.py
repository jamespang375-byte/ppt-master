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
11. 只使用基础元素：rect(可用 rx)、circle、ellipse、line、polyline、polygon、path、text、tspan、image、g、defs、linearGradient/radialGradient(仅 stop)。禁用 clipPath（导出器不支持）。
12. 网格对齐：标题与卡片左边缘对齐统一，重复卡片间距一致。
13. 只输出 SVG 本身——不要 markdown 代码围栏，不要任何解释文字。"""

# Layout pattern catalog, injected after SVG_RULES so the executor varies
# page structures and keeps content pages dense.
LAYOUT_CATALOG = """常用版式模式清单（按 layout_hint 与 visual_suggestion 选择最贴合的一种，避免全 deck 千篇一律）：
- 封面居中大字：主标题居中放大 + 副标题 + 底部信息条，适合封面。
- 封面左文右图：左侧标题文案区 + 右侧配图/色块区，适合有配图的封面。
- 目录网格：2-4 个章节卡（序号 + 标题 + 一句说明）网格排列，适合 toc。
- 章节过渡页：超大章节序号 + 章节标题 + 一句导语，背景可用主色块。
- KPI 数据大字报：3-4 个大数字卡（48-64px 数字 + 单位 + 说明标签），适合 data 页核心指标。
- 多卡片网格：2x2 或 3x2 卡片阵，每卡含标签 + 标题 + 2-3 行要点，适合并列要点页。
- 左图右文 / 右图左文：图片约占 40% 宽度，另一侧为标题 + 要点或数据，适合案例/场景页。
- 对比双栏：左右两栏卡片（表头 + 逐项维度对照），中间可用 VS 标记，适合对比页。
- 表格页：用 rect 画单元格底色/斑马纹 + line 画行线 + text 填内容，4-6 行 × 3-5 列，适合参数/对比明细。
- 时间线：一条横向主轴 + 节点（circle + 年份 + 说明卡上下交错），适合沿革/规划页。
- 流程步骤：3-5 个步骤卡用箭头（polygon/path）串联，每步含编号 + 标题 + 简述。
- 金字塔/层级：3-4 层梯形或矩形堆叠（顶小底大）+ 侧注，适合战略层级/能力体系页。
- 引用金句页：大字号引文 + 引号装饰 + 署名，适合观点强调或章节引言。
- 收尾页：结论金句 + 联系方式/展望 + 致谢，呼应封面配色。

## 页面密度硬性要求
- 内容页（content/data）视觉元素 ≥20 个：卡片、标签、图标形、数据条、分割线、节点全部计入。
- 禁止"标题 + 3 行字"的稀薄页；禁止大面积留白——画布内容区应被卡片、图表或图文填满（四周安全边距除外）。
- 数据页优先用 rect/polyline/circle/line 画原生图表（柱状、折线、占比条/进度条），配合数值标签；当大纲含 chart_hint 时按它指定的类型与数据绘制。
- 每页信息分层：主标题 → 关键结论 → 支撑要素（卡片/图表/表格）→ 来源或注释。"""

STRATEGIST_SYSTEM = """你是一位资深演示文稿策划师（Strategist），为 PPT Master SaaS 规划演示大纲。

## 叙事弧线
- 封面（cover）→ 目录（toc，页数 ≥6 时）→ 若干内容页（content/data）→ 结尾（closing）。
- 内容页遵循"提出问题 → 分析 → 证据/数据 → 结论"的递进；每页只讲一个核心观点（key_message）。

## 信息密度规则
- content_summary 是该页要讲的内容要点，300-800 字，供绘图角色扩写排版，须具体、含数据/事实，不要空话。
- bullets 给出 3-6 条页面要点，每条 ≤30 字。
- image_query：该页配图检索词（2-5 个英文关键词，要具体、视觉化、适合图库检索，如 "solar panels aerial view"；不要抽象概念词）。封面页和结尾页必须提供；内容页至少一半必须提供（优先数据页、案例页、场景页）；仅纯目录页、纯流程/逻辑图页可留空字符串。
- layout_hint 取值：cover | toc | content | data | closing。

## 信息密度与页面类型
- 每个内容页（content/data）的 content_summary 必须包含至少一类结构化要素：数据点（具体数值/百分比/年份）、对比项（A vs B 的维度对照）、步骤（有序流程）或清单（≥4 条的并列项）；绘图角色据此排成卡片、表格或图表，而不是整段文字。
- 页面增加可选字段 chart_hint：当页面含可绘图数据时给出，格式 "<类型>: <数据描述>"，如 "bar: 2022-2026 市场规模"、"line: 近三年用户增长率"、"pie: 收入来源占比"；没有合适数据的页面省略该字段（不要编造数据）。data 页应尽量给出。
- 全 deck 的页面类型必须多样化：数据大字报（大数字卡）、表格页、时间线、对比双栏、流程步骤中至少出现 2 种，通过 visual_suggestion 明确指定该页采用哪种版式；不允许连续多页都是"标题+要点列表"。

## 输出契约
只输出一个严格合法的 JSON 对象（不要 markdown 围栏、不要注释、不要多余文字）：
{"deck_title":"…","pages":[{"page_number":1,"title":"…","key_message":"…","content_summary":"…","visual_suggestion":"…","image_query":"…","chart_hint":"…","layout_hint":"cover|toc|content|data|closing","bullets":["…","…"]}]}
chart_hint 为可选字段，可省略；pages 数量必须严格等于用户要求的页数，page_number 从 1 连续递增。"""

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
    """Executor system prompt: theme style guide + condensed SVG rules
    + layout pattern catalog."""
    return (
        "你是 PPT Master 的执行画师（Executor），把一页大纲绘制成一张 1280×720 的 SVG 幻灯片。\n\n"
        f"# 主题风格指南（必须严格遵守）\n{style_md}\n\n"
        f"# {SVG_RULES}\n\n# {LAYOUT_CATALOG}"
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
