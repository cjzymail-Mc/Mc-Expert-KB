# -*- coding: utf-8 -*-
"""QD 红白 deck html 遮罩截图（文字透明、伪元素透明、img 隐藏）→ _slide_shots_masked/*.png
用法: py -3 -X utf8 screenshot_deck_masked.py <deck.html> [outdir]
与 extract_deck_layout.py 共享 LAYOUT_CSS（教训 C-2）。
"""
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

from playwright.sync_api import sync_playwright

from deck_common import CANVAS_W, CANVAS_H, MASK_CSS


def main():
    html = Path(sys.argv[1]).resolve()
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else html.parent / "_slide_shots_masked"
    out.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(
            viewport={"width": int(CANVAS_W), "height": int(CANVAS_H)},
            device_scale_factor=3,  # 3780x2160，清晰度/体积平衡点
        )
        page.goto(html.as_uri(), wait_until="domcontentloaded")
        page.add_style_tag(content=MASK_CSS)
        page.wait_for_timeout(800)
        slides = page.query_selector_all("section.slide")
        for i, slide in enumerate(slides, 1):
            slide.screenshot(path=str(out / f"slide_{i:02d}.png"))
        browser.close()
    print(f"masked shots: {len(slides)} 页 -> {out}")


if __name__ == "__main__":
    main()
