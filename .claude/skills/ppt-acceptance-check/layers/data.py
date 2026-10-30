#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""L1 数据层 —— 读 chart series / textbox text / picture / table，
和契约里的 expected_from / expected 值比对。

支持的 check：
  text_equals                       固定字符串比对
  text_contains                     子串包含
  text_equals_computed              text_equals 别名（语义上"动态计算"，但都走值比对）
  chart_series_values               chart 的 series.Values 对比 expected 列表
  chart_series_differs_from_template  new chart 的 series 必须与 template 同名 chart 不同；
                                    完全相同则 FAIL（证明代码根本没把数据写进去）
  picture_present                   shape 存在即过（用于"不该缺图"断言）
  table_cell_equals                 按 detail.row/col 取 cell，文本相等

expected 解析（优先级）：
  1. rule.expected               直接给值（推荐写法）
  2. rule.expected_from = "..."  DSL，目前支持：
       hardcoded:<json>
       excel:<sheet_kw>:<col_or_cols>:<agg>
         col: 'AD' 单列；'AD,AE' 双列（仅 range 类聚合用）
         agg: mode / sum / mean / count_contains=<substr> / range / list
  契约顶层应给 data_sources.excel = 'path/to/source.xlsx' 让 excel: DSL 用。
"""
from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from layers.common import Finding, LayerResult


# ────────── expected_from DSL ──────────

def _excel_col_to_index(col: str) -> int:
    """'A' -> 0, 'AD' -> 29."""
    col = col.strip().upper()
    n = 0
    for ch in col:
        n = n * 26 + (ord(ch) - ord("A") + 1)
    return n - 1


def _load_excel_column(excel_path: str, sheet_kw: str, col: str) -> List[Any]:
    """从 excel 取一列原始值（去掉表头第 1 行）。"""
    import sys
    helpers = Path(__file__).resolve().parents[2] / "office-com-helpers"
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
        # 给一列时：[min, max]
        try:
            nums = [float(v) for v in cleaned]
            return [min(nums), max(nums)]
        except Exception:
            return None
    return None


def resolve_expected(rule: Dict[str, Any], contract) -> Tuple[Any, str]:
    """返回 (expected_value, resolution_note)。失败时 expected_value=None。"""
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
                    # 双列 range：取两列拼一起算 [min,max]
                    pooled: List[Any] = []
                    for c in cols:
                        pooled.extend(_load_excel_column(excel_path, sheet_kw, c))
                    return _agg_column(pooled, "range"), f"excel:{sheet_kw}:{col_spec}:{agg}"
                # 否则按列分别聚合，返回 dict
                out = {c: _agg_column(_load_excel_column(excel_path, sheet_kw, c), agg)
                       for c in cols}
                return out, f"excel:{sheet_kw}:{col_spec}:{agg}"
            else:
                values = _load_excel_column(excel_path, sheet_kw, col_spec)
                return _agg_column(values, agg), f"excel:{sheet_kw}:{col_spec}:{agg}"
        except Exception as e:
            return None, f"excel DSL 执行失败: {e}"

    return None, f"未识别的 expected_from: {spec!r}"


# ────────── 各 check 实现 ──────────

def _read_text(shape) -> str:
    try:
        if int(getattr(shape, "HasTextFrame", 0) or 0) != -1:
            return ""
        return str(shape.TextFrame.TextRange.Text or "")
    except Exception:
        return ""


def _read_chart_series(shape) -> List[List[Any]]:
    """返回 [[s1_v1, s1_v2, ...], [s2_v1, ...], ...]。COM 失败返回 []。"""
    try:
        if int(getattr(shape, "HasChart", 0) or 0) != -1:
            return []
        chart = shape.Chart
        n = chart.SeriesCollection().Count
        out = []
        for i in range(1, n + 1):
            s = chart.SeriesCollection(i)
            try:
                vals = list(s.Values)
            except Exception:
                vals = []
            out.append(vals)
        return out
    except Exception:
        return []


def _read_table_cell(shape, row: int, col: int) -> str:
    try:
        if int(getattr(shape, "HasTable", 0) or 0) != -1:
            return ""
        cell = shape.Table.Cell(row, col)
        return str(cell.Shape.TextFrame.TextRange.Text or "")
    except Exception:
        return ""


def _check_skip_if_trace(rule: Dict[str, Any], trace_index) -> Tuple[bool, str]:
    """skip_if_trace = 'event_name.called == false' 这种简单条件。"""
    if not rule.get("skip_if_trace") or trace_index is None:
        return False, ""
    expr = rule["skip_if_trace"]
    m = re.match(r"\s*(\w+)\.called\s*==\s*(true|false)\s*$", expr, re.IGNORECASE)
    if not m:
        return False, ""
    event_name, expected_called = m.group(1), m.group(2).lower() == "true"
    events = trace_index.get_events(event_name) if hasattr(trace_index, "get_events") else []
    actual_called = any(ev.get("called", True) for ev in events)
    if actual_called == expected_called:
        return True, f"skip: {expr}"
    return False, ""


# ────────── 单条规则执行 ──────────

def _eval_chart_series_match(actual: List[List[Any]], expected: Any,
                             tol: float = 0.01) -> Tuple[bool, str]:
    """expected 可以是嵌套 list（按 series 比对），或扁平 list（拼起来比对）。"""
    if expected is None:
        return False, "expected 为 None"
    if isinstance(expected, list) and expected and isinstance(expected[0], list):
        if len(actual) != len(expected):
            return False, f"series count: actual={len(actual)} expected={len(expected)}"
        for i, (a_row, e_row) in enumerate(zip(actual, expected)):
            if len(a_row) != len(e_row):
                return False, f"series {i+1} length: {len(a_row)} vs {len(e_row)}"
            for j, (a, e) in enumerate(zip(a_row, e_row)):
                try:
                    if abs(float(a) - float(e)) > tol:
                        return False, f"series {i+1}[{j+1}]: actual={a} expected={e}"
                except Exception:
                    if str(a) != str(e):
                        return False, f"series {i+1}[{j+1}]: actual={a!r} expected={e!r}"
        return True, "match"
    # range: [min, max]
    if isinstance(expected, list) and len(expected) == 2:
        flat = [v for row in actual for v in row]
        try:
            nums = [float(v) for v in flat if v is not None]
            if not nums:
                return False, "actual chart empty"
            a_min, a_max = min(nums), max(nums)
            return (abs(a_min - float(expected[0])) <= tol and
                    abs(a_max - float(expected[1])) <= tol), \
                   f"range actual=[{a_min},{a_max}] expected={expected}"
        except Exception:
            pass
    return False, f"unsupported expected shape: {type(expected).__name__}"


def _resolve_shape_on_new(rule: Dict[str, Any], l0_result, slide_key: str):
    """根据规则的 shape 名（按 template 命名）找 new 侧对应 shape 对象 + name。
    回退：直接按 rule['shape'] 在 new 侧找。
    """
    target_name = rule.get("shape")
    if not target_name:
        return None, None
    if l0_result is None:
        return None, target_name

    shapes = getattr(l0_result, "shapes_by_slide", {}).get(slide_key, {})
    new_shapes = shapes.get("new", {})
    pairs = getattr(l0_result, "pairs_by_slide", {}).get(slide_key, [])

    new_name = None
    for p in pairs:
        if p["template"] == target_name:
            new_name = p["new"]
            break
    if new_name is None:
        # 直接按 template 名找 new（可能名字相同）
        if target_name in new_shapes:
            new_name = target_name
    return new_name, target_name


def run(*, contract, pres_new, pres_template,
        slide_pairs: List[Tuple[int, int]], l0_result=None,
        trace_index=None) -> LayerResult:
    lr = LayerResult(layer="L1")
    rules = contract.rules_for_layer("L1")
    if not rules:
        lr.notes.append("L1: no rules in contract")
        return lr

    # 把 slide_pairs 索引化：tpl_idx -> new_idx
    new_by_tpl = {tpl_idx: new_idx for new_idx, tpl_idx in slide_pairs}

    for rule in rules:
        rid = rule.get("id", "L1_unnamed")
        sev = rule.get("severity", "must_fix")
        slide_filter = rule.get("slide")  # 可选

        # 先评估 skip_if_trace
        skip, reason = _check_skip_if_trace(rule, trace_index)
        if skip:
            lr.add(Finding(
                rule_id=rid, layer="L1", severity="tolerate", passed=False,
                shape=rule.get("shape"),
                message=f"豁免：{reason}",
            ))
            continue

        # 决定本规则要在哪些 slide 上跑
        slides_to_check = []
        for new_idx, tpl_idx in slide_pairs:
            if slide_filter is not None and tpl_idx != int(slide_filter):
                continue
            slides_to_check.append((new_idx, tpl_idx))

        for new_idx, tpl_idx in slides_to_check:
            slide_key = f"p{tpl_idx}"
            new_name, tpl_name = _resolve_shape_on_new(rule, l0_result, slide_key)
            if not new_name:
                lr.add(Finding(
                    rule_id=rid, layer="L1", severity=sev, passed=False,
                    slide=tpl_idx, shape=tpl_name,
                    message=f"shape '{tpl_name}' 在 new 侧找不到对应（L0 配对失败）",
                ))
                continue

            try:
                slide_new = pres_new.Slides(new_idx)
                # 按 name 找 shape
                shape_obj = None
                for i in range(1, slide_new.Shapes.Count + 1):
                    s = slide_new.Shapes(i)
                    if str(s.Name) == new_name:
                        shape_obj = s
                        break
                if shape_obj is None:
                    lr.add(Finding(
                        rule_id=rid, layer="L1", severity=sev, passed=False,
                        slide=tpl_idx, shape=new_name,
                        message=f"slide {new_idx} 上找不到 shape '{new_name}'",
                    ))
                    continue
            except Exception as e:
                lr.add(Finding(
                    rule_id=rid, layer="L1", severity=sev, passed=False,
                    slide=tpl_idx, shape=new_name,
                    message=f"读 shape 失败：{e}",
                ))
                continue

            check = rule.get("check", "")
            expected, exp_note = resolve_expected(rule, contract)

            if check == "text_equals" or check == "text_equals_computed":
                actual = _read_text(shape_obj).strip()
                exp_str = str(expected) if expected is not None else ""
                passed = actual == exp_str
                lr.add(Finding(
                    rule_id=rid, layer="L1", severity=sev, passed=passed,
                    slide=tpl_idx, shape=new_name,
                    message=f"text: actual={actual!r} expected={exp_str!r} ({exp_note})",
                    detail={"actual": actual, "expected": exp_str, "expected_from": exp_note},
                ))

            elif check == "text_contains":
                actual = _read_text(shape_obj)
                sub = str(expected or "")
                passed = sub in actual
                lr.add(Finding(
                    rule_id=rid, layer="L1", severity=sev, passed=passed,
                    slide=tpl_idx, shape=new_name,
                    message=f"text contains {sub!r}: {passed} (actual snippet={actual[:60]!r})",
                ))

            elif check == "chart_series_values":
                actual = _read_chart_series(shape_obj)
                tol = float(rule.get("tolerance", 0.01))
                passed, msg = _eval_chart_series_match(actual, expected, tol=tol)
                lr.add(Finding(
                    rule_id=rid, layer="L1", severity=sev, passed=passed,
                    slide=tpl_idx, shape=new_name,
                    message=f"chart series ({exp_note}): {msg}",
                    detail={"actual": actual, "expected": expected, "expected_from": exp_note},
                ))

            elif check == "chart_series_differs_from_template":
                # new 侧 series 必须与 template 同名 shape 的 series 不同。
                # 完全相同 → FAIL（说明写入根本没生效，还是模板默认值）。
                actual = _read_chart_series(shape_obj)

                # 读 template 侧同名 shape
                tpl_shape_obj = None
                try:
                    slide_tpl = pres_template.Slides(tpl_idx)
                    for i in range(1, slide_tpl.Shapes.Count + 1):
                        s = slide_tpl.Shapes(i)
                        if str(s.Name) == tpl_name:
                            tpl_shape_obj = s
                            break
                except Exception:
                    pass

                if tpl_shape_obj is None:
                    lr.add(Finding(
                        rule_id=rid, layer="L1", severity="warn", passed=False,
                        slide=tpl_idx, shape=new_name,
                        message=f"template 侧找不到 shape '{tpl_name}'，无法比对 series diff",
                    ))
                else:
                    tpl_series = _read_chart_series(tpl_shape_obj)
                    tol = float(rule.get("tolerance", 0.01))
                    # 若 actual == tpl_series（在容差内）则视为没有被写动 → FAIL
                    same, same_msg = _eval_chart_series_match(actual, tpl_series, tol=tol)
                    passed = not same  # 不同才算 PASS
                    lr.add(Finding(
                        rule_id=rid, layer="L1", severity=sev, passed=passed,
                        slide=tpl_idx, shape=new_name,
                        message=(
                            f"chart_series_differs_from_template: "
                            f"{'series 与模板相同（写入未生效）' if same else 'series 与模板不同（写入有效）'}"
                            f" | tpl={tpl_series} actual={actual}"
                        ),
                        detail={"actual": actual, "template": tpl_series, "same": same},
                    ))

            elif check == "picture_present":
                # 能找到 shape_obj 就过
                lr.add(Finding(
                    rule_id=rid, layer="L1", severity=sev, passed=True,
                    slide=tpl_idx, shape=new_name,
                    message="picture present",
                ))

            elif check == "table_cell_equals":
                row = int(rule.get("row", 1))
                col = int(rule.get("col", 1))
                actual = _read_table_cell(shape_obj, row, col).strip()
                exp_str = str(expected) if expected is not None else ""
                passed = actual == exp_str
                lr.add(Finding(
                    rule_id=rid, layer="L1", severity=sev, passed=passed,
                    slide=tpl_idx, shape=new_name,
                    message=f"table[{row},{col}]: actual={actual!r} expected={exp_str!r}",
                ))

            else:
                lr.add(Finding(
                    rule_id=rid, layer="L1", severity="warn", passed=False,
                    slide=tpl_idx, shape=new_name,
                    message=f"未识别的 check: {check!r}",
                ))

    return lr
