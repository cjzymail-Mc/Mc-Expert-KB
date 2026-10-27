#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verify_docx.py - INDEPENDENT deterministic verifier for a built DOCX.

Does NOT trust the builder's "save succeeded". Re-reads the output and checks:
  - output magic is plaintext 50 4B 03 04
  - table count, table label fidelity (if contract requires)
  - cell-by-cell value equality (if contract requires)
  - 3-state HIGHLIGHT contract:
      RED cells were written and STAY red
      NONE / YELLOW cells were NOT written (independent negatives)
  - output SHA-256 reported

Verdict -> exit code:  PASS=0 / FAIL=1 / BLOCKED=2.
THE FINAL VERDICT ALWAYS REACHES THE EXIT CODE (false-PASS fix:
a verify() that returns a verdict but main() never sys.exit produces exit 0 on FAIL).

cell-level RED rule (C1 mc-expert must-lock #1): cell=red iff ALL runs red.
none-miswrite: a cell expected to be NONE was written -> FAIL
yellow-miswrite: a cell expected to be YELLOW was written -> FAIL

Usage: python verify_docx.py --output o.docx --contract c.json [--source t.docx]
Exit: 0 PASS / 1 FAIL / 2 BLOCKED
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
    try:
        with open(path, "rb") as fh:
            for chunk in iter(lambda: fh.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()
    except Exception:
        return ""


class Verdict:
    PASS = "PASS"
    FAIL = "FAIL"
    BLOCKED = "BLOCKED"


def _exit_code(verdict):
    return {"PASS": 0, "FAIL": 1, "BLOCKED": 2}[verdict]


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


def verify(output_path, contract, source_path=None) -> dict:
    findings = []
    head = _read_magic(output_path)
    if not head.startswith(_PLAINTEXT_ZIP):
        hex_str = " ".join(f"{b:02X}" for b in head) if head else "(unreadable)"
        findings.append({"check": "output_magic", "passed": False,
                         "detail": f"output not plaintext ({hex_str})"})
        return {"verdict": Verdict.BLOCKED, "findings": findings,
                "output_sha256": _sha256(output_path), "source_sha256": _sha256(source_path) if source_path else None}
    findings.append({"check": "output_magic", "passed": True, "detail": "plaintext PK 03 04"})

    from docx import Document
    try:
        doc = Document(output_path)
    except Exception as e:
        findings.append({"check": "open", "passed": False, "detail": str(e)})
        return {"verdict": Verdict.BLOCKED, "findings": findings,
                "output_sha256": _sha256(output_path), "source_sha256": _sha256(source_path) if source_path else None}
    findings.append({"check": "open", "passed": True, "detail": "python-docx opened"})

    tables = list(doc.tables)

    # expected table count
    exp_tables = contract.get("expected_table_count")
    if exp_tables is not None:
        ok = len(tables) == exp_tables
        findings.append({"check": "table_count", "passed": ok,
                         "detail": f"got {len(tables)} expected {exp_tables}"})

    # required anchors present in collected text
    all_text_parts = [p.text for p in doc.paragraphs]
    for t in tables:
        for row in t.rows:
            for cell in row.cells:
                all_text_parts.append(cell.text)
    all_text = "\n".join(all_text_parts)
    for anchor in contract.get("required_anchors", []):
        ok = anchor in all_text
        findings.append({"check": "anchor_present", "anchor": anchor, "passed": ok})

    # plain table-cell value checks
    for s in contract.get("table_cells", []):
        tidx = int(s["table"]) - 1
        ok = False
        detail = ""
        if 0 <= tidx < len(tables):
            cell = tables[tidx].cell(int(s["row"]), int(s["col"]))
            actual = cell.text
            ok = actual == s["expected"]
            detail = f"[t{s['table']} r{s['row']} c{s['col']}] actual={actual!r} expected={s['expected']!r}"
        else:
            detail = f"table {s['table']} out of range"
        findings.append({"check": "table_cell", "id": s.get("id", str(s)), "passed": ok, "detail": detail})

    # highlight contract checks
    hc = contract.get("highlight_contract")
    if hc:
        # red cells: must be written (value matches) AND stay red
        for rc in hc.get("red_cells", []):
            tidx = int(rc["table"]) - 1
            ok = False
            detail = ""
            if 0 <= tidx < len(tables):
                cell = tables[tidx].cell(int(rc["row"]), int(rc["col"]))
                state = _cell_highlight_state(cell)
                value_ok = cell.text == rc["expected_value"]
                red_ok = state == "red"
                ok = value_ok and red_ok
                detail = (f"[t{rc['table']} r{rc['row']} c{rc['col']}] "
                          f"value={cell.text!r} expected={rc['expected_value']!r} value_ok={value_ok}; "
                          f"state={state} red_ok={red_ok}")
            else:
                detail = f"table {rc['table']} out of range"
            findings.append({"check": "red_cell_written_and_kept_red", "id": rc.get("id", str(rc)),
                             "passed": ok, "detail": detail})
        # positive control: known red fixture cell must read red (probe discriminates)
        for pc in hc.get("red_positive_controls", []):
            tidx = int(pc["table"]) - 1
            ok = False
            detail = ""
            if 0 <= tidx < len(tables):
                cell = tables[tidx].cell(int(pc["row"]), int(pc["col"]))
                state = _cell_highlight_state(cell)
                ok = state == "red"
                detail = f"[t{pc['table']} r{pc['row']} c{pc['col']}] state={state} (expected red for positive control)"
            else:
                detail = f"table {pc['table']} out of range"
            findings.append({"check": "red_positive_control", "id": pc.get("id", str(pc)),
                             "passed": ok, "detail": detail})
        # none cells: must NOT have been written (text unchanged from expected original)
        for nc in hc.get("none_cells", []):
            tidx = int(nc["table"]) - 1
            ok = False
            detail = ""
            if 0 <= tidx < len(tables):
                cell = tables[tidx].cell(int(nc["row"]), int(nc["col"]))
                unchanged = cell.text == nc["expected_original"]
                ok = unchanged
                detail = (f"[t{nc['table']} r{nc['row']} c{nc['col']}] "
                          f"actual={cell.text!r} expected_original={nc['expected_original']!r} unchanged={unchanged}")
            else:
                detail = f"table {nc['table']} out of range"
            findings.append({"check": "none_cell_not_written", "id": nc.get("id", str(nc)),
                             "passed": ok, "detail": detail})
        # yellow cells: must NOT have been written
        for yc in hc.get("yellow_cells", []):
            tidx = int(yc["table"]) - 1
            ok = False
            detail = ""
            if 0 <= tidx < len(tables):
                cell = tables[tidx].cell(int(yc["row"]), int(yc["col"]))
                unchanged = cell.text == yc["expected_original"]
                ok = unchanged
                detail = (f"[t{yc['table']} r{yc['row']} c{yc['col']}] "
                          f"actual={cell.text!r} expected_original={yc['expected_original']!r} unchanged={unchanged}")
            else:
                detail = f"table {yc['table']} out of range"
            findings.append({"check": "yellow_cell_not_written", "id": yc.get("id", str(yc)),
                             "passed": ok, "detail": detail})

    # inserted-table checks
    for itc in contract.get("inserted_tables", []):
        anchor = itc["anchor"]
        # the table should exist immediately after the anchor paragraph
        found = False
        for para in doc.paragraphs:
            if para.text.strip() == anchor.strip():
                nxt = para._p.getnext()
                if nxt is not None and nxt.tag.endswith("}tbl"):
                    found = True
                break
        ok = found == itc.get("expected_present", True)
        findings.append({"check": "inserted_table_after_anchor", "anchor": anchor,
                         "passed": ok, "detail": f"found={found}"})

    overall_pass = all(f.get("passed", False) for f in findings)
    return {"verdict": Verdict.PASS if overall_pass else Verdict.FAIL,
            "findings": findings,
            "output_sha256": _sha256(output_path),
            "source_sha256": _sha256(source_path) if source_path else None}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", required=True)
    ap.add_argument("--contract", required=True)
    ap.add_argument("--source", required=False)
    ap.add_argument("--report-dir", required=False,
                    help="if set, write report.json + report.md (honest layers_skipped/exit_code) here")
    args = ap.parse_args()

    contract = json.loads(Path(args.contract).read_text(encoding="utf-8"))
    result = verify(args.output, contract, source_path=args.source)

    verdict = result["verdict"]
    exit_code = _exit_code(verdict)
    summary = {"verdict": verdict, "exit_code": exit_code,
               "exit_code_contract": {"PASS": 0, "FAIL": 1, "BLOCKED": 2},
               "findings_count": len(result["findings"]),
               "failures": [f for f in result["findings"] if not f.get("passed", False)],
               "output_sha256": result["output_sha256"],
               "source_sha256": result.get("source_sha256")}
    print(json.dumps(summary, ensure_ascii=False, indent=2))

    # honest report: layers_skipped=["visual","delivery"] + exit_code, only when requested
    if args.report_dir:
        import report
        report.write_reports(result, args.contract, args.report_dir, exit_code=exit_code)

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
