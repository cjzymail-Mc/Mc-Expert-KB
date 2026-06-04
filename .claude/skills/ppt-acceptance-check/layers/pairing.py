#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""L0 配对层 —— 把 contract.shape_pairing + COM shape 提取串起来。

调用上层 pairing.pair_shapes 做实际匹配；
本模块负责按 slide_pairs 循环 + 把结果写成 Finding。
"""
from __future__ import annotations

from typing import Any, Dict, List, Tuple

import pairing as pairing_engine
from layers.common import Finding, LayerResult, extract_slide_shape_refs


def run(*, contract, pres_new, pres_template, slide_pairs: List[Tuple[int, int]]) -> LayerResult:
    """L0 跑配对。

    Args:
      contract: Contract 对象
      pres_new / pres_template: COM Presentation 对象
      slide_pairs: [(new_idx, template_idx), ...]

    Returns: LayerResult，附加 ctx 数据以便后续层复用：
      result.notes 第一项是 'pairs_by_slide' 的 JSON 路径...
    其实更优雅的是直接挂在 LayerResult 上。我们 hack 一个属性。
    """
    lr = LayerResult(layer="L0")
    pairs_by_slide: Dict[str, List[Dict[str, str]]] = {}
    shapes_by_slide: Dict[str, Dict[str, Any]] = {}

    sp_cfg = contract.shape_pairing
    rules = sp_cfg.get("rules", ["strip_clone_suffix"])
    geom_tol = contract.tolerance("geometry_px", 2.0)

    for new_idx, tpl_idx in slide_pairs:
        slide_key = f"p{tpl_idx}"
        try:
            slide_new = pres_new.Slides(new_idx)
            slide_tpl = pres_template.Slides(tpl_idx)
        except Exception as e:
            lr.add(Finding(
                rule_id="L0_slide_access",
                layer="L0", severity="must_fix", passed=False,
                slide=tpl_idx,
                message=f"无法读取 slide_pair {new_idx}:{tpl_idx}: {e}",
            ))
            continue

        new_refs = extract_slide_shape_refs(slide_new)
        tpl_refs = extract_slide_shape_refs(slide_tpl)

        result = pairing_engine.pair_shapes(
            new_refs, tpl_refs,
            manual_overrides=contract.manual_overrides(slide_key),
            rules=rules,
            geometry_tolerance=geom_tol,
        )

        pairs_by_slide[slide_key] = result.pairs
        shapes_by_slide[slide_key] = {
            "new": {s.name: s for s in new_refs},
            "template": {s.name: s for s in tpl_refs},
            "new_idx": new_idx,
            "template_idx": tpl_idx,
        }

        # 命中即 PASS，不命中（只在一方）按 must_fix 报
        for pair in result.pairs:
            lr.add(Finding(
                rule_id=f"L0_pair_{pair['new']}",
                layer="L0", severity="must_fix", passed=True,
                slide=tpl_idx, shape=pair["new"],
                message=f"{pair['new']} ↔ {pair['template']} via {pair['method']}",
            ))
        for name in result.only_new:
            lr.add(Finding(
                rule_id=f"L0_only_new_{name}",
                layer="L0", severity="warn", passed=False,
                slide=tpl_idx, shape=name,
                message=f"仅在 new 中：{name}（template 无对应 shape）",
            ))
        for name in result.only_template:
            lr.add(Finding(
                rule_id=f"L0_only_template_{name}",
                layer="L0", severity="warn", passed=False,
                slide=tpl_idx, shape=name,
                message=f"仅在 template 中：{name}（new 无对应 shape）",
            ))
        for note in result.notes:
            lr.notes.append(f"[p{tpl_idx}] {note}")

    # 挂在 LayerResult 上供后续层复用（共享 pairing 结果）
    lr.pairs_by_slide = pairs_by_slide  # type: ignore[attr-defined]
    lr.shapes_by_slide = shapes_by_slide  # type: ignore[attr-defined]
    return lr
