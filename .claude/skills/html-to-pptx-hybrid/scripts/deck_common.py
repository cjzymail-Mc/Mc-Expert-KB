# -*- coding: utf-8 -*-
"""QD 红白 deck html→pptx 管线共享常量。
教训 C-2：extract 与 screenshot 必须共享同一 LAYOUT_CSS，否则坐标系偏差。
"""

CANVAS_W = 1260.0   # HTML CSS px
CANVAS_H = 720.0
SLIDE_W_PT = 960.0  # 16:9 (C-1：显式尺寸，禁用 SlideSize 枚举)
SLIDE_H_PT = 540.0
SX = SLIDE_W_PT / CANVAS_W
SY = SLIDE_H_PT / CANVAS_H

LAYOUT_CSS = """
.wrapper { padding: 0 !important; max-width: 1260px !important; margin: 0 !important; }
section.slide { width: 1260px !important; height: 720px !important;
                min-height: 720px !important; max-height: 720px !important;
                margin: 0 !important; border-radius: 0 !important;
                overflow: hidden !important; box-shadow: none !important; }
"""

# 遮罩 = LAYOUT_CSS + 文字透明（含 ::before/::after/::marker 伪元素）。
# 水印是 background-image(SVG)，不受 color 影响，自然保留在截图层。
MASK_CSS = LAYOUT_CSS + """
* { color: transparent !important; -webkit-text-fill-color: transparent !important; }
*::before, *::after { color: transparent !important;
                      -webkit-text-fill-color: transparent !important; }
li::marker { color: transparent !important; }
img { visibility: hidden !important; }
"""
