#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""inspect_word_template.py — 用 win32com COM 提取 .docx 的结构信息（含三态染色 + 占位符）。

任何 docx 模板填充类项目的强制前置步骤。docx 唯一的 inspect 路径（pptx 走 inspect-ppt-template、xlsx 走 inspect-excel-template）：
  - 表格用 tbl.Range.Cells 遍历（兼容合并单元格；早期实现用 tbl.Cell(1,ci) 在合并单元格上会抛）
  - 每个 cell 读 HighlightColorIndex → 三态分桶（red=6 / yellow=7 / uncolored=0 / other）
  - 全文档扫描 {{占位符}}（含 StoryRanges 与 Headers），构建 token → 落点交叉表
  - Headers + Footers 都扫
  - 支持 --active 桥接当前打开的 Word（GetActiveObject）

加密文件兼容：Ldterm 透明加密 .doc/.docx 对 win32com 启动的 WINWORD.EXE 进程透明（白名单）。
Python 写出的 .json/.md 不会被反向加密。

Usage:
    # 文件模式（默认）：另起 Word 进程，ReadOnly 打开
    python inspect_word_template.py --docx "path/to/template.docx" --out-dir "path/to/output/"

    # 实时模式：桥接到正在运行的 Word（避开文件锁）
    python inspect_word_template.py --active --out-dir "out/"
    python inspect_word_template.py --active --docx "path/to/x.docx" --out-dir "out/"

    # 表格过滤
    python inspect_word_template.py --docx "x.docx" --tables "1,3-5" --out-dir "out/"

    # 全段落转储（默认前 200 段，剔空后）
    python inspect_word_template.py --docx "x.docx" --all-paragraphs --out-dir "out/"

Outputs:
    <out-dir>/inspect_word_report.json
    <out-dir>/inspect_word_report.md

硬规则:
- try/except 读 COM 属性（getattr 在 COM 对象上也抛错）
- 文件模式：DispatchEx 强制新进程 + ReadOnly=True，finally 里 Quit() 防进程残留
- 实时模式：GetActiveObject 复用用户进程，**绝不 Quit / Close**
- 表格用 tbl.Range.Cells 遍历（合并单元格安全；T1 含合并单元格时 tbl.Cell(r,c) 直接抛）
- Word.Documents.Open 必须绝对路径（相对路径按 Word 默认目录解析，非 cwd）
- 占位符正则严格用 \\{\\{[^{}]+\\}\\}（跟 verify_docx_highlight_consistency.py 保持一致）
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")


# ---------- 三态染色常量（CLAUDE.md §3 / feature02 verify_docx_highlight_consistency.py） ----------
WD_HIGHLIGHT_RED = 6
WD_HIGHLIGHT_YELLOW = 7
WD_HIGHLIGHT_NONE = 0

PLACEHOLDER_RE = re.compile(r"\{\{[^{}]+\}\}")


def highlight_label(hl_index):
    """COM HighlightColorIndex → 三态契约 label。"""
    if hl_index == WD_HIGHLIGHT_RED:
        return "red"
    if hl_index == WD_HIGHLIGHT_YELLOW:
        return "yellow"
    if hl_index == WD_HIGHLIGHT_NONE:
        return "uncolored"
    return f"other_{hl_index}"


# ---------- COM 安全访问 ----------
def safe(obj, attr, default=None):
    """COM 对象属性安全读取。"""
    try:
        return getattr(obj, attr)
    except Exception:
        return default


def trunc(s, n=80):
    if not s:
        return ""
    s = str(s).replace("\r", "↵").replace("\n", "↵").replace("\x07", "").replace("\x0b", "")
    return s if len(s) <= n else s[:n] + "..."


def norm_cell_text(text):
    """归一化 Word range 文本：剥 cell 结束符 \\x07 / 段落符 \\r / \\x0b 与首尾空白。

    与 verify_docx_highlight_consistency.py 的 _norm 一致，保证探针基线 == 自检基线。
    """
    if not text:
        return ""
    return (str(text).replace("\x07", "").replace("\r", "")
            .replace("\x0b", "").replace("\n", "").strip())


def parse_table_filter(spec):
    """解析 "1-3,5,7-9" → {1,2,3,5,7,8,9}。空串/None → None（=不过滤）。"""
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


# ---------- DOCX 扫描 ----------
def inspect_docx(path, tables_filter=None, all_paragraphs=False, use_active=False):
    """扫 docx 结构。

    Args:
        path: docx 路径。use_active=True 时可选（None 则取 ActiveDocument）。
        tables_filter: set[int] | None。仅扫这些 table 索引；None=全扫。
        all_paragraphs: True=转储全部段落（剔空后），False=前 200 段。
        use_active: True=GetActiveObject 桥接正在运行的 Word（不 Quit）；
                    False=DispatchEx 新进程 + ReadOnly Open（兜底 Quit）。

    Returns:
        dict with keys: path, mode, tables_filter, paragraphs_total, tables, paragraphs_sample,
                        sections, story_ranges, placeholders_unique, placeholders_by_location, summary
    """
    import win32com.client as win32

    word = None
    doc = None
    opened_by_us = False  # 仅当 False 时跳过 Close/Quit（active 模式不能动用户进程）

    try:
        if use_active:
            try:
                word = win32.GetActiveObject("Word.Application")
            except Exception as e:
                raise RuntimeError(
                    f"--active 模式失败：未检测到运行中的 Word（{e}）。"
                    "请先打开目标 .docx 再重试，或去掉 --active 走文件模式。"
                )
            if path:
                abs_target = os.path.abspath(str(path)).lower()
                doc_count = safe(word.Documents, "Count", 0)
                for i in range(1, doc_count + 1):
                    d = word.Documents(i)
                    full = str(safe(d, "FullName", "")).lower()
                    if full == abs_target:
                        doc = d
                        break
                if doc is None:
                    open_list = []
                    for i in range(1, doc_count + 1):
                        open_list.append(str(safe(word.Documents(i), "FullName", "?")))
                    raise RuntimeError(
                        f"--active 找不到打开的 docx: {path}\n  当前打开的有:\n  - "
                        + "\n  - ".join(open_list)
                    )
            else:
                try:
                    doc = word.ActiveDocument
                except Exception as e:
                    raise RuntimeError(f"--active 拿不到 ActiveDocument: {e}")
        else:
            word = win32.DispatchEx("Word.Application")
            word.Visible = False
            word.DisplayAlerts = 0
            try:
                word.AutomationSecurity = 3  # msoAutomationSecurityForceDisable
            except Exception:
                pass
            try:
                word.ScreenUpdating = False
            except Exception:
                pass
            doc = word.Documents.Open(
                os.path.abspath(str(path)),
                ReadOnly=True,
                ConfirmConversions=False,
                AddToRecentFiles=False,
            )
            opened_by_us = True

        result = {
            "path": str(safe(doc, "FullName", path) or path),
            "mode": "active" if use_active else "open",
            "tables_filter": sorted(tables_filter) if tables_filter else None,
            "all_paragraphs": bool(all_paragraphs),
            "paragraphs_total": 0,
            "tables": [],
            "paragraphs_sample": [],
            "sections": [],
            "story_ranges": [],
            "placeholders_unique": [],
            "placeholders_by_location": [],
            "summary": {},
        }

        try:
            # === Tables（含三态染色 + 占位符） ===
            tbl_count = safe(doc.Tables, "Count", 0)
            placeholder_locations = {}  # token → list of location dict

            for ti in range(1, tbl_count + 1):
                if tables_filter is not None and ti not in tables_filter:
                    continue
                tbl = doc.Tables(ti)
                rows = safe(tbl.Rows, "Count", 0)
                cols = safe(tbl.Columns, "Count", 0)
                cells_info = []
                tbl_hl_summary = {"red": 0, "yellow": 0, "uncolored": 0, "other_color": 0}
                tbl_placeholders = set()

                # tbl.Range.Cells 安全遍历：合并单元格只出现一次，自带 RowIndex/ColumnIndex
                try:
                    cells_iter = tbl.Range.Cells
                except Exception:
                    cells_iter = []
                for cell in cells_iter:
                    try:
                        ri = int(cell.RowIndex)
                        ci = int(cell.ColumnIndex)
                    except Exception:
                        continue
                    try:
                        hl = int(cell.Range.HighlightColorIndex)
                    except Exception:
                        hl = -1
                    raw_text = ""
                    try:
                        raw_text = cell.Range.Text or ""
                    except Exception:
                        pass
                    norm_text = norm_cell_text(raw_text)
                    label = highlight_label(hl)
                    if label == "red":
                        tbl_hl_summary["red"] += 1
                    elif label == "yellow":
                        tbl_hl_summary["yellow"] += 1
                    elif label == "uncolored":
                        tbl_hl_summary["uncolored"] += 1
                    else:
                        tbl_hl_summary["other_color"] += 1

                    # 占位符落点收集
                    for tok in PLACEHOLDER_RE.findall(raw_text):
                        tbl_placeholders.add(tok)
                        placeholder_locations.setdefault(tok, []).append({
                            "kind": "table_cell",
                            "table": ti, "row": ri, "col": ci,
                        })

                    cells_info.append({
                        "row": ri, "col": ci,
                        "highlight_index": hl,
                        "highlight_label": label,
                        "text_preview": trunc(norm_text, 80),
                    })

                result["tables"].append({
                    "index": ti,
                    "rows": rows,
                    "cols": cols,
                    "highlight_summary": tbl_hl_summary,
                    "cells": cells_info,
                    "placeholders_in_table": sorted(tbl_placeholders),
                })

            # === Paragraphs ===
            para_count = safe(doc.Paragraphs, "Count", 0)
            result["paragraphs_total"] = para_count
            cap = para_count if all_paragraphs else min(para_count, 400)
            kept = 0
            kept_cap = para_count if all_paragraphs else 200
            for i in range(1, cap + 1):
                if kept >= kept_cap:
                    break
                p = doc.Paragraphs(i)
                txt = safe(p.Range, "Text", "") or ""
                if len(txt.strip()) < 2:
                    continue
                style_name = ""
                try:
                    style_name = str(p.Style.NameLocal)
                except Exception:
                    pass
                # 段落里的占位符也落点
                for tok in PLACEHOLDER_RE.findall(txt):
                    placeholder_locations.setdefault(tok, []).append({
                        "kind": "paragraph",
                        "paragraph_index": i,
                    })
                result["paragraphs_sample"].append({
                    "index": i,
                    "style": style_name,
                    "text": trunc(txt, 120),
                })
                kept += 1

            # === Sections / Headers / Footers ===
            sec_count = safe(doc.Sections, "Count", 0)
            for si in range(1, sec_count + 1):
                sec = doc.Sections(si)
                sec_entry = {"index": si, "headers": [], "footers": []}
                for kind, accessor in (("headers", "Headers"), ("footers", "Footers")):
                    try:
                        coll = getattr(sec, accessor)
                        n = int(coll.Count)
                    except Exception:
                        n = 0
                    for hi in range(1, n + 1):
                        try:
                            item = coll(hi)
                            exists = bool(safe(item, "Exists", False))
                            text = safe(item.Range, "Text", "") or ""
                            for tok in PLACEHOLDER_RE.findall(text):
                                placeholder_locations.setdefault(tok, []).append({
                                    "kind": kind[:-1],  # header / footer
                                    "section": si,
                                    "index": hi,
                                })
                            sec_entry[kind].append({
                                "index": hi,
                                "exists": exists,
                                "text_preview": trunc(text, 100),
                            })
                        except Exception:
                            pass
                result["sections"].append(sec_entry)

            # === StoryRanges ===
            try:
                sr_count = int(doc.StoryRanges.Count)
            except Exception:
                sr_count = 0
            for i in range(1, sr_count + 1):
                try:
                    sr = doc.StoryRanges(i)
                    sr_type = safe(sr, "StoryType", -1)
                    sr_text = safe(sr, "Text", "") or ""
                    for tok in PLACEHOLDER_RE.findall(sr_text):
                        placeholder_locations.setdefault(tok, []).append({
                            "kind": "story_range",
                            "story_index": i,
                            "story_type": sr_type,
                        })
                    result["story_ranges"].append({
                        "story_index": i,
                        "story_type": sr_type,
                        "text_preview": trunc(sr_text, 100),
                    })
                except Exception:
                    pass

            # === Placeholders 汇总 ===
            unique_tokens = sorted(placeholder_locations.keys())
            result["placeholders_unique"] = unique_tokens
            result["placeholders_by_location"] = [
                {"token": tok, "occurrences": len(placeholder_locations[tok]),
                 "locations": placeholder_locations[tok]}
                for tok in unique_tokens
            ]

            # === Summary ===
            hl_total = {"red": 0, "yellow": 0, "uncolored": 0, "other_color": 0}
            for t in result["tables"]:
                for k in hl_total:
                    hl_total[k] += t["highlight_summary"][k]
            result["summary"] = {
                "table_count_total": tbl_count,
                "tables_scanned": len(result["tables"]),
                "paragraphs_total": para_count,
                "paragraphs_sampled": len(result["paragraphs_sample"]),
                "section_count": sec_count,
                "story_range_count": sr_count,
                "highlight": hl_total,
                "placeholders_unique_count": len(unique_tokens),
                "placeholders_total_occurrences": sum(
                    len(v) for v in placeholder_locations.values()
                ),
            }
        finally:
            if opened_by_us and doc is not None:
                try:
                    doc.Close(SaveChanges=0)
                except Exception:
                    pass
    finally:
        if opened_by_us and word is not None:
            try:
                word.Quit()
            except Exception:
                pass

    return result


# ---------- 报告渲染 ----------
def write_md_report(data, md_path):
    md = []
    md.append("# Word Inspect 报告\n")
    md.append("> 由 `inspect-word-template` skill 生成。\n")
    md.append("> 用于写 `docx_mapping.json` / 染色驱动填充逻辑前定位 cell 染色 + 占位符落点。\n\n")

    md.append(f"## DOCX: `{data['path']}`\n")
    mode = data.get("mode", "open")
    md.append(f"- 模式：`{mode}`（active=桥接运行中 Word / open=ReadOnly 新进程）")
    if data.get("tables_filter"):
        md.append(f"- 表过滤：`{data['tables_filter']}`")
    if data.get("all_paragraphs"):
        md.append(f"- 段落模式：`--all-paragraphs`（无 200 段上限）")
    md.append("")

    s = data["summary"]
    md.append("### 摘要\n")
    md.append(f"- 表格：扫描 {s['tables_scanned']} / 总 {s['table_count_total']}")
    md.append(f"- 段落：采样 {s['paragraphs_sampled']} / 总 {s['paragraphs_total']}（剔空后）")
    md.append(f"- Sections：{s['section_count']} / StoryRanges：{s['story_range_count']}")
    md.append(f"- **染色三态**：🔴 红 `{s['highlight']['red']}` / 🟡 黄 `{s['highlight']['yellow']}`"
              f" / ⬜ 无色 `{s['highlight']['uncolored']}` / 其它色 `{s['highlight']['other_color']}`")
    md.append(f"- **占位符**：unique `{s['placeholders_unique_count']}` 个，"
              f"总出现 `{s['placeholders_total_occurrences']}` 次")
    md.append("")

    # 表格细节
    md.append("## Tables（含三态染色 cell 清单）\n")
    if not data["tables"]:
        md.append("（无表 / 被过滤掉）\n")
    for t in data["tables"]:
        hs = t["highlight_summary"]
        md.append(f"### Table {t['index']}（{t['rows']}×{t['cols']}）"
                  f" — 🔴 {hs['red']} / 🟡 {hs['yellow']}"
                  f" / ⬜ {hs['uncolored']} / 其它 {hs['other_color']}\n")
        if t["placeholders_in_table"]:
            md.append(f"占位符：{', '.join('`' + tok + '`' for tok in t['placeholders_in_table'])}\n")
        md.append("| row | col | highlight | 文本预览 |")
        md.append("|-----|-----|-----------|---------|")
        # 三态优先：red 先 / yellow 次 / uncolored 抽样 / other_color 全列
        red_cells = [c for c in t["cells"] if c["highlight_label"] == "red"]
        yellow_cells = [c for c in t["cells"] if c["highlight_label"] == "yellow"]
        other_cells = [c for c in t["cells"] if c["highlight_label"].startswith("other_")]
        uncolored_cells = [c for c in t["cells"] if c["highlight_label"] == "uncolored"]

        def emit(cells, emoji):
            for c in cells:
                md.append(f"| {c['row']} | {c['col']} | {emoji} {c['highlight_label']}"
                          f" ({c['highlight_index']}) | {c['text_preview']} |")

        emit(red_cells, "🔴")
        emit(yellow_cells, "🟡")
        emit(other_cells, "🟣")
        # 无色 cell 数量大时 truncate（前 30 + 后省略）
        if len(uncolored_cells) > 30:
            emit(uncolored_cells[:30], "⬜")
            md.append(f"| ... | ... | ⬜ uncolored | （余 {len(uncolored_cells) - 30} 个无色 cell 见 JSON） |")
        else:
            emit(uncolored_cells, "⬜")
        md.append("")

    # 段落
    md.append("## Paragraphs（采样剔空段，用作 Find/Replace 锚点候选）\n")
    md.append("> 禁止用 paragraph 的 start/end 数字定位（用户改排版会漂移）—— 用 Find 语义锚点。\n")
    md.append("| 段索引 | style | 文本预览 |")
    md.append("|-------|-------|---------|")
    for p in data["paragraphs_sample"]:
        md.append(f"| {p['index']} | {p['style']} | {p['text']} |")
    md.append("")

    # Sections
    md.append("## Sections / Headers / Footers（页脚三联水印的可能位置）\n")
    for sec in data["sections"]:
        md.append(f"### Section {sec['index']}\n")
        if sec["headers"]:
            md.append("**Headers**")
            for h in sec["headers"]:
                md.append(f"- header_idx {h['index']} (exists={h['exists']}): `{h['text_preview']}`")
        if sec["footers"]:
            md.append("**Footers**")
            for f in sec["footers"]:
                md.append(f"- footer_idx {f['index']} (exists={f['exists']}): `{f['text_preview']}`")
        if not sec["headers"] and not sec["footers"]:
            md.append("- （无 Headers / Footers）")
        md.append("")

    # StoryRanges
    md.append("## StoryRanges（不同 story = 主体/页眉/页脚/批注/文本框）\n")
    md.append("> 漏处理 story = 模板填充最常见坑（如 `{{project.name}}` 落在页脚未被替换）\n")
    md.append("| # | story_type | text_preview |")
    md.append("|---|-----------|-------------|")
    for sr in data["story_ranges"]:
        md.append(f"| {sr['story_index']} | {sr['story_type']} | {sr['text_preview']} |")
    md.append("")

    # Placeholders
    md.append("## Placeholders（双闸门契约的核心信号）\n")
    md.append("> 占位符 = 散值身份（token 名）；染色 = 表格闸门（CLAUDE.md §3 双闸门规则）\n")
    if not data["placeholders_by_location"]:
        md.append("（模板内无 `{{...}}` 占位符）\n")
    else:
        md.append("| token | 出现次数 | 落点 |")
        md.append("|-------|---------|------|")
        for entry in data["placeholders_by_location"]:
            locs = entry["locations"]
            loc_strs = []
            for loc in locs[:6]:
                if loc["kind"] == "table_cell":
                    loc_strs.append(f"T{loc['table']}({loc['row']},{loc['col']})")
                elif loc["kind"] == "paragraph":
                    loc_strs.append(f"P{loc['paragraph_index']}")
                elif loc["kind"] in ("header", "footer"):
                    loc_strs.append(f"sec{loc['section']}/{loc['kind']}{loc['index']}")
                elif loc["kind"] == "story_range":
                    loc_strs.append(f"story{loc['story_index']}(type={loc['story_type']})")
                else:
                    loc_strs.append(str(loc))
            extra = f" +{len(locs) - 6}" if len(locs) > 6 else ""
            md.append(f"| `{entry['token']}` | {entry['occurrences']} | {' / '.join(loc_strs)}{extra} |")
        md.append("")

    Path(md_path).write_text("\n".join(md), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="docx 结构探针（含三态染色 + 占位符审计）")
    parser.add_argument("--docx", default="", help="Word 模板路径（可选；--active 时省略取 ActiveDocument）")
    parser.add_argument("--active", action="store_true",
                        help="实时模式：用 GetActiveObject 桥接正在运行的 Word，"
                             "避开文件锁，可扫用户正在编辑的 docx（不会 Quit 用户进程）。")
    parser.add_argument("--tables", default="",
                        help="只扫指定 table。语法：'1-3,5,7-9'。仅作用于 tables 部分。")
    parser.add_argument("--all-paragraphs", action="store_true",
                        help="转储全部段落（默认前 200 段，已剔空段）")
    parser.add_argument("--out-dir", required=True, help="输出目录")
    args = parser.parse_args()

    if not args.docx and not args.active:
        print("[ERR] --docx / --active 至少要提供一个")
        return 1

    try:
        tables_filter = parse_table_filter(args.tables)
    except ValueError as e:
        print(f"[ERR] --tables 解析失败: {e}（示例: --tables '1-3,5,7-9'）")
        return 1

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    mode_tag = "ACTIVE" if args.active else "OPEN"
    target = args.docx or "(ActiveDocument)"
    filter_tag = f" tables={sorted(tables_filter)}" if tables_filter else ""
    paras_tag = " all-paragraphs" if args.all_paragraphs else ""
    print(f"[inspect-word] {mode_tag}: {target}{filter_tag}{paras_tag}")

    data = inspect_docx(
        args.docx or None,
        tables_filter=tables_filter,
        all_paragraphs=args.all_paragraphs,
        use_active=args.active,
    )

    s = data["summary"]
    print(f"  → 表 {s['tables_scanned']}/{s['table_count_total']}，"
          f"段落 {s['paragraphs_sampled']}/{s['paragraphs_total']}，"
          f"sections {s['section_count']}，stories {s['story_range_count']}")
    print(f"  → 染色 🔴 {s['highlight']['red']} / 🟡 {s['highlight']['yellow']}"
          f" / ⬜ {s['highlight']['uncolored']} / 其它 {s['highlight']['other_color']}")
    print(f"  → 占位符 unique {s['placeholders_unique_count']} 个，"
          f"总出现 {s['placeholders_total_occurrences']} 次")

    json_path = out_dir / "inspect_word_report.json"
    md_path = out_dir / "inspect_word_report.md"
    json_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    write_md_report(data, md_path)

    print(f"\n[inspect-word] 完成")
    print(f"  JSON: {json_path}")
    print(f"  MD:   {md_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
