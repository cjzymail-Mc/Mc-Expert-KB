# -*- coding: utf-8 -*-
"""deck.html 预览截图（无遮罩，仅供人工/AI 目检版面溢出）。
用法: python preview_screenshot.py <deck.html 路径> [输出目录]
"""
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

from playwright.sync_api import sync_playwright

html = Path(sys.argv[1]).resolve()
out = Path(sys.argv[2]) if len(sys.argv) > 2 else html.parent / "_preview_shots"
out.mkdir(parents=True, exist_ok=True)

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width": 1260, "height": 720})
    page.goto(html.as_uri(), wait_until="domcontentloaded")
    page.wait_for_timeout(500)
    slides = page.query_selector_all("section.slide")
    print(f"slides found: {len(slides)}")
    # 溢出检测：scrollHeight > clientHeight 即内容超出 720
    overflow = page.evaluate(
        """() => Array.from(document.querySelectorAll('section.slide'))
              .map((s,i) => ({i: i+1, sh: s.scrollHeight, ch: s.clientHeight}))
              .filter(o => o.sh > o.ch + 1)"""
    )
    print(f"overflow slides: {overflow if overflow else '无'}")
    for i, slide in enumerate(slides, 1):
        slide.screenshot(path=str(out / f"slide_{i:02d}.png"))
    browser.close()
print(f"saved -> {out}")
