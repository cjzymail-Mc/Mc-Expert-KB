# -*- coding: utf-8 -*-
"""QD 红白 deck：manifest + 遮罩截图 → win32com 装配可编辑 pptx（Hybrid 路线）。
用法: py -3 -X utf8 export_deck_pptx.py <manifest.json> <shots_dir> <out.pptx> [--slides 1-3]
- C-1: SlideWidth/Height 显式 960x540
- C-5: 段落分隔 \r
- C-6: 文本框宽度 8% buffer
- C-7: COM 常量用数值字面量
- 路径含 [ ]：SaveAs 先到 %TEMP% 再 shutil.move
- 本机 Ldterm：COM SaveAs 产物首字节 88 7D 1C 为预期（拍板点 #7），非故障
"""
import argparse
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

import win32com.client as win32

from deck_common import SLIDE_W_PT, SLIDE_H_PT, SX, SY

FONT = "Microsoft YaHei"
ACCENT = "#E53238"      # 表头红（skills/report-deck-qd-redwhite token）
TBL_BORDER = "#D9D9D9"
TBL_HDR_BORDER = "#C42A30"
TBL_STRIPE = "#F7F7F7"


def x(px): return px * SX
def y(px): return px * SY
def pt(px): return px * 0.75


def rgb(hex_str):
    return int(hex_str[1:3], 16) + (int(hex_str[3:5], 16) << 8) + (int(hex_str[5:7], 16) << 16)


def runs_to_text(runs):
    return "".join(r["text"] for r in runs).replace("\n", "\r")  # C-5


def apply_runs(tr, runs, base_color, base_bold, start=1):
    """按字符区间还原行内染色/加粗（红蓝语义铁律）。返回结束位置。"""
    pos = start
    for r in runs:
        t = r["text"].replace("\n", "\r")
        if not t:
            continue
        if r["color"] != base_color or bool(r["bold"]) != bool(base_bold):
            seg = tr.Characters(pos, len(t))
            seg.Font.Color.RGB = rgb(r["color"])
            seg.Font.Bold = -1 if r["bold"] else 0
        pos += len(t)
    return pos


def add_textbox(slide, el):
    ex, ey, ew, eh = el["x"], el["y"], el["w"], el["h"]
    buf_w = max(ew, ew * 1.08)  # C-6
    shp = slide.Shapes.AddTextbox(1, x(ex), y(ey), x(buf_w), y(eh))
    tf = shp.TextFrame
    tf.WordWrap = -1
    tf.AutoSize = 0
    role = el.get("role", "")
    centered_block = ("toc-num" in role) or ("qd-badge" in role)
    if centered_block:
        tf.MarginLeft = tf.MarginRight = tf.MarginTop = tf.MarginBottom = 0
        tf.VerticalAnchor = 3  # msoAnchorMiddle
    else:
        tf.MarginLeft = x(el.get("pad_l", 0))
        tf.MarginTop = y(el.get("pad_t", 0))
        tf.MarginRight = x(el.get("pad_r", 0))
        tf.MarginBottom = y(el.get("pad_b", 0))
    tr = tf.TextRange
    tr.Text = runs_to_text(el["runs"])
    tr.Font.NameFarEast = FONT
    tr.Font.Name = FONT
    tr.Font.Size = pt(el["font_size_px"])
    tr.Font.Bold = -1 if el["bold"] else 0
    tr.Font.Color.RGB = rgb(el["color"])
    tr.ParagraphFormat.Alignment = 2 if centered_block else el.get("align", 1)
    lr = el.get("line_ratio", 1.2)
    tr.ParagraphFormat.LineRuleWithin = -1
    tr.ParagraphFormat.SpaceWithin = lr
    apply_runs(tr, el["runs"], el["color"], el["bold"])
    return shp


def add_bullets(slide, el):
    ex, ey, ew, eh = el["x"], el["y"], el["w"], el["h"]
    shp = slide.Shapes.AddTextbox(1, x(ex), y(ey), x(max(ew, ew * 1.08)), y(eh))
    tf = shp.TextFrame
    tf.WordWrap = -1
    tf.AutoSize = 0
    tf.MarginLeft = tf.MarginRight = tf.MarginTop = tf.MarginBottom = 0
    tr = tf.TextRange
    tr.Text = "\r".join(runs_to_text(it["runs"]) for it in el["items"])
    tr.Font.NameFarEast = FONT
    tr.Font.Name = FONT
    tr.Font.Size = pt(el["font_size_px"])
    tr.Font.Bold = -1 if el["bold"] else 0
    tr.Font.Color.RGB = rgb(el["color"])
    tr.ParagraphFormat.Alignment = el.get("align", 1)
    tr.ParagraphFormat.LineRuleWithin = -1
    tr.ParagraphFormat.SpaceWithin = el.get("line_ratio", 1.2)
    pos = 1
    for i, it in enumerate(el["items"], 1):
        p = tr.Paragraphs(i, 1)
        p.ParagraphFormat.Bullet.Visible = -1
        if el.get("ordered"):
            p.ParagraphFormat.Bullet.Type = 2  # ppBulletNumbered
        else:
            p.ParagraphFormat.Bullet.Type = 1
            p.ParagraphFormat.Bullet.Character = 8226
        p.ParagraphFormat.LineRuleAfter = 0
        p.ParagraphFormat.SpaceAfter = 3.75  # ≈ li margin-bottom 5px
        pos = apply_runs(tr, it["runs"], el["color"], el["bold"], start=pos)
        pos += 1  # 段落分隔 \r
    return shp


def add_table(slide, el):
    rows = el["rows"]
    n_rows, n_cols = len(rows), max(len(r) for r in rows)
    shp = slide.Shapes.AddTable(n_rows, n_cols, x(el["x"]), y(el["y"]), x(el["w"]), y(el["h"]))
    tbl = shp.Table
    total_w = x(el["w"])
    for ci, frac in enumerate(el.get("col_fracs", [])[:n_cols]):
        tbl.Columns(ci + 1).Width = total_w * frac
    for ri, rh in enumerate(el.get("row_heights", [])[:n_rows]):
        tbl.Rows(ri + 1).Height = y(rh)
    for ri, row in enumerate(rows):
        for ci, cell_data in enumerate(row):
            cell = tbl.Cell(ri + 1, ci + 1)
            tf = cell.Shape.TextFrame
            tf.MarginLeft = tf.MarginRight = x(16)
            tf.MarginTop = tf.MarginBottom = y(5)
            tr = tf.TextRange
            tr.Text = cell_data["text"]
            tr.Font.NameFarEast = FONT
            tr.Font.Name = FONT
            tr.ParagraphFormat.Alignment = 1
            is_hdr = cell_data.get("is_header")
            tr.Font.Size = pt(14 if is_hdr else 13.5)
            tr.Font.Bold = -1 if (is_hdr or cell_data.get("bold")) else 0
            if is_hdr:
                tr.Font.Color.RGB = rgb("#ffffff")
                cell.Shape.Fill.ForeColor.RGB = rgb(ACCENT)
            else:
                tr.Font.Color.RGB = rgb("#000000")
                # CSS tr:nth-child(odd)（1 基，表头占 tr1）→ 数据行 ri 偶数为条纹
                stripe = (ri % 2 == 0)
                cell.Shape.Fill.ForeColor.RGB = rgb(TBL_STRIPE if stripe else "#ffffff")
            cell.Shape.Fill.Solid()
            border_color = rgb(TBL_HDR_BORDER if is_hdr else TBL_BORDER)
            for side in (1, 2, 3, 4):  # ppBorderTop/Left/Bottom/Right
                ln = cell.Borders(side)
                ln.ForeColor.RGB = border_color
                ln.Weight = 0.75
                ln.Visible = -1
    return shp


def add_bg_screenshot(slide, shot_path):
    shp = slide.Shapes.AddPicture(str(shot_path), 0, -1, 0, 0, SLIDE_W_PT, SLIDE_H_PT)
    shp.ZOrder(1)  # msoSendToBack
    return shp


def parse_slide_range(spec):
    if not spec:
        return None
    out = set()
    for part in spec.split(","):
        part = part.strip()
        if "-" in part:
            a, b = part.split("-")
            out.update(range(int(a), int(b) + 1))
        elif part:
            out.add(int(part))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("manifest")
    ap.add_argument("shots_dir")
    ap.add_argument("out_pptx")
    ap.add_argument("--slides", default=os.environ.get("SLIDE_RANGE", ""))
    args = ap.parse_args()

    manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
    shots = Path(args.shots_dir).resolve()  # COM 进程工作目录不同，必须绝对路径
    out = Path(args.out_pptx).resolve()
    only = parse_slide_range(args.slides)
    slides_data = [s for s in manifest["slides"] if (only is None or s["index"] in only)]

    tmp_out = Path(tempfile.gettempdir()) / f"__tmp_deck_{os.getpid()}.pptx"
    app = win32.Dispatch("PowerPoint.Application")
    app.Visible = True  # Windows 限制：不能 False
    pres = app.Presentations.Add()
    warn = 0
    try:
        pres.PageSetup.SlideWidth = SLIDE_W_PT   # C-1
        pres.PageSetup.SlideHeight = SLIDE_H_PT
        for pos, sd in enumerate(slides_data, start=1):
            idx = sd["index"]
            slide = pres.Slides.Add(pos, 12)  # ppLayoutBlank
            shot = shots / f"slide_{idx:02d}.png"
            if shot.exists():
                add_bg_screenshot(slide, shot)
            else:
                print(f"  [WARN] 缺截图 {shot.name}")
                warn += 1
            for el in sd["elements"]:
                try:
                    if el["type"] == "text":
                        add_textbox(slide, el)
                    elif el["type"] == "bullets":
                        add_bullets(slide, el)
                    elif el["type"] == "table":
                        add_table(slide, el)
                except Exception as exc:
                    print(f"  [WARN] p{idx} {el['type']}({el.get('role','')}) 失败: {exc}")
                    warn += 1
            print(f"  p{idx} ok ({len(sd['elements'])} elements)")
        pres.SaveAs(str(tmp_out), 24)  # ppSaveAsOpenXMLPresentation
    finally:
        try:
            pres.Close()
        except Exception:
            pass
        try:
            app.Quit()
        except Exception:
            pass

    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        out.unlink()
    shutil.move(str(tmp_out), str(out))
    head = out.read_bytes()[:4]
    state = "密文 88 7D 1C（本机 Ldterm 预期终态）" if head[:3] == b"\x88\x7d\x1c" else \
            ("明文 50 4B" if head[:2] == b"PK" else f"未知 {head.hex()}")
    print(f"done: {len(slides_data)} 页, warn={warn} -> {out}")
    print(f"首字节: {state}")
    sys.exit(1 if warn else 0)


if __name__ == "__main__":
    main()
