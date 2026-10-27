#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""inspect_template.py - structure discovery for a plaintext DOCX template.

Mandatory pre-fill step: the template is a black box; slots/anchors/highlight
states must be discovered, not guessed. Emits JSON + MD.

Exit: 0 ok / 2 BLOCKED (non-plaintext).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

_PLAINTEXT_ZIP = b"PK\x03\x04"


def _read_magic(path, n=8):
    try:
        with open(path, "rb") as fh:
            return fh.read(n)
    except Exception:
        return b""


def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _cell_highlight_state(cell) -> str:
    from docx.enum.text import WD_COLOR_INDEX
    has_red = False
    has_yellow = False
    has_other = False
    run_count = 0
    for para in cell.paragraphs:
        for run in para.runs:
            run_count += 1
            hc = run.font.highlight_color
            if hc == WD_COLOR_INDEX.RED:
                has_red = True
            elif hc == WD_COLOR_INDEX.YELLOW:
                has_yellow = True
            elif hc is None:
                has_other = True
            else:
                has_other = True
    if run_count == 0:
        return "none"
    if has_red and not has_yellow and not has_other:
        return "red"
    if has_yellow and not has_red:
        return "yellow"
    return "none"


def inspect(path) -> dict:
    from docx import Document
    doc = Document(path)
    paragraphs = [{"index": i, "text": p.text} for i, p in enumerate(doc.paragraphs)]
    tables = []
    for ti, table in enumerate(doc.tables, start=1):
        rows = []
        for ri, row in enumerate(table.rows):
            cells = []
            for ci, cell in enumerate(row.cells):
                cells.append({"row": ri, "col": ci, "text": cell.text,
                              "highlight_state": _cell_highlight_state(cell)})
            rows.append(cells)
        tables.append({"table": ti, "rows": len(table.rows), "cols": len(table.columns),
                       "cells": rows})
    sections = []
    for si, section in enumerate(doc.sections, start=1):
        header_text = "\n".join(p.text for p in section.header.paragraphs) if section.header else ""
        footer_text = "\n".join(p.text for p in section.footer.paragraphs) if section.footer else ""
        sections.append({"section": si, "header_text": header_text, "footer_text": footer_text})
    return {"paragraphs": paragraphs, "tables": tables, "sections": sections}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--out", required=False, default=".")
    args = ap.parse_args()

    head = _read_magic(args.path)
    if not head.startswith(_PLAINTEXT_ZIP):
        hex_str = " ".join(f"{b:02X}" for b in head) if head else "(unreadable)"
        print(json.dumps({"status": "BLOCKED", "reason": "not plaintext",
                          "magic_hex": hex_str}, ensure_ascii=False))
        return 2

    result = inspect(args.path)
    result["source_path"] = args.path
    result["source_sha256"] = _sha256(args.path)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "inspect_report.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    md = ["# Inspect Report", "",
          f"- source: `{args.path}`",
          f"- source sha256: `{result['source_sha256']}`",
          f"- paragraphs: {len(result['paragraphs'])}",
          f"- tables: {len(result['tables'])}", ""]
    for t in result["tables"]:
        md.append(f"## table {t['table']} ({t['rows']}x{t['cols']})")
        for row in t["cells"]:
            for cell in row:
                md.append(f"- [{cell['row']},{cell['col']}] hl={cell['highlight_state']} text={cell['text']!r}")
    (out / "inspect_report.md").write_text("\n".join(md), encoding="utf-8")
    print(json.dumps({"status": "OK", "paragraphs": len(result["paragraphs"]),
                      "tables": len(result["tables"]),
                      "out_dir": str(out)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
