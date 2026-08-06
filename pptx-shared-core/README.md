# pptx-shared-core (staged, non user-scope)

> PPTX golden-copy production core + deterministic verifier. Staged at
> `[feature-08-double-workflow-Build]/pptx-shared-core/` during double-session run
> `22a36f65`. Project-neutral: no brand names, no project-private paths, no COM.

## What this is

A minimal, self-contained PPTX **golden-reference** production route, first version:

- reads plaintext PPTX templates (`50 4B 03 04`), refuses encrypted input (`88 7D 1C` -> STOP, exit 2)
- fills long-anchor-first + explicit text/table slots via python-pptx
- verifies output deterministically: magic, slide count, required anchors, slot text/cell
  contents, duplicate-picture-coordinate detection, OOXML rels/media residue, SHA-256 binding
- verdict always reaches exit code: **PASS=0 / FAIL=1 / BLOCKED=2**

Explicitly NOT in v1: visual LLM, auto-fix, COM template probe, render-to-image,
legacy DLP decrypt, HTML/CSS hybrid, Excel, Word.

## Layout

```
scripts/
  file_probe.py        magic-byte router (plaintext->python / cipher->BLOCKED exit 2)
  inspect_template.py  structure discovery (JSON+MD)
  build_pptx.py        golden-copy builder: copy -> fill anchors/slots/images, fail-protect
  verify_pptx.py       independent deterministic verifier -> exit-coded verdict
  report.py            verify wrapper (report.json/md)
  resolve_core.py      multi-position core resolver (env var / shared sibling / staging / walk-up)
fixtures/
  make_fixtures.py     regenerates all fixtures (project-neutral)
  pos_template.pptx    positive: text slot + table slot + picture
  neg_duplicate_pics.pptx  image-pool stacking bug class
  neg_encrypted.bin        88 7D 1C head -> BLOCKED
contracts/
  pos_slot_map.json / pos_contract.json     positive build+verify
  neg_semantic_contract.json               asserts expected text vs wrong output
  neg_duplicate_contract.json              asserts duplicate detection
run_matrix.py             6-case deterministic matrix (exit 0 = all pass)
entries/
  claude/SKILL.md + resolve_core.py    Claude thin entry (multi-position resolver)
  codex/SKILL.md  + resolve_core.py    Codex thin entry (multi-position resolver)
staging-install/          mirror install layout (B-CP3-PRE proof)
output/                   machine evidence: matrix reports + built products
```

## Acceptance matrix (done_when evidence)

Run: `python run_matrix.py --out-dir <fresh-unique-dir>` -> exit 0 means all 6 cases match.

| case | chain | expected | verdict |
|------|-------|----------|---------|
| R1 pos | build->verify | build 0 / verify 0 | PASS |
| R2 neg-sem | wrong title->verify | build 0 / verify 1 | PASS |
| R3 neg-dup | verify duplicate pics | verify 1 | PASS |
| R4 neg-tbl | wrong table cell->verify | build 0 / verify 1 | PASS |
| R5 neg-rels | verify orphan media | verify 1 | PASS |
| R6 neg-enc | build encrypted input | exit 2 (BLOCKED) | PASS |

The negative classes required by done_when #4 (fake-PASS / duplicate-image / wrong-table) plus rels-residue all exit non-zero; encrypted input exits 2 (BLOCKED).

## Per-run hash semantics (NOT a fixed golden target)

python-pptx embeds a creation timestamp in OOXML core props, so the **product
SHA-256 varies per run**. The matrix records a determinism probe (build same
input N times, compare hashes). The product hash is a **per-run binding**, not
a fixed golden target. The source template hash (`d4116cba…`) is stable and is
the real identity anchor.

## Entry↔core resolution contract (B-CP3-PRE + B-CP3-PACKAGE)

Thin entries resolve the shared core via esolve_core.py\ (multi-position probe).
The **install package is frozen** in \INSTALL_MANIFEST.json\ (25 files, source→target
+ SHA-256) with an explicit exclude list (output/, __pycache__/, ledgers,
staging-install/, entries/, temp probes). A clean-package test proved the
manifest subset is self-sufficient (both entries resolve, matrix 6/6 PASS,
build+verify+BLOCKED pass from the clean path). See \MASTER_WRITE_PLAN.md\ for
the pre-write master file list and rollback plan.

Note: the \mirror_resolution_smoke\ evidence block (formerly mislabeled
\resh_discovery_build\) tests resolve_core invocation from the mirror entry
position — it is NOT a fresh-session platform discovery. Real fresh-session
discovery is deferred to final CP3 after master install.

Thin entries (`entries/claude/`, `entries/codex/`) and the mirror install layout
(`staging-install/`) both resolve the shared core via `resolve_core.py`, which
probes: env var `PPTX_GOLDEN_CORE` → sibling `shared/pptx-shared-core` (mirror
install) → `../../scripts/` (staging) → walk-up repo `pptx-shared-core`.
See `HASH_PARITY.md` for the parity proof.

## Defect found and fixed during CP0/CP1

The frozen C2 matrix in feature-07 had a latent false-PASS: R2 "neg-semantic" used a
builder slot-map as the verifier contract, so `neg_semantic_built.pptx` (containing
"Hello WRONGTEXT") wrongly exited 0. This core's `neg_semantic_contract.json` asserts
`required_anchors:["Hello World"]` + slot `expected:"Hello World"`, so the wrong output
now correctly exits 1. The matrix runner proves it.

## Source lineage

Lifted from the feature-07 `build-pptx-from-template` tool cluster (debranded: removed
project references from docstrings/comments). See `FEATURE07-MAINTENANCE-BOUNDARY.md`
for the read-only maintenance boundary. The original production bundle referenced by
the task does not exist on this machine; the in-repo feature-07 cluster and its
verified fixture matrix were the closest source of truth.

## Boundaries

- Non user-scope staging: this core lives in feature-08 until CP3 user-scope authorization.
- All four negative classes (fake-PASS/semantic, duplicate-image, wrong-table, rels-residue) are self-contained in this core with their own fixtures and all exit non-zero.
- Plaintext `50 4B` output is internal-middleware only; external delivery stays behind
  the repo's plaintext-Office compliance gate (done_when #8).