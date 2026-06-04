#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""[L0 结构层] —— 断言 xlsx-under-test 的结构性事实：
sheet 是否存在 / UsedRange 维度下限 / 表头是否含必有列名。

结构性断言**豁免护栏①**（可在契约 inline 写期望的 sheet 名 / 列名 / 维度——
这些是结构契约，不是工艺单业务值）。

锚点优先级：NamedRange > sheet+表头列名 > A1。`Cells(r,c)` 裸数字不出现在业务逻辑。

支持的 check：
  sheet_exists      rule.sheet（精确或模糊）能解析到 worksheet
  dimensions_min    rule.expected = {"rows": N, "cols": M}，UsedRange 维度 >=
  has_columns       rule.expected = ["列名A","列名B"]，header_row 行须全部含
  named_range_exists rule.name 的定义名存在
"""
from __future__ import annotations

from typing import Any, Dict, List

from layers.common import Finding, LayerResult
from layers import xlcom


def run(*, contract, wb) -> LayerResult:
    lr = LayerResult(layer="L0")
    rules = contract.rules_for_layer("L0")
    if not rules:
        lr.notes.append("L0: no rules in contract")
        return lr

    header_row = int((contract.raw.get("structure") or {}).get("header_row", 1) or 1)

    for rule in rules:
        rid = rule.get("id", "L0_unnamed")
        sev = rule.get("severity", "must_fix")
        check = rule.get("check", "")
        sheet_name = rule.get("sheet")

        if check == "named_range_exists":
            name = rule.get("name", "")
            sh, rng = xlcom.resolve_named_range(wb, name)
            passed = rng is not None
            lr.add(Finding(rule_id=rid, layer="L0", severity=sev, passed=passed,
                           shape=f"name:{name}",
                           message=f"NamedRange '{name}' 存在: {passed}"))
            continue

        # 其余 check 都需要先解析 sheet
        sh, matched = xlcom.resolve_sheet(wb, name=sheet_name, fuzzy=sheet_name)

        if check == "sheet_exists":
            passed = sh is not None
            lr.add(Finding(rule_id=rid, layer="L0", severity=sev, passed=passed,
                           shape=str(sheet_name),
                           message=f"sheet '{sheet_name}' 存在: {passed}"
                                   + (f"（匹配到 '{matched}'）" if passed and matched != sheet_name else "")))
            continue

        if sh is None:
            lr.add(Finding(rule_id=rid, layer="L0", severity=sev, passed=False,
                           shape=str(sheet_name),
                           message=f"sheet '{sheet_name}' 未找到，无法跑 {check}"))
            continue

        if check == "dimensions_min":
            rows, cols, addr = xlcom.used_dims(sh)
            exp = rule.get("expected") or {}
            min_rows = int(exp.get("rows", 0) or 0)
            min_cols = int(exp.get("cols", 0) or 0)
            passed = rows >= min_rows and cols >= min_cols
            lr.add(Finding(
                rule_id=rid, layer="L0", severity=sev, passed=passed, shape=matched,
                message=f"维度 {rows}×{cols} (used={addr}) >= 下限 {min_rows}×{min_cols}: {passed}",
                detail={"rows": rows, "cols": cols, "min_rows": min_rows, "min_cols": min_cols},
            ))

        elif check == "has_columns":
            want = rule.get("expected") or []
            if isinstance(want, str):
                want = [want]
            headers = xlcom.header_cells(sh, header_row)
            missing = [w for w in want
                       if not any(w == h or (w and w in h) for h in headers)]
            passed = not missing
            lr.add(Finding(
                rule_id=rid, layer="L0", severity=sev, passed=passed, shape=matched,
                message=f"必有列 {want}（header_row={header_row}）"
                        + ("：全部命中" if passed else f"：缺 {missing}"),
                detail={"want": want, "missing": missing, "headers": headers[:40]},
            ))

        else:
            lr.add(Finding(rule_id=rid, layer="L0", severity="warn", passed=False,
                           shape=matched or str(sheet_name),
                           message=f"未识别的 check: {check!r}"))

    return lr
