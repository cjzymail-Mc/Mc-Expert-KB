#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""make_fixtures.py - generate the self-contained fixture set for pptx-shared-core.

Fixtures are project-neutral (no brand names, no project paths) and exercise the
three historical negative classes plus the encrypted-routing positive control:

  pos_template.pptx        - 2 slides: text slot "Title 1", subtitle anchor,
                             slide 2 has a 1x1 table "Table 1" and a picture.
  neg_encrypted.bin        - 88 7D 1C head (encrypted marker) -> BLOCKED.

Built outputs (produced by build_pptx + the matrix runner) exercise the negatives.
"""
import sys
from pathlib import Path
from pptx import Presentation
from pptx.util import Inches, Pt


def _solid_png():
    from PIL import Image
    import io
    buf = io.BytesIO()
    Image.new("RGBA", (10, 10), (255, 0, 0, 255)).save(buf, format="PNG")
    buf.seek(0)
    return buf


def make_pos_template(out):
    prs = Presentation()
    prs.slide_width = Inches(10)
    prs.slide_height = Inches(7.5)
    blank = prs.slide_layouts[6]
    s1 = prs.slides.add_slide(blank)
    tx = s1.shapes.add_textbox(Inches(1), Inches(1), Inches(6), Inches(1))
    tx.name = "Title 1"
    tx.text_frame.text = "Hello {{NAME}}"
    sub = s1.shapes.add_textbox(Inches(1), Inches(2), Inches(6), Inches(1))
    sub.name = "Subtitle 1"
    sub.text_frame.text = "Short {{N}}"
    s2 = prs.slides.add_slide(blank)
    pic = s2.shapes.add_picture(_solid_png(), Inches(1), Inches(1), Inches(3), Inches(2))
    pic.name = "Picture 1"
    tbl_shape = s2.shapes.add_table(2, 2, Inches(1), Inches(4), Inches(4), Inches(1.5))
    tbl_shape.name = "Table 1"
    tbl_shape.table.cell(0, 0).text = "Key"
    tbl_shape.table.cell(0, 1).text = "Value"
    tbl_shape.table.cell(1, 0).text = "Name"
    tbl_shape.table.cell(1, 1).text = "{{VALUE}}"
    prs.save(out)
    return out


def make_encrypted(out):
    Path(out).write_bytes(b"\x88\x7d\x1c\x00\x00\x00\x00\x00FAKE_CIPHERTEXT")
    return out


def make_duplicate_pic_template(out):
    """A built-style pptx whose slide-2 has TWO pictures with identical L/T/W/H
    (the image-pool stacking bug class)."""
    prs = Presentation()
    prs.slide_width = Inches(10)
    prs.slide_height = Inches(7.5)
    blank = prs.slide_layouts[6]
    s1 = prs.slides.add_slide(blank)
    tx = s1.shapes.add_textbox(Inches(1), Inches(1), Inches(6), Inches(1))
    tx.name = "Title 1"
    tx.text_frame.text = "Hello World"
    p1 = s1.shapes.add_picture(_solid_png(), Inches(1), Inches(1), Inches(3), Inches(2))
    p1.name = "Picture 1"
    p2 = s1.shapes.add_picture(_solid_png(), Inches(1), Inches(1), Inches(3), Inches(2))
    p2.name = "Picture 2"
    prs.save(out)
    return out


if __name__ == "__main__":
    outdir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
    outdir.mkdir(parents=True, exist_ok=True)
    make_pos_template(outdir / "pos_template.pptx")
    make_encrypted(outdir / "neg_encrypted.bin")
    make_duplicate_pic_template(outdir / "neg_duplicate_pics.pptx")
    print("fixtures written to", outdir)