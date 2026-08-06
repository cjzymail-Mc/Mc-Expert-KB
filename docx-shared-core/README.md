# docx-shared-core (staged, non user-scope)

> DOCX golden-copy production core + deterministic verifier. Staged at
> `[feature-09-codex-Office-skill-Build]/docx-shared-core/` during double-session run
> `6aa8470b`. Project-neutral: no brand names, no project-private paths, no COM.

## What this is

A minimal, self-contained DOCX **golden-reference** production route, first version:

- reads plaintext DOCX templates (`50 4B 03 04`), refuses encrypted input (`88 7D 1C` -> STOP, exit 2)
- refuses OLE/CFB legacy `.doc` (`D0 CF 11 E0` -> BLOCKED exit 2; needs a COM extension, not in this core)
- fills long-anchor-first `{{token}}` across body/table-cells/headers/footers + explicit slots (text, red-cell-driven, table-insert)
- enforces the Word 3-state HIGHLIGHT contract (RED=must-replace+keep-red, YELLOW=skip, none=skip)
- verifies output deterministically: magic, table count, anchors, cell values, 3-state highlight,
  inserted-table adjacency, SHA-256 binding
- verdict always reaches exit code: **PASS=0 / FAIL=1 / BLOCKED=2**

Explicitly NOT in v1: visual LLM, auto-fix, COM template probe, render-to-image,
legacy DLP decrypt, HTML/CSS hybrid, Excel, PPTX, live fresh-session cutover.

## Layout

```
scripts/
  file_probe.py        magic-byte router (plaintext->python / cipher->BLOCKED / OLE->BLOCKED / unknown->BLOCKED)
  inspect_template.py  structure discovery (JSON+MD)
  build_docx.py        golden-copy builder: copy -> anchors/slots/red-cell/highlight contract, fail-protect
  verify_docx.py       independent deterministic verifier -> exit-coded verdict
  report.py            verify wrapper (report.json/md)
  resolve_core.py      multi-position core resolver (env var / shared sibling / staging / walk-up)
fixtures/
  make_fixtures.py     regenerates all fixtures (project-neutral)
  pos_template.docx    positive: header anchor {{TITLE}}, 3x3 table with red/yellow/none cells
  neg_encrypted.bin        88 7D 1C head -> BLOCKED
  neg_ole.bin              D0 CF 11 E0 head -> BLOCKED (legacy .doc, unsupported)
contracts/
  pos_slot_map.json / pos_contract.json     positive build+verify
run_matrix.py               12-case acceptance matrix (fresh outdir) + determinism probe
quick_validate.py           entry reachability + minimal positive chain
HASH_PARITY.md              per-file SHA-256 baseline
README.md                   this file
```

## 3-state highlight contract (Word-specific, structural OOXML attribute)

| state | WD_COLOR_INDEX | builder action | verifier assertion |
|---|---|---|---|
| RED | 6 | write value + re-apply red (audit trace) | cell written AND stays red |
| YELLOW | 7 | skip (manual marker) | not written (miswrite -> FAIL) |
| none | (no highlight) | skip | not written (miswrite -> FAIL) |

cell = red iff ALL runs in the cell are red (avoids mixed-run ambiguity).

## Acceptance matrix (done_when)

| case | chain | expected | proves |
|---|---|---|---|
| C_pos | build -> verify | 0 / 0 | positive green |
| C_missing_anchor | build absent anchor | build 1 | fail-protect (no overwrite) |
| C_output_exists | build to existing out | build 1 | refuse-overwrite |
| C_none_miswrite | verify none-cell miswrite | verify 1 | none-miswrite caught |
| C_yellow_miswrite | verify yellow-cell miswrite | verify 1 | yellow-miswrite caught |
| C_multi_bad | verify none+yellow simultaneous | verify 1 | diagnosis stable |
| C_non_unique_anchor | build duplicated table_insert anchor | build 1 | non-unique anchor caught |
| C_encrypted | build encrypted.bin template | build 2 | 88 7D 1C BLOCKED |
| C_ole | build ole.bin template | build 2 | D0 CF 11 E0 BLOCKED |
| C_file_probe_routes | file_probe.py direct-run 3 fixtures | exit 0/2/2 | file_probe routes python/BLOCKED/BLOCKED |
| C_verify_blocked_enc | verify neg_encrypted.bin as output | verify 2 | verify BLOCKED branch (88 7D 1C) |
| C_verify_blocked_ole | verify neg_ole.bin as output | verify 2 | verify BLOCKED branch (D0 CF 11 E0) |

Determinism probe builds the same input N times; python-docx may embed a creation
timestamp, so the product hash is per-run, not a fixed golden target. Only per-run
SHA-256 binding is valid; the source template hash is the identity anchor.

## Source lineage

Mirrors the proven `pptx-shared-core` (feature-08). The Word 3-state highlight
contract mirrors the `three-state-coloring-contract-word-only` skill + the July
Word seed pipeline (read-only reference). This is the first translation of COM
`HighlightColorIndex` semantics into python-docx `run.font.highlight_color`; a
positive RED control fixture ships to prove the probe discriminates.

## Boundaries

- Non user-scope staging: this core lives in feature-09 until CP3 user-scope authorization.
- Legacy `.doc` (OLE/CFB) and encrypted OOXML are not handled here; a COM extension (human-triggered) may serve them.
- Plaintext `50 4B` output is internal-middleware only; external delivery stays behind the repo's plaintext-Office compliance gate.
