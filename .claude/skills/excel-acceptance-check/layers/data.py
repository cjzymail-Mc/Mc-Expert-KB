#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""[L1 数据层] —— 读 xlsx-under-test 的 cell / column 实际值，
和契约里的 expected / expected_from 比对。

护栏①：L1 期望值**只来自外部真相**——`inline`(结构性可) 或 `excel:` DSL
（从 contract.data_sources.excel 指向的外部 xlsx 取真相）。**禁在契约/脚本
hardcode 工艺单具体业务值**。结构性断言走 L0。

DSL 段（_excel_col_to_index / _load_excel_column / _agg_column / resolve_expected）
是 ppt-acceptance-check/layers/data.py(:38-150) 的提取复用件——逻辑等价，未改语义。
run() 是按 Excel 重写的（ppt 版 run() 的 slide/shape/chart 耦合不可复用）。

支持的 check：
  cell_equals          单元格(锚点)值 == expected（trim 后字符串比较）
  cell_contains        单元格值 包含 expected 子串
  column_agg_equals    对某列聚合(mode/sum/mean/count_contains/list) == expected

锚点优先级（rule 字段）：name(NamedRange) > sheet+cell(A1) / sheet+column。
"""
from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from layers.common import Finding, LayerResult
from layers import xlcom


# ────────── expected_from DSL（提取自 ppt data.py，逻辑等价）──────────

def _excel_col_to_index(col: str) -> int:
    """'A' -> 0, 'AD' -> 29（0-based，给 _load_excel_column 用）。"""
    col = col.strip().upper()
    n = 0
    for ch in col:
        n = n * 26 + (ord(ch) - ord("A") + 1)
    return n - 1


def _load_excel_column(excel_path: str, sheet_kw: str, col: str) -> List[Any]:
    """从外部 excel 取一列原始值（去掉表头第 1 行）。复用 office-com-helpers。"""
    import sys
    helpers = Path.home() / ".claude" / "skills" / "office-com-helpers"
    if str(helpers) not in sys.path:
        sys.path.insert(0, str(helpers))
    from office_com_helpers import load_excel_rows

    rows, _, _ = load_excel_rows(
        excel_path=excel_path,
        sheet_name=sheet_kw,
        fuzzy_keyword=sheet_kw,
    )
    if not rows or len(rows) < 2:
        return []
    idx = _excel_col_to_index(col)
    out: List[Any] = []
    for row in rows[1:]:
        if idx < len(row):
            out.append(row[idx])
    return out


def _a1_to_rc(a1: str) -> Optional[Tuple[int, int]]:
    """'$B$5' / 'B5' -> (row=5, col=2)（1-based）。解析失败返回 None。"""
    m = re.match(r"^\s*\$?([A-Za-z]+)\$?(\d+)\s*$", str(a1))
    if not m:
        return None
    return int(m.group(2)), _excel_col_to_index(m.group(1)) + 1


def _load_excel_cell(excel_path: str, sheet_kw: str, a1: str) -> Any:
    """从外部 excel 取单格值（A1 绝对地址）。

    复用 office-com-helpers.load_excel_rows（拿 UsedRange.Value）。
    **假设该 sheet 的 UsedRange 自 A1 起**（绝对 A1 → rows 下标直接映射）；
    本 repo 评审/规格表均如此。若 UsedRange 不从 A1 起，此映射会偏移。
    """
    import sys
    helpers = Path.home() / ".claude" / "skills" / "office-com-helpers"
    if str(helpers) not in sys.path:
        sys.path.insert(0, str(helpers))
    from office_com_helpers import load_excel_rows

    rows, _, _ = load_excel_rows(excel_path=excel_path, sheet_name=sheet_kw,
                                 fuzzy_keyword=sheet_kw)
    rc = _a1_to_rc(a1)
    if not rows or rc is None:
        return None
    r, c = rc
    if 0 <= r - 1 < len(rows):
        row = rows[r - 1]
        if 0 <= c - 1 < len(row):
            return row[c - 1]
    return None


def _agg_column(values: List[Any], agg: str) -> Any:
    """聚合策略。"""
    cleaned = [v for v in values if v is not None and v != ""]
    if not cleaned:
        return None
    if agg == "mode":
        return Counter(str(v) for v in cleaned).most_common(1)[0][0]
    if agg == "sum":
        try:
            return sum(float(v) for v in cleaned)
        except Exception:
            return None
    if agg == "mean":
        try:
            nums = [float(v) for v in cleaned]
            return sum(nums) / len(nums)
        except Exception:
            return None
    if agg.startswith("count_contains="):
        sub = agg.split("=", 1)[1]
        return sum(1 for v in cleaned if sub in str(v))
    if agg == "list":
        return cleaned
    if agg == "range":
        try:
            nums = [float(v) for v in cleaned]
            return [min(nums), max(nums)]
        except Exception:
            return None
    return None


def resolve_expected(rule: Dict[str, Any], contract) -> Tuple[Any, str]:
    """返回 (expected_value, resolution_note)。失败时 expected_value=None。

    护栏①：业务值优先走 excel: DSL（外部真相）；inline 仅限结构性/格式期望。
    """
    if "expected" in rule:
        return rule["expected"], "inline"

    spec = rule.get("expected_from")
    if not spec:
        return None, "no expected / expected_from given"

    spec = str(spec).strip()
    if spec.startswith("hardcoded:"):
        raw = spec[len("hardcoded:"):]
        try:
            return json.loads(raw), "hardcoded(json)"
        except Exception:
            return raw, "hardcoded(str)"

    if spec.startswith("excel_cell:"):
        # excel_cell:<sheet_kw>:<A1>  取外部 xlsx 单格值（单值真相，最常用）
        parts = spec[len("excel_cell:"):].split(":")
        if len(parts) < 2:
            return None, f"bad excel_cell DSL: {spec!r}"
        sheet_kw, a1 = parts[0], parts[1]
        excel_path = (contract.raw.get("data_sources") or {}).get("excel")
        if not excel_path:
            return None, "contract.data_sources.excel 未配置，无法解析 excel_cell: DSL"
        try:
            return _load_excel_cell(excel_path, sheet_kw, a1), f"excel_cell:{sheet_kw}:{a1}"
        except Exception as e:
            return None, f"excel_cell DSL 执行失败: {e}"

    if spec.startswith("excel:"):
        # excel:<sheet_kw>:<col_or_cols>:<agg>
        parts = spec[len("excel:"):].split(":")
        if len(parts) < 3:
            return None, f"bad excel DSL: {spec!r}"
        sheet_kw, col_spec, agg = parts[0], parts[1], ":".join(parts[2:])

        excel_path = (contract.raw.get("data_sources") or {}).get("excel")
        if not excel_path:
            return None, "contract.data_sources.excel 未配置，无法解析 excel: DSL"

        try:
            if "," in col_spec:
                cols = [c.strip() for c in col_spec.split(",")]
                if agg == "range":
                    pooled: List[Any] = []
                    for c in cols:
                        pooled.extend(_load_excel_column(excel_path, sheet_kw, c))
                    return _agg_column(pooled, "range"), f"excel:{sheet_kw}:{col_spec}:{agg}"
                out = {c: _agg_column(_load_excel_column(excel_path, sheet_kw, c), agg)
                       for c in cols}
                return out, f"excel:{sheet_kw}:{col_spec}:{agg}"
            else:
                values = _load_excel_column(excel_path, sheet_kw, col_spec)
                return _agg_column(values, agg), f"excel:{sheet_kw}:{col_spec}:{agg}"
        except Exception as e:
            return None, f"excel DSL 执行失败: {e}"

    return None, f"未识别的 expected_from: {spec!r}"


# ────────── 锚点 → 实际值（xlsx-under-test）──────────

def _resolve_actual(wb, rule: Dict[str, Any]) -> Tuple[Any, str, str]:
    """按锚点优先级取 xlsx-under-test 的实际值。

    Returns: (actual_value, locator_str, err)。err 非空表示定位失败。
    """
    # 1) NamedRange（最高优先级）
    name = rule.get("name")
    if name:
        sh, rng = xlcom.resolve_named_range(wb, name)
        if rng is None:
            return None, name, f"NamedRange '{name}' 未找到"
        return xlcom.read_range_value(rng), f"name:{name}", ""

    # 2) sheet + cell(A1) / column
    sheet_name = rule.get("sheet")
    sh, matched = xlcom.resolve_sheet(wb, name=sheet_name, fuzzy=sheet_name)
    if sh is None:
        return None, str(sheet_name), f"sheet '{sheet_name}' 未找到"

    cell = rule.get("cell")
    if cell:
        return xlcom.read_cell_value(sh, cell), f"{matched}!{cell}", ""

    # column 聚合留给 column_agg_equals 自己处理（返回列名占位）
    col = rule.get("column")
    if col:
        return None, f"{matched}!col:{col}", "__column__"

    return None, matched, "规则缺锚点(name/cell/column)"


# ────────── 主流程 ──────────

def run(*, contract, wb) -> LayerResult:
    lr = LayerResult(layer="L1")
    rules = contract.rules_for_layer("L1")
    if not rules:
        lr.notes.append("L1: no rules in contract")
        return lr

    header_row = int((contract.raw.get("structure") or {}).get("header_row", 1) or 1)

    for rule in rules:
        rid = rule.get("id", "L1_unnamed")
        sev = rule.get("severity", "must_fix")
        check = rule.get("check", "")
        expected, exp_note = resolve_expected(rule, contract)

        # column_agg_equals 走专门分支（要先聚合列）
        if check == "column_agg_equals":
            sheet_name = rule.get("sheet")
            sh, matched = xlcom.resolve_sheet(wb, name=sheet_name, fuzzy=sheet_name)
            col = rule.get("column")
            agg = rule.get("agg", "mode")
            if sh is None or not col:
                lr.add(Finding(rule_id=rid, layer="L1", severity=sev, passed=False,
                               shape=str(sheet_name),
                               message=f"column_agg_equals 定位失败（sheet={sheet_name} column={col}）"))
                continue
            vals = xlcom.read_column_values(sh, col, header_row=header_row)
            actual = _agg_column(vals, agg)
            passed = (expected is not None) and (str(actual) == str(expected))
            lr.add(Finding(
                rule_id=rid, layer="L1", severity=sev, passed=passed,
                shape=f"{matched}!col:{col}({agg})",
                message=f"column agg: actual={actual!r} expected={expected!r} ({exp_note})",
                detail={"actual": actual, "expected": expected, "expected_from": exp_note},
            ))
            continue

        actual, locator, err = _resolve_actual(wb, rule)
        if err and err != "__column__":
            lr.add(Finding(rule_id=rid, layer="L1", severity=sev, passed=False,
                           shape=locator, message=f"定位失败：{err}"))
            continue

        if check == "cell_equals":
            a = xlcom.safe_text(actual).strip()
            e = "" if expected is None else str(expected).strip()
            passed = a == e
            lr.add(Finding(
                rule_id=rid, layer="L1", severity=sev, passed=passed, shape=locator,
                message=f"cell: actual={a!r} expected={e!r} ({exp_note})",
                detail={"actual": a, "expected": e, "expected_from": exp_note},
            ))

        elif check == "cell_contains":
            a = xlcom.safe_text(actual)
            sub = "" if expected is None else str(expected)
            passed = bool(sub) and (sub in a)
            lr.add(Finding(
                rule_id=rid, layer="L1", severity=sev, passed=passed, shape=locator,
                message=f"cell contains {sub!r}: {passed} (actual snippet={a[:60]!r}) ({exp_note})",
                detail={"actual": a, "expected_substr": sub, "expected_from": exp_note},
            ))

        else:
            lr.add(Finding(rule_id=rid, layer="L1", severity="warn", passed=False,
                           shape=locator, message=f"未识别的 check: {check!r}"))

    return lr
