#!/usr/bin/env python3
"""生成 PPT Master Agent 品牌图标（app/packaging/assets/）。

画的是前端同款 logo（app.js 里的内联 SVG）：#2563eb 圆角方块 +
白色幻灯片矩形 + 短横线。产物：
  pptsaas.ico  Windows 多尺寸图标（16-256），供 pptsaas.spec 的 EXE(icon=)
  pptsaas.png  512x512，供 AppImage 的 .desktop Icon=

用法：python3 app/packaging/make_icons.py
依赖：Pillow（skills 管线依赖里已有）
"""

from pathlib import Path

from PIL import Image, ImageDraw

ASSETS = Path(__file__).resolve().parent / "assets"
BLUE = (37, 99, 235, 255)        # #2563eb
WHITE = (255, 255, 255, 255)


def render(size: int) -> Image.Image:
    """4x 超采样绘制再缩小，保证小尺寸边缘平滑。"""
    scale = 4
    s = size * scale
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    # 圆角方块底（对应 SVG 的 rx=7/32）
    d.rounded_rectangle([0, 0, s - 1, s - 1], radius=s * 7 / 32, fill=BLUE)
    # 白色幻灯片矩形（x=7,y=8,w=18,h=12,rx=2，32 基准）
    d.rounded_rectangle(
        [s * 7 / 32, s * 8 / 32, s * 25 / 32, s * 20 / 32],
        radius=s * 2 / 32, fill=WHITE)
    # 底部短横线（x=7,y=23,w=10,h=2.5,rx=1.2，透明度 0.8）
    line = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    ImageDraw.Draw(line).rounded_rectangle(
        [s * 7 / 32, s * 23 / 32, s * 17 / 32, s * 25.5 / 32],
        radius=s * 1.2 / 32, fill=(255, 255, 255, 204))
    img = Image.alpha_composite(img, line)
    return img.resize((size, size), Image.LANCZOS)


def main() -> None:
    ASSETS.mkdir(parents=True, exist_ok=True)
    sizes = [16, 24, 32, 48, 64, 128, 256]
    images = [render(s) for s in sizes]
    ico_path = ASSETS / "pptsaas.ico"
    images[-1].save(
        ico_path,
        format="ICO",
        sizes=[(s, s) for s in sizes],
        append_images=images[:-1],
    )
    png_path = ASSETS / "pptsaas.png"
    render(512).save(png_path, format="PNG")
    for p in (ico_path, png_path):
        print(f"{p}  {p.stat().st_size} bytes")


if __name__ == "__main__":
    main()
