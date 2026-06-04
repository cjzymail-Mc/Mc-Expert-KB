#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""聚合 6 层结果 → acceptance_report.md + acceptance_report.json."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from layers.common import Finding, LayerResult


LAYER_TITLES = {
    "L0": "L0 配对",
    "L1": "L1 数据",
    "L2": "L2 格式",
    "L3": "L3 染色",
    "L4": "L4 行为",
    "L5": "L5 视觉",
}


def _finding_to_dict(f: Finding) -> Dict[str, Any]:
    return {
        "rule_id": f.rule_id,
        "layer": f.layer,
        "severity": f.severity,
        "passed": f.passed,
        "shape": f.shape,
        "slide": f.slide,
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
              mode: str, slide_pairs: List, args_summary: Dict[str, Any]) -> Dict[str, Any]:
    total_must_fix = sum(lr.must_fix_violations for lr in layer_results)
    total_warn = sum(lr.warnings for lr in layer_results)
    total_tol = sum(lr.tolerated for lr in layer_results)
    verdict = "FAIL" if total_must_fix > 0 else "PASS"

    return {
        "verdict": verdict,
        "mode": mode,
        "contract": contract_path,
        "slide_pairs": [f"{a}:{b}" for a, b in slide_pairs],
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


def _render_md(report: Dict[str, Any]) -> str:
    lines: List[str] = []
    s = report["summary"]
    verdict = report["verdict"]
    lines.append(f"# PPT 验收报告\n")
    lines.append(f"**结论：{verdict}**  "
                 f"（必修 {s['must_fix']} / 警告 {s['warn']} / 容忍 {s['tolerated']}）\n")
    lines.append(f"- 模式：`{report['mode']}`")
    lines.append(f"- 契约：`{report['contract'] or '(无，全严格默认)'}`")
    lines.append(f"- slide pairs：{', '.join(report['slide_pairs'])}")
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

    # L0 配对摘要（让人一眼看到 fuzzy 是怎么命中的）
    l0 = next((l for l in report["layers"] if l["layer"] == "L0"), None)
    if l0:
        pair_findings = [f for f in l0["findings"]
                         if f["passed"] and f["rule_id"].startswith("L0_pair_")]
        if pair_findings:
            lines.append("## L0 配对命中\n")
            for f in pair_findings:
                lines.append(f"- [p{f['slide']}] {f['message']}")
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
            sp = f" [p{f['slide']}]" if f["slide"] is not None else ""
            shp = f" {f['shape']}" if f["shape"] else ""
            lines.append(f"### [{f['layer']}] {f['rule_id']}{sp}{shp}")
            lines.append(f"- {f['message']}")
            if f["detail"]:
                lines.append(f"- 详情：`{json.dumps(f['detail'], ensure_ascii=False)}`")
            lines.append("")

    # 警告清单
    warns = []
    for lyr in report["layers"]:
        for f in lyr["findings"]:
            if not f["passed"] and f["severity"] == "warn":
                warns.append(f)
    if warns:
        lines.append("## 警告清单（不阻断）\n")
        for f in warns:
            sp = f" [p{f['slide']}]" if f["slide"] is not None else ""
            shp = f" {f['shape']}" if f["shape"] else ""
            lines.append(f"- [{f['layer']}] {f['rule_id']}{sp}{shp} — {f['message']}")
        lines.append("")

    # 容忍清单
    tols = []
    for lyr in report["layers"]:
        for f in lyr["findings"]:
            if not f["passed"] and f["severity"] == "tolerate":
                tols.append(f)
    if tols:
        lines.append("## 容忍清单（已豁免）\n")
        for f in tols:
            sp = f" [p{f['slide']}]" if f["slide"] is not None else ""
            shp = f" {f['shape']}" if f["shape"] else ""
            lines.append(f"- [{f['layer']}] {f['rule_id']}{sp}{shp} — {f['message']}")
        lines.append("")

    # 每层详细（含通过项，便于审计）
    lines.append("## 详细清单（含通过项）\n")
    for lyr in report["layers"]:
        title = LAYER_TITLES.get(lyr["layer"], lyr["layer"])
        if not lyr["findings"]:
            continue
        lines.append(f"### {title}")
        for f in lyr["findings"]:
            sp = f" [p{f['slide']}]" if f["slide"] is not None else ""
            mark = "✓" if f["passed"] else ("⚠" if f["severity"] == "warn" else "✗")
            lines.append(f"- {mark} [{f['severity']}] {f['rule_id']}{sp} — {f['message']}")
        lines.append("")

    return "\n".join(lines) + "\n"
