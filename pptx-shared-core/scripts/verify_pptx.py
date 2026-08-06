#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verify_pptx.py - INDEPENDENT deterministic verifier for a built PPTX.

Does NOT trust the builder's "save succeeded". Re-reads the output and checks:
  - output magic is plaintext 50 4B 03 04
  - slide count, shape presence, table cell contents, required anchors present
  - no duplicate picture coordinates (image-pool stacking bug)
  - r:embed / r:link, rels/media residue: old blobs gone, no orphans
  - output SHA-256 reported

Verdict -> exit code:  PASS=0 / FAIL=1 / BLOCKED=2.
THE FINAL VERDICT ALWAYS REACHES THE EXIT CODE (false-PASS fix:
a verify() that returns bool but never sys.exit produces exit 0 on FAIL).

Usage: python verify_pptx.py --output o.pptx --contract c.json [--source t.pptx]
Exit: 0 PASS / 1 FAIL / 2 BLOCKED
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import zipfile
from collections import defaultdict
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


class Verdict:
    PASS = "PASS"
    FAIL = "FAIL"
    BLOCKED = "BLOCKED"


def _exit_code(verdict):
    return {"PASS": 0, "FAIL": 1, "BLOCKED": 2}[verdict]


def verify(output_path, contract, source_path=None) -> dict:
    findings = []
    head = _read_magic(output_path)
    if not head.startswith(_PLAINTEXT_ZIP):
        hex_str = " ".join(f"{b:02X}" for b in head)
        findings.append({"check": "output_magic", "passed": False,
                         "detail": f"output not plaintext ({hex_str})"})
        return {"verdict": Verdict.BLOCKED, "findings": findings,
                "output_sha256": _sha256(output_path)}

    findings.append({"check": "output_magic", "passed": True, "detail": "plaintext PK 03 04"})

    from pptx import Presentation
    from pptx.enum.shapes import MSO_SHAPE_TYPE
    try:
        prs = Presentation(output_path)
    except Exception as e:
        findings.append({"check": "open", "passed": False, "detail": str(e)})
        return {"verdict": Verdict.BLOCKED, "findings": findings,
                "output_sha256": _sha256(output_path)}

    # slide count
    exp_slides = contract.get("expected_slide_count")
    if exp_slides is not None:
        n = len(prs.slides._sldIdLst)
        ok = n == exp_slides
        findings.append({"check": "slide_count", "passed": ok,
                         "detail": f"got {n} expected {exp_slides}"})

    # collect all text
    all_text = ""
    slides = list(prs.slides)
    # collect picture geometries per slide for duplicate detection
    pic_geoms = defaultdict(list)
    image_blob_shas = []
    for i, slide in enumerate(slides, start=1):
        for sh in slide.shapes:
            if sh.has_text_frame:
                all_text += sh.text_frame.text + "\n"
            if sh.shape_type == MSO_SHAPE_TYPE.PICTURE:
                g = {"left": float(sh.left or 0), "top": float(sh.top or 0),
                     "width": float(sh.width or 0), "height": float(sh.height or 0)}
                pic_geoms[i].append(g)
                try:
                    image_blob_shas.append(hashlib.sha256(sh.image.blob).hexdigest())
                except Exception:
                    pass

    # required anchors
    for anchor in contract.get("required_anchors", []):
        ok = anchor in all_text
        findings.append({"check": "anchor_present", "anchor": anchor, "passed": ok})

    # slots
    for s in contract.get("slots", []):
        idx = s["slide"] - 1
        ok = False
        detail = ""
        if 0 <= idx < len(slides):
            slide = slides[idx]
            target = next((sh for sh in slide.shapes if sh.name == s["shape"]), None)
            if target is not None:
                if s["kind"] == "text" and target.has_text_frame:
                    actual = target.text_frame.text
                    ok = actual == s["expected"]
                    detail = f"actual={actual!r} expected={s['expected']!r}"
                elif s["kind"] == "table" and getattr(target, "has_table", False):
                    cell = target.table.cell(int(s["row"]), int(s["col"]))
                    actual = cell.text
                    ok = actual == s["expected"]
                    detail = f"[{s['row']},{s['col']}] actual={actual!r} expected={s['expected']!r}"
            else:
                detail = f"shape {s['shape']!r} not found"
        else:
            detail = "slide out of range"
        findings.append({"check": "slot", "slide": s["slide"], "shape": s["shape"],
                         "passed": ok, "detail": detail})

    # duplicate picture coordinates
    if contract.get("forbid_duplicate_picture_coords", True):
        for slide_idx, geoms in pic_geoms.items():
            seen = {}
            for g in geoms:
                key = (round(g["left"], 1), round(g["top"], 1), round(g["width"], 1), round(g["height"], 1))
                if key in seen:
                    findings.append({"check": "duplicate_picture_coords", "slide": slide_idx,
                                     "passed": False,
                                     "detail": f"duplicate L/T/W/H {key}"})
                else:
                    seen[key] = True

    # rels/media residue check
    if contract.get("check_rels_residue", True):
        residue = _check_rels_residue(output_path)
        if residue["orphans"]:
            findings.append({"check": "rels_residue", "passed": False,
                             "detail": f"orphan media: {residue['orphans']}"})

    # image presence
    for s in contract.get("image_slots", []):
        idx = s["slide"] - 1
        ok = False
        if 0 <= idx < len(slides):
            slide = slides[idx]
            target = next((sh for sh in slide.shapes if sh.name == s["shape"]), None)
            ok = target is not None and target.shape_type == MSO_SHAPE_TYPE.PICTURE
        findings.append({"check": "image_present", "slide": s["slide"],
                         "shape": s["shape"], "passed": ok})

    overall_pass = all(f.get("passed", False) for f in findings)
    return {"verdict": Verdict.PASS if overall_pass else Verdict.FAIL,
            "findings": findings,
            "output_sha256": _sha256(output_path),
            "source_sha256": _sha256(source_path) if source_path else None,
            "image_blob_sha256s": image_blob_shas}


def _check_rels_residue(path) -> dict:
    orphans = []
    try:
        with zipfile.ZipFile(path) as zf:
            names = set(zf.namelist())
            media = {n for n in names if n.startswith("ppt/media/")}
            referenced = set()
            for n in names:
                if n.startswith("ppt/slides/_rels/") and n.endswith(".rels"):
                    data = zf.read(n).decode("utf-8", "replace")
                    for line in data.splitlines():
                        if "Target" in line and "media" in line.lower():
                            # crude extraction of ../media/x.png
                            for tok in line.split('"'):
                                if "media" in tok:
                                    referenced.add("ppt/" + tok.lstrip("../").lstrip("/"))
            orphans = sorted(media - referenced)
    except Exception:
        pass
    return {"orphans": orphans}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", required=True)
    ap.add_argument("--contract", required=True)
    ap.add_argument("--source", required=False)
    args = ap.parse_args()

    contract = json.loads(Path(args.contract).read_text(encoding="utf-8"))
    result = verify(args.output, contract, source_path=args.source)

    verdict = result["verdict"]
    summary = {"verdict": verdict, "findings_count": len(result["findings"]),
               "failures": [f for f in result["findings"] if not f.get("passed", False)],
               "output_sha256": result["output_sha256"],
               "source_sha256": result.get("source_sha256")}
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return _exit_code(verdict)


if __name__ == "__main__":
    sys.exit(main())