# -*- coding: utf-8 -*-
"""明文 pptx 视觉语言探针（python-pptx 直读，不走 COM）。
dump: 画布尺寸 / theme 配色+字体 / 每页背景+shape 填充/线条/文字 run 级字体字号颜色。
用法: python dump_ppt_visual.py <pptx>
"""
import sys
import zipfile
import re
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

from pptx import Presentation
from pptx.util import Emu

src = Path(sys.argv[1])

# ---- theme: 配色方案 + 字体方案（直接 parse theme xml）----
with zipfile.ZipFile(src) as z:
    themes = [n for n in z.namelist() if re.match(r"ppt/theme/theme\d+\.xml", n)]
    for tn in themes:
        xml = z.read(tn).decode("utf-8")
        print(f"=== {tn} ===")
        m = re.search(r'<a:clrScheme name="([^"]*)"', xml)
        print(f"clrScheme: {m.group(1) if m else '?'}")
        for tag in ["dk1", "lt1", "dk2", "lt2", "accent1", "accent2", "accent3",
                    "accent4", "accent5", "accent6", "hlink", "folHlink"]:
            mm = re.search(rf'<a:{tag}>.*?(?:val|lastClr)="([0-9A-Fa-f]{{6}})"', xml, re.S)
            print(f"  {tag}: #{mm.group(1) if mm else '?'}")
        for which in ["majorFont", "minorFont"]:
            mm = re.search(rf'<a:{which}>\s*<a:latin typeface="([^"]*)"', xml)
            ea = re.search(rf'<a:{which}>.*?<a:ea typeface="([^"]*)"', xml, re.S)
            print(f"  {which}: latin={mm.group(1) if mm else '?'} ea={ea.group(1) if ea else '?'}")

prs = Presentation(str(src))
print(f"\n画布: {Emu(prs.slide_width).pt:.0f} x {Emu(prs.slide_height).pt:.0f} pt, slides={len(prs.slides)}")


def color_of(cf):
    try:
        t = cf.type
        if t is None:
            return None
        if str(t).startswith("MSO_THEME"):
            pass
        if cf.type == 1:  # RGB
            return f"#{cf.rgb}"
        return f"theme:{cf.theme_color}{('+' + format(cf.brightness, '.2f')) if cf.brightness else ''}"
    except Exception:
        return None


def fill_desc(fill):
    try:
        ft = fill.type
        if ft == 1:  # solid
            return f"solid {color_of(fill.fore_color)}"
        if ft == 3:
            return "gradient"
        if ft == 6:
            return "picture"
        if ft == 5:
            return "background(none)"
        return str(ft)
    except Exception:
        return "?"


def dump_shape(sh, indent="  "):
    try:
        name = sh.name
        st = sh.shape_type
        geo = f"L{Emu(sh.left).pt:.0f} T{Emu(sh.top).pt:.0f} W{Emu(sh.width).pt:.0f} H{Emu(sh.height).pt:.0f}"
    except Exception:
        name, st, geo = "?", "?", "?"
    line = f"{indent}[{st}] {name} {geo}"
    try:
        line += f" fill={fill_desc(sh.fill)}"
    except Exception:
        pass
    try:
        if sh.line.color and sh.line.color.type is not None:
            w = sh.line.width
            line += f" line={color_of(sh.line.color)} {Emu(w).pt if w else '?'}pt"
    except Exception:
        pass
    print(line)
    if sh.has_text_frame:
        for p in sh.text_frame.paragraphs:
            for r in p.runs:
                if not r.text.strip():
                    continue
                f = r.font
                sz = f"{f.size.pt:.0f}pt" if f.size else "inherit"
                col = color_of(f.color) if f.color else None
                print(f"{indent}    run: {r.text[:40]!r} font={f.name} ea={getattr(f,'name','')} "
                      f"size={sz} bold={f.bold} color={col}")
    if sh.shape_type == 6:  # group
        for sub in sh.shapes:
            dump_shape(sub, indent + "  ")


for i, slide in enumerate(prs.slides, 1):
    print(f"\n--- Slide {i} (layout={slide.slide_layout.name}) ---")
    try:
        bg = slide.background.fill
        print(f"  background: {fill_desc(bg)}")
    except Exception:
        pass
    for sh in slide.shapes:
        dump_shape(sh)
