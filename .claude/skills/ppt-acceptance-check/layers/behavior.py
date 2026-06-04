#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""L4 行为层 —— pipeline 落盘的 jsonl trace 断言.

支持的 check：
  trace_event_present  rule.expected_events 中每个 event 都必须出现过；
                       called=False 不算"出现"（避免 GPT 写"我没调"骗过）
                       可加 scope: "production" 限定模式
  no_trace_event       rule.forbidden_events 中任一出现即 fail
  trace_event_count    rule.event + rule.min_count / max_count

trace 文件缺失 / 不可读 时 L4 降级：
  - LayerResult.degraded = True
  - 报告里显式标注降级原因
  - 已配置的规则全部出 warn Finding 而不是 must_fix（避免把"没装 trace"误报成 fail）
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from layers.common import Finding, LayerResult


class TraceIndex:
    """读 jsonl trace 后做按 event 名分类的索引。"""

    def __init__(self, events: List[Dict[str, Any]]) -> None:
        self.events = events
        self._by_name: Dict[str, List[Dict[str, Any]]] = {}
        for e in events:
            self._by_name.setdefault(e.get("event", ""), []).append(e)

    def get_events(self, name: str) -> List[Dict[str, Any]]:
        return self._by_name.get(name, [])

    def event_present(self, name: str) -> bool:
        """event 出现过且至少有一条 called != false。"""
        evs = self.get_events(name)
        if not evs:
            return False
        for e in evs:
            if e.get("called", True) is not False:
                return True
        return False

    @classmethod
    def load(cls, path: Optional[str]) -> Optional["TraceIndex"]:
        if not path:
            return None
        p = Path(path)
        if not p.exists():
            return None
        events: List[Dict[str, Any]] = []
        with open(p, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    events.append(json.loads(line))
                except Exception:
                    continue
        return cls(events)


def run(*, contract, trace_path: Optional[str]) -> LayerResult:
    lr = LayerResult(layer="L4")
    rules = contract.rules_for_layer("L4")

    trace_index = TraceIndex.load(trace_path)
    if trace_index is None:
        lr.degraded = True
        lr.degraded_reason = (
            f"无 pipeline trace（path={trace_path!r}）；"
            f"L4 规则全部降级为 warn，无法验证 COM 失败 / GPT 调用类暗坑。"
        )
        if not rules:
            return lr

    if not rules:
        lr.notes.append("L4: no rules in contract")
        return lr

    for rule in rules:
        rid = rule.get("id", "L4_unnamed")
        sev = rule.get("severity", "must_fix")
        if trace_index is None:
            sev = "warn"  # 降级

        # scope: "production" 类规则在 smoke 模式下应该已被 contract 改写为 tolerate；
        # 这里再额外做一层 safety check
        scope = rule.get("scope")
        if scope and scope != contract.mode:
            lr.add(Finding(
                rule_id=rid, layer="L4", severity="tolerate", passed=False,
                message=f"豁免：rule.scope={scope} 不匹配当前 mode={contract.mode}",
            ))
            continue

        check = rule.get("check", "")

        if check == "trace_event_present":
            expected_events = rule.get("expected_events") or []
            if trace_index is None:
                lr.add(Finding(
                    rule_id=rid, layer="L4", severity=sev, passed=False,
                    message=f"trace 缺失，无法验证 {expected_events}",
                ))
                continue
            missing = [e for e in expected_events if not trace_index.event_present(e)]
            passed = not missing
            lr.add(Finding(
                rule_id=rid, layer="L4", severity=sev, passed=passed,
                message=f"trace events present: {len(expected_events) - len(missing)}"
                        f"/{len(expected_events)}; missing={missing}",
                detail={"expected": expected_events, "missing": missing},
            ))

        elif check == "no_trace_event":
            forbidden = rule.get("forbidden_events") or []
            if trace_index is None:
                lr.add(Finding(
                    rule_id=rid, layer="L4", severity=sev, passed=False,
                    message=f"trace 缺失，无法验证 forbidden={forbidden}",
                ))
                continue
            found = [e for e in forbidden if trace_index.get_events(e)]
            passed = not found
            lr.add(Finding(
                rule_id=rid, layer="L4", severity=sev, passed=passed,
                message=f"forbidden events found: {found}" if found
                        else f"no forbidden events: {forbidden}",
                detail={"forbidden": forbidden, "found": found},
            ))

        elif check == "trace_event_count":
            ev = rule.get("event", "")
            min_c = int(rule.get("min_count", 0))
            max_c = rule.get("max_count")
            if trace_index is None:
                lr.add(Finding(
                    rule_id=rid, layer="L4", severity=sev, passed=False,
                    message=f"trace 缺失，无法验证 {ev} 计数",
                ))
                continue
            cnt = len(trace_index.get_events(ev))
            passed = cnt >= min_c and (max_c is None or cnt <= int(max_c))
            lr.add(Finding(
                rule_id=rid, layer="L4", severity=sev, passed=passed,
                message=f"event {ev} count={cnt} (min={min_c} max={max_c})",
            ))

        else:
            lr.add(Finding(
                rule_id=rid, layer="L4", severity="warn", passed=False,
                message=f"未识别的 check: {check!r}",
            ))

    return lr
