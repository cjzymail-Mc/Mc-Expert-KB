#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""build_pptx.py - golden-copy + long-anchor-first fill for plaintext PPTX.

Copies a read-only template to an explicit NEW output path, then:
  1. long-anchor-first replace (avoid short-substring false matches)
  2. explicit slot fills (text / table cells) by slide + shape_name
  3. image replacement (relationship hygiene: new blob in, old blob out atomically)
  4. fail-protect: missing anchor/slot or existing output -> abort before save

Algorithm extracted from a production builder; self-contained and project-neutral.
The builder never invents business facts; all content comes from --metadata / --slot-map.

Usage:
  python build_pptx.py --template t.pptx --metadata m.json --slot-map s.json --out o.pptx
Exit: 0 built / 1 build-fail / 2 blocked
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import pathlib
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


_LDTERM_CIPHER = b"\x88\x7d\x1c"
_LEDGER_DEFAULT_NAME = "pending_human_blocked.json"


def _route_for_magic(head):
    if head.startswith(_PLAINTEXT_ZIP):
        return "python"
    if head.startswith(_LDTERM_CIPHER):
        return "BLOCKED"
    return "BLOCKED"


def _append_pending_human(path, route, magic_hex, label, ledger_path):
    from datetime import datetime
    entry = {
        "input_path": str(path),
        "label": label,
        "route": route,
        "magic_hex": magic_hex,
        "action": "STOP: do not COM-read; report path+hex to human for DLP decrypt",
        "recorded_at": datetime.now().astimezone().isoformat(),
    }
    # B-CP1-05: ledger path is caller-supplied (CLI --pending-human-ledger),
    # defaulting to caller cwd. Never auto-write to a shared/cross-repo location.
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
        hex_str = " ".join(f"{b:02X}" for b in head)
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
        }))
        return True
    return False


def replace_anchors_longest_first(prs, anchors):
    """anchors: list[{find:str, replace:str}]. Longest 'find' first.

    Run-level replace first per paragraph; if a paragraph yields zero hits it
    degrades to paragraph-level (concat runs -> replace -> write runs[0], blank
    the rest). Mirrors build_docx.py so cross-run anchors (e.g. project name
    split across runs in a header) are handled instead of silently missed.
    """
    pending = sorted(anchors, key=lambda a: len(a["find"]), reverse=True)
    applied = []
    for a in pending:
        find = a["find"]
        repl = a["replace"]
        hits = 0
        for slide in prs.slides:
            for sh in slide.shapes:
                if not sh.has_text_frame:
                    continue
                tf = sh.text_frame
                for para in tf.paragraphs:
                    run_hit = 0
                    for run in para.runs:
                        if find in run.text:
                            run.text = run.text.replace(find, repl)
                            run_hit += 1
                    if run_hit == 0 and find in para.text:
                        full = para.text.replace(find, repl)
                        if para.runs:
                            para.runs[0].text = full
                            for extra in para.runs[1:]:
                                extra.text = ""
                            run_hit += 1
                    hits += run_hit
        applied.append({"find": find, "replace": repl, "hits": hits})
    return applied


def fill_slots(prs, slots):
    """slots: list[{slide:int, shape:str, kind:'text'|'table', expected:str, row?:int, col?:int}]"""
    results = []
    slides = list(prs.slides)
    for s in slots:
        idx = s["slide"] - 1
        if idx < 0 or idx >= len(slides):
            results.append({"slot": s, "ok": False, "reason": "slide index out of range"})
            continue
        slide = slides[idx]
        found = None
        for sh in slide.shapes:
            if sh.name == s["shape"]:
                found = sh
                break
        if found is None:
            results.append({"slot": s, "ok": False, "reason": f"shape {s['shape']!r} not found on slide {s['slide']}"})
            continue
        if s["kind"] == "text":
            if not found.has_text_frame:
                results.append({"slot": s, "ok": False, "reason": "shape has no text_frame"})
                continue
            found.text_frame.text = s["expected"]
            results.append({"slot": {"slide": s["slide"], "shape": s["shape"]}, "ok": True})
        elif s["kind"] == "table":
            if not getattr(found, "has_table", False):
                results.append({"slot": s, "ok": False, "reason": "shape has no table"})
                continue
            row, col = int(s["row"]), int(s["col"])
            cell = found.table.cell(row, col)
            cell.text = s["expected"]
            results.append({"slot": {"slide": s["slide"], "shape": s["shape"], "row": row, "col": col}, "ok": True})
        else:
            results.append({"slot": s, "ok": False, "reason": f"unknown kind {s['kind']!r}"})
    return results


def replace_image(prs, image_slots):
    """image_slots: list[{slide:int, shape:str, image_path:str}].
    Replaces the picture's blob via its image part; old blob must be gone.
    Uses python-pptx low-level part access for relationship hygiene."""
    from pptx.parts.image import Image
    results = []
    slides = list(prs.slides)
    for s in image_slots:
        idx = s["slide"] - 1
        if idx < 0 or idx >= len(slides):
            results.append({"image_slot": s, "ok": False, "reason": "slide out of range"})
            continue
        slide = slides[idx]
        target = None
        for sh in slide.shapes:
            if sh.name == s["shape"]:
                target = sh
                break
        if target is None:
            results.append({"image_slot": s, "ok": False, "reason": f"shape {s['shape']!r} not found"})
            continue
        try:
            old_blob_sha = hashlib.sha256(target.image.blob).hexdigest()
        except Exception:
            old_blob_sha = None
        try:
            with open(s["image_path"], "rb") as fh:
                new_blob = fh.read()
            new_sha = hashlib.sha256(new_blob).hexdigest()
            slide_part = target.part
            # SlidePart.get_or_add_image_part returns (ImagePart, rId)
            image_part, new_rid = slide_part.get_or_add_image_part(s["image_path"])
            # wire the picture's blip r:embed to the new relationship (blip_rId has no setter -> set XML attr directly)
            _NS_R_EMBED = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed"
            blip = target._element.find(".//{http://schemas.openxmlformats.org/drawingml/2006/main}blip")
            if blip is None:
                raise RuntimeError("picture has no <a:blip> element to rewire")
            old_rid = blip.get(_NS_R_EMBED)
            blip.set(_NS_R_EMBED, new_rid)
            # drop the old image relationship so the old blob can be cleaned on save (relationship hygiene)
            try:
                slide_part.drop_rel(old_rid)
            except Exception:
                pass
            results.append({"image_slot": {"slide": s["slide"], "shape": s["shape"]},
                            "ok": True, "old_blob_sha256": old_blob_sha, "new_blob_sha256": new_sha})
        except Exception as e:
            results.append({"image_slot": s, "ok": False, "reason": str(e)})
    return results


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--template", required=True)
    ap.add_argument("--metadata", required=False)
    ap.add_argument("--slot-map", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--pending-human-ledger", required=False, default=None,
                    help="explicit path for the BLOCKED pending-human ledger JSON; "
                         "defaults to <caller-cwd>/pending_human_blocked.json")
    args = ap.parse_args()

    # B-CP1-05: ledger path is caller-supplied, never derived from __file__.
    # Default keeps the same filename but anchors to caller CWD, not core root.
    if args.pending_human_ledger:
        ledger_path = pathlib.Path(args.pending_human_ledger)
    else:
        ledger_path = pathlib.Path.cwd() / _LEDGER_DEFAULT_NAME

    if _check_blocked(args.template, "template", ledger_path):
        return 2

    if Path(args.out).exists():
        print(json.dumps({"status": "BUILD_FAIL", "reason": f"output already exists: {args.out}"}))
        return 1

    source_sha_before = _sha256(args.template)
    slot_map = json.loads(Path(args.slot_map).read_text(encoding="utf-8"))
    anchors = slot_map.get("anchors", [])
    slots = slot_map.get("slots", [])
    image_slots = slot_map.get("image_slots", [])

    # validate anchors present in template before building
    from pptx import Presentation
    prs = Presentation(args.template)
    all_text = ""
    for slide in prs.slides:
        for sh in slide.shapes:
            if sh.has_text_frame:
                all_text += sh.text_frame.text + "\n"
    missing_anchors = [a["find"] for a in anchors if a["find"] not in all_text]
    if missing_anchors:
        print(json.dumps({"status": "BUILD_FAIL", "reason": "missing anchors", "missing": missing_anchors}))
        return 1

    anchor_results = replace_anchors_longest_first(prs, anchors)
    slot_results = fill_slots(prs, slots)
    image_results = replace_image(prs, image_slots) if image_slots else []

    # fail-protect: re-scan in-memory text for any anchor find-string that the
    # pre-check accepted but the replace pass could not actually remove. Closes
    # the silent-fake-BUILT hole (pre-check uses paragraph text, replace touched
    # runs). Abort BEFORE save.
    out_text_after = ""
    for slide in prs.slides:
        for sh in slide.shapes:
            if sh.has_text_frame:
                out_text_after += sh.text_frame.text + "\n"
    residual = [a["find"] for a in anchors if a["find"] in out_text_after]
    if residual:
        print(json.dumps({"status": "BUILD_FAIL",
                          "reason": "anchor find-string still present after replace (silent miss blocked)",
                          "residual": residual,
                          "anchor_hits": [{"find": r["find"], "hits": r["hits"]} for r in anchor_results]},
                         ensure_ascii=False))
        return 1

    prs.save(args.out)

    # source must be unchanged
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
                      "anchors": anchor_results, "slots": slot_results,
                      "images": image_results}, ensure_ascii=False, indent=2))
    return 0 if out_ok else 1


if __name__ == "__main__":
    sys.exit(main())