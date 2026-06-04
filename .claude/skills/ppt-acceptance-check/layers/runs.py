#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""L3 染色 / Runs 层 —— character-run 级别的字体 / 颜色断言.

支持的 check：
  has_color_runs        该 shape 至少有 N 个"非默认色"或"非默认 bold"的 run
                        expected_min（默认 1）
  has_bold_runs         bold=True 的 run 数 ≥ expected_min
  runs_match_template   新 shape 的 run 结构（颜色/bold 切换点）和模板对齐
                        ⚠ 模板=旧样式 / 代码=新样式时不可用：会把"shape 根本没动"
                        和"shape 改对了"都算 PASS，需要用 runs_match_signature
  runs_match_signature  与契约内嵌的 expected_runs 严格对比，**不依赖 template**
                        适合"代码意图升级超出模板原状态"——比如同 shape 多字号/多
                        颜色的视觉契约。默认过滤纯空白 run（CR/LF 段间分隔符）

依赖 L0 的 pairing 结果；shape 配对失败的会出 must_fix Finding（而不是像昨天那样
runs 报告全空什么都没说）。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from layers.common import Finding, LayerResult


def _shape_by_name(slide, name: str):
    try:
        for i in range(1, slide.Shapes.Count + 1):
            s = slide.Shapes(i)
            if str(s.Name) == name:
                return s
    except Exception:
        pass
    return None


def _walk_runs(shape) -> List[Dict[str, Any]]:
    """逐字符扫描 shape.TextFrame.TextRange，按 (rgb, bold, italic, size) 切 run。

    返回 [{"start": 1, "len": 5, "rgb": 0xFF0000, "bold": True, "italic": False, "size": 16.0, "text": "红色"}, ...]
    无文本框时返回 []。
    """
    runs: List[Dict[str, Any]] = []
    try:
        if int(getattr(shape, "HasTextFrame", 0) or 0) != -1:
            return runs
        tr = shape.TextFrame.TextRange
        n = int(tr.Length)
        if n <= 0:
            return runs

        def _attrs(idx: int):
            try:
                ch = tr.Characters(idx, 1)
                try:
                    rgb = int(ch.Font.Color.RGB)
                except Exception:
                    rgb = None
                try:
                    bold = int(ch.Font.Bold)  # -1 True, 0 False
                except Exception:
                    bold = None
                try:
                    italic = int(ch.Font.Italic)  # -1 True, 0 False
                except Exception:
                    italic = None
                try:
                    size = float(ch.Font.Size)
                except Exception:
                    size = None
                try:
                    txt = str(ch.Text)
                except Exception:
                    txt = ""
                return rgb, bold, italic, size, txt
            except Exception:
                return None, None, None, None, ""

        cur_rgb, cur_bold, cur_italic, cur_size, cur_text = _attrs(1)
        cur_start = 1
        cur_len = 1
        for i in range(2, n + 1):
            rgb, bold, italic, size, txt = _attrs(i)
            if (rgb, bold, italic, size) == (cur_rgb, cur_bold, cur_italic, cur_size):
                cur_len += 1
                cur_text += txt
            else:
                runs.append({"start": cur_start, "len": cur_len,
                             "rgb": cur_rgb, "bold": cur_bold,
                             "italic": cur_italic, "size": cur_size,
                             "text": cur_text})
                cur_start, cur_len = i, 1
                cur_rgb, cur_bold, cur_italic, cur_size, cur_text = rgb, bold, italic, size, txt
        runs.append({"start": cur_start, "len": cur_len,
                     "rgb": cur_rgb, "bold": cur_bold,
                     "italic": cur_italic, "size": cur_size,
                     "text": cur_text})
    except Exception:
        pass
    return runs


def _count_non_default_color_runs(runs: List[Dict[str, Any]]) -> int:
    if not runs:
        return 0
    default_rgb = runs[0]["rgb"]
    return sum(1 for r in runs if r["rgb"] != default_rgb)


def _count_bold_runs(runs: List[Dict[str, Any]]) -> int:
    return sum(1 for r in runs if r["bold"] == -1)


def _iter_targets(rule, l0_result, slide_pairs):
    target = rule.get("shape", "*")
    slide_filter = rule.get("slide")  # 可选 tpl_idx 过滤；不设则对所有 slide_pairs 跑
    for new_idx, tpl_idx in slide_pairs:
        if slide_filter is not None and tpl_idx != int(slide_filter):
            continue
        slide_key = f"p{tpl_idx}"
        pairs = getattr(l0_result, "pairs_by_slide", {}).get(slide_key, []) if l0_result else []
        if target == "*":
            for p in pairs:
                yield (new_idx, tpl_idx, p["new"], p["template"])
        else:
            matched = False
            for p in pairs:
                if p["template"] == target or p["new"] == target:
                    yield (new_idx, tpl_idx, p["new"], p["template"])
                    matched = True
                    break
            if not matched and l0_result is not None:
                # 配对失败：发 must_fix Finding 让 caller 知道
                yield (new_idx, tpl_idx, None, target)


def run(*, contract, pres_new, pres_template,
        slide_pairs: List[Tuple[int, int]], l0_result=None) -> LayerResult:
    lr = LayerResult(layer="L3")
    rules = contract.rules_for_layer("L3")
    if not rules:
        lr.notes.append("L3: no rules in contract")
        return lr

    for rule in rules:
        rid = rule.get("id", "L3_unnamed")
        sev = rule.get("severity", "must_fix")
        check = rule.get("check", "")

        for new_idx, tpl_idx, new_name, tpl_name in _iter_targets(rule, l0_result, slide_pairs):
            if new_name is None:
                lr.add(Finding(
                    rule_id=f"{rid}::{tpl_name}", layer="L3", severity=sev, passed=False,
                    slide=tpl_idx, shape=tpl_name,
                    message=f"shape '{tpl_name}' 在 new 侧找不到对应（L0 配对失败）",
                ))
                continue

            try:
                slide_new = pres_new.Slides(new_idx)
                shape_new = _shape_by_name(slide_new, new_name)
                if shape_new is None:
                    lr.add(Finding(
                        rule_id=f"{rid}::{new_name}", layer="L3", severity=sev,
                        passed=False, slide=tpl_idx, shape=new_name,
                        message=f"slide {new_idx} 上找不到 shape '{new_name}'",
                    ))
                    continue
            except Exception as e:
                lr.add(Finding(
                    rule_id=f"{rid}::{new_name}", layer="L3", severity=sev,
                    passed=False, slide=tpl_idx, shape=new_name,
                    message=f"shape 读取失败：{e}",
                ))
                continue

            runs_new = _walk_runs(shape_new)

            if check == "has_color_runs":
                expected_min = int(rule.get("expected_min", 1))
                cnt = _count_non_default_color_runs(runs_new)
                passed = cnt >= expected_min
                lr.add(Finding(
                    rule_id=f"{rid}::{new_name}", layer="L3", severity=sev,
                    passed=passed, slide=tpl_idx, shape=new_name,
                    message=f"非默认色 runs: actual={cnt} expected_min={expected_min}",
                    detail={"runs_count": len(runs_new), "non_default_color": cnt},
                ))

            elif check == "has_bold_runs":
                expected_min = int(rule.get("expected_min", 1))
                cnt = _count_bold_runs(runs_new)
                passed = cnt >= expected_min
                lr.add(Finding(
                    rule_id=f"{rid}::{new_name}", layer="L3", severity=sev,
                    passed=passed, slide=tpl_idx, shape=new_name,
                    message=f"bold runs: actual={cnt} expected_min={expected_min}",
                ))

            elif check == "runs_match_template":
                try:
                    slide_tpl = pres_template.Slides(tpl_idx)
                    shape_tpl = _shape_by_name(slide_tpl, tpl_name)
                    runs_tpl = _walk_runs(shape_tpl) if shape_tpl else []
                except Exception:
                    runs_tpl = []
                # check_dims 控制比对的维度，默认 (rgb, bold, italic, size)
                # 字体名不验（项目约定：PPT 全局微软雅黑，由 _write_text 兜底设置）
                # 兼容旧契约：可显式给 ["rgb", "bold"] 退回旧行为
                dims = rule.get("check_dims") or ["rgb", "bold", "italic", "size"]
                seq_new = [tuple(r.get(d) for d in dims) for r in runs_new]
                seq_tpl = [tuple(r.get(d) for d in dims) for r in runs_tpl]
                passed = seq_new == seq_tpl
                lr.add(Finding(
                    rule_id=f"{rid}::{new_name}", layer="L3", severity=sev,
                    passed=passed, slide=tpl_idx, shape=new_name,
                    message=f"runs structure (dims={dims}): new={len(seq_new)} runs vs template={len(seq_tpl)} runs",
                    detail={"dims": dims, "new_seq": seq_new, "template_seq": seq_tpl},
                ))

            elif check == "runs_match_signature":
                # 与契约内嵌的 expected_runs 严格对比，不查 template。
                # 触发场景：代码意图升级超出模板原状态（如同 shape 多字号 / 多颜色），
                # 用 runs_match_template 会把"shape 没动"和"shape 改对了"混在一起。
                # ignore_whitespace_runs 默认 true：过滤纯 CR/LF/空白 run（PPT 跨段时
                # \r 字符会被 _walk_runs 视作独立 run，但其 size/rgb 是继承的、语义上无意义）。
                expected = rule.get("expected_runs") or []
                dims = rule.get("check_dims") or ["rgb", "bold", "size"]
                ignore_ws = bool(rule.get("ignore_whitespace_runs", True))

                def _is_ws_run(r):
                    t = r.get("text", "") or ""
                    return bool(t) and not t.strip()

                eff_runs = [r for r in runs_new if not (ignore_ws and _is_ws_run(r))]
                seq_new = [tuple(r.get(d) for d in dims) for r in eff_runs]
                seq_exp = [tuple(e.get(d) for d in dims) for e in expected]
                passed = seq_new == seq_exp
                lr.add(Finding(
                    rule_id=f"{rid}::{new_name}", layer="L3", severity=sev,
                    passed=passed, slide=tpl_idx, shape=new_name,
                    message=f"runs signature (dims={dims}, ignore_ws={ignore_ws}): new={len(seq_new)} runs vs expected={len(seq_exp)} runs",
                    detail={
                        "dims": dims,
                        "new_seq": seq_new,
                        "expected_seq": seq_exp,
                        "new_runs_text": [r.get("text", "") for r in eff_runs],
                    },
                ))

            elif check == "paragraphs_match_signature":
                # 按 PPT 原生段落（\r 分隔）切行，段内按 MERGE_DIMS 合并 run，
                # 逐段比对 run 签名序列。
                # rule 字段：
                #   expected_paragraphs: list，每项 {"runs":[{rgb,bold,size,...}], 可选 "alignment"}
                #   check_dims: list，默认与 MERGE_DIMS 对齐（["rgb","bold","size"]）
                import sys as _sys
                import os as _os
                _skill_root = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
                if _skill_root not in _sys.path:
                    _sys.path.insert(0, _skill_root)
                from paragraph_runs import extract_paragraph_runs, MERGE_DIMS as _MERGE_DIMS

                expected_paras = rule.get("expected_paragraphs") or []
                dims = rule.get("check_dims") or list(_MERGE_DIMS)

                # 护栏 #1：合并维度 ⊇ 断言维度
                # 若 check_dims 包含 MERGE_DIMS 之外的维度，自动扩充 merge_dims，
                # 确保这些维度的 run 边界不被合并掉，才能可靠断言。
                eff_merge = tuple(list(_MERGE_DIMS) + [d for d in dims if d not in _MERGE_DIMS])

                new_paras = extract_paragraph_runs(shape_new, merge_dims=eff_merge)

                # 段数校验
                if len(new_paras) != len(expected_paras):
                    lr.add(Finding(
                        rule_id=f"{rid}::{new_name}", layer="L3", severity=sev,
                        passed=False, slide=tpl_idx, shape=new_name,
                        message=(
                            f"paragraphs_match_signature: 段数不符 "
                            f"new={len(new_paras)} expected={len(expected_paras)}"
                        ),
                        detail={
                            "dims": dims,
                            "eff_merge": list(eff_merge),
                            "new_para_count": len(new_paras),
                            "expected_para_count": len(expected_paras),
                        },
                    ))
                else:
                    # 逐段比对 run 签名
                    all_ok = True
                    para_details = []
                    for pi, (np, ep) in enumerate(zip(new_paras, expected_paras)):
                        new_seq = [tuple(r.get(d) for d in dims) for r in np.get("runs", [])]
                        exp_seq = [tuple(e.get(d) for d in dims) for e in ep.get("runs", [])]
                        ok = (new_seq == exp_seq)
                        # 可选：校验 alignment
                        align_ok = True
                        if "alignment" in ep and ep["alignment"] is not None:
                            align_ok = (np.get("alignment") == ep["alignment"])
                        seg_ok = ok and align_ok
                        if not seg_ok:
                            all_ok = False
                        para_details.append({
                            "para_idx": pi + 1,
                            "ok": seg_ok,
                            "new_seq": new_seq,
                            "expected_seq": exp_seq,
                            "new_runs_text": [r.get("text", "") for r in np.get("runs", [])],
                            "new_alignment": np.get("alignment"),
                            "expected_alignment": ep.get("alignment"),
                        })
                    lr.add(Finding(
                        rule_id=f"{rid}::{new_name}", layer="L3", severity=sev,
                        passed=all_ok, slide=tpl_idx, shape=new_name,
                        message=(
                            f"paragraphs_match_signature (dims={dims}, eff_merge={list(eff_merge)}): "
                            f"{len(new_paras)} paras, "
                            f"{'all ok' if all_ok else 'mismatch in some paras'}"
                        ),
                        detail={"dims": dims, "eff_merge": list(eff_merge), "paragraphs": para_details},
                    ))

            else:
                lr.add(Finding(
                    rule_id=f"{rid}::{new_name}", layer="L3", severity="warn",
                    passed=False, slide=tpl_idx, shape=new_name,
                    message=f"未识别的 check: {check!r}",
                ))

    return lr
