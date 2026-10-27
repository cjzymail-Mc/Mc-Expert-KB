# Shared-core hash parity (B-CP3-PACKAGE re-pinned 2026-08-05)

The shared core is a **single source of truth**. Both platform entries
(`entries/claude/` and `entries/codex/`) and the mirror install layout
(`staging-install/`) resolve to it via `resolve_core.py`. No entry contains a
copy of the core scripts. This file records the SHA-256 baseline.

## Core script SHA-256 (current, B-CP1-05 + B-CP3-PRE + B-CP3-PACKAGE)

| file | SHA-256 |
|---|---|
| scripts/build_pptx.py | BACDD462F9633664DA06BE4420FA9ACE9B646FDD98450DF166379AA6BD23979B |
| scripts/file_probe.py | EE9E76E5A0AF57642F7E10F35740BC32D51749E6B3B3DADF251630EC01611DFE |
| scripts/inspect_template.py | 2C7C70752F89EB43A04BDBE7540AEF41A3A9E360BBAE5E9C37E21DC768C82B7B |
| scripts/report.py | 1721E9A3788E8B7D69697731C560364E4E61256107FCB6E9CA650DCE8EF63EE9 |
| scripts/verify_pptx.py | A3EE51FAABC17B4AD159B8F239A1B11DEF3B1A5EC7591D3236CDF03AA4EA5D5C |
| scripts/resolve_core.py | 9FB3E17A5A7D3299F1053D0B3C474F8AE73D27350EC6348B11E103369B527F26 |
| run_matrix.py | 04691D9FC1901BC6795366A14E8E2639433BB191F181760F41BD3FCED1B1F73E |

> Note: `run_matrix.py` changed since the prior pin (added explicit
> `R5_neg_rels_residue` to `done_when_mapping`). `build_pptx.py` changed in
> B-CP1-05 (ledger path caller-supplied). `resolve_core.py` is new (B-CP3-PRE).
> Re-pin after any core change. The `INSTALL_MANIFEST.json` carries per-file
> SHA-256 for the frozen install package.

## Resolution contract (NOT a hardcoded relative path)

Entries do NOT hardcode `../../scripts/`. Each entry ships `resolve_core.py`
which probes (first hit wins): env var `PPTX_GOLDEN_CORE` → sibling
`shared/pptx-shared-core` (mirror install) → `../../scripts/` (staging) →
walk-up repo `pptx-shared-core`.

## B-CP3-PRE parity proof

All 4 entry positions resolve (exit 0) to a core whose `build_pptx.py` shares
one SHA-256. See `output/cp3-pre-evidence-*/cp3_pre_evidence.json`.

## B-CP3-PACKAGE clean-package proof

A 25-file install package extracted from `INSTALL_MANIFEST.json` (no
output/pycache/ledgers/entries/staging debris) is self-sufficient: both entries
resolve, matrix 6/6 PASS, build+verify+BLOCKED all pass from the clean path.
See `output/cp3-package-clean-*/pptx-shared-core/output/clean-package-test/clean_package_evidence.json`.

## Two thin entries (platform-only differences)

- `entries/claude/SKILL.md` + `resolve_core.py` → `.claude/skills/pptx-golden-build/`
- `entries/codex/SKILL.md` + `resolve_core.py` → `.agents/skills/pptx-golden-build/`

Neither contains business logic, core-script copies, brand names, or absolute
machine paths.

## Single-source rule (no double-write)

If the core changes, the baseline above and `INSTALL_MANIFEST.json` must be
re-pinned and both entries still only *point* to the single core.