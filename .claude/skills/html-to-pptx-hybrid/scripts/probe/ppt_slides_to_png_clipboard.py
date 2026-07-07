# -*- coding: utf-8 -*-
"""pptx 各页渲染为明文 PNG（COM 只读 + Slide.Copy → 剪贴板 → ImageGrab，绕开
Ldterm 对 POWERPNT 落盘文件的反向加密；见 skills/[★] images-via-clipboard.md）。
用法: python ppt_slides_to_png_clipboard.py <pptx> <out_dir>
"""
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

import win32com.client as win32
from PIL import ImageGrab

src = Path(sys.argv[1]).resolve()
out = Path(sys.argv[2]).resolve()
out.mkdir(parents=True, exist_ok=True)

app = win32.Dispatch("PowerPoint.Application")
pres = None
try:
    pres = app.Presentations.Open(str(src), ReadOnly=True, WithWindow=False)
    n = pres.Slides.Count
    print(f"slides: {n}")
    for i in range(1, n + 1):
        pres.Slides(i).Copy()
        img = None
        deadline = time.time() + 6.0
        while time.time() < deadline:
            img = ImageGrab.grabclipboard()
            if img is not None and not isinstance(img, list):
                break
            time.sleep(0.3)
        if img is None or isinstance(img, list):
            print(f"  slide {i}: 剪贴板未取到位图 FAIL")
            continue
        p = out / f"tpl_{i:02d}.png"
        img.save(p)
        head = p.read_bytes()[:4]
        print(f"  slide {i}: {img.size} -> {p.name} 首字节 {head.hex(' ')}")
finally:
    try:
        if pres is not None:
            pres.Close()
    except Exception:
        pass
    try:
        app.Quit()
    except Exception:
        pass
