#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""inspect_excel_template.py — 用 win32com COM 提取 .xlsx / .xls 的结构信息。

任何 AI 要理解源 Excel 数据结构的场景的强制前置步骤。AI 看不到
sheet 名 / 列名 / 单元格格式，必须先扫一次再决定读取策略。

加密文件兼容：本机 Ldterm 透明加密 .xlsx，对 win32com 启动的 EXCEL.EXE 透明。

Usage:
    # 文件模式（默认）：另起 Excel 进程，ReadOnly 打开
    python inspect_excel_template.py \\
        --xlsx "path/to/source.xlsx" \\
        --out-dir "path/to/output/"

    # 实时模式：桥接到正在运行的 Excel（避开文件锁，可扫用户正在编辑的 xlsx）
    python inspect_excel_template.py --active --out-dir "out/"
    python inspect_excel_template.py --active --xlsx "path/to/x.xlsx" --out-dir "out/"

    # sheet 关键词过滤（模糊子串匹配 + 多关键词逗号分隔，OR 语义）
    python inspect_excel_template.py --xlsx "x.xlsx" --sheets "问卷,跑量" --out-dir "out/"

    # 自定义预览行数（默认 5）
    python inspect_excel_template.py --xlsx "x.xlsx" --preview-rows 10 --out-dir "out/"

    （--xlsx / --active 至少给一个；--active 默认扫 ActiveWorkbook）

Outputs:
    <out-dir>/inspect_excel_report.json   # 给后续编 mapping 的程序消费
    <out-dir>/inspect_excel_report.md     # 给人类阅读

硬规则:
- 用 try/except 读 COM 属性（复用 office-com-helpers 的 com_get）
- 文件模式：DispatchEx 强制新进程 + ReadOnly=True，finally 里 Quit() 防进程残留
- 实时模式：GetActiveObject 复用用户进程，**绝不 Quit / Close**，永不修改
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

# 复用 office-com-helpers（sibling skill 目录）
_HELPERS_DIR = Path(__file__).resolve().parent.parent / "office-com-helpers"
if _HELPERS_DIR.exists() and str(_HELPERS_DIR) not in sys.path:
    sys.path.insert(0, str(_HELPERS_DIR))
try:
    from office_com_helpers import safe_print, com_get, to_rows, safe_text
except ImportError as e:
    print(f"[ERR] 找不到 office_com_helpers (expected at {_HELPERS_DIR}): {e}")
    sys.exit(1)


# ---------- 工具 ----------
def trunc(s, n=80):
    if s is None or s == "":
        return ""
    s = str(s).replace("\r", "↵").replace("\n", "↵").replace("\x07", "")
    return s if len(s) <= n else s[:n] + "..."


def parse_sheet_filter(spec):
    """解析 "问卷,跑量" → ["问卷","跑量"]。空 → None（=不过滤）。"""
    if spec is None or not str(spec).strip():
        return None
    return [k.strip() for k in str(spec).split(",") if k.strip()]


def sheet_matches(name, keywords):
    """关键词 OR 语义子串匹配。keywords=None → 全通过。"""
    if keywords is None:
        return True
    return any(kw in name for kw in keywords)


def _is_blank(v):
    """单元格是否视作空。None / "" / 仅空白字符 都算空。"""
    if v is None:
        return True
    s = str(v).strip()
    return s == "" or s == "\x07"


def detect_stray_cells(rows_data, max_preview=20):
    """检测 used_range 内但主数据块外的"孤岛"非空单元格。

    主数据块判定策略（保守、可解释）：
      - 主块列宽 main_cols = 第 1 行从 A1 起连续非空的列数
      - 主块行高 main_rows = 主块列宽范围内连续非空行的行数
      - 主块 = 行 [1..main_rows] × 列 [1..main_cols]

    Stray = 在 used_range 内但主块外的非空单元格（典型场景：上一轮跑脚本的临时数据，
    把 used_range 撑大了，但主数据区还是原来的；下次跑前清掉这些 stray 能避免污染）。

    Args:
        rows_data: List[List[Any]]，UsedRange.Value 经 to_rows 归一化后的二维数组
        max_preview: stray 单元格预览上限（避免 noise）

    Returns:
        dict {
            "main_block": "$A$1:$AJ$10" 或 "" （主块不可判定时空串）,
            "main_rows": int,
            "main_cols": int,
            "stray_count": int,
            "stray_preview": [{"address": "AK5", "row": 5, "col": 37, "value": "..."}],
            "note": str,
        }
    """
    info = {
        "main_block": "",
        "main_rows": 0,
        "main_cols": 0,
        "stray_count": 0,
        "stray_preview": [],
        "note": "",
    }

    if not rows_data:
        return info

    n_rows = len(rows_data)
    n_cols = max((len(r) if isinstance(r, (list, tuple)) else 0 for r in rows_data), default=0)
    if n_rows == 0 or n_cols == 0:
        return info

    # 主块列宽：第 1 行 A1 起连续非空列数
    first_row = rows_data[0] if isinstance(rows_data[0], (list, tuple)) else []
    main_cols = 0
    for ci in range(len(first_row)):
        if _is_blank(first_row[ci]):
            break
        main_cols = ci + 1
    if main_cols == 0:
        info["note"] = "第 1 行 A1 为空，无法判定主块（跳过 stray 检测）"
        return info

    # 主块行高：在 main_cols 范围内连续非空行
    main_rows = 0
    for ri in range(n_rows):
        row = rows_data[ri] if isinstance(rows_data[ri], (list, tuple)) else []
        row_cells = row[:main_cols]
        if any(not _is_blank(c) for c in row_cells):
            main_rows = ri + 1
        else:
            break

    info["main_rows"] = main_rows
    info["main_cols"] = main_cols
    if main_rows > 0 and main_cols > 0:
        info["main_block"] = f"$A$1:${col_letter(main_cols)}${main_rows}"

    # 扫 stray：used_range 内但主块外的非空单元格
    stray_count = 0
    preview = []
    for ri in range(n_rows):
        row = rows_data[ri] if isinstance(rows_data[ri], (list, tuple)) else []
        for ci in range(n_cols):
            in_main = (ri < main_rows) and (ci < main_cols)
            if in_main:
                continue
            cell = row[ci] if ci < len(row) else None
            if not _is_blank(cell):
                stray_count += 1
                if len(preview) < max_preview:
                    preview.append({
                        "address": f"{col_letter(ci + 1)}{ri + 1}",
                        "row": ri + 1,
                        "col": ci + 1,
                        "value": trunc(str(cell), 60),
                    })

    info["stray_count"] = stray_count
    info["stray_preview"] = preview
    if stray_count > 0:
        info["note"] = (
            f"⚠️ used_range 比主块大，有 {stray_count} 个非空单元格落在主块外——"
            "极可能是上一轮跑脚本残留的临时数据。下次跑前清掉这些单元格可避免污染。"
        )
    return info


def scan_blanks(ws, used, rows_data, max_list=200, cell_cap=20000):
    """空值（待填）单元格扫描（--blanks 薄层）。

    设计要点（避免 COM storm —— 旧会话卡死根因就是逐格 COM 遍历）：
      - 空/非空判定走 `rows_data`（used.Value 已 bulk 一次性取，纯 Python 快）。
      - **仅对"候选空格"逐个探 `MergeCells`**：合并填充区只有主格(左上)在
        used.Value 里有值，成员格返回 None → bulk 判空会把它误判为空（虚高）。
        只有探 merge 才能纠正。已填实格不探（省 COM）。
      - 合并区按主格(左上)只记一次，成员格 continue，防计数虚高。
      - 总格数超 cell_cap 时退化为纯 bulk 判空（不探 merge），加 note 说明风险。

    不读 Interior.Color（路线 (b) 空值驱动，不依赖染色）。

    Returns:
        dict {
            "blank": int, "filled": int, "merged_blank": int,
            "cells": [{"address": "B7", "merged": bool}],  # 仅收空格，截断 max_list
            "truncated": bool, "note": str,
        }
    """
    info = {"blank": 0, "filled": 0, "merged_blank": 0,
            "cells": [], "truncated": False, "note": ""}
    if not rows_data:
        return info

    try:
        r0 = int(com_get(used, "Row", 1) or 1)       # UsedRange 起始行(可能非 1)
        c0 = int(com_get(used, "Column", 1) or 1)    # UsedRange 起始列(可能非 A)
    except Exception:
        r0, c0 = 1, 1

    n_rows = len(rows_data)
    n_cols = max((len(r) if isinstance(r, (list, tuple)) else 0 for r in rows_data), default=0)
    total_cells = n_rows * n_cols

    # 退化路径：太大不探 merge，纯 bulk 判空（避免 COM storm）
    if total_cells > cell_cap:
        for row in rows_data:
            for v in (row if isinstance(row, (list, tuple)) else []):
                if _is_blank(v):
                    info["blank"] += 1
                else:
                    info["filled"] += 1
        info["note"] = (
            f"UsedRange 单元格数 {total_cells} 超阈值 {cell_cap}，跳过合并格探测——"
            "空值计数可能含合并填充区成员格虚高（仅供量级参考）。"
        )
        return info

    merge_resolved = set()  # 已结算的合并区主格 (r,c)；防成员格重复计

    for i in range(n_rows):
        row = rows_data[i] if isinstance(rows_data[i], (list, tuple)) else []
        for j in range(n_cols):
            ar, ac = r0 + i, c0 + j           # 真实 1-based 行列(含 UsedRange 偏移)
            v = row[j] if j < len(row) else None
            if not _is_blank(v):
                info["filled"] += 1           # 实填格直接计，不探 merge(主格在此)
                continue
            # 候选空格 → 探 merge（成员格虚高的唯一纠正手段）
            cell = None
            is_merged = False
            try:
                cell = ws.Cells(ar, ac)
                is_merged = bool(com_get(cell, "MergeCells", False))
            except Exception:
                is_merged = False
            if not is_merged:
                info["blank"] += 1
                if len(info["cells"]) < max_list:
                    info["cells"].append({"address": f"{col_letter(ac)}{ar}", "merged": False})
                continue
            # 合并空格：定位主格(左上)
            try:
                marea = cell.MergeArea
                mr = int(com_get(marea, "Row", ar) or ar)
                mc = int(com_get(marea, "Column", ac) or ac)
            except Exception:
                mr, mc = ar, ac
            if (mr, mc) in merge_resolved:
                continue                       # 该合并区已结算
            merge_resolved.add((mr, mc))
            if (mr, mc) == (ar, ac):
                # 主格本身就是当前空格 → 整个合并区为空 → 记一次
                info["blank"] += 1
                info["merged_blank"] += 1
                if len(info["cells"]) < max_list:
                    info["cells"].append({"address": f"{col_letter(mc)}{mr}", "merged": True})
            # else: 主格在别处且已处理过——若主格空它早入 merge_resolved 不会到这；
            #       故主格必为实填(已计 filled)，当前成员格不再计。直接略过。

    if len(info["cells"]) >= max_list:
        info["truncated"] = True
    return info


# ---------- XLSX 扫描 ----------
# Sheet 类型常量（Excel COM）
XL_WORKSHEET = -4167   # xlWorksheet
XL_CHART = -4109       # xlChart
XL_DIALOG_SHEET = -4116
XL_EXCEL4_MACRO = 3
XL_EXCEL4_INTL_MACRO = 4

# Visible 常量
XL_SHEET_VISIBLE = -1
XL_SHEET_HIDDEN = 0
XL_SHEET_VERY_HIDDEN = 2


def visible_label(v):
    return {
        XL_SHEET_VISIBLE: "visible",
        XL_SHEET_HIDDEN: "hidden",
        XL_SHEET_VERY_HIDDEN: "very_hidden",
    }.get(v, f"?{v}")


def inspect_xlsx(path, sheets_filter=None, use_active=False, preview_rows=5,
                 scan_blanks_flag=False):
    """扫 xlsx 结构。

    Args:
        path: xlsx 路径。use_active=True 时可选（None 则取 ActiveWorkbook）。
        sheets_filter: list[str] | None。关键词列表，OR 语义子串匹配。
        use_active: True=GetActiveObject 桥接正在运行的 Excel（不 Quit）；
                    False=DispatchEx 新进程 + ReadOnly Open（兜底 Quit）。
        preview_rows: 每 sheet 预览数据行数（不含表头）。
        scan_blanks_flag: True 时追加空值（待填）单元格薄层扫描（--blanks）。
                          False 时输出与历史 100% 一致（向后兼容）。
    """
    import win32com.client as win32

    excel = None
    wb = None
    opened_by_us = False  # 仅当 True 时关闭/退出（active 模式不能动用户进程）

    try:
        if use_active:
            try:
                excel = win32.GetActiveObject("Excel.Application")
            except Exception as e:
                raise RuntimeError(
                    f"--active 模式失败：未检测到运行中的 Excel ({e})。"
                    "请先打开目标 .xlsx 再重试，或去掉 --active 走文件模式。"
                )
            if path:
                abs_target = os.path.abspath(str(path)).lower()
                wb_count = com_get(excel.Workbooks, "Count", 0)
                for i in range(1, wb_count + 1):
                    w = excel.Workbooks(i)
                    full = str(com_get(w, "FullName", "")).lower()
                    if full == abs_target:
                        wb = w
                        break
                if wb is None:
                    open_list = []
                    for i in range(1, wb_count + 1):
                        open_list.append(str(com_get(excel.Workbooks(i), "FullName", "?")))
                    raise RuntimeError(
                        f"--active 找不到打开的 xlsx: {path}\n  当前打开的:\n  - "
                        + "\n  - ".join(open_list)
                    )
            else:
                try:
                    wb = excel.ActiveWorkbook
                except Exception as e:
                    raise RuntimeError(f"--active 拿不到 ActiveWorkbook: {e}")
                if wb is None:
                    raise RuntimeError("--active 模式：Excel 已开但没有 ActiveWorkbook（可能只有空白窗口）")
        else:
            excel = win32.DispatchEx("Excel.Application")
            try:
                excel.Visible = False
            except Exception:
                pass
            try:
                excel.DisplayAlerts = False
            except Exception:
                pass
            wb = excel.Workbooks.Open(
                os.path.abspath(str(path)),
                0,      # UpdateLinks
                True,   # ReadOnly
            )
            opened_by_us = True

        result = {
            "path": str(com_get(wb, "FullName", path) or path),
            "mode": "active" if use_active else "open",
            "sheets_filter": sheets_filter,
            "preview_rows": preview_rows,
            "scan_blanks": scan_blanks_flag,
            "sheet_count_total": 0,
            "sheets_scanned": 0,
            "sheets": [],
        }
        if scan_blanks_flag:
            result["summary"] = {"blanks": {"blank": 0, "filled": 0, "merged_blank": 0}}

        try:
            sheet_count = com_get(wb.Sheets, "Count", 0)
            result["sheet_count_total"] = sheet_count

            for si in range(1, sheet_count + 1):
                try:
                    sh = wb.Sheets(si)
                except Exception:
                    continue
                name = str(com_get(sh, "Name", f"?{si}"))
                if not sheet_matches(name, sheets_filter):
                    continue

                sh_type = com_get(sh, "Type", -1)
                is_worksheet = (sh_type == XL_WORKSHEET)
                sheet_info = {
                    "sheet_index": si,
                    "name": name,
                    "type": sh_type,
                    "type_label": "worksheet" if is_worksheet else (
                        "chart" if sh_type == XL_CHART else f"other({sh_type})"
                    ),
                    "visible": com_get(sh, "Visible", -1),
                    "visible_label": visible_label(com_get(sh, "Visible", -1)),
                    "used_range": "",
                    "rows": 0,
                    "cols": 0,
                    "header_row": [],
                    "preview": [],
                    "stray": None,  # 由 detect_stray_cells 填充
                    "note": "",
                }

                if not is_worksheet:
                    sheet_info["note"] = "非 Worksheet（chart/macro/dialog），跳过 UsedRange"
                    result["sheets"].append(sheet_info)
                    continue

                # UsedRange 元数据
                try:
                    used = sh.UsedRange
                    sheet_info["used_range"] = str(com_get(used, "Address", ""))
                    sheet_info["rows"] = int(com_get(used.Rows, "Count", 0) or 0)
                    sheet_info["cols"] = int(com_get(used.Columns, "Count", 0) or 0)
                except Exception as e:
                    sheet_info["note"] = f"UsedRange 读取失败: {e}"
                    result["sheets"].append(sheet_info)
                    continue

                # 表头 + 数据预览
                try:
                    raw = used.Value
                except Exception as e:
                    sheet_info["note"] = f"UsedRange.Value 读取失败: {e}"
                    result["sheets"].append(sheet_info)
                    continue

                rows_data = to_rows(raw)
                if rows_data:
                    first = rows_data[0]
                    sheet_info["header_row"] = [trunc(safe_text(v), 40) for v in first]
                    for r in rows_data[1: preview_rows + 1]:
                        sheet_info["preview"].append([trunc(safe_text(v), 60) for v in r])
                    # stray cells 检测（used_range 外脏数据）
                    sheet_info["stray"] = detect_stray_cells(rows_data)
                else:
                    sheet_info["note"] = "sheet 为空"

                # 空值（待填）薄层扫描（--blanks）
                if scan_blanks_flag:
                    bl = scan_blanks(sh, used, rows_data)
                    sheet_info["blank_summary"] = {
                        "blank": bl["blank"],
                        "filled": bl["filled"],
                        "merged_blank": bl["merged_blank"],
                    }
                    if bl["note"]:
                        sheet_info["blank_summary"]["note"] = bl["note"]
                    sheet_info["blank_cells"] = bl["cells"]
                    sheet_info["blank_cells_truncated"] = bl["truncated"]
                    agg = result["summary"]["blanks"]
                    agg["blank"] += bl["blank"]
                    agg["filled"] += bl["filled"]
                    agg["merged_blank"] += bl["merged_blank"]

                result["sheets"].append(sheet_info)

            result["sheets_scanned"] = len(result["sheets"])
        finally:
            if opened_by_us and wb is not None:
                try:
                    wb.Close(False)
                except Exception:
                    pass
    finally:
        if opened_by_us and excel is not None:
            try:
                excel.Quit()
            except Exception:
                pass

    return result


# ---------- 报告渲染 ----------
def write_md_report(data, md_path):
    md = []
    md.append("# Excel Inspect 报告\n")
    md.append("> 由 `inspect-excel-template` skill 生成。\n")
    md.append("> 用于定位源 Excel 的 sheet 名 / 列名 / 数据格式，决定 `load_excel_rows` 等读取策略。\n\n")

    md.append(f"## 文件: `{data['path']}`\n")
    md.append(f"- 模式：`{data['mode']}`（active=桥接运行中 Excel / open=ReadOnly 新进程）")
    md.append(f"- 总 sheet 数：{data['sheet_count_total']}")
    md.append(f"- 扫描 sheet 数：{data['sheets_scanned']}")
    if data.get("sheets_filter"):
        md.append(f"- sheet 关键词过滤：`{data['sheets_filter']}`（OR 语义子串匹配）")
    md.append(f"- 预览行数上限：{data['preview_rows']}")
    if data.get("scan_blanks") and data.get("summary", {}).get("blanks"):
        b = data["summary"]["blanks"]
        total = b["blank"] + b["filled"]
        ratio = f"{(b['blank'] / total * 100):.1f}%" if total else "n/a"
        md.append(
            f"- 空值扫描（--blanks）：空 **{b['blank']}** / 已填 {b['filled']} "
            f"（空格占比 {ratio}；其中合并空格 {b['merged_blank']}）"
        )
    md.append("")

    md.append("## Sheet 索引（按物理顺序；用作 `wb.Sheets(N)` / `wb.Sheets('name')` 定位）\n")
    md.append("| # | name | type | visible | rows × cols | used_range | stray? |")
    md.append("|---|------|------|---------|-------------|-----------|--------|")
    for s in data["sheets"]:
        rc = f"{s['rows']} × {s['cols']}" if s['rows'] else "-"
        stray_info = s.get("stray") or {}
        stray_count = stray_info.get("stray_count", 0)
        stray_flag = f"⚠️ {stray_count}" if stray_count > 0 else "-"
        md.append(
            f"| {s['sheet_index']} | `{s['name']}` | {s['type_label']} | "
            f"{s['visible_label']} | {rc} | `{s['used_range']}` | {stray_flag} |"
        )
    md.append("")

    for s in data["sheets"]:
        md.append(f"### Sheet {s['sheet_index']}: `{s['name']}`\n")
        md.append(f"- type: `{s['type_label']}` (Type={s['type']})")
        md.append(f"- visible: `{s['visible_label']}`")
        md.append(f"- used_range: `{s['used_range']}`  ({s['rows']} 行 × {s['cols']} 列)")
        if s["note"]:
            md.append(f"- note: {s['note']}")
        md.append("")

        if s["header_row"]:
            md.append("**表头（第 1 行；列名清单）**：\n")
            md.append("| col # | Excel 列字母 | 列名 |")
            md.append("|-------|-------------|------|")
            for i, h in enumerate(s["header_row"], 1):
                md.append(f"| {i} | {col_letter(i)} | {h} |")
            md.append("")

        if s["preview"]:
            md.append(f"**前 {len(s['preview'])} 行数据预览**：\n")
            headers = s["header_row"] if s["header_row"] else [f"col{i}" for i in range(1, len(s["preview"][0]) + 1)]
            row_label = "#"
            md.append("| " + " | ".join([row_label] + headers) + " |")
            md.append("|" + "|".join(["---"] * (len(headers) + 1)) + "|")
            for i, row in enumerate(s["preview"], 2):  # 第 2 行开始（第 1 行是表头）
                cells = [str(c) if c is not None else "" for c in row]
                while len(cells) < len(headers):
                    cells.append("")
                cells = cells[: len(headers)]
                md.append("| " + " | ".join([str(i)] + cells) + " |")
            md.append("")

        # Stray cells 警告（used_range 外脏数据残留）
        stray = s.get("stray") or {}
        if stray.get("stray_count", 0) > 0:
            md.append(f"**⚠️ Stray 单元格警告**：\n")
            md.append(f"- 主数据块：`{stray.get('main_block', '?')}`（{stray.get('main_rows', 0)} 行 × {stray.get('main_cols', 0)} 列）")
            md.append(f"- used_range：`{s['used_range']}`（{s['rows']} 行 × {s['cols']} 列）")
            md.append(f"- 主块外非空单元格：**{stray['stray_count']} 个**（极可能是上一轮临时数据残留）")
            if stray.get("stray_preview"):
                md.append(f"- 预览（前 {len(stray['stray_preview'])} 个）：")
                md.append("")
                md.append("  | address | value |")
                md.append("  |---------|-------|")
                for sp in stray["stray_preview"]:
                    md.append(f"  | `{sp['address']}` | {sp['value']} |")
            md.append("")
            md.append(f"  > **建议**：跑 pipeline 前清掉这些单元格（或在脚本入口加 `ws.Range(主块外区域).Clear()`），")
            md.append(f"  > 避免污染本轮处理。详见 `inspect-excel-template` SKILL.md `## Stray cells 检测`。")
            md.append("")
        elif stray.get("note"):
            md.append(f"- stray 检测：{stray['note']}")
            md.append("")

        # 空值（待填）单元格（--blanks）
        bs = s.get("blank_summary")
        if bs is not None:
            total = bs["blank"] + bs["filled"]
            ratio = f"{(bs['blank'] / total * 100):.1f}%" if total else "n/a"
            md.append("**空值（待填）单元格**：\n")
            md.append(
                f"- 空 **{bs['blank']}** / 已填 {bs['filled']}（空格占比 {ratio}；"
                f"合并空格 {bs['merged_blank']}，按主格只记一次）"
            )
            if bs.get("note"):
                md.append(f"- note: {bs['note']}")
            cells = s.get("blank_cells") or []
            if cells:
                shown = ", ".join(
                    f"`{c['address']}`{'(merged)' if c['merged'] else ''}" for c in cells
                )
                md.append(f"- 空格地址（前 {len(cells)} 个）：{shown}")
                if s.get("blank_cells_truncated"):
                    md.append(f"  > ⚠️ 清单已截断至 {len(cells)} 个，总数见上方计数。")
            md.append("")

    Path(md_path).write_text("\n".join(md), encoding="utf-8")


def col_letter(n):
    """1→A, 26→Z, 27→AA, 28→AB."""
    s = ""
    while n > 0:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--xlsx", default="",
                        help=".xlsx / .xls 路径（可选）。--active 模式下省略则取 ActiveWorkbook。")
    parser.add_argument("--active", action="store_true",
                        help="实时模式：GetActiveObject 桥接运行中的 Excel，"
                             "避开文件锁，可扫用户正在编辑的 xlsx（不会 Quit 用户进程）。")
    parser.add_argument("--sheets", default="",
                        help="sheet 关键词过滤（模糊子串匹配；多个关键词逗号分隔，OR 语义）。"
                             "示例：'问卷,跑量'。")
    parser.add_argument("--preview-rows", type=int, default=5,
                        help="每个 sheet 数据预览行数（默认 5；不含表头）")
    parser.add_argument("--blanks", action="store_true",
                        help="追加空值（待填）单元格薄层扫描：统计 blank/filled/merged_blank "
                             "并列出空格地址（合并格按主格只记一次）。默认关，关时输出与历史一致。")
    parser.add_argument("--out-dir", required=True, help="输出目录")
    args = parser.parse_args()

    if not args.xlsx and not args.active:
        safe_print("[ERR] --xlsx / --active 至少要提供一个")
        return 1

    sheets_filter = parse_sheet_filter(args.sheets)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    mode_tag = "ACTIVE" if args.active else "OPEN"
    target = args.xlsx or "(ActiveWorkbook)"
    filter_tag = f" sheets~{sheets_filter}" if sheets_filter else ""
    safe_print(f"[inspect] XLSX[{mode_tag}]: {target}{filter_tag}")

    data = inspect_xlsx(
        args.xlsx or None,
        sheets_filter=sheets_filter,
        use_active=args.active,
        preview_rows=args.preview_rows,
        scan_blanks_flag=args.blanks,
    )

    safe_print(f"  → 扫描 {data['sheets_scanned']}/{data['sheet_count_total']} sheets")

    json_path = out_dir / "inspect_excel_report.json"
    md_path = out_dir / "inspect_excel_report.md"
    json_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    write_md_report(data, md_path)

    safe_print(f"\n[inspect] 完成")
    safe_print(f"  JSON: {json_path}")
    safe_print(f"  MD:   {md_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
