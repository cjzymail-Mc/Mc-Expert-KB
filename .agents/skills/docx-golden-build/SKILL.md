---
name: docx-golden-build
description: Build and deterministically verify a plaintext DOCX from a golden template using the shared docx-shared-core. Use when the task is golden-reference DOCX production (fill anchors/slots, 3-state highlight contract) with exit-coded acceptance. Refuses encrypted input (88 7D 1C) and OLE/CFB legacy .doc (D0 CF 11 E0). Not for visual rendering, COM, Excel, or PPTX.
---

# docx-golden-build (Codex thin entry)

This is a **platform-thin entry** for Codex. All business logic lives in the
**single shared core** (`docx-shared-core/`). This entry only adapts the
Codex discovery/invoke surface.

## How to locate the shared core (resolution contract)

The core is found by a **multi-position resolver**, NOT by a hardcoded
`../../scripts/` path (that only works in the staging layout and breaks at a
real install position like `.agents/skills/`).

Two equivalent ways, both work in staging AND mirror install:

1. **Resolver helper** (recommended): run `resolve_core.py` shipped next to
   this `SKILL.md`:
   ```
   python resolve_core.py
   ```
   Prints `{"status":"RESOLVED","core_root":"..."}` and exits 0; exit 2 means
   unresolved (fail-loud, never guess).

2. **Env override** (install-time injection): set `DOCX_GOLDEN_CORE=<core-dir>`
   before invoking, so the resolver hits that path first.

The resolver probes (first hit wins): env var `DOCX_GOLDEN_CORE` → sibling
`shared/docx-shared-core` (mirror install) → `../../scripts/` (staging) →
walk-up repo `docx-shared-core` (deep `.agents/skills/` layout).

Do NOT hardcode absolute machine paths, and do NOT copy the core scripts here.
The core is the single source of truth; this entry is a pointer + Codex adapter.

## Codex-specific surface

- **Discovery**: this `SKILL.md` frontmatter makes Codex discover the skill.
  On this machine the real shared skills surface is `.agents/skills/`
  (`CODEX_HOME` is `.codex-glm`; user-scope skills are surfaced via the
  `~/.agents/skills` junction). The install target for this entry is therefore
  `.agents/skills/docx-golden-build/` — NOT `$CODEX_HOME/skills/` or
  `.codex/skills/` (those are stale landing points and must not be used).
  CP3-PACKAGE handles the real migration under user authorization.
- **Invocation**: Codex resolves the core (above), then calls the core scripts
  via its shell tool, e.g.:
  - Probe: `python <core>/scripts/file_probe.py <docx-or-bin>`
  - Inspect: `python <core>/scripts/inspect_template.py <template.docx> --out <dir>`
  - Build: `python <core>/scripts/build_docx.py --template t.docx --slot-map s.json --out o.docx [--pending-human-ledger <path>]`
  - Verify: `python <core>/scripts/verify_docx.py --output o.docx --contract c.json [--source t.docx]`
  - Matrix: `python <core>/run_matrix.py --out-dir <fresh-unique-dir>`
  - Quick validate: `python <core>/quick_validate.py --entry <this-entry-dir> --out-dir <fresh>`
- **Exit-code contract** (the only thing the upper layer reads): PASS=0 / FAIL=1 / BLOCKED=2.

## 3-state highlight contract (Word-specific)

The DOCX core mirrors the Word 3-state coloring contract as a STRUCTURAL OOXML
attribute (not rendering):
- RED (WD_COLOR_INDEX=6): must-replace cell. Builder writes the value AND re-applies
  red so the cell stays red for audit.
- YELLOW (WD_COLOR_INDEX=7): manual marker. Skip; verifier catches a miswrite as FAIL.
- none: do not touch. Verifier catches a miswrite as FAIL.

cell = red iff ALL runs in the cell are red (avoids mixed-run ambiguity).

## What this entry must NOT contain

- No business logic (no DOCX parsing, no verification rules).
- No copy of the core scripts (`resolve_core.py` is a thin resolver, not core logic).
- No brand names, project paths, or machine-specific absolute paths.
- No COM / visual rendering / Excel / PPTX.

## Shared-core hash parity

The core scripts' SHA-256 baseline is pinned in `HASH_PARITY.md` (inside the
shared core). This entry points to them; it must not diverge.
Verify parity with: `Get-FileHash <core>/scripts/*.py -Algorithm SHA256`.

## CP3 note (user-scope migration, NOT yet authorized)

Moving this entry into `.agents/skills/docx-golden-build/` and writing the shared
core into the authorized external master skills directory requires explicit user
write authorization. Until then, this entry stays in-repo as a non-user-scope
staging copy. The `staging-install/` mirror layout proves both install positions
resolve the same canonical core.
