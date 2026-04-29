from __future__ import annotations

import os
from pathlib import Path

ASSETS_DIR = Path(os.getenv("ASSETS_DIR", "/data/assets"))


def main() -> None:
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError as exc:
        raise SystemExit("Missing dependency: add pillow to requirements.txt") from exc

    thumbs = ASSETS_DIR / "thumbs"
    covers = ASSETS_DIR / "covers"
    thumbs.mkdir(parents=True, exist_ok=True)
    covers.mkdir(parents=True, exist_ok=True)

    def make(path: Path, size: tuple[int, int], title: str, subtitle: str) -> None:
        img = Image.new("RGB", size, (15, 118, 110))
        draw = ImageDraw.Draw(img)

        try:
            font_big = ImageFont.truetype("DejaVuSans-Bold.ttf", max(18, size[0] // 12))
            font_small = ImageFont.truetype("DejaVuSans.ttf", max(12, size[0] // 22))
        except Exception:
            font_big = None
            font_small = None

        draw.rectangle([18, 18, size[0]-18, size[1]-18], outline=(220, 252, 247), width=3)
        draw.text((32, size[1]//2 - 28), title, fill=(255, 255, 255), font=font_big)
        draw.text((32, size[1]//2 + 14), subtitle, fill=(220, 252, 247), font=font_small)
        img.save(path, "JPEG", quality=85, optimize=True)
        print(f"Created {path}")

    make(thumbs / "fallback-article.jpg", (640, 360), "GREEN BUILDER", "Article")
    make(covers / "fallback-magazine.jpg", (420, 560), "GREEN BUILDER", "Magazine Archive")


if __name__ == "__main__":
    main()
