#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""每层共用的数据结构 + COM 读取助手。"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# ────────── 验收结果数据结构 ──────────

@dataclass
class Finding:
    """一条规则的检查结果。"""
    rule_id: str
    layer: str
    severity: str           # must_fix / warn / tolerate
    passed: bool
    shape: Optional[str] = None
    slide: Optional[int] = None
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


# ────────── COM shape extraction (L0 配对地基用的最小数据) ──────────

def shape_kind(shape) -> str:
    """从 PPT shape 推断 type 字符串。Chart / Picture / TextBox / Table / AutoShape / Group / Unknown。"""
    try:
        # MsoShapeType: 3=Chart, 13=Picture, 17=TextBox, 19=Table, 1=AutoShape, 6=Group
        # 用 HasChart / HasTable / HasTextFrame + Type 综合判断
        if int(getattr(shape, "HasChart", 0) or 0) == -1:
            return "Chart"
        if int(getattr(shape, "HasTable", 0) or 0) == -1:
            return "Table"
        t = int(getattr(shape, "Type", 0) or 0)
        if t == 13:
            return "Picture"
        if t == 17:
            return "TextBox"
        if t == 6:
            return "Group"
        if t == 1:
            return "AutoShape"
        if int(getattr(shape, "HasTextFrame", 0) or 0) == -1:
            return "TextBox"
        return "Unknown"
    except Exception:
        return "Unknown"


def shape_text(shape) -> str:
    """读 shape 内文字（含 Table 单元格 / TextFrame）。COM 异常返回 ''。"""
    try:
        if int(getattr(shape, "HasTextFrame", 0) or 0) != -1:
            return ""
        return str(shape.TextFrame.TextRange.Text or "")
    except Exception:
        return ""


def extract_slide_shape_refs(slide) -> list:
    """提取一个 slide 上所有 shape 的最小信息（给 pairing 用）。

    Returns: List[ShapeRef]
    """
    from pairing import ShapeRef
    out = []
    try:
        n = slide.Shapes.Count
    except Exception:
        return out
    for i in range(1, n + 1):
        try:
            shp = slide.Shapes(i)
            out.append(ShapeRef(
                name=str(shp.Name),
                shape_type=shape_kind(shp),
                left=float(getattr(shp, "Left", 0) or 0),
                top=float(getattr(shp, "Top", 0) or 0),
                width=float(getattr(shp, "Width", 0) or 0),
                height=float(getattr(shp, "Height", 0) or 0),
            ))
        except Exception:
            continue
    return out
