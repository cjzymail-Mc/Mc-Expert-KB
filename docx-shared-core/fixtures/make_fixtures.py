#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""make_fixtures.py - generate the self-contained fixture set for docx-shared-core.

Fixtures are project-neutral (no brand names, no project paths) and exercise the
DOCX invariants: 3-state highlight contract (red/yellow/none), long-anchor
replace, table-cell slot fill, and the encrypted/OLE routing negatives.

Outputs (written to the given outdir, default .):
  pos_template.docx        - 1 table (3x3). [1,0]=red (must-replace),
                             [1,1]=yellow (manual marker), [1,2]=none (do not touch).
                             Header paragraph with {{TITLE}} anchor.
  neg_encrypted.bin        - 88 7D 1C head (encrypted marker) -> BLOCKED.
  neg_ole.bin              - D0 CF 11 E0 head (OLE/CFB legacy .doc) -> BLOCKED.

Requires python-docx (the builder's only third-party dep).
"""
import sys
from pathlib import Path
from docx import Document
from docx.enum.text import WD_COLOR_INDEX


def _set_cell_red(cell, text):
    cell.text = text
    for para in cell.paragraphs:
        for run in para.runs:
            run.font.highlight_color = WD_COLOR_INDEX.RED


def _set_cell_yellow(cell, text):
    cell.text = text
    for para in cell.paragraphs:
        for run in para.runs:
            run.font.highlight_color = WD_COLOR_INDEX.YELLOW


def _set_cell_none(cell, text):
    cell.text = text
    # explicitly no highlight


def make_pos_template(out):
    doc = Document()
    # header paragraph with anchor
    doc.add_paragraph("Report: {{TITLE}}")
    doc.add_paragraph("Intro line before table.")
    # 3x3 table
    table = doc.add_table(rows=3, cols=3)
    table.style = "Table Grid"
    # header row
    for ci, htext in enumerate(["Field", "Value", "Note"]):
        table.cell(0, ci).text = htext
    # row 1: red (must replace), yellow (marker), none (do not touch)
    _set_cell_red(table.cell(1, 0), "{{RED_VALUE}}")
    _set_cell_yellow(table.cell(1, 1), "MANUAL_MARKER")
    _set_cell_none(table.cell(1, 2), "fixed-note")
    # row 2: plain cells
    table.cell(2, 0).text = "static-a"
    table.cell(2, 1).text = "static-b"
    table.cell(2, 2).text = "static-c"
    doc.add_paragraph("Outro line after table.")
    doc.save(out)


def make_encrypted(out):
    # 88 7D 1C head + fake ciphertext
    Path(out).write_bytes(b"\x88\x7d\x1c\x00\x00\x00\x00\x00FAKE_CIPHERTEXT")


def make_ole(out):
    # D0 CF 11 E0 head + filler (CFB storage marker)
    filler = b"\x00" * 24
    Path(out).write_bytes(b"\xD0\xCF\x11\xE0\xA1\xB1\x1A\xE1" + filler)


if __name__ == "__main__":
    outdir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
    outdir.mkdir(parents=True, exist_ok=True)
    make_pos_template(outdir / "pos_template.docx")
    make_encrypted(outdir / "neg_encrypted.bin")
    make_ole(outdir / "neg_ole.bin")
    print("fixtures written to", outdir)
