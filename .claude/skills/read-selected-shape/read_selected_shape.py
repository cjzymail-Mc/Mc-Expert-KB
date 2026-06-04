#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""read_selected_shape.py — 读取当前鼠标选中的 PPT shape 的完整信息.

用法：
    1. 在 PowerPoint 里选中一个或多个 shape
    2. 运行：
        python skills/read_selected_shape.py            # 精简版（兼容旧调用）
        python skills/read_selected_shape.py --full     # 全参数版（run 级字体 + 阴影 + 3D + chart/table 详情）

用途：
    - 调试 per-template 适配时查 shape 名称（中/英文内部名）
    - 获取微调所需坐标（Left/Top/Width/Height）
    - 查看 shape 文本内容（段落 + run 级字体 / 颜色 / 字号）
    - 图表类 shape 打印图表类型、系列数据、IsLinked 状态
    - 图片类 shape 打印原生尺寸 + 裁剪框
    - 表格类 shape 打印行列数 + 每格文本

输出到 stdout（UTF-8 强制），方便直接贴回对话。
"""
from __future__ import annotations

import sys
import win32com.client

# 强制 stdout UTF-8，避免 cp936 把中文 shape 名/文本打成乱码
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

# ---- PowerPoint MsoShapeType 常量（仅列常见的） -----------------------------
MSO_SHAPE_TYPE = {
    1: "AutoShape", 2: "Callout", 3: "Chart", 4: "Comment",
    5: "Freeform", 6: "Group", 7: "EmbeddedOLEObject", 8: "FormControl",
    9: "Line", 10: "LinkedOLEObject", 11: "LinkedPicture", 12: "OLEControlObject",
    13: "Picture", 14: "Placeholder", 15: "TextEffect", 16: "Media",
    17: "TextBox", 18: "ScriptAnchor", 19: "Table", 20: "Canvas",
    21: "Diagram", 22: "Ink", 23: "InkComment", 24: "IgxGraphic",
}
SELECTION_TYPE = {0: "None", 1: "Slides", 2: "Shapes", 3: "Text"}


def _safe(fn, default=None):
    try:
        return fn()
    except Exception:
        return default


def _rgb(color_long):
    """Convert COM BGR long int → 'R,G,B' string."""
    try:
        c = int(color_long)
        return f"{c & 0xFF},{(c >> 8) & 0xFF},{(c >> 16) & 0xFF}"
    except Exception:
        return str(color_long)


# ---------------------------------------------------------------------------
# 文本：段落 + run 级
# ---------------------------------------------------------------------------
def _print_text_details(sh, full: bool):
    try:
        tf = sh.TextFrame
        if not int(_safe(lambda: tf.HasText, 0)):
            print("  TEXT=（空）")
            return
        tr = tf.TextRange
        full_text = str(_safe(lambda: tr.Text, ""))
        print(f"  TEXT_FULL={full_text.replace(chr(13), '[CR]').replace(chr(10), '[LF]')[:500]}")
        print(f"  TEXT_LEN={len(full_text)}")

        if full:
            print(f"  TEXTFRAME: "
                  f"MarginL/T/R/B="
                  f"{_safe(lambda: tf.MarginLeft, '-')}/"
                  f"{_safe(lambda: tf.MarginTop, '-')}/"
                  f"{_safe(lambda: tf.MarginRight, '-')}/"
                  f"{_safe(lambda: tf.MarginBottom, '-')}"
                  f"  WordWrap={_safe(lambda: tf.WordWrap, '-')}"
                  f"  AutoSize={_safe(lambda: tf.AutoSize, '-')}")
            # VerticalAnchor / Orientation 在 TextFrame2 上
            tf2 = _safe(lambda: sh.TextFrame2, None)
            if tf2:
                print(f"  TEXTFRAME2: "
                      f"VerticalAnchor={_safe(lambda: tf2.VerticalAnchor, '-')}"
                      f"  Orientation={_safe(lambda: tf2.Orientation, '-')}")

        paragraphs = _safe(lambda: tr.Paragraphs(), None)
        pcount = int(_safe(lambda: paragraphs.Count, 0)) if paragraphs else 0
        print(f"  PARAGRAPHS={pcount}")
        for i in range(1, min(pcount, 30) + 1):
            p = tr.Paragraphs(i)
            ptext = str(_safe(lambda: p.Text, "")).rstrip("\r\n")
            pf = _safe(lambda: p.ParagraphFormat, None)
            if not full:
                # 兼容旧输出：只打 1 行段落级 font 概览
                fname = _safe(lambda: p.Font.Name, "")
                fsize = _safe(lambda: p.Font.Size, "")
                fbold = _safe(lambda: p.Font.Bold, "")
                fcolor = _safe(lambda: p.Font.Color.RGB, "")
                print(f"    p{i}: text={ptext!r} font={fname} size={fsize} "
                      f"bold={fbold} color=RGB({_rgb(fcolor) if fcolor != '' else '-'})")
                continue

            # --full：完整段落 + run 级
            align = _safe(lambda: pf.Alignment, "-") if pf else "-"
            space_within = _safe(lambda: pf.SpaceWithin, "-") if pf else "-"
            space_before = _safe(lambda: pf.SpaceBefore, "-") if pf else "-"
            space_after = _safe(lambda: pf.SpaceAfter, "-") if pf else "-"
            print(f"    p{i}: text={ptext!r}")
            print(f"      ALIGN={align}  LINESP_WITHIN={space_within}  "
                  f"SP_BEFORE={space_before}  SP_AFTER={space_after}")
            runs = _safe(lambda: p.Runs(), None)
            rcount = int(_safe(lambda: runs.Count, 0)) if runs else 0
            print(f"      RUNS={rcount}")
            for ri in range(1, rcount + 1):
                r = p.Runs(ri)
                fnt = r.Font
                rtext = str(_safe(lambda: r.Text, "")).rstrip("\r\n")
                print(f"      run{ri}: text={rtext!r}")
                print(f"        FONT: Name={_safe(lambda: fnt.Name, '-')}"
                      f"  Ascii={_safe(lambda: fnt.NameAscii, '-')}"
                      f"  FarEast={_safe(lambda: fnt.NameFarEast, '-')}")
                print(f"        SIZE={_safe(lambda: fnt.Size, '-')}"
                      f"  BOLD={_safe(lambda: fnt.Bold, '-')}"
                      f"  ITALIC={_safe(lambda: fnt.Italic, '-')}"
                      f"  UNDERLINE={_safe(lambda: fnt.Underline, '-')}"
                      f"  SHADOW={_safe(lambda: fnt.Shadow, '-')}"
                      f"  EMBOSS={_safe(lambda: fnt.Emboss, '-')}")
                rgb_val = _safe(lambda: fnt.Color.RGB, "")
                print(f"        COLOR.RGB=RGB({_rgb(rgb_val) if rgb_val != '' else '-'})"
                      f"  TYPE={_safe(lambda: fnt.Color.Type, '-')}"
                      f"  BRIGHTNESS={_safe(lambda: fnt.Color.Brightness, '-')}"
                      f"  BASELINE={_safe(lambda: fnt.BaselineOffset, '-')}")
    except Exception as e:
        print(f"  TEXT_READ_ERROR={e}")


# ---------------------------------------------------------------------------
# Chart
# ---------------------------------------------------------------------------
def _print_chart_details(sh, full: bool):
    try:
        chart = sh.Chart
        print(f"  CHART_TYPE={_safe(lambda: chart.ChartType, '-')}")
        print(f"  CHART_IS_LINKED={_safe(lambda: chart.ChartData.IsLinked, '-')}")
        print(f"  HAS_TITLE={_safe(lambda: int(chart.HasTitle), 0)}")
        if int(_safe(lambda: chart.HasTitle, 0)):
            print(f"  TITLE_TEXT={_safe(lambda: chart.ChartTitle.Text, '-')!r}")
        sc = _safe(lambda: chart.SeriesCollection(), None)
        scount = int(_safe(lambda: sc.Count, 0)) if sc else 0
        print(f"  SERIES_COUNT={scount}")
        for si in range(1, scount + 1):
            s = chart.SeriesCollection(si)
            name = _safe(lambda: s.Name, "")
            vals = _safe(lambda: list(s.Values), [])
            xvals = _safe(lambda: list(s.XValues), [])
            print(f"    series{si}: name={name!r} values={vals} xvalues={xvals}")
            if full:
                fill_rgb = _safe(lambda: s.Format.Fill.ForeColor.RGB, "")
                print(f"      FILL.RGB=RGB({_rgb(fill_rgb) if fill_rgb != '' else '-'})"
                      f"  MARKER_STYLE={_safe(lambda: s.MarkerStyle, '-')}")
        if full:
            # Axes
            for ax_idx, label in ((1, "X"), (2, "Y")):
                ax = _safe(lambda i=ax_idx: chart.Axes(i), None)
                if ax:
                    print(f"  AXIS_{label}: Min={_safe(lambda: ax.MinimumScale, '-')}  "
                          f"Max={_safe(lambda: ax.MaximumScale, '-')}  "
                          f"HasTitle={_safe(lambda: int(ax.HasTitle), 0)}")
    except Exception as e:
        print(f"  CHART_READ_ERROR={e}")


# ---------------------------------------------------------------------------
# Picture
# ---------------------------------------------------------------------------
def _print_picture_details(sh, full: bool):
    try:
        pf = sh.PictureFormat
        for attr in ("CropLeft", "CropTop", "CropRight", "CropBottom",
                     "Brightness", "Contrast"):
            v = _safe(lambda a=attr: getattr(pf, a), "-")
            print(f"  PICTURE_{attr}={v}")
        if full:
            print(f"  COLOR_TYPE={_safe(lambda: pf.ColorType, '-')}")
            lf = _safe(lambda: sh.LinkFormat, None)
            if lf:
                print(f"  LINK_SOURCE={_safe(lambda: lf.SourceFullName, '-')}"
                      f"  AutoUpdate={_safe(lambda: lf.AutoUpdate, '-')}")
    except Exception as e:
        print(f"  PICTURE_READ_ERROR={e}")


# ---------------------------------------------------------------------------
# Table
# ---------------------------------------------------------------------------
def _print_table_details(sh, full: bool):
    try:
        tbl = sh.Table
        rows = int(_safe(lambda: tbl.Rows.Count, 0))
        cols = int(_safe(lambda: tbl.Columns.Count, 0))
        print(f"  TABLE: rows={rows}  cols={cols}")
        if full:
            for ri in range(1, rows + 1):
                for ci in range(1, cols + 1):
                    cell = _safe(lambda r=ri, c=ci: tbl.Cell(r, c), None)
                    if not cell:
                        continue
                    txt = _safe(lambda: cell.Shape.TextFrame.TextRange.Text, "")
                    merged = _safe(lambda: cell.Merged, "-")
                    print(f"    cell[{ri},{ci}]: text={txt!r} merged={merged}")
    except Exception as e:
        print(f"  TABLE_READ_ERROR={e}")


# ---------------------------------------------------------------------------
# Fill + Line + Shadow + 3D
# ---------------------------------------------------------------------------
def _print_fill_line(sh, full: bool):
    try:
        f = sh.Fill
        fcolor = _safe(lambda: f.ForeColor.RGB, "")
        print(f"  FILL: visible={_safe(lambda: f.Visible, '-')} "
              f"type={_safe(lambda: f.Type, '-')} "
              f"color=RGB({_rgb(fcolor) if fcolor != '' else '-'}) "
              f"transparency={_safe(lambda: f.Transparency, '-')}")
    except Exception:
        pass
    try:
        ln = sh.Line
        lcolor = _safe(lambda: ln.ForeColor.RGB, "")
        line_msg = (f"  LINE: visible={_safe(lambda: ln.Visible, '-')} "
                    f"weight={_safe(lambda: ln.Weight, '-')} "
                    f"color=RGB({_rgb(lcolor) if lcolor != '' else '-'})")
        if full:
            line_msg += (f"  Dash={_safe(lambda: ln.DashStyle, '-')}"
                         f"  Style={_safe(lambda: ln.Style, '-')}")
        print(line_msg)
    except Exception:
        pass
    if not full:
        return
    try:
        s = sh.Shadow
        print(f"  SHADOW: visible={_safe(lambda: s.Visible, '-')}"
              f"  type={_safe(lambda: s.Type, '-')}"
              f"  blur={_safe(lambda: s.Blur, '-')}"
              f"  offX={_safe(lambda: s.OffsetX, '-')}"
              f"  offY={_safe(lambda: s.OffsetY, '-')}"
              f"  transp={_safe(lambda: s.Transparency, '-')}")
    except Exception:
        pass
    try:
        td = sh.ThreeD
        td_visible = _safe(lambda: td.Visible, 0)
        if td_visible:
            print(f"  3D: visible={td_visible}"
                  f"  depth={_safe(lambda: td.Depth, '-')}"
                  f"  contour_w={_safe(lambda: td.ContourWidth, '-')}")
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Shape 主体
# ---------------------------------------------------------------------------
def _print_shape(sh, idx, full: bool):
    print(f"========== SHAPE {idx} ==========")
    name = _safe(lambda: sh.Name, "")
    typ = _safe(lambda: int(sh.Type), -1)
    typ_name = MSO_SHAPE_TYPE.get(typ, f"Unknown({typ})")
    print(f"  NAME={name!r}   （COM 内部名，和'选择窗格'的本地化显示可能不同）")
    print(f"  TYPE={typ}  ({typ_name})")
    print(f"  SHAPE_ID={_safe(lambda: sh.Id, '')}")
    print(f"  POSITION: Left={_safe(lambda: sh.Left, '')} "
          f"Top={_safe(lambda: sh.Top, '')} "
          f"Width={_safe(lambda: sh.Width, '')} "
          f"Height={_safe(lambda: sh.Height, '')}")
    print(f"  ROTATION={_safe(lambda: sh.Rotation, '')}")
    print(f"  Z_ORDER={_safe(lambda: sh.ZOrderPosition, '')}")
    print(f"  VISIBLE={_safe(lambda: sh.Visible, '')}")
    print(f"  HAS_TEXT_FRAME={_safe(lambda: int(sh.HasTextFrame), 0)}")
    print(f"  HAS_CHART={_safe(lambda: 1 if bool(sh.HasChart) else 0, 0)}")
    print(f"  HAS_TABLE={_safe(lambda: 1 if bool(sh.HasTable) else 0, 0)}")
    print(f"  AUTO_SHAPE_TYPE={_safe(lambda: sh.AutoShapeType, '')}")

    if int(_safe(lambda: sh.HasTextFrame, 0)):
        _print_text_details(sh, full)

    if _safe(lambda: bool(sh.HasChart), False):
        _print_chart_details(sh, full)

    if typ in (11, 13):  # Picture / LinkedPicture
        _print_picture_details(sh, full)

    if _safe(lambda: bool(sh.HasTable), False):
        _print_table_details(sh, full)

    if typ in (1, 17):  # AutoShape / TextBox
        _print_fill_line(sh, full)

    print()


def main(argv: list[str]):
    full = "--full" in argv

    try:
        app = win32com.client.GetActiveObject("PowerPoint.Application")
    except Exception as e:
        print(f"PPT_NOT_ACTIVE: {e}")
        return 1

    try:
        sel = app.ActiveWindow.Selection
        stype = int(sel.Type)
    except Exception as e:
        print(f"NO_SELECTION: {e}")
        return 1

    print(f"SELECTION_TYPE={stype} ({SELECTION_TYPE.get(stype, '?')})")
    print(f"MODE={'full' if full else 'compact'}  （--full 打开 run 级 / 阴影 / 3D / chart 详情）")
    if stype not in (2, 3):
        print("请先在 PPT 里选中一个或多个 shape 再运行。")
        return 0

    try:
        sr = sel.ShapeRange
        cnt = int(sr.Count)
    except Exception as e:
        print(f"NO_SHAPERANGE: {e}")
        return 1

    print(f"SHAPE_COUNT={cnt}")
    try:
        slide = app.ActiveWindow.View.Slide
        print(f"SLIDE_INDEX={_safe(lambda: slide.SlideIndex, '?')}")
    except Exception:
        pass
    print()

    for i in range(1, cnt + 1):
        _print_shape(sr.Item(i), i, full)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]) or 0)
