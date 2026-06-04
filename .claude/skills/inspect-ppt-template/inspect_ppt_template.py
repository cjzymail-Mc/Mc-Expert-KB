#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""inspect_ppt_template.py — 用 win32com COM 提取 .pptx 的结构信息。

任何 PPT 模板填充类项目的强制前置步骤。AI 不缺判断力，缺感知能力——
.pptx 是黑盒，AI 看不到 shape 内部名、母版三联水印的位置、布局继承关系。
这个脚本是被迫造的"探针"。

加密文件兼容：本机 Ldterm 透明加密 .pptx，对 win32com 启动的 POWERPNT.EXE 透明（白名单）。
Python 写出的 .json/.md 不会被反向加密。

注：docx 走 `inspect-word-template`（含染色三态分桶 + 占位符审计）；
    xlsx 走 `inspect-excel-template`。三者职责单一，命名规则统一。

Usage:
    # 文件模式（默认）：另起 PowerPoint 进程，ReadOnly 打开
    python inspect_ppt_template.py \\
        --pptx "path/to/template.pptx" \\
        --out-dir "path/to/output/"

    # 实时模式：桥接到正在运行的 PowerPoint（避开文件锁，可扫用户正在编辑的 ppt）
    python inspect_ppt_template.py --active --out-dir "out/"
    python inspect_ppt_template.py --active --pptx "path/to/x.pptx" --out-dir "out/"

    # 页面过滤：只扫指定 slide（用作"对比 page A vs page B+C"等场景）
    python inspect_ppt_template.py --pptx "x.pptx" --slides "12,13-14" --out-dir "out/"
    python inspect_ppt_template.py --active --slides "12-14" --out-dir "out/"

    # 全字段模式（--full）：展开 paragraph + run 级字体/字号/颜色/bold
    #   触发场景：模板里同 shape 内有多字号 / 多颜色 / 同段多 run 样式差异，
    #   默认 text-only 输出看不出来，需要 --full 才能让 AI 感知到这层结构。
    python inspect_ppt_template.py --active --slides "9" --full --out-dir "out/"

    （--pptx / --active 至少给一个；--active 默认扫 ActivePresentation）

Outputs:
    <out-dir>/inspect_report.json   # 给后续编 mapping 的程序消费
    <out-dir>/inspect_report.md     # 给人类阅读

硬规则:
- 用 try/except 读 COM 属性，不用 getattr（COM 对象 getattr 抛错）
- 文件模式：DispatchEx 强制新进程 + ReadOnly=True，finally 里 Quit() 防进程残留
- 实时模式：GetActiveObject 复用用户进程，**绝不 Quit / Close**，永不修改

历史：
- 2026-05-26 提为用户级 skill（原名 inspect-office-template，docx + pptx 一锅出）
- 2026-05-27 重命名 inspect-ppt-template，docx 处理代码剥离到 inspect-word-template
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")


# ---------- COM 安全访问 ----------
def safe(obj, attr, default=None):
    """COM 对象属性安全读取。"""
    try:
        return getattr(obj, attr)
    except Exception:
        return default


def text_of(shape):
    """读 PPT shape 的 TextFrame 文字。

    不依赖 HasText（实测在 ReadOnly 模式下假阴性），直接尝试读 Text。
    """
    if not bool(safe(shape, "HasTextFrame", False)):
        return ""
    try:
        return str(shape.TextFrame.TextRange.Text or "")
    except Exception:
        return ""


def trunc(s, n=80):
    if not s:
        return ""
    s = str(s).replace("\r", "↵").replace("\n", "↵").replace("\x07", "")
    return s if len(s) <= n else s[:n] + "..."


def extract_paragraphs(shape):
    """读 shape.TextFrame 的 Paragraphs / Runs 层级（保留 PPT 原始结构，不合并同属性 run）。

    与 ppt-acceptance-check 的 _walk_runs 不同：那个是**验收用** walker，按属性切割且合并相邻
    同属性 run；这个是**inspect 用**，忠实呈现 PPT 内部 paragraph.Runs() 结构，便于人审
    定位"哪段哪 run 是什么样式"。

    Returns: list[dict]，无文本框 / 取不到 paragraphs 时返回 []。
    每个 paragraph:
        {"index": 1, "text": "...", "alignment": int, "runs": [
            {"text": "...", "size": 11.0, "rgb": 16777215, "bold": -1, "italic": 0,
             "font_name": "微软雅黑"}, ...
        ]}
    """
    if not bool(safe(shape, "HasTextFrame", False)):
        return []
    try:
        tf = shape.TextFrame
        # 不依赖 HasText（ReadOnly 模式假阴性）
        tr = tf.TextRange
        para_count = int(safe(tr.Paragraphs(), "Count", 0) or 0)
    except Exception:
        return []
    if para_count <= 0:
        return []

    paragraphs = []
    for pi in range(1, para_count + 1):
        try:
            para = tr.Paragraphs(pi)
            ptext = str(safe(para, "Text", "") or "").rstrip("\r\n")
            try:
                palign = int(safe(para.ParagraphFormat, "Alignment", -1) or -1)
            except Exception:
                palign = -1
            runs = []
            try:
                run_count = int(safe(para.Runs(), "Count", 0) or 0)
            except Exception:
                run_count = 0
            for ri in range(1, run_count + 1):
                try:
                    r = para.Runs(ri)
                    rtext = str(safe(r, "Text", "") or "")
                    fnt = safe(r, "Font", None)
                    rgb = None
                    if fnt is not None:
                        try:
                            rgb = int(fnt.Color.RGB)
                        except Exception:
                            rgb = None
                    runs.append({
                        "text": rtext,
                        "size": safe(fnt, "Size", None) if fnt is not None else None,
                        "rgb": rgb,
                        "bold": safe(fnt, "Bold", None) if fnt is not None else None,
                        "italic": safe(fnt, "Italic", None) if fnt is not None else None,
                        "font_name": str(safe(fnt, "Name", "") or "") if fnt is not None else "",
                    })
                except Exception:
                    continue
            paragraphs.append({
                "index": pi,
                "text": ptext,
                "alignment": palign,
                "runs": runs,
            })
        except Exception:
            continue
    return paragraphs


def parse_slide_filter(spec):
    """解析 "1-5,8,10-12" → {1,2,3,4,5,8,10,11,12}。空串/None → None（=不过滤）。"""
    if spec is None or not str(spec).strip():
        return None
    out = set()
    for part in str(spec).split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            a, b = part.split("-", 1)
            out.update(range(int(a.strip()), int(b.strip()) + 1))
        else:
            out.add(int(part))
    return out


# ---------- PPTX 扫描 ----------
def inspect_pptx(path, slides_filter=None, use_active=False, with_runs=False):
    """扫 pptx 结构。

    Args:
        path: pptx 路径。use_active=True 时可选（None 则取 ActivePresentation）。
        slides_filter: set[int] | None。仅扫这些 slide_index；None=全扫。
        use_active: True=GetActiveObject 桥接正在运行的 PowerPoint（不 Quit）；
                    False=DispatchEx 新进程 + ReadOnly Open（兜底 Quit）。
        with_runs: True=每个 shape 多 dump 一份 paragraphs/runs 详情（size/rgb/bold/italic/font_name）
                   触发场景：同 shape 多字号 / 多颜色 / 同段多 run 的视觉契约调研。
                   默认 False（避免 JSON / MD 输出爆炸）。
    """
    import win32com.client as win32

    ppt = None
    pres = None
    opened_by_us = False  # 仅当 False 时跳过 Close/Quit（active 模式不能动用户进程）

    try:
        if use_active:
            try:
                ppt = win32.GetActiveObject("PowerPoint.Application")
            except Exception as e:
                raise RuntimeError(
                    f"--active 模式失败：未检测到运行中的 PowerPoint（{e}）。"
                    "请先打开目标 .pptx 再重试，或去掉 --active 走文件模式。"
                )
            if path:
                abs_target = os.path.abspath(str(path)).lower()
                pres_count = safe(ppt.Presentations, "Count", 0)
                for i in range(1, pres_count + 1):
                    p = ppt.Presentations(i)
                    full = str(safe(p, "FullName", "")).lower()
                    if full == abs_target:
                        pres = p
                        break
                if pres is None:
                    open_list = []
                    for i in range(1, pres_count + 1):
                        open_list.append(str(safe(ppt.Presentations(i), "FullName", "?")))
                    raise RuntimeError(
                        f"--active 找不到打开的 ppt: {path}\n  当前打开的有:\n  - "
                        + "\n  - ".join(open_list)
                    )
            else:
                try:
                    pres = ppt.ActivePresentation
                except Exception as e:
                    raise RuntimeError(f"--active 拿不到 ActivePresentation: {e}")
        else:
            ppt = win32.DispatchEx("PowerPoint.Application")
            try:
                ppt.DisplayAlerts = 0
            except Exception:
                pass
            pres = ppt.Presentations.Open(
                os.path.abspath(str(path)),
                ReadOnly=True,
                Untitled=False,
                WithWindow=False,
            )
            opened_by_us = True

        result = {
            "path": str(safe(pres, "FullName", path) or path),
            "mode": "active" if use_active else "open",
            "slides_filter": sorted(slides_filter) if slides_filter else None,
            "with_runs": bool(with_runs),
            "slide_count": 0,
            "slides": [],
            "slide_masters": [],
            "custom_layouts": [],
        }

        try:
            slide_count = safe(pres.Slides, "Count", 0)
            result["slide_count"] = slide_count

            for sn in range(1, slide_count + 1):
                if slides_filter is not None and sn not in slides_filter:
                    continue
                slide = pres.Slides(sn)
                shapes_info = []
                try:
                    shape_count = slide.Shapes.Count
                except Exception:
                    shape_count = 0
                for k in range(1, shape_count + 1):
                    try:
                        shp = slide.Shapes(k)
                    except Exception:
                        continue
                    name = safe(shp, "Name", f"?{k}")
                    stype = safe(shp, "Type", -1)
                    L = float(safe(shp, "Left", 0) or 0)
                    T = float(safe(shp, "Top", 0) or 0)
                    W = float(safe(shp, "Width", 0) or 0)
                    H = float(safe(shp, "Height", 0) or 0)
                    has_tf = bool(safe(shp, "HasTextFrame", False))
                    has_chart = bool(safe(shp, "HasChart", False))
                    text_preview = trunc(text_of(shp), 120)
                    sh_entry = {
                        "shape_index": k,
                        "name": str(name) if name is not None else "",
                        "type": int(stype) if isinstance(stype, int) else -1,
                        "geometry": {
                            "L": round(L, 1),
                            "T": round(T, 1),
                            "W": round(W, 1),
                            "H": round(H, 1),
                        },
                        "has_text_frame": has_tf,
                        "has_chart": has_chart,
                        "text": text_preview,
                    }
                    if with_runs and has_tf:
                        sh_entry["paragraphs"] = extract_paragraphs(shp)
                    shapes_info.append(sh_entry)
                result["slides"].append({
                    "slide_index": sn,
                    "shape_count": shape_count,
                    "shapes": shapes_info,
                })

            master_count = 0
            masters_obj = None
            try:
                masters_obj = pres.SlideMasters
                master_count = masters_obj.Count
            except Exception as e:
                print(f"  [warn] SlideMasters 不可访问: {e}")
            for mi in range(1, master_count + 1):
                master = masters_obj(mi)
                master_shapes = []
                try:
                    msh_count = master.Shapes.Count
                except Exception:
                    msh_count = 0
                for k in range(1, msh_count + 1):
                    try:
                        shp = master.Shapes(k)
                    except Exception:
                        continue
                    master_shapes.append({
                        "shape_index": k,
                        "name": str(safe(shp, "Name", f"?{k}")),
                        "type": int(safe(shp, "Type", -1) or -1),
                        "text": trunc(text_of(shp), 120),
                    })
                result["slide_masters"].append({
                    "master_index": mi,
                    "shapes": master_shapes,
                })

                try:
                    layout_count = master.CustomLayouts.Count
                except Exception:
                    layout_count = 0
                for li in range(1, layout_count + 1):
                    layout = master.CustomLayouts(li)
                    lay_shapes = []
                    try:
                        lsh_count = layout.Shapes.Count
                    except Exception:
                        lsh_count = 0
                    for k in range(1, lsh_count + 1):
                        try:
                            shp = layout.Shapes(k)
                        except Exception:
                            continue
                        txt = trunc(text_of(shp), 100)
                        if not txt:
                            continue
                        lay_shapes.append({
                            "name": str(safe(shp, "Name", f"?{k}")),
                            "text": txt,
                        })
                    if lay_shapes:
                        result["custom_layouts"].append({
                            "master_index": mi,
                            "layout_index": li,
                            "name": str(safe(layout, "Name", "")),
                            "shapes_with_text": lay_shapes,
                        })
        finally:
            if opened_by_us and pres is not None:
                try:
                    pres.Close()
                except Exception:
                    pass
    finally:
        if opened_by_us and ppt is not None:
            try:
                ppt.Quit()
            except Exception:
                pass

    return result


# ---------- 报告渲染 ----------
def write_md_report(pptx_data, md_path):
    md = []
    md.append("# PPT Inspect 报告\n")
    md.append("> 由 `inspect-ppt-template` skill 生成。\n")
    md.append("> 用于写 `template_mapping.py` / `*_mapping.json` 时定位 pptx shape names。\n\n")

    md.append(f"## PPTX: `{pptx_data['path']}`\n")
    mode = pptx_data.get("mode", "open")
    slides_filter = pptx_data.get("slides_filter")
    md.append(f"- 模式：`{mode}`（active=桥接运行中 PowerPoint / open=ReadOnly 新进程）")
    md.append(f"- 总页数：{pptx_data['slide_count']}")
    if slides_filter:
        md.append(f"- 页面过滤：`{slides_filter}`（仅扫这些 slide）")
    md.append("")

    with_runs = bool(pptx_data.get("with_runs"))

    def _rgb_hex(v):
        if v is None:
            return "?"
        try:
            n = int(v)
            r = n & 0xFF
            g = (n >> 8) & 0xFF
            b = (n >> 16) & 0xFF
            return f"#{r:02X}{g:02X}{b:02X}"
        except Exception:
            return str(v)

    for s in pptx_data["slides"]:
        md.append(f"### Slide {s['slide_index']}（{s['shape_count']} shapes）\n")
        md.append("| idx | name | type | text? | chart? | L/T/W/H | text 预览 |")
        md.append("|-----|------|------|-------|--------|---------|----------|")
        for sh in s["shapes"]:
            g = sh["geometry"]
            geom = f"{g['L']:.0f}/{g['T']:.0f}/{g['W']:.0f}/{g['H']:.0f}"
            tf_flag = "✓" if sh["has_text_frame"] else ""
            ch_flag = "✓" if sh["has_chart"] else ""
            md.append(f"| {sh['shape_index']} | `{sh['name']}` | {sh['type']} | {tf_flag} | {ch_flag} | {geom} | {sh['text']} |")
        md.append("")

        if with_runs:
            # 紧跟 shape 表格输出 paragraph / run 详情（仅含 paragraphs 非空的 shape）
            detail_lines = []
            for sh in s["shapes"]:
                paras = sh.get("paragraphs") or []
                if not paras:
                    continue
                detail_lines.append(f"- `{sh['name']}` (idx={sh['shape_index']}, paragraphs={len(paras)}):")
                for p in paras:
                    p_run_count = len(p.get("runs") or [])
                    p_text = trunc(p.get("text", ""), 60)
                    detail_lines.append(
                        f"  - p{p['index']} align={p.get('alignment','?')} runs={p_run_count}: \"{p_text}\""
                    )
                    for r in p.get("runs") or []:
                        rgb_hex = _rgb_hex(r.get("rgb"))
                        size = r.get("size")
                        size_s = f"{float(size):.1f}pt" if size is not None else "?"
                        bold = r.get("bold")
                        bold_s = "B" if bold == -1 else "" if bold == 0 else f"B={bold}"
                        italic = r.get("italic")
                        italic_s = "I" if italic == -1 else ""
                        fname = r.get("font_name", "")
                        flags = "/".join(x for x in [bold_s, italic_s] if x)
                        flag_part = f" {flags}" if flags else ""
                        font_part = f" font={fname}" if fname else ""
                        r_text = trunc(r.get("text", ""), 40)
                        detail_lines.append(
                            f"    - {size_s} {rgb_hex}{flag_part}{font_part}: \"{r_text}\""
                        )
            if detail_lines:
                md.append("**Run-level detail（--full 模式）：**\n")
                md.extend(detail_lines)
                md.append("")

    if pptx_data["slide_masters"]:
        md.append("## SlideMasters（页脚三联水印通常在母版）\n")
        for m in pptx_data["slide_masters"]:
            md.append(f"### Master {m['master_index']}\n")
            md.append("| idx | name | type | text |")
            md.append("|-----|------|------|------|")
            for sh in m["shapes"]:
                md.append(f"| {sh['shape_index']} | `{sh['name']}` | {sh['type']} | {sh['text']} |")
            md.append("")

    if pptx_data["custom_layouts"]:
        md.append("## CustomLayouts（仅列含文字的 shape）\n")
        md.append("| master | layout | layout_name | shapes |")
        md.append("|--------|--------|-------------|--------|")
        for cl in pptx_data["custom_layouts"]:
            shapes_str = " / ".join(f"`{sh['name']}`=`{sh['text']}`" for sh in cl["shapes_with_text"][:5])
            md.append(f"| {cl['master_index']} | {cl['layout_index']} | {cl['name']} | {shapes_str} |")
        md.append("")

    Path(md_path).write_text("\n".join(md), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pptx", default="",
                        help="PPT 模板路径（可选）。--active 模式下若省略则取 ActivePresentation。")
    parser.add_argument("--active", action="store_true",
                        help="实时模式：用 GetActiveObject 桥接正在运行的 PowerPoint，"
                             "避开文件锁，可扫用户正在编辑的 ppt（不会 Quit 用户进程）。")
    parser.add_argument("--slides", default="",
                        help="只扫指定 slide。语法：'1-5,8,10-12'。")
    parser.add_argument("--full", action="store_true",
                        help="全字段模式：每个 shape 多 dump paragraph + run 级字段（size / rgb / bold / italic / font_name）。"
                             "默认 off 以避免输出爆炸。同 shape 多字号/多颜色调研时必开。")
    parser.add_argument("--out-dir", required=True, help="输出目录")
    args = parser.parse_args()

    if not args.pptx and not args.active:
        print("[ERR] --pptx / --active 至少要提供一个")
        return 1

    try:
        slides_filter = parse_slide_filter(args.slides)
    except ValueError as e:
        print(f"[ERR] --slides 解析失败: {e}（示例: --slides '1-5,8,10-12'）")
        return 1

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    mode_tag = "ACTIVE" if args.active else "OPEN"
    target = args.pptx or "(ActivePresentation)"
    filter_tag = f" slides={sorted(slides_filter)}" if slides_filter else ""
    full_tag = " --full" if args.full else ""
    print(f"[inspect] PPTX[{mode_tag}]: {target}{filter_tag}{full_tag}")
    pptx_data = inspect_pptx(
        args.pptx or None,
        slides_filter=slides_filter,
        use_active=args.active,
        with_runs=args.full,
    )
    scanned = len(pptx_data["slides"])
    total = pptx_data["slide_count"]
    print(f"  → 扫描 {scanned}/{total} slides，masters {len(pptx_data['slide_masters'])}")

    json_path = out_dir / "inspect_report.json"
    md_path = out_dir / "inspect_report.md"
    json_path.write_text(
        json.dumps({"pptx": pptx_data}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    write_md_report(pptx_data, md_path)

    print(f"\n[inspect] 完成")
    print(f"  JSON: {json_path}")
    print(f"  MD:   {md_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
