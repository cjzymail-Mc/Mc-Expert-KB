#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""inspect_template.py - python-pptx structure discovery for a plaintext template.

Mandatory pre-fill step: the template is a black box; slots/anchors must be discovered,
not guessed. Emits JSON + MD of slides, shapes (name/type/text/geometry), tables, pictures,
and image relationships (r:embed / rels / media).

Source: inspect-ppt-template (COM) reimplemented with python-pptx (no COM).
Usage: python inspect_template.py <template.pptx> --out <dir>
Exit: 0 ok / 2 blocked
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import zipfile
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


def _geom(shape):
    try:
        return {"left": float(shape.left or 0), "top": float(shape.top or 0),
                "width": float(shape.width or 0), "height": float(shape.height or 0)}
    except Exception:
        return {"left": None, "top": None, "width": None, "height": None}


def _text(shape):
    if shape.has_text_frame:
        return shape.text_frame.text
    return ""


def _table(shape):
    out = []
    if getattr(shape, "has_table", False):
        for r, row in enumerate(shape.table.rows):
            for c, cell in enumerate(row.cells):
                out.append({"row": r, "col": c, "text": cell.text})
    return out


def inspect(path) -> dict:
    from pptx import Presentation
    from pptx.enum.shapes import MSO_SHAPE_TYPE
    prs = Presentation(path)
    slides = []
    for idx, slide in enumerate(prs.slides, start=1):
        shapes = []
        for sh in slide.shapes:
            entry = {"name": sh.name, "type": str(sh.shape_type),
                     "geometry": _geom(sh), "text": _text(sh)}
            tbl = _table(sh)
            if tbl:
                entry["table"] = tbl
            if sh.shape_type == MSO_SHAPE_TYPE.PICTURE:
                try:
                    entry["image_blob_sha256"] = hashlib.sha256(sh.image.blob).hexdigest()
                except Exception:
                    entry["image_blob_sha256"] = None
            shapes.append(entry)
        slides.append({"slide": idx, "shapes": shapes})
    return {"slide_count": len(slides), "slides": slides}


def _rels_media(path) -> dict:
    """List rels + media in the pptx zip for residue diagnosis (rels/media hygiene)."""
    out = {"rels_files": [], "media_files": []}
    try:
        with zipfile.ZipFile(path) as zf:
            for name in zf.namelist():
                if name.startswith("ppt/slides/_rels/") and name.endswith(".rels"):
                    data = zf.read(name).decode("utf-8", "replace")
                    embeds = [ln for ln in data.splitlines() if "image" in ln.lower() or "r:embed" in ln or "Target" in ln]
                    out["rels_files"].append({"file": name, "image_targets": embeds})
                elif name.startswith("ppt/media/"):
                    out["media_files"].append({"file": name, "bytes": len(zf.read(name))})
    except Exception as e:
        out["error"] = str(e)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("template")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    head = _read_magic(args.template)
    if not head.startswith(_PLAINTEXT_ZIP):
        hex_str = " ".join(f"{b:02X}" for b in head)
        print(json.dumps({"route": "BLOCKED", "reason": f"not plaintext ({hex_str})", "path": args.template}))
        return 2

    result = inspect(args.template)
    result["source_path"] = str(args.template)
    result["source_sha256"] = _sha256(args.template)
    result["rels_media"] = _rels_media(args.template)

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "inspect_report.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    md_lines = [f"# Inspect Report", "",
                f"- source: `{args.template}`", f"- sha256: `{result['source_sha256']}`",
                f"- slides: {result['slide_count']}", ""]
    for sl in result["slides"]:
        md_lines.append(f"## Slide {sl['slide']}")
        for sh in sl["shapes"]:
            md_lines.append(f"- **{sh['name']}** ({sh['type']}) geom={sh['geometry']}")
            if sh.get("text"):
                md_lines.append(f"  - text: {sh['text']!r}")
            if sh.get("table"):
                md_lines.append(f"  - table cells: {len(sh['table'])}")
            if sh.get("image_blob_sha256"):
                md_lines.append(f"  - image sha256: `{sh['image_blob_sha256']}`")
    (out_dir / "inspect_report.md").write_text("\n".join(md_lines), encoding="utf-8")

    print(json.dumps({"route": "python", "slide_count": result["slide_count"],
                      "report": str(out_dir / "inspect_report.json")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())