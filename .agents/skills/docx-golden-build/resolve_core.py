#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""resolve_core.py - locate the docx-shared-core from any install position.

Problem this solves:
  The thin entry SKILL.md must NOT hardcode `../../scripts/` (that only works in
  the staging layout and breaks at a real install position like
  `.agents/skills/docx-golden-build/SKILL.md`).

Resolution contract (probed in order, first hit wins):
  1. explicit env var DOCX_GOLDEN_CORE (install-time injection)
  2. sibling shared-core next to the skills root:
       <skills-parent>/shared/docx-shared-core        (mirror install)
  3. feature-09 staging layout:
       <entry>/../../scripts/                         (entries/<platform>)
  4. walk-up repo fallback: any parent holding docx-shared-core/scripts/build_docx.py

Prints the resolved core dir (absolute) and a marker the entry is real, then
exits 0 on success / 2 if no candidate resolves (fail-loud, never guess).

Usage:  python resolve_core.py
        python resolve_core.py --json
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def _probe_marker(d: Path) -> bool:
    return (d / "scripts" / "build_docx.py").is_file()


def resolve_core(entry_file: str | None = None) -> Path | None:
    here = Path(entry_file).resolve() if entry_file else Path(__file__).resolve()

    # 1. explicit env var (install-time path injection)
    env = os.environ.get("DOCX_GOLDEN_CORE")
    if env:
        cand = Path(env)
        if _probe_marker(cand):
            return cand

    # 2. sibling shared-core next to the skills root (mirror install):
    #    <repo>/.agents/skills/docx-golden-build/SKILL.md -> <repo>/shared/docx-shared-core
    up = here.parent
    for _ in range(4):
        shared_cand = up / "shared" / "docx-shared-core"
        if _probe_marker(shared_cand):
            return shared_cand
        up = up.parent

    # 3. feature-09 staging layout: entries/<platform>/SKILL.md -> ../../scripts/
    staging = here.parent.parent / "scripts"
    if staging.is_dir() and (staging / "build_docx.py").is_file():
        return staging.parent

    # 4. walk-up repo fallback: any parent holding docx-shared-core
    repo_cand = here
    for _ in range(8):
        repo_cand = repo_cand.parent
        if (repo_cand / "docx-shared-core" / "scripts" / "build_docx.py").is_file():
            return repo_cand / "docx-shared-core"

    return None


def main() -> int:
    core = resolve_core()
    as_json = "--json" in sys.argv
    if core is None:
        msg = {"status": "UNRESOLVED",
               "reason": "no candidate core position matched; set DOCX_GOLDEN_CORE or fix install layout"}
        print(json.dumps(msg, ensure_ascii=False))
        return 2
    out = {"status": "RESOLVED", "core_root": str(core),
           "build_script": str(core / "scripts" / "build_docx.py"),
           "probe_marker_ok": (core / "scripts" / "build_docx.py").is_file()}
    print(json.dumps(out, ensure_ascii=False, indent=2) if not as_json else json.dumps(out, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
