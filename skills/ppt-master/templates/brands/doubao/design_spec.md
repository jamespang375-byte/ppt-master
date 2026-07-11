---
brand_id: doubao
kind: brand
summary: Doubao brand identity — modern, vibrant, card-based designs with teal, blue, and warm gold accents
keywords: [doubao, vibrant, modern, tech, card-layout]
primary_color: "#00A88F"
---

# Doubao (豆包) Brand Specification

> Identity-only preset. No SVG page roster — pages are composed freely under these constraints.

## I. Brand Overview

| Property | Value |
|---|---|
| Brand Name | Doubao Style / 豆包风格 |
| Use Cases | AI/LLM tech talks, modern web product updates, product launches, developer events, youth/community presentations |
| Tone | Modern, vibrant, friendly, clear, multi-color expressive, clean card-based UI layout |

## II. Color Scheme

| Role | HEX | Provenance | Notes |
|---|---|---|---|
| primary | `#00A88F` | fact | Doubao Teal Green — extracted from active slides |
| secondary | `#2563EB` | fact | Royal Blue — Tailwind Blue-600 |
| accent (warm) | `#D4AF37` | fact | Warm Gold / Yellow |
| accent (alert) | `#C00000` | fact | Alert Red |
| text | `#1F2329` | fact | ByteDance/Feishu primary dark text |
| muted-text | `#4B5563` | fact | Secondary gray text — Tailwind Gray-600 |
| bg | `#FFFFFF` | fact | Standard light background |
| surface | `#F3F4F6` | approx | Light gray for card backgrounds and container borders |

The color scheme emphasizes bright, highly saturated brand colors (Teal Green, Royal Blue, Gold) laid out on clean white backgrounds with light gray card surfaces. This creates a high-contrast, modern "web application" interface feel.

## III. Typography

| Role | Family | Weight |
|---|---|---|
| title | `Inter, "Noto Sans SC", "Microsoft YaHei", sans-serif` | 600–700 |
| body | `Inter, "Noto Sans SC", sans-serif` | 400 |

Prefer `Noto Sans SC` for CJK characters and `Inter` for Latin numerals and characters to achieve a high-end web aesthetic.

## IV. Logo

This is a generic preset style. No specific brand logo file is locked.
If a logo is used:
- Position: Top-left or top-right header corner.
- Clean space: 0.5x logo height.

## V. Voice & Tone

- Formality: neutral-casual
- Person: we / you (English), 我们 / 你 (Chinese)
- Emoji: allowed
- Abbreviations: common-abbrev-allowed
- Style: tech-friendly, simple, interactive, card-organized bullet points

## VI. Icon Style

- Preference: linear / tabler icons
- Recommended libraries: `tabler-outline` or `tabler-filled`
- Style notes: Keep stroke weight thin to moderate (approx. 1.5px to 2.0px equivalent) to align with modern SaaS app styling.
