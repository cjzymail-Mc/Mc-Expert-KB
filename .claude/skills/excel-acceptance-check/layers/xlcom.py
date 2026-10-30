#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""[新写] Excel COM 读取 + 锚点解析助手（L0/L1/L3 共用）。

锚点优先级（硬约束）：NamedRange > sheet+表头列名 > 单元格地址(A1) > 行列数字(禁)。
本模块**只读不写**（验收只断言）。读值统一走 COM Range，复用 office-com-helpers 的
com_get / safe_text 防 COM 属性异常。

Excel 不禁 A1（A1 是 Excel 原生稳定锚点）；禁的是把裸 `Cells(r,c)` 数字坐标当业务锚点。
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, List, Optional, Tuple

# 复用 office-com-helpers
_HELPERS = Path(__file__).resolve().parents[2] / "office-com-helpers"
if _HELPERS.exists() and str(_HELPERS) not in sys.path:
    sys.path.insert(0, str(_HELPERS))
try:
    from office_com_helpers import com_get, safe_text
except Exception:  # pragma: no cover - 兜底
    def com_get(obj, attr, default=None):
        try:
            return getattr(obj, attr)
        except Exception:
            return default

    def safe_text(v):
        return "" if v is None else str(v)


def col_letter_to_index(col: str) -> int:
    """'A'->1, 'AA'->27（COM 1-based）。"""
    col = str(col).strip().upper()
    n = 0
    for ch in col:
        if not ("A" <= ch <= "Z"):
            break
        n = n * 26 + (ord(ch) - ord("A") + 1)
    return n


def index_to_col_letter(n: int) -> str:
    """1->A, 27->AA（COM 1-based）。"""
    s = ""
    while n > 0:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def resolve_sheet(wb, name: Optional[str] = None, fuzzy: Optional[str] = None):
    """按 精确名 → 模糊子串 解析 worksheet。找不到返回 (None, "")。

    Returns: (sheet_com_obj | None, matched_name)
    """
    try:
        cnt = int(com_get(wb.Sheets, "Count", 0) or 0)
    except Exception:
        return None, ""
    # 1) 精确
    if name:
        for i in range(1, cnt + 1):
            sh = wb.Sheets(i)
            if str(com_get(sh, "Name", "")) == name:
                return sh, name
    # 2) 模糊
    kw = fuzzy or name
    if kw:
        for i in range(1, cnt + 1):
            sh = wb.Sheets(i)
            nm = str(com_get(sh, "Name", ""))
            if kw in nm:
                return sh, nm
    return None, ""


def used_dims(sheet) -> Tuple[int, int, str]:
    """(rows, cols, address)。读取失败返回 (0,0,'')。"""
    try:
        used = sheet.UsedRange
        rows = int(com_get(used.Rows, "Count", 0) or 0)
        cols = int(com_get(used.Columns, "Count", 0) or 0)
        addr = str(com_get(used, "Address", ""))
        return rows, cols, addr
    except Exception:
        return 0, 0, ""


def header_cells(sheet, header_row: int = 1) -> List[str]:
    """读 header_row 行（在 UsedRange 范围内）的列名清单（trim 后字符串）。"""
    out: List[str] = []
    try:
        used = sheet.UsedRange
        c0 = int(com_get(used, "Column", 1) or 1)
        ncols = int(com_get(used.Columns, "Count", 0) or 0)
        for j in range(ncols):
            cell = sheet.Cells(header_row, c0 + j)
            out.append(safe_text(com_get(cell, "Value", "")).strip())
    except Exception:
        pass
    return out


def resolve_named_range(wb, name: str):
    """按 workbook 定义名解析 → (sheet, range_obj)。失败返回 (None, None)。"""
    try:
        nm = wb.Names(name)
        rng = nm.RefersToRange
        sh = rng.Worksheet
        return sh, rng
    except Exception:
        return None, None


def read_cell_value(sheet, a1: str) -> Any:
    """读单元格 A1 地址的值（合并格读主格值）。失败返回 None。"""
    try:
        rng = sheet.Range(a1)
        # 合并格：取主格(MergeArea 左上)值，避免读到成员格的 None
        if bool(com_get(rng, "MergeCells", False)):
            rng = rng.MergeArea.Cells(1, 1)
        return com_get(rng, "Value", None)
    except Exception:
        return None


def read_range_value(rng) -> Any:
    """读一个已解析的 Range 对象的值。"""
    try:
        if bool(com_get(rng, "MergeCells", False)):
            rng = rng.MergeArea.Cells(1, 1)
        return com_get(rng, "Value", None)
    except Exception:
        return None


def read_column_values(sheet, col: str, header_row: int = 1) -> List[Any]:
    """读某列（列字母 或 表头列名）从 header_row+1 起到 UsedRange 末尾的值。

    col 既可是列字母('AD')也可是表头名('开发号')——先按字母解析，否则在
    header_cells 里找列名。找不到返回 []。
    """
    try:
        used = sheet.UsedRange
        r0 = int(com_get(used, "Row", 1) or 1)
        c0 = int(com_get(used, "Column", 1) or 1)
        nrows = int(com_get(used.Rows, "Count", 0) or 0)
    except Exception:
        return []

    col_idx = col_letter_to_index(col)
    # 不是纯列字母 → 当表头名找
    if col_idx == 0 or str(col).strip().upper() != index_to_col_letter(col_idx):
        headers = header_cells(sheet, header_row)
        col_idx = 0
        target = str(col).strip()
        for j, h in enumerate(headers):
            if h == target or (target and target in h):
                col_idx = c0 + j
                break
        if col_idx == 0:
            return []

    out: List[Any] = []
    start_row = max(r0, header_row + 1)
    end_row = r0 + nrows - 1
    for r in range(start_row, end_row + 1):
        try:
            out.append(com_get(sheet.Cells(r, col_idx), "Value", None))
        except Exception:
            out.append(None)
    return out
