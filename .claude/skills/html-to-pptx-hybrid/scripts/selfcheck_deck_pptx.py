# -*- coding: utf-8 -*-
"""pptx 自检：win32com 重开（复制到 temp 再开，避路径 [ ] 与就地写扰动）逐页对比 manifest。
用法: py -3 -X utf8 selfcheck_deck_pptx.py <out.pptx> <manifest.json> [--slides 1-3]
检查项：页数 / 每页元素配对（按全文不截断匹配，C-8 警告）/ 坐标偏差≤3pt / 表格行列与单元格文本。
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

from deck_common import SX, SY

TOL_PT = 3.0


def norm(s):
    return " ".join(str(s).replace("\r", "\n").split())


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
    ap.add_argument("pptx")
    ap.add_argument("manifest")
    ap.add_argument("--slides", default="")
    args = ap.parse_args()

    manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
    only = parse_slide_range(args.slides)
    expected_slides = [s for s in manifest["slides"] if (only is None or s["index"] in only)]

    src = Path(args.pptx).resolve()
    tmp = Path(tempfile.gettempdir()) / f"__tmp_check_{os.getpid()}.pptx"
    shutil.copy(str(src), str(tmp))

    problems = []
    app = win32.Dispatch("PowerPoint.Application")
    pres = app.Presentations.Open(str(tmp), -1, 0, 0)  # ReadOnly, WithWindow=False
    try:
        if pres.Slides.Count != len(expected_slides):
            problems.append(f"页数 {pres.Slides.Count} != 期望 {len(expected_slides)}")
        for pos in range(1, min(pres.Slides.Count, len(expected_slides)) + 1):
            sd = expected_slides[pos - 1]
            slide = pres.Slides(pos)
            # 收集实际 shape：文本框 / 表格 / 图片
            actual_texts, actual_tables, n_pics = [], [], 0
            for i in range(1, slide.Shapes.Count + 1):
                shp = slide.Shapes(i)
                if shp.HasTable:
                    actual_tables.append(shp)
                elif shp.Type == 13:  # msoPicture
                    n_pics += 1
                else:
                    try:
                        if shp.HasTextFrame and shp.TextFrame.HasText:
                            # 全文读取，不截断（坑警告）
                            actual_texts.append((shp, norm(shp.TextFrame.TextRange.Text)))
                    except Exception:
                        pass
            if n_pics != 1:
                problems.append(f"p{sd['index']}: 截图层图片数 {n_pics} != 1")

            exp_texts = [e for e in sd["elements"] if e["type"] in ("text", "bullets")]
            exp_tables = [e for e in sd["elements"] if e["type"] == "table"]
            if len(actual_tables) != len(exp_tables):
                problems.append(f"p{sd['index']}: 表格数 {len(actual_tables)} != {len(exp_tables)}")
            used = set()
            for e in exp_texts:
                if e["type"] == "text":
                    want = norm(e["text"])
                else:
                    want = norm("\n".join(it["text"] for it in e["items"]))
                hit = None
                for j, (shp, txt) in enumerate(actual_texts):
                    if j in used:
                        continue
                    if txt == want:
                        hit = j
                        break
                if hit is None:
                    problems.append(f"p{sd['index']}: 缺文本元素 [{want[:40]}…]")
                    continue
                used.add(hit)
                shp = actual_texts[hit][0]
                dx = abs(shp.Left - e["x"] * SX)
                dy = abs(shp.Top - e["y"] * SY)
                if dx > TOL_PT or dy > TOL_PT:
                    problems.append(
                        f"p{sd['index']}: [{want[:24]}…] 坐标偏差 dx={dx:.1f} dy={dy:.1f} pt")
            extra = len(actual_texts) - len(used)
            if extra:
                leftovers = [t[:30] for j, (_, t) in enumerate(actual_texts) if j not in used]
                problems.append(f"p{sd['index']}: 多出 {extra} 个文本元素 {leftovers}")
            for shp, e in zip(actual_tables, exp_tables):
                tbl = shp.Table
                if tbl.Rows.Count != len(e["rows"]):
                    problems.append(f"p{sd['index']}: 表行数 {tbl.Rows.Count} != {len(e['rows'])}")
                    continue
                for ri, row in enumerate(e["rows"], 1):
                    for ci, cell_data in enumerate(row, 1):
                        got = norm(tbl.Cell(ri, ci).Shape.TextFrame.TextRange.Text)
                        if got != norm(cell_data["text"]):
                            problems.append(
                                f"p{sd['index']}: 表({ri},{ci}) '{got[:20]}' != '{norm(cell_data['text'])[:20]}'")
                dx = abs(shp.Left - e["x"] * SX)
                dy = abs(shp.Top - e["y"] * SY)
                if dx > TOL_PT or dy > TOL_PT:
                    problems.append(f"p{sd['index']}: 表格坐标偏差 dx={dx:.1f} dy={dy:.1f} pt")
    finally:
        try:
            pres.Close()
        except Exception:
            pass
        try:
            app.Quit()
        except Exception:
            pass
        try:
            tmp.unlink()
        except Exception:
            pass

    if problems:
        print(f"FAIL ({len(problems)} 项):")
        for p in problems:
            print(" -", p)
        sys.exit(1)
    print(f"PASS: {len(expected_slides)} 页全部通过（元素配对/坐标≤{TOL_PT}pt/表格单元格）")


if __name__ == "__main__":
    main()
