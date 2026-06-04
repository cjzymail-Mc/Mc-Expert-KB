#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""acceptance_contract.json 加载 + 规则解析 + 三态 severity.

契约结构：
  {
    "version": 1,
    "shape_pairing": {"strategy": "fuzzy", "rules": [...], "manual_overrides": {...}},
    "tolerances": {"geometry_px": 2, "font_size_pt": 0.5, ...},
    "rules": [
      {"id": ..., "shape": ..., "layer": "L1", "check": "...",
       "expected_from": "...", "severity": "must_fix" | "warn" | "tolerate",
       "skip_if_trace": "..."}
    ],
    "modes": {"smoke": {"rule_overrides": {...}}, "production": {}}
  }

三态 severity：
  must_fix  → 必修，归入 exit code 1
  warn      → 记录不阻断
  tolerate  → 豁免（条件或模式）

无契约时：全严格 + 默认 fuzzy 配对。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional


SEVERITY_MUST_FIX = "must_fix"
SEVERITY_WARN = "warn"
SEVERITY_TOLERATE = "tolerate"

DEFAULT_TOLERANCES = {
    "geometry_px": 2.0,
    "font_size_pt": 0.5,
    "color_rgb_distance": 0,
    "ssim_threshold": 0.96,
}

DEFAULT_PAIRING = {
    "strategy": "fuzzy",
    "rules": ["strip_clone_suffix"],
    "manual_overrides": {},
}


class Contract:
    """加载 + 查询契约。"""

    def __init__(self, data: Optional[Dict[str, Any]] = None,
                 mode: str = "production"):
        self.raw = data or {}
        self.mode = mode
        self.version = self.raw.get("version", 1)

        self.shape_pairing = {**DEFAULT_PAIRING, **self.raw.get("shape_pairing", {})}
        self.tolerances = {**DEFAULT_TOLERANCES, **self.raw.get("tolerances", {})}
        self.rules: List[Dict[str, Any]] = list(self.raw.get("rules", []))
        self.modes: Dict[str, Any] = self.raw.get("modes", {})

        self._apply_mode_overrides()

    @classmethod
    def load(cls, path: Optional[str], mode: str = "production") -> "Contract":
        if not path:
            return cls(None, mode=mode)
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"契约文件不存在: {path}")
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls(data, mode=mode)

    def _apply_mode_overrides(self) -> None:
        """modes.<mode>.rule_overrides 把 rule_id 的 severity 改写成新值。"""
        mode_cfg = self.modes.get(self.mode, {})
        overrides = mode_cfg.get("rule_overrides", {}) if isinstance(mode_cfg, dict) else {}
        if not overrides:
            return
        for rule in self.rules:
            rid = rule.get("id")
            if rid and rid in overrides:
                rule["severity"] = overrides[rid]

    def rules_for_layer(self, layer: str) -> List[Dict[str, Any]]:
        return [r for r in self.rules if r.get("layer") == layer]

    def tolerance(self, key: str, default: float = 0.0) -> float:
        return float(self.tolerances.get(key, default))

    def manual_overrides(self, slide_key: str) -> Dict[str, str]:
        """slide_key 形如 'p13'；返回 {new_shape_name: template_shape_name}。"""
        ov = self.shape_pairing.get("manual_overrides", {}) or {}
        return ov.get(slide_key, {}) or {}


def severity_to_exit_contribution(sev: str) -> int:
    """must_fix → 1，其他 → 0。"""
    return 1 if sev == SEVERITY_MUST_FIX else 0


def normalize_severity(sev: Any, default: str = SEVERITY_MUST_FIX) -> str:
    s = str(sev or "").strip().lower()
    if s in (SEVERITY_MUST_FIX, SEVERITY_WARN, SEVERITY_TOLERATE):
        return s
    return default


if __name__ == "__main__":
    print("contract.py self-test")
    c = Contract()
    assert c.tolerances["geometry_px"] == 2.0
    assert c.shape_pairing["strategy"] == "fuzzy"
    assert c.rules_for_layer("L1") == []

    sample = {
        "version": 1,
        "rules": [
            {"id": "r1", "layer": "L1", "severity": "must_fix"},
            {"id": "r2", "layer": "L4", "severity": "must_fix"},
        ],
        "modes": {"smoke": {"rule_overrides": {"r2": "tolerate"}}},
    }
    c2 = Contract(sample, mode="smoke")
    rmap = {r["id"]: r["severity"] for r in c2.rules}
    assert rmap["r1"] == "must_fix"
    assert rmap["r2"] == "tolerate"

    assert severity_to_exit_contribution("must_fix") == 1
    assert severity_to_exit_contribution("warn") == 0
    assert normalize_severity("MUST_FIX") == "must_fix"
    assert normalize_severity("xxx") == "must_fix"
    print("  OK")
