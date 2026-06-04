#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""不依赖 COM 的 smoke test：
  - contract / pairing / report 都能 import 并产出一份报告
  - L4 行为层在 trace 缺失时降级 + trace 存在时正常断言
  - report.json/md 能写出来
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).parent.resolve()
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(Path.home() / ".claude" / "skills" / "office-com-helpers"))

from contract import Contract
from layers.behavior import run as run_l4
from layers.common import Finding, LayerResult
from report import aggregate, write_reports


def test_l4_degraded():
    c = Contract({"version": 1, "rules": [
        {"id": "gpt_must_be_called", "layer": "L4", "check": "trace_event_present",
         "expected_events": ["gpt_strengths", "gpt_drawbacks"], "severity": "must_fix"},
    ]})
    r = run_l4(contract=c, trace_path=None)
    assert r.degraded
    # rule 还在跑（但 severity 被降级为 warn）
    assert len(r.findings) == 1
    assert r.findings[0].severity == "warn"
    print("  L4 降级测试 OK")


def test_l4_with_trace():
    from office_com_helpers import TraceLogger
    tmp = Path(tempfile.gettempdir()) / "acceptance_smoke_trace.jsonl"
    if tmp.exists():
        tmp.unlink()
    with TraceLogger(tmp) as t:
        t.event("gpt_strengths", called=True, slide=13)
        # gpt_drawbacks 缺失故意
        t.event("com_api_failed_but_continued", api="Activate", attempts=3)

    c = Contract({
        "version": 1,
        "rules": [
            {"id": "gpt_must_be_called", "layer": "L4",
             "check": "trace_event_present",
             "expected_events": ["gpt_strengths", "gpt_drawbacks"],
             "severity": "must_fix"},
            {"id": "no_silent_com_failure", "layer": "L4",
             "check": "no_trace_event",
             "forbidden_events": ["com_api_failed_but_continued"],
             "severity": "must_fix"},
        ],
    })
    r = run_l4(contract=c, trace_path=str(tmp))
    assert not r.degraded
    by_id = {f.rule_id: f for f in r.findings}
    assert not by_id["gpt_must_be_called"].passed  # missing gpt_drawbacks
    assert "gpt_drawbacks" in str(by_id["gpt_must_be_called"].detail)
    assert not by_id["no_silent_com_failure"].passed  # com_api_failed found
    print("  L4 带 trace OK")
    tmp.unlink()


def test_report_aggregation():
    lr0 = LayerResult(layer="L0")
    lr0.add(Finding(rule_id="L0_pair_TextBox 1", layer="L0",
                    severity="must_fix", passed=True,
                    slide=13, shape="TextBox 1",
                    message="TextBox 1 ↔ TextBox 1 via exact"))
    lr1 = LayerResult(layer="L1")
    lr1.add(Finding(rule_id="chart63_temp_range", layer="L1",
                    severity="must_fix", passed=False,
                    slide=13, shape="Chart 8",
                    message="series mismatch"))
    lr1.add(Finding(rule_id="tbx50_mode", layer="L1",
                    severity="warn", passed=False,
                    slide=13, shape="TextBox 50",
                    message="text differs"))

    rep = aggregate([lr0, lr1], contract_path="x.json", mode="production",
                    slide_pairs=[(12, 13)], args_summary={})
    assert rep["verdict"] == "FAIL"
    assert rep["summary"]["must_fix"] == 1
    assert rep["summary"]["warn"] == 1

    out = Path(tempfile.gettempdir()) / "acceptance_smoke_out"
    write_reports(rep, out)
    j = json.loads((out / "acceptance_report.json").read_text(encoding="utf-8"))
    assert j["verdict"] == "FAIL"
    md = (out / "acceptance_report.md").read_text(encoding="utf-8")
    assert "L0 配对命中" in md
    assert "必修违反清单" in md
    assert "chart63_temp_range" in md
    print(f"  报告聚合 OK → {out / 'acceptance_report.md'}")


def test_smoke_mode_override():
    c = Contract({
        "version": 1,
        "rules": [
            {"id": "r1", "layer": "L3", "severity": "must_fix"},
        ],
        "modes": {"smoke": {"rule_overrides": {"r1": "tolerate"}}},
    }, mode="smoke")
    assert c.rules[0]["severity"] == "tolerate"
    print("  smoke 模式 override OK")


if __name__ == "__main__":
    print("ppt-acceptance-check smoke_test")
    test_l4_degraded()
    test_l4_with_trace()
    test_report_aggregation()
    test_smoke_mode_override()
    print("ALL OK")
