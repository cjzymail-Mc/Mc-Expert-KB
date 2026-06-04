#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""L0：shape 配对。是后面所有 layer 的地基。

策略（按契约 shape_pairing.rules 顺序应用）：
  1. manual_overrides     —— 项目契约硬指定
  2. exact name match
  3. strip_clone_suffix   —— 'Picture 12 副本' ≈ 'Picture 12'；'Chart 8 (1)' ≈ 'Chart 8'
  4. ignore_chart_auto_renumber —— Chart 8/12/15/18 ≈ Chart 63（按 type=Chart + 几何近似）[v2]
  5. match_by_position_if_name_lost —— L/T/W/H 近似匹配 [v2]

返回结构（PairingResult）:
  {
    "pairs": [{"new": "Chart 8", "template": "Chart 63", "method": "manual_override"}, ...],
    "only_new": ["TextBox 99"],
    "only_template": ["Picture 50"],
    "notes": ["..."]
  }

并不读取 shape 几何 / 内容；只用 name + 简单 fuzzy。
真实 shape 信息由 caller 在调用前提取（用 win32com 或本 skill 的 shape_extract）。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


CLONE_SUFFIX_PATTERNS = [
    re.compile(r"\s*副本\s*\d*\s*$"),       # PowerPoint 中文 Clone
    re.compile(r"\s*\(\d+\)\s*$"),          # "Picture 12 (1)"
    re.compile(r"\s*-\s*Copy(\s*\d+)?\s*$", re.IGNORECASE),  # English copy
    re.compile(r"\s*Copy of\s+", re.IGNORECASE),
]


@dataclass
class ShapeRef:
    name: str
    shape_type: Optional[str] = None  # 'Chart' / 'Picture' / 'TextBox' / 'Table' / 'AutoShape'
    left: Optional[float] = None
    top: Optional[float] = None
    width: Optional[float] = None
    height: Optional[float] = None


@dataclass
class PairingResult:
    pairs: List[Dict[str, str]] = field(default_factory=list)
    only_new: List[str] = field(default_factory=list)
    only_template: List[str] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)


def strip_clone_suffix(name: str) -> str:
    """去掉 clone 后缀，返回 base name。"""
    s = name
    for pat in CLONE_SUFFIX_PATTERNS:
        s = pat.sub("", s)
    return s.strip()


def _name_kind(name: str) -> Tuple[str, Optional[int]]:
    """从 shape name 拆出 ('Chart', 63) / ('TextBox', 50) 这种结构。"""
    m = re.match(r"^([A-Za-z]+)\s*(\d+)?", name.strip())
    if not m:
        return (name.strip(), None)
    kind = m.group(1)
    num = int(m.group(2)) if m.group(2) else None
    return (kind, num)


def pair_shapes(
    new_shapes: List[ShapeRef],
    template_shapes: List[ShapeRef],
    *,
    manual_overrides: Optional[Dict[str, str]] = None,
    rules: Optional[List[str]] = None,
    geometry_tolerance: float = 5.0,
) -> PairingResult:
    """配对两份 shape 列表。

    Args:
      new_shapes / template_shapes: 待配对的 ShapeRef 列表
      manual_overrides: {new_name: template_name} 项目契约硬指定
      rules: 启用的策略列表，默认 ['strip_clone_suffix']
      geometry_tolerance: ignore_chart_auto_renumber / match_by_position_if_name_lost
                          时用的 L/T 容差（PPT 点）
    """
    manual_overrides = manual_overrides or {}
    rules = rules or ["strip_clone_suffix"]

    result = PairingResult()
    new_by_name = {s.name: s for s in new_shapes}
    tpl_by_name = {s.name: s for s in template_shapes}
    matched_new: set[str] = set()
    matched_tpl: set[str] = set()

    # 1. manual_overrides
    for new_name, tpl_name in manual_overrides.items():
        if new_name in new_by_name and tpl_name in tpl_by_name:
            result.pairs.append({
                "new": new_name, "template": tpl_name, "method": "manual_override"
            })
            matched_new.add(new_name)
            matched_tpl.add(tpl_name)
        else:
            result.notes.append(
                f"manual_override 失败：new='{new_name}' tpl='{tpl_name}' "
                f"（new in shapes={new_name in new_by_name}, "
                f"tpl in shapes={tpl_name in tpl_by_name}）"
            )

    # 2. exact name match
    for name in list(new_by_name.keys()):
        if name in matched_new:
            continue
        if name in tpl_by_name and name not in matched_tpl:
            result.pairs.append({
                "new": name, "template": name, "method": "exact"
            })
            matched_new.add(name)
            matched_tpl.add(name)

    # 3. strip_clone_suffix
    if "strip_clone_suffix" in rules:
        tpl_base_to_name: Dict[str, str] = {}
        for name in tpl_by_name:
            if name in matched_tpl:
                continue
            tpl_base_to_name.setdefault(strip_clone_suffix(name), name)

        for name in list(new_by_name.keys()):
            if name in matched_new:
                continue
            base = strip_clone_suffix(name)
            if base in tpl_base_to_name:
                tpl_name = tpl_base_to_name.pop(base)
                if tpl_name in matched_tpl:
                    continue
                result.pairs.append({
                    "new": name, "template": tpl_name, "method": "strip_clone_suffix"
                })
                matched_new.add(name)
                matched_tpl.add(tpl_name)

    # 4. ignore_chart_auto_renumber —— 同 kind + 几何近似（仅对 Chart/Picture）
    if "ignore_chart_auto_renumber" in rules:
        for new_name, new_s in new_by_name.items():
            if new_name in matched_new:
                continue
            new_kind, _ = _name_kind(new_name)
            if new_kind not in ("Chart", "Picture"):
                continue
            best_tpl = None
            best_dist = float("inf")
            for tpl_name, tpl_s in tpl_by_name.items():
                if tpl_name in matched_tpl:
                    continue
                tpl_kind, _ = _name_kind(tpl_name)
                if tpl_kind != new_kind:
                    continue
                if new_s.left is None or tpl_s.left is None:
                    continue
                dist = abs((new_s.left or 0) - (tpl_s.left or 0)) + \
                       abs((new_s.top or 0) - (tpl_s.top or 0))
                if dist < best_dist and dist <= geometry_tolerance * 4:
                    best_dist = dist
                    best_tpl = tpl_name
            if best_tpl:
                result.pairs.append({
                    "new": new_name, "template": best_tpl,
                    "method": f"ignore_chart_auto_renumber(dist={best_dist:.1f})"
                })
                matched_new.add(new_name)
                matched_tpl.add(best_tpl)

    # 5. match_by_position_if_name_lost —— 不限 kind 的几何匹配（兜底）
    if "match_by_position_if_name_lost" in rules:
        for new_name, new_s in new_by_name.items():
            if new_name in matched_new:
                continue
            if new_s.left is None:
                continue
            best_tpl = None
            best_dist = float("inf")
            for tpl_name, tpl_s in tpl_by_name.items():
                if tpl_name in matched_tpl:
                    continue
                if tpl_s.left is None:
                    continue
                dist = abs((new_s.left or 0) - (tpl_s.left or 0)) + \
                       abs((new_s.top or 0) - (tpl_s.top or 0))
                if dist < best_dist and dist <= geometry_tolerance:
                    best_dist = dist
                    best_tpl = tpl_name
            if best_tpl:
                result.pairs.append({
                    "new": new_name, "template": best_tpl,
                    "method": f"position(dist={best_dist:.1f})"
                })
                matched_new.add(new_name)
                matched_tpl.add(best_tpl)

    # 收尾
    for name in new_by_name:
        if name not in matched_new:
            result.only_new.append(name)
    for name in tpl_by_name:
        if name not in matched_tpl:
            result.only_template.append(name)

    return result


if __name__ == "__main__":
    print("pairing.py self-test")

    # Test strip_clone_suffix
    assert strip_clone_suffix("Picture 12 副本") == "Picture 12"
    assert strip_clone_suffix("Picture 12 副本 2") == "Picture 12"
    assert strip_clone_suffix("Chart 8 (1)") == "Chart 8"
    assert strip_clone_suffix("Picture 12") == "Picture 12"

    # Test exact match
    a = [ShapeRef("TextBox 1"), ShapeRef("Chart 8")]
    b = [ShapeRef("TextBox 1"), ShapeRef("Chart 8")]
    r = pair_shapes(a, b)
    assert len(r.pairs) == 2
    assert r.only_new == []
    assert r.only_template == []

    # Test strip_clone_suffix
    a = [ShapeRef("Picture 12 副本")]
    b = [ShapeRef("Picture 12")]
    r = pair_shapes(a, b)
    assert len(r.pairs) == 1
    assert r.pairs[0]["method"] == "strip_clone_suffix"

    # Test manual_overrides
    a = [ShapeRef("Chart 8")]
    b = [ShapeRef("Chart 63")]
    r = pair_shapes(a, b, manual_overrides={"Chart 8": "Chart 63"})
    assert len(r.pairs) == 1
    assert r.pairs[0]["method"] == "manual_override"

    # Test ignore_chart_auto_renumber
    a = [ShapeRef("Chart 8", "Chart", left=100, top=100, width=200, height=150)]
    b = [ShapeRef("Chart 63", "Chart", left=101, top=99, width=200, height=150)]
    r = pair_shapes(a, b, rules=["ignore_chart_auto_renumber"])
    assert len(r.pairs) == 1
    assert "ignore_chart_auto_renumber" in r.pairs[0]["method"]

    # Test only_new / only_template
    a = [ShapeRef("TextBox 99")]
    b = [ShapeRef("Picture 50")]
    r = pair_shapes(a, b)
    assert r.only_new == ["TextBox 99"]
    assert r.only_template == ["Picture 50"]

    print("  OK")
