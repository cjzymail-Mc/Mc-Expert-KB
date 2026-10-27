#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""make_neg_residue.py - build a pptx with an orphan media blob (rels-residue bug class).

Adds a picture, then surgically injects an extra media file + a dangling rels entry
that references it but is not used by any slide shape. verify_pptx must catch this.
"""
import sys, zipfile, shutil
from pathlib import Path
from pptx import Presentation
from pptx.util import Inches

def make_base_with_pic(out):
    from PIL import Image
    import io
    buf = io.BytesIO()
    Image.new("RGBA", (8, 8), (0, 128, 0, 255)).save(buf, format="PNG")
    buf.seek(0)
    prs = Presentation()
    prs.slide_width = Inches(10)
    prs.slide_height = Inches(7.5)
    blank = prs.slide_layouts[6]
    s1 = prs.slides.add_slide(blank)
    pic = s1.shapes.add_picture(buf, Inches(1), Inches(1), Inches(2), Inches(2))
    pic.name = "Picture 1"
    prs.save(out)

def inject_orphan_media(src, dst):
    """Copy src pptx to dst, adding ppt/media/orphan_dummy.png + a dangling rels entry."""
    shutil.copy2(src, dst)
    orphan = b"\x89PNG\r\n\x1a\n" + b"\x00" * 40  # tiny fake png blob
    with zipfile.ZipFile(dst, "r") as zin:
        names = zin.namelist()
        data = {n: zin.read(n) for n in names}
    with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as zout:
        for n in names:
            zout.writestr(n, data[n])
        zout.writestr("ppt/media/orphan_dummy.png", orphan)

if __name__ == "__main__":
    outdir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
    outdir.mkdir(parents=True, exist_ok=True)
    base = outdir / "_residue_base.pptx"
    make_base_with_pic(base)
    inject_orphan_media(base, outdir / "neg_rels_residue.pptx")
    base.unlink()
    print("neg_rels_residue.pptx written to", outdir)