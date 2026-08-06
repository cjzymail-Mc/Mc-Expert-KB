#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""build_docx.py - golden-copy + long-anchor-first fill for plaintext DOCX.

Copies a read-only template to an explicit NEW output path, then:
  1. long-anchor-first `{{token}}` replace across body paragraphs, table cells,
     and every header/footer paragraph (run-level then paragraph-level degrade,
     to catch anchors split across runs)
  2. explicit slot fills (text slot, table-cell slot) by paragraph-anchor or
     table-index + cell coords
  3. 3-state HIGHLIGHT contract (RED cell = must-replace: write value and
     RE-APPLY red so the cell stays red for human audit; YELLOW/none = skip)
  4. fail-protect: encrypted input -> BLOCKED; missing anchor / existing output /
     non-unique target -> BUILD_FAIL before save (never overwrite)

Self-contained and project-neutral. The builder never invents business facts;
all content comes from --slot-map.

Highlight contract (mirrors three-state-coloring-contract-word-only + Word seed):
  RED    WD_COLOR_INDEX.RED    (6) -> must replace: write + keep red
  YELLOW WD_COLOR_INDEX.YELLOW (7) -> manual marker: skip (do not write)
  none   (no highlight)            -> do not touch

cell-level RED rule (C1 mc-expert must-lock #1): a cell counts as RED iff ALL
its runs are RED; mixed-run cells are treated as non-red (not a clean replace
target) and are skipped.

Usage:
  python build_docx.py --template t.docx --slot-map s.json --out o.docx
                       [--pending-human-ledger <path>]
Exit: 0 built / 1 build-fail / 2 blocked
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

_PLAINTEXT_ZIP = b"PK\x03\x04"
_LDTERM_CIPHER = b"\x88\x7d\x1c"
_OLE_CFB = b"\xD0\xCF\x11\xE0"
_LEDGER_DEFAULT_NAME = "pending_human_blocked.json"


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


def _route_for_magic(head):
    if head.startswith(_PLAINTEXT_ZIP):
        return "python"
    if head.startswith(_LDTERM_CIPHER):
        return "BLOCKED"
    if head.startswith(_OLE_CFB):
        return "BLOCKED"
    return "BLOCKED"


def _append_pending_human(path, route, magic_hex, label, ledger_path):
    entry = {
        "input_path": str(path),
        "label": label,
        "route": route,
        "magic_hex": magic_hex,
        "action": "STOP: do not COM-read; report path+hex to human for DLP decrypt",
        "recorded_at": datetime.now().astimezone().isoformat(),
    }
    ledger = []
    if ledger_path.exists():
        try:
            ledger = json.loads(ledger_path.read_text(encoding="utf-8")) or []
        except Exception:
            ledger = []
    ledger.append(entry)
    ledger_path.write_text(json.dumps(ledger, ensure_ascii=False, indent=2), encoding="utf-8")
    return ledger_path


def _check_blocked(path, label, ledger_path):
    head = _read_magic(path)
    if not head.startswith(_PLAINTEXT_ZIP):
        hex_str = " ".join(f"{b:02X}" for b in head) if head else "(unreadable)"
        route = _route_for_magic(head)
        ledger_path = _append_pending_human(path, route, hex_str, label, ledger_path)
        print(json.dumps({
            "status": "BLOCKED",
            "route": route,
            "input_path": str(path),
            "label": label,
            "magic_hex": hex_str,
            "pending_human_ledger": str(ledger_path),
            "reason": "not plaintext; STOP, no COM; recorded to pending-human ledger",
        }, ensure_ascii=False))
        return True
    return False


# ---- highlight helpers (structural OOXML attribute, not rendering) ----

def _cell_highlight_state(cell) -> str:
    """Return 'red' | 'yellow' | 'none' for a table cell.

    cell = red iff ALL runs across all paragraphs are RED.
    cell = yellow iff (not all red) AND at least one run is YELLOW.
    cell = none otherwise.
    """
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


def _set_cell_text_keep_red(cell, new_text):
    """Write value into the first paragraph's first run, blank the rest, delete
    extra paragraphs, and re-apply RED highlight so the cell stays red for audit."""
    from docx.enum.text import WD_COLOR_INDEX
    paras = cell.paragraphs
    first = paras[0]
    # ensure at least one run
    if not first.runs:
        first.add_run("")
    first.runs[0].text = new_text
    first.runs[0].font.highlight_color = WD_COLOR_INDEX.RED
    for extra in first.runs[1:]:
        extra.text = ""
    for extra_para in paras[1:]:
        extra_para._element.getparent().remove(extra_para._element)
    return {"written": new_text, "kept_red": True}


def replace_anchors_longest_first(doc, anchors):
    """anchors: list[{find:str, replace:str}]. Longest 'find' first.

    Walks body paragraphs, every table cell's paragraphs, and every
    header/footer paragraph. Run-level replace first; if a paragraph yields zero
    hits it degrades to paragraph-level (concat runs -> replace -> write runs[0]).
    """
    pending = sorted(anchors, key=lambda a: len(a["find"]), reverse=True)
    applied = []

    def _paragraphs_iter(doc):
        for para in doc.paragraphs:
            yield para
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    for para in cell.paragraphs:
                        yield para
        for section in doc.sections:
            for hf in (section.header, section.footer, section.first_page_header,
                       section.first_page_footer, section.even_page_header,
                       section.even_page_footer):
                try:
                    for para in hf.paragraphs:
                        yield para
                except Exception:
                    pass

    for a in pending:
        find = a["find"]
        repl = a["replace"]
        hits = 0
        for para in _paragraphs_iter(doc):
            # run-level first
            run_hit = 0
            for run in para.runs:
                if find in run.text:
                    run.text = run.text.replace(find, repl)
                    run_hit += 1
            if run_hit == 0 and find in para.text:
                # degrade to paragraph-level
                full = para.text.replace(find, repl)
                if para.runs:
                    para.runs[0].text = full
                    for extra in para.runs[1:]:
                        extra.text = ""
                    run_hit += 1
            hits += run_hit
        applied.append({"find": find, "replace": repl, "hits": hits})
    return applied


def fill_slots(doc, slots):
    """slots: list of slot dicts. Kinds:
       - text:    {table:int, row:int, col:int, value:str}
       - red_cell_driven: {table:int, row:int, col:int, value:str}
            writes value ONLY if the target cell is red (cell=all-runs-red);
            re-applies red. Non-red cells recorded as skipped.
       - table_insert: {anchor:str (unique paragraph text), headers:[...], rows:[[...]]}
            inserts a new table right after the unique anchor paragraph.
    """
    results = []
    tables = list(doc.tables)
    for s in slots:
        kind = s.get("kind", "text")
        if kind in ("text", "red_cell_driven"):
            tidx = int(s["table"]) - 1
            if tidx < 0 or tidx >= len(tables):
                results.append({"slot": s, "ok": False, "reason": f"table index {s['table']} out of range"})
                continue
            cell = tables[tidx].cell(int(s["row"]), int(s["col"]))
            if kind == "red_cell_driven":
                state = _cell_highlight_state(cell)
                if state != "red":
                    results.append({"slot": s.get("id", str(s)), "ok": True, "skipped": True,
                                    "reason": f"cell not red (state={state}); contract = skip"})
                    continue
                _set_cell_text_keep_red(cell, s["value"])
                results.append({"slot": s.get("id", str(s)), "ok": True, "written": True,
                                "kept_red": True, "value": s["value"]})
            else:
                cell.text = s["value"]
                results.append({"slot": s.get("id", str(s)), "ok": True, "written": True,
                                "value": s["value"]})
        elif kind == "table_insert":
            anchor_text = s["anchor"]
            headers = s.get("headers", [])
            rows = s.get("rows", [])
            target = None
            count = 0
            for para in doc.paragraphs:
                if para.text.strip() == anchor_text.strip():
                    target = para
                    count += 1
            if count == 0:
                results.append({"slot": s.get("id", str(s)), "ok": False,
                                "reason": f"anchor not found: {anchor_text!r}"})
                continue
            if count > 1:
                results.append({"slot": s.get("id", str(s)), "ok": False,
                                "reason": f"anchor not unique ({count} matches): {anchor_text!r}"})
                continue
            ncols = len(headers) if headers else (len(rows[0]) if rows else 0)
            if ncols == 0:
                results.append({"slot": s.get("id", str(s)), "ok": False,
                                "reason": "table_insert needs headers or rows"})
                continue
            new_table = doc.add_table(rows=1 + len(rows), cols=ncols)
            for ci, htext in enumerate(headers):
                new_table.cell(0, ci).text = str(htext)
            for ri, rowvals in enumerate(rows, start=1):
                for ci, val in enumerate(rowvals):
                    if ci < ncols:
                        new_table.cell(ri, ci).text = str(val)
            target._p.addnext(new_table._tbl)
            results.append({"slot": s.get("id", str(s)), "ok": True, "inserted": True,
                            "anchor": anchor_text, "shape": [1 + len(rows), ncols]})
        else:
            results.append({"slot": s.get("id", str(s)), "ok": False, "reason": f"unknown kind {kind!r}"})
    return results


def _collect_all_text(doc):
    parts = []
    for para in doc.paragraphs:
        parts.append(para.text)
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                parts.append(cell.text)
    for section in doc.sections:
        for hf in (section.header, section.footer):
            try:
                for para in hf.paragraphs:
                    parts.append(para.text)
            except Exception:
                pass
    return "\n".join(parts)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--template", required=True)
    ap.add_argument("--slot-map", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--pending-human-ledger", required=False,
                    default=_LEDGER_DEFAULT_NAME)
    args = ap.parse_args()

    ledger_path = Path(args.pending_human_ledger).resolve()

    # 1. blocked gate on template
    if _check_blocked(args.template, "template", ledger_path):
        return 2

    # 2. refuse to overwrite existing output
    if Path(args.out).exists():
        print(json.dumps({"status": "BUILD_FAIL",
                          "reason": "output already exists; refusing to overwrite",
                          "out": args.out}))
        return 1

    slot_map = json.loads(Path(args.slot_map).read_text(encoding="utf-8"))
    anchors = slot_map.get("anchors", [])
    slots = slot_map.get("slots", [])

    source_sha_before = _sha256(args.template)

    from docx import Document
    doc = Document(args.template)

    # 3. all anchors must be present before any mutation
    all_text = _collect_all_text(doc)
    missing = [a["find"] for a in anchors if a["find"] not in all_text]
    if missing:
        print(json.dumps({"status": "BUILD_FAIL", "reason": "missing anchors", "missing": missing}))
        return 1

    anchor_results = replace_anchors_longest_first(doc, anchors)
    slot_results = fill_slots(doc, slots)

    # fail-protect: any failed anchor/slot must abort BEFORE save (never overwrite / never save a bad build)
    failed_slots = [r for r in slot_results if r.get("ok") is False]
    if failed_slots:
        print(json.dumps({"status": "BUILD_FAIL",
                          "reason": "one or more slots failed (e.g. non-unique target / out-of-range / unknown kind)",
                          "failed_slots": failed_slots}, ensure_ascii=False, indent=2))
        return 1

    doc.save(args.out)

    # 4. source must be unchanged
    source_sha_after = _sha256(args.template)
    if source_sha_before != source_sha_after:
        print(json.dumps({"status": "BUILD_FAIL", "reason": "source file changed during build",
                          "before": source_sha_before, "after": source_sha_after}))
        return 1

    out_head = _read_magic(args.out)
    out_ok = out_head.startswith(_PLAINTEXT_ZIP)
    print(json.dumps({"status": "BUILT" if out_ok else "BUILD_FAIL",
                      "out": args.out, "out_sha256": _sha256(args.out),
                      "out_is_plaintext": out_ok,
                      "source_sha256_unchanged": source_sha_before == source_sha_after,
                      "anchors": anchor_results, "slots": slot_results}, ensure_ascii=False, indent=2))
    return 0 if out_ok else 1


if __name__ == "__main__":
    sys.exit(main())
