#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""report.py - structured JSON + human summary for verify_docx findings.

Binds input/source/output contract+tool hashes; lists which verification layers ran
vs skipped. NEVER claims visual or delivery PASS when only structural/semantic layers ran.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def write_reports(verify_result, contract_path, out_dir, layers_run=None, exit_code=None):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    layers_run = layers_run or ["magic", "structure", "semantic", "highlight", "inserted_table"]
    layers_skipped = ["visual", "delivery"]  # not in first version

    report = {
        "verdict": verify_result["verdict"],
        "output_sha256": verify_result.get("output_sha256"),
        "source_sha256": verify_result.get("source_sha256"),
        "contract_path": str(contract_path),
        "tool_version": "docx-shared-core v0.1",
        "exit_code": exit_code,
        "exit_code_contract": {"PASS": 0, "FAIL": 1, "BLOCKED": 2},
        "layers_run": layers_run,
        "layers_skipped": layers_skipped,
        "honest_claim_note": (
            "Only structural/semantic/highlight layers ran. Do NOT claim visual or delivery PASS."
            if "visual" not in layers_run else ""
        ),
        "findings": verify_result.get("findings", []),
        "failures": [f for f in verify_result.get("findings", []) if not f.get("passed", False)],
    }
    (out_dir / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    md = ["# Verify Report", "",
          f"- verdict: **{report['verdict']}**",
          f"- exit code: `{report['exit_code']}` (PASS=0 / FAIL=1 / BLOCKED=2)",
          f"- exit code contract: PASS=0 / FAIL=1 / BLOCKED=2",
          f"- contract path: `{report['contract_path']}`",
          f"- output sha256: `{report['output_sha256']}`",
          f"- source sha256: `{report['source_sha256']}`",
          f"- layers run: {', '.join(layers_run)}",
          f"- layers skipped: {', '.join(layers_skipped)}", ""]
    if report["honest_claim_note"]:
        md.append(f"> {report['honest_claim_note']}")
        md.append("")
    if report["failures"]:
        md.append("## Failures")
        for fl in report["failures"]:
            md.append(f"- {fl}")
    else:
        md.append("No failures.")
    (out_dir / "report.md").write_text("\n".join(md), encoding="utf-8")
    return report


if __name__ == "__main__":
    print("report.py module — imported by verify_docx.py; use verify_docx.py as entry point.")
