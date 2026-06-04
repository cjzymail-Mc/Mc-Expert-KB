#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""L5 视觉层 —— 导出 PNG + SSIM 比对.

吸收自 ppt-visual-fidelity-check（slide_export_png + ssim_compare）。
SSIM 阈值从契约 tolerances.ssim_threshold 读，默认 0.96。

每对 slide_pair 出一条 Finding（PASS/FAIL = SSIM ≥ 阈值）。
导出的 PNG 落在 out_dir / "visual" 下方便人审。
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import List, Tuple

from layers.common import Finding, LayerResult


def _import_visual_funcs():
    """复用 ppt-visual-fidelity-check 的函数，避免重写。"""
    visual_skill = Path.home() / ".claude" / "skills" / "ppt-visual-fidelity-check"
    if str(visual_skill) not in sys.path:
        sys.path.insert(0, str(visual_skill))
    from ppt_visual_check import slide_export_png, ssim_compare
    return slide_export_png, ssim_compare


def run(*, contract, ppt_app, pres_new, pres_template,
        slide_pairs: List[Tuple[int, int]], out_dir: Path) -> LayerResult:
    lr = LayerResult(layer="L5")
    threshold = contract.tolerance("ssim_threshold", 0.96)

    try:
        slide_export_png, ssim_compare = _import_visual_funcs()
    except Exception as e:
        lr.degraded = True
        lr.degraded_reason = f"无法加载 ppt-visual-fidelity-check: {e}"
        return lr

    visual_dir = Path(out_dir) / "visual"
    visual_dir.mkdir(parents=True, exist_ok=True)

    for new_idx, tpl_idx in slide_pairs:
        try:
            slide_new = pres_new.Slides(new_idx)
            slide_tpl = pres_template.Slides(tpl_idx)
        except Exception as e:
            lr.add(Finding(
                rule_id=f"L5_ssim_p{tpl_idx}", layer="L5", severity="must_fix",
                passed=False, slide=tpl_idx,
                message=f"slide 访问失败：{e}",
            ))
            continue

        out_new = visual_dir / f"new_{new_idx:03d}.png"
        out_tpl = visual_dir / f"template_{tpl_idx:03d}.png"
        ok_new = slide_export_png(ppt_app, slide_new, str(out_new))
        ok_tpl = slide_export_png(ppt_app, slide_tpl, str(out_tpl))
        if not (ok_new and ok_tpl):
            lr.add(Finding(
                rule_id=f"L5_ssim_p{tpl_idx}", layer="L5", severity="warn",
                passed=False, slide=tpl_idx,
                message=f"PNG 导出失败（new={ok_new} tpl={ok_tpl}）",
            ))
            continue

        score = ssim_compare(str(out_new), str(out_tpl))
        passed = score >= threshold
        lr.add(Finding(
            rule_id=f"L5_ssim_p{tpl_idx}", layer="L5", severity="must_fix",
            passed=passed, slide=tpl_idx,
            message=f"SSIM={score:.4f} (threshold={threshold})",
            detail={
                "ssim": score, "threshold": threshold,
                "png_new": str(out_new), "png_template": str(out_tpl),
            },
        ))

    return lr
