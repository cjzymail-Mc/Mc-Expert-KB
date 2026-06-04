#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""L2 格式层 —— shape 几何 / fill / AutoSize / 字号差异.

支持的 check：
  geometry_within_tolerance  L/T/W/H 在 contract.tolerances.geometry_px 范围内
  autosize_matches_template  TextFrame.AutoSize 一致
  font_size_within_tolerance 段落 0 字号在 font_size_pt 范围内
  fill_color_equals          shape.Fill.ForeColor.RGB 一致

shape: "*" 表示对所有配对 shape 跑。
缺少 L2 规则时，自动加默认两条：
  - geometry_global (must_fix)
  - autosize_global (warn)
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from layers.common import Finding, LayerResult


DEFAULT_RULES = [
    {
        "id": "geometry_global", "shape": "*", "layer": "L2",
        "check": "geometry_within_tolerance", "severity": "must_fix",
    },
    {
        "id": "autosize_global", "shape": "*", "layer": "L2",
        "check": "autosize_matches_template", "severity": "warn",
    },
]


def _geom(shape) -> Dict[str, float]:
    try:
        return {
            "left": float(getattr(shape, "Left", 0) or 0),
            "top": float(getattr(shape, "Top", 0) or 0),
            "width": float(getattr(shape, "Width", 0) or 0),
            "height": float(getattr(shape, "Height", 0) or 0),
        }
    except Exception:
        return {"left": 0, "top": 0, "width": 0, "height": 0}


def _autosize(shape) -> Optional[int]:
    try:
        if int(getattr(shape, "HasTextFrame", 0) or 0) != -1:
            return None
        return int(shape.TextFrame.AutoSize)
    except Exception:
        return None


def _para0_font_size(shape) -> Optional[float]:
    try:
        if int(getattr(shape, "HasTextFrame", 0) or 0) != -1:
            return None
        para = shape.TextFrame.TextRange.Paragraphs(1)
        return float(para.Font.Size)
    except Exception:
        return None


def _fill_rgb(shape) -> Optional[int]:
    try:
        return int(shape.Fill.ForeColor.RGB)
    except Exception:
        return None


def _shape_by_name(slide, name: str):
    try:
        for i in range(1, slide.Shapes.Count + 1):
            s = slide.Shapes(i)
            if str(s.Name) == name:
                return s
    except Exception:
        pass
    return None


def _iter_targets(rule, l0_result, slide_pairs):
    """yield (new_idx, tpl_idx, new_name, tpl_name) for each shape this rule covers.

    支持 (2026-05-27 fix6-c)：
      - rule.shape = "*" 时，rule.excludes (list of shape names) 内的 shape 跳过
        （用于"全局规则 + 某 shape 设计上不该被规则覆盖"，如 apparel TextBox 24
         按样本数动态拉长 height）。
      - rule.slide (int) 限定只在某一个 template slide 上跑（已有，未受影响）。
    """
    target = rule.get("shape", "*")
    excludes = set(rule.get("excludes", []) or [])
    slide_filter = rule.get("slide")
    for new_idx, tpl_idx in slide_pairs:
        if slide_filter is not None and tpl_idx != int(slide_filter):
            continue
        slide_key = f"p{tpl_idx}"
        pairs = getattr(l0_result, "pairs_by_slide", {}).get(slide_key, []) if l0_result else []
        if target == "*":
            for p in pairs:
                if p["template"] in excludes or p["new"] in excludes:
                    continue
                yield (new_idx, tpl_idx, p["new"], p["template"])
        else:
            for p in pairs:
                if p["template"] == target or p["new"] == target:
                    yield (new_idx, tpl_idx, p["new"], p["template"])
                    break


def run(*, contract, pres_new, pres_template,
        slide_pairs: List[Tuple[int, int]], l0_result=None) -> LayerResult:
    lr = LayerResult(layer="L2")
    rules = contract.rules_for_layer("L2")
    if not rules:
        rules = DEFAULT_RULES
        lr.notes.append("L2: 无契约规则，已应用默认 geometry + autosize")

    geom_tol = contract.tolerance("geometry_px", 2.0)
    font_tol = contract.tolerance("font_size_pt", 0.5)

    for rule in rules:
        rid = rule.get("id", "L2_unnamed")
        sev = rule.get("severity", "must_fix")
        check = rule.get("check", "")

        for new_idx, tpl_idx, new_name, tpl_name in _iter_targets(rule, l0_result, slide_pairs):
            try:
                slide_new = pres_new.Slides(new_idx)
                slide_tpl = pres_template.Slides(tpl_idx)
                shape_new = _shape_by_name(slide_new, new_name)
                shape_tpl = _shape_by_name(slide_tpl, tpl_name)
                if shape_new is None or shape_tpl is None:
                    lr.add(Finding(
                        rule_id=f"{rid}::{new_name}", layer="L2", severity=sev,
                        passed=False, slide=tpl_idx, shape=new_name,
                        message=f"shape 未找到（new={shape_new is not None} tpl={shape_tpl is not None}）",
                    ))
                    continue
            except Exception as e:
                lr.add(Finding(
                    rule_id=f"{rid}::{new_name}", layer="L2", severity=sev,
                    passed=False, slide=tpl_idx, shape=new_name,
                    message=f"shape 读取失败：{e}",
                ))
                continue

            if check == "geometry_within_tolerance":
                # fix6-c: rule.tolerance 覆盖全局 geom_tol（用于已知设计上动态变形的 shape，
                # 如 apparel TextBox 24 按样本数拉长 height —— per-shape rule 配 tolerance:200,
                # severity:warn 比全局严格 2px 更准确）
                rule_tol = float(rule.get("tolerance", geom_tol))
                gn, gt = _geom(shape_new), _geom(shape_tpl)
                diffs = {k: abs(gn[k] - gt[k]) for k in ("left", "top", "width", "height")}
                worst = max(diffs.items(), key=lambda kv: kv[1])
                passed = worst[1] <= rule_tol
                lr.add(Finding(
                    rule_id=f"{rid}::{new_name}", layer="L2", severity=sev,
                    passed=passed, slide=tpl_idx, shape=new_name,
                    message=f"geom diff worst={worst[0]}={worst[1]:.2f} (tol={rule_tol})",
                    detail={"new": gn, "template": gt, "diffs": diffs, "tolerance": rule_tol},
                ))

            elif check == "autosize_matches_template":
                an, at = _autosize(shape_new), _autosize(shape_tpl)
                if an is None and at is None:
                    continue  # 非文本 shape 跳过
                passed = an == at
                lr.add(Finding(
                    rule_id=f"{rid}::{new_name}", layer="L2", severity=sev,
                    passed=passed, slide=tpl_idx, shape=new_name,
                    message=f"autosize: new={an} template={at}",
                    detail={"new": an, "template": at},
                ))

            elif check == "font_size_within_tolerance":
                fn, ft = _para0_font_size(shape_new), _para0_font_size(shape_tpl)
                if fn is None and ft is None:
                    continue
                if fn is None or ft is None:
                    lr.add(Finding(
                        rule_id=f"{rid}::{new_name}", layer="L2", severity=sev,
                        passed=False, slide=tpl_idx, shape=new_name,
                        message=f"font size only one side readable: new={fn} template={ft}",
                    ))
                    continue
                diff = abs(fn - ft)
                passed = diff <= font_tol
                lr.add(Finding(
                    rule_id=f"{rid}::{new_name}", layer="L2", severity=sev,
                    passed=passed, slide=tpl_idx, shape=new_name,
                    message=f"font size diff={diff:.2f} (tol={font_tol})",
                    detail={"new": fn, "template": ft},
                ))

            elif check == "fill_color_equals":
                cn, ct = _fill_rgb(shape_new), _fill_rgb(shape_tpl)
                if cn is None and ct is None:
                    continue
                passed = cn == ct
                lr.add(Finding(
                    rule_id=f"{rid}::{new_name}", layer="L2", severity=sev,
                    passed=passed, slide=tpl_idx, shape=new_name,
                    message=f"fill RGB: new={cn} template={ct}",
                ))

            else:
                lr.add(Finding(
                    rule_id=f"{rid}::{new_name}", layer="L2", severity="warn",
                    passed=False, slide=tpl_idx, shape=new_name,
                    message=f"未识别的 check: {check!r}",
                ))

    return lr
