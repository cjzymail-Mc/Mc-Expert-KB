#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""[L3 空值层 · 第二批] —— 契约声明"必填区"，断言无空格残留。

语义：必填区里出现空格 = 漏填 → must_fix（默认）。**非必填区的空不报**
（与第一步 inspect-excel `--blanks` 的"全量盘点"分工不同：那是体检，这是红线断言）。
吃第一步同款判空语义（None / "" / 纯空白 / \\x07 算空）+ 合并格读主格（防成员格假空）。

必填区声明（锚点优先级 name > range > cells）：
  rule.name   NamedRange，区内所有格须非空
  rule.range  'A4:E9' A1 区间，区内所有格须非空（合并格按主格只判一次）
  rule.cells  ['C4','H4',...] 显式地址清单

check：no_blank_in_required（唯一）。severity 默认 must_fix。
"""
from __future__ import annotations

from typing import Any, List, Tuple

from layers.common import Finding, LayerResult
from layers import xlcom

_CELL_CAP = 5000  # 必填区遍历上限（必填区本应小而显式，超出只是兜底防呆）


def _is_blank(v: Any) -> bool:
    if v is None:
        return True
    s = str(v).strip()
    return s == "" or s == "\x07"


def _collect_targets(sh, rng) -> List[Tuple[str, Any]]:
    """遍历一个 Range 的单元格 → [(address, value)]，合并格按主格只收一次。"""
    out: List[Tuple[str, Any]] = []
    seen = set()
    try:
        total = int(xlcom.com_get(rng.Cells, "Count", 0) or 0)
    except Exception:
        total = 0
    if total > _CELL_CAP:
        return out  # 调用方据空列表给 degraded note
    try:
        cells_iter = rng.Cells
    except Exception:
        return out
    for cell in cells_iter:
        try:
            if bool(xlcom.com_get(cell, "MergeCells", False)):
                top = cell.MergeArea.Cells(1, 1)
                addr = str(xlcom.com_get(top, "Address", "")).replace("$", "")
                if addr in seen:
                    continue
                seen.add(addr)
                out.append((addr, xlcom.com_get(top, "Value", None)))
            else:
                addr = str(xlcom.com_get(cell, "Address", "")).replace("$", "")
                out.append((addr, xlcom.com_get(cell, "Value", None)))
        except Exception:
            continue
    return out


def run(*, contract, wb) -> LayerResult:
    lr = LayerResult(layer="L3")
    rules = contract.rules_for_layer("L3")
    if not rules:
        lr.notes.append("L3: no rules in contract")
        return lr

    for rule in rules:
        rid = rule.get("id", "L3_unnamed")
        sev = rule.get("severity", "must_fix")
        check = rule.get("check", "no_blank_in_required")
        if check != "no_blank_in_required":
            lr.add(Finding(rule_id=rid, layer="L3", severity="warn", passed=False,
                           message=f"未识别的 check: {check!r}"))
            continue

        targets: List[Tuple[str, Any]] = []
        locator = ""
        capped = False

        # 1) NamedRange
        name = rule.get("name")
        if name:
            sh, rng = xlcom.resolve_named_range(wb, name)
            if rng is None:
                lr.add(Finding(rule_id=rid, layer="L3", severity=sev, passed=False,
                               shape=f"name:{name}", message=f"NamedRange '{name}' 未找到"))
                continue
            locator = f"name:{name}"
            targets = _collect_targets(sh, rng)
            capped = not targets
        else:
            sheet_name = rule.get("sheet")
            sh, matched = xlcom.resolve_sheet(wb, name=sheet_name, fuzzy=sheet_name)
            if sh is None:
                lr.add(Finding(rule_id=rid, layer="L3", severity=sev, passed=False,
                               shape=str(sheet_name),
                               message=f"sheet '{sheet_name}' 未找到"))
                continue
            # 2) range
            if rule.get("range"):
                locator = f"{matched}!{rule['range']}"
                try:
                    rng = sh.Range(rule["range"])
                    targets = _collect_targets(sh, rng)
                    capped = not targets
                except Exception as e:
                    lr.add(Finding(rule_id=rid, layer="L3", severity=sev, passed=False,
                                   shape=locator, message=f"range '{rule['range']}' 解析失败: {e}"))
                    continue
            # 3) cells 显式清单
            elif rule.get("cells"):
                locator = f"{matched}!cells"
                for a1 in rule["cells"]:
                    targets.append((str(a1), xlcom.read_cell_value(sh, str(a1))))
            else:
                lr.add(Finding(rule_id=rid, layer="L3", severity=sev, passed=False,
                               shape=matched, message="规则缺必填区声明(name/range/cells)"))
                continue

        if capped:
            lr.degraded = True
            lr.degraded_reason = f"{rid}: 必填区超 {_CELL_CAP} 格，跳过（必填区应小而显式）"
            lr.add(Finding(rule_id=rid, layer="L3", severity="warn", passed=False,
                           shape=locator,
                           message=f"必填区过大(>{_CELL_CAP} 格)，未断言——请收窄必填区声明"))
            continue

        blanks = [addr for addr, val in targets if _is_blank(val)]
        passed = not blanks
        lr.add(Finding(
            rule_id=rid, layer="L3", severity=sev, passed=passed, shape=locator,
            message=(f"必填区 {len(targets)} 格全部已填" if passed
                     else f"必填区 {len(targets)} 格中 {len(blanks)} 格为空(漏填): {blanks[:50]}"),
            detail={"required": len(targets), "blank": len(blanks),
                    "blank_addresses": blanks[:200]},
        ))

    return lr
