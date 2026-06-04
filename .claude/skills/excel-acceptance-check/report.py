#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""[改写自 ppt-acceptance-check/report.py] 聚合各层结果 → acceptance_report.md + .json。

Excel 化改动（约 20 行）相对 ppt 版：
  - 标题「PPT 验收报告」→「Excel 验收报告」
  - LAYER_TITLES → Excel 层名（L0 结构 / L1 数据 / L3 空值）
  - aggregate() 去掉必填的 slide_pairs，改可选 sheets 列表
  - _render_md 去掉 [p{slide}] 渲染（Excel 用 shape 字段当定位串）+ 去掉 PPT 专属
    「L0 配对命中」节
聚合/分桶/dataclass→dict 逻辑与 ppt 版等价。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from layers.common import Finding, LayerResult


LAYER_TITLES = {
    "L0": "L0 结构",
    "L1": "L1 数据",
    "L3": "L3 空值",
}


def _finding_to_dict(f: Finding) -> Dict[str, Any]:
    return {
        "rule_id": f.rule_id,
        "layer": f.layer,
        "severity": f.severity,
        "passed": f.passed,
        "locator": f.shape,     # Excel: shape 字段借用为定位串
        "message": f.message,
        "detail": f.detail,
    }


def _layer_to_dict(lr: LayerResult) -> Dict[str, Any]:
    return {
        "layer": lr.layer,
        "passed": lr.passed_count,
        "warnings": lr.warnings,
        "tolerated": lr.tolerated,
        "must_fix_violations": lr.must_fix_violations,
        "degraded": lr.degraded,
        "degraded_reason": lr.degraded_reason,
        "notes": lr.notes,
        "findings": [_finding_to_dict(f) for f in lr.findings],
    }


def aggregate(layer_results: List[LayerResult], *, contract_path: str,
              mode: str, args_summary: Dict[str, Any],
              sheets: Optional[List[str]] = None) -> Dict[str, Any]:
    total_must_fix = sum(lr.must_fix_violations for lr in layer_results)
    total_warn = sum(lr.warnings for lr in layer_results)
    total_tol = sum(lr.tolerated for lr in layer_results)
    verdict = "FAIL" if total_must_fix > 0 else "PASS"

    return {
        "verdict": verdict,
        "mode": mode,
        "contract": contract_path,
        "sheets": sheets or [],
        "summary": {
            "must_fix": total_must_fix,
            "warn": total_warn,
            "tolerated": total_tol,
        },
        "args": args_summary,
        "layers": [_layer_to_dict(lr) for lr in layer_results],
    }


def write_reports(report: Dict[str, Any], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "acceptance_report.json"
    md_path = out_dir / "acceptance_report.md"

    json_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    md_path.write_text(_render_md(report), encoding="utf-8")


def _loc(f: Dict[str, Any]) -> str:
    """findings dict → 定位串后缀（Excel: locator）。"""
    return f" `{f['locator']}`" if f.get("locator") else ""


def _render_md(report: Dict[str, Any]) -> str:
    lines: List[str] = []
    s = report["summary"]
    verdict = report["verdict"]
    lines.append("# Excel 验收报告\n")
    lines.append(f"**结论：{verdict}**  "
                 f"（必修 {s['must_fix']} / 警告 {s['warn']} / 容忍 {s['tolerated']}）\n")
    lines.append(f"- 模式：`{report['mode']}`")
    lines.append(f"- 契约：`{report['contract'] or '(无，全严格默认)'}`")
    if report.get("sheets"):
        lines.append(f"- 涉及 sheet：{', '.join(report['sheets'])}")
    lines.append("")

    # 摘要表
    lines.append("## 摘要\n")
    lines.append("| 层 | 通过 | 警告 | 容忍 | 必修违反 | 降级 |")
    lines.append("|---|---|---|---|---|---|")
    for lyr in report["layers"]:
        title = LAYER_TITLES.get(lyr["layer"], lyr["layer"])
        deg = "⚠ " + lyr.get("degraded_reason", "") if lyr.get("degraded") else ""
        lines.append(
            f"| {title} | {lyr['passed']} | {lyr['warnings']} | "
            f"{lyr['tolerated']} | {lyr['must_fix_violations']} | {deg} |"
        )
    lines.append("")

    # 必修违反清单（永远先看这个）
    must_fix_findings: List[Dict[str, Any]] = []
    for lyr in report["layers"]:
        for f in lyr["findings"]:
            if not f["passed"] and f["severity"] == "must_fix":
                must_fix_findings.append(f)
    if must_fix_findings:
        lines.append("## 必修违反清单（先看这里）\n")
        for f in must_fix_findings:
            lines.append(f"### [{f['layer']}] {f['rule_id']}{_loc(f)}")
            lines.append(f"- {f['message']}")
            if f["detail"]:
                lines.append(f"- 详情：`{json.dumps(f['detail'], ensure_ascii=False)}`")
            lines.append("")

    # 警告清单
    warns = [f for lyr in report["layers"] for f in lyr["findings"]
             if not f["passed"] and f["severity"] == "warn"]
    if warns:
        lines.append("## 警告清单（不阻断）\n")
        for f in warns:
            lines.append(f"- [{f['layer']}] {f['rule_id']}{_loc(f)} — {f['message']}")
        lines.append("")

    # 容忍清单
    tols = [f for lyr in report["layers"] for f in lyr["findings"]
            if not f["passed"] and f["severity"] == "tolerate"]
    if tols:
        lines.append("## 容忍清单（已豁免）\n")
        for f in tols:
            lines.append(f"- [{f['layer']}] {f['rule_id']}{_loc(f)} — {f['message']}")
        lines.append("")

    # 每层详细（含通过项，便于审计）
    lines.append("## 详细清单（含通过项）\n")
    for lyr in report["layers"]:
        title = LAYER_TITLES.get(lyr["layer"], lyr["layer"])
        if not lyr["findings"]:
            continue
        lines.append(f"### {title}")
        for f in lyr["findings"]:
            mark = "✓" if f["passed"] else ("⚠" if f["severity"] == "warn" else "✗")
            lines.append(f"- {mark} [{f['severity']}] {f['rule_id']}{_loc(f)} — {f['message']}")
        lines.append("")

    return "\n".join(lines) + "\n"
