# COPIED FROM ppt-acceptance-check/layers/common.py @2026-06-03 仅 Finding/LayerResult 两个数据结构 改动需同步
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""每层共用的验收结果数据结构。

（本文件**只**搬了 ppt 版 common.py 的 Finding / LayerResult 两个 dataclass，
 没搬 PPT shape extraction 段(原文 :56-117 的 shape_kind/shape_text/
 extract_slide_shape_refs)——那些是 PPT 专用、Excel 不需要。改这两个结构需两处同步。）

Finding 字段在 Excel 语境下的复用约定：
  - `shape`  → 借用为 Excel 定位串（如 "正式BOM!C3" / "正式BOM" / 列名）。
  - `slide`  → Excel 不用，保持 None（report 渲染因此不会出现 [p{n}]）。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class Finding:
    """一条规则的检查结果。"""
    rule_id: str
    layer: str
    severity: str           # must_fix / warn / tolerate
    passed: bool
    shape: Optional[str] = None    # Excel: 借用为定位串(sheet!cell / sheet / 列名)
    slide: Optional[int] = None    # Excel: 不用，恒 None
    message: str = ""
    detail: Dict[str, Any] = field(default_factory=dict)


@dataclass
class LayerResult:
    layer: str
    findings: List[Finding] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)
    degraded: bool = False
    degraded_reason: str = ""

    def add(self, f: Finding) -> None:
        self.findings.append(f)

    @property
    def passed_count(self) -> int:
        return sum(1 for f in self.findings if f.passed)

    @property
    def must_fix_violations(self) -> int:
        return sum(1 for f in self.findings
                   if not f.passed and f.severity == "must_fix")

    @property
    def warnings(self) -> int:
        return sum(1 for f in self.findings
                   if not f.passed and f.severity == "warn")

    @property
    def tolerated(self) -> int:
        return sum(1 for f in self.findings
                   if not f.passed and f.severity == "tolerate")
