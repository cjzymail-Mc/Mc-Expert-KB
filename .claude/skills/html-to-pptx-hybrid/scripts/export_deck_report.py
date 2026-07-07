# -*- coding: utf-8 -*-
"""RD38 皮研发汇报 deck：manifest + 遮罩截图 → win32com 装配可编辑 pptx（折中 Hybrid）。
用法: py -3 -X utf8 export_deck_report.py <manifest.json> <shots_dir> <out.pptx> [--slides 1-3]

与 export_deck_pptx.py（QD 红白）同骨架，差异：
- centered 旗标驱动居中 + 垂直居中（.num 折角块 / .bignum）。
- 表格逐 cell 用 manifest 抓到的真实 color/bg（皮肤无关，不硬编码 QD 红表头）。
- 列表 marker_mode：bg=红方块在截图层(markerless 内缩) / up,down=▲▼ glyph 被截图吃掉(overlay 补 marker run)。
- C-1/C-5/C-6/C-7 全守；路径含 [ ]：SaveAs 先 %TEMP% 再 shutil.move；Ldterm 产物首字节 88 7D 1C 为预期。
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
# ↓ 仅作**回退默认**：L3 已治本（色从 manifest 的 marker_color / cell.border 读，跟随配色模板）。
#   旧 manifest（无这些字段）或抓色失败时回退到下列硬编码（= 默认 RD38 红蓝），不再是唯一真相源。
TBL_BORDER = "#D9D9D9"          # 回退：普通格线（=--line 中性）
TBL_HDR_BORDER = "#2A4A78"      # 回退：表头边线（=--navy-line）
MARKER = {"up": ("▲", "#E53238"), "down": ("▼", "#0064D2")}  # ▲▼ glyph 字符 + 回退色
# 紧致单行标题（绝对定位/自适应宽，PPT 字体略宽易把英文/末字挤到第二行）→ 强制不换行
NO_WRAP_ROLES = {"tb", "subhead", "eyebrow", "subtitle", "carrier", "badge",
                 "cn", "en", "ctitle", "csub", "rt", "rs", "it-t"}


def x(px): return px * SX
def y(px): return px * SY
def pt(px): return px * 0.75


def rgb(hex_str):
    return int(hex_str[1:3], 16) + (int(hex_str[3:5], 16) << 8) + (int(hex_str[5:7], 16) << 16)


def runs_to_text(runs):
    return "".join(r["text"] for r in runs).replace("\n", "\r")  # C-5


def apply_runs(tr, runs, base_color, base_bold, start=1):
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
    centered = el.get("centered")
    buf_w = ew if centered else max(ew, ew * 1.08)  # C-6（居中框不加 buffer，靠满框居中对齐）
    shp = slide.Shapes.AddTextbox(1, x(ex), y(ey), x(buf_w), y(eh))
    tf = shp.TextFrame
    tf.WordWrap = 0 if el.get("role") in NO_WRAP_ROLES else -1
    tf.AutoSize = 0
    if centered:
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
    tr.ParagraphFormat.Alignment = 2 if centered else el.get("align", 1)
    tr.ParagraphFormat.LineRuleWithin = -1
    tr.ParagraphFormat.SpaceWithin = el.get("line_ratio", 1.4)
    apply_runs(tr, el["runs"], el["color"], el["bold"])
    if centered:
        # AddTextbox 默认 ShapeToFitText 会把高度塌成一行 → 重置满框，VerticalAnchor middle 才真居中
        shp.Left, shp.Top = x(ex), y(ey)
        shp.Width, shp.Height = x(buf_w), y(eh)
    return shp


def add_bullets(slide, el):
    mode = el.get("marker_mode", "bg")
    pad_l = el.get("pad_l", 0)
    ex, ey, ew, eh = el["x"], el["y"], el["w"], el["h"]
    if mode == "bg":
        # 红方块 marker 在截图层 → 文字内缩躲开，markerless
        ex = ex + pad_l
        ew = ew - pad_l
    shp = slide.Shapes.AddTextbox(1, x(ex), y(ey), x(max(ew, ew * 1.05)), y(eh))
    tf = shp.TextFrame
    tf.WordWrap = -1
    tf.AutoSize = 0
    tf.MarginLeft = tf.MarginRight = tf.MarginTop = tf.MarginBottom = 0
    tr = tf.TextRange

    # 每行文本（box 列表补回 ▲/▼ glyph）
    lines, marker_lens = [], []
    for it in el["items"]:
        body = runs_to_text(it["runs"])
        if mode in MARKER:
            glyph, _ = MARKER[mode]
            lines.append(f"{glyph} {body}")
            marker_lens.append(2)  # "▲ "
        else:
            lines.append(body)
            marker_lens.append(0)
    tr.Text = "\r".join(lines)
    tr.Font.NameFarEast = FONT
    tr.Font.Name = FONT
    tr.Font.Size = pt(el["font_size_px"])
    tr.Font.Bold = -1 if el["bold"] else 0
    tr.Font.Color.RGB = rgb(el["color"])
    tr.ParagraphFormat.Alignment = el.get("align", 1)
    tr.ParagraphFormat.LineRuleWithin = -1
    tr.ParagraphFormat.SpaceWithin = el.get("line_ratio", 1.5)

    pos = 1
    for i, it in enumerate(el["items"], 1):
        p = tr.Paragraphs(i, 1)
        p.ParagraphFormat.Bullet.Visible = 0   # markerless（marker 来自截图或 glyph run）
        p.ParagraphFormat.SpaceAfter = pt(7)
        mlen = marker_lens[i - 1]
        if mlen:  # ▲/▼ marker run 染色（L3 治本：色取 manifest marker_color 跟随 palette，缺则回退硬编码）
            seg = tr.Characters(pos, 1)
            seg.Font.Color.RGB = rgb(el.get("marker_color") or MARKER[mode][1])
            seg.Font.Bold = -1
        pos = apply_runs(tr, it["runs"], el["color"], el["bold"], start=pos + mlen)
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
            tf.MarginLeft = tf.MarginRight = x(14)
            tf.MarginTop = tf.MarginBottom = y(6)
            tr = tf.TextRange
            tr.Text = cell_data["text"]
            tr.Font.NameFarEast = FONT
            tr.Font.Name = FONT
            tr.ParagraphFormat.Alignment = 1
            is_hdr = cell_data.get("is_header")
            tr.Font.Size = pt(14.5 if is_hdr else 14)
            tr.Font.Bold = -1 if (is_hdr or cell_data.get("bold")) else 0
            # 逐 cell 用 manifest 真实色（皮肤无关）
            tr.Font.Color.RGB = rgb(cell_data.get("color", "#000000"))
            cell.Shape.Fill.ForeColor.RGB = rgb(cell_data.get("bg", "#ffffff"))
            cell.Shape.Fill.Solid()
            # L3 治本：border 色取 manifest（th=navy-line/td=line 随 palette），缺则回退硬编码
            border_color = rgb(cell_data.get("border") or (TBL_HDR_BORDER if is_hdr else TBL_BORDER))
            for side in (1, 2, 3, 4):
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
    shots = Path(args.shots_dir).resolve()
    out = Path(args.out_pptx).resolve()
    only = parse_slide_range(args.slides)
    slides_data = [s for s in manifest["slides"] if (only is None or s["index"] in only)]

    tmp_out = Path(tempfile.gettempdir()) / f"__tmp_deck_report_{os.getpid()}.pptx"
    app = win32.Dispatch("PowerPoint.Application")
    app.Visible = True
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
