---
name: pptx-golden-build
description: Build and deterministically verify a plaintext PPTX from a golden template using the shared pptx-shared-core. Use when the task is golden-reference PPTX production (fill anchors/slots/images) with exit-coded acceptance. Refuses encrypted input (88 7D 1C). Not for visual rendering, COM, Excel, or Word.
---

# pptx-golden-build (Claude thin entry)

This is a **platform-thin entry** for Claude. All business logic lives in the
**single shared core** (`pptx-shared-core/`). This entry only adapts the
Claude discovery/invoke surface.

## How to locate the shared core (resolution contract)

The core is found by a **multi-position resolver**, NOT by a hardcoded
`../../scripts/` path (that only works in the staging layout and breaks at a
real install position like `.claude/skills/`).

Two equivalent ways, both work in staging AND mirror install:

1. **Resolver helper** (recommended): run `resolve_core.py` shipped next to
   this `SKILL.md`:
   ```
   python resolve_core.py
   ```
   Prints `{"status":"RESOLVED","core_root":"..."}` and exits 0; exit 2 means
   unresolved (fail-loud, never guess).

2. **Env override** (install-time injection): set `PPTX_GOLDEN_CORE=<core-dir>`
   before invoking, so the resolver hits that path first.

The resolver probes (first hit wins): env var `PPTX_GOLDEN_CORE` → sibling
`shared/pptx-shared-core` (mirror install) → `../../scripts/` (staging) →
walk-up repo `pptx-shared-core` (deep `.agents/skills/` layout).

Do NOT hardcode absolute machine paths, and do NOT copy the core scripts here.
The core is the single source of truth; this entry is a pointer + Claude adapter.

## Claude-specific surface

- **Discovery**: this `SKILL.md` frontmatter makes Claude discover the skill.
  The install target for this entry is `.claude/skills/pptx-golden-build/`.
  CP3-PACKAGE handles the real migration under user authorization.
- **Invocation**: Claude resolves the core (above), then calls the core scripts
  via its shell tool, e.g.:
  - Probe: `python <core>/scripts/file_probe.py <pptx-or-bin>`
  - Build: `python <core>/scripts/build_pptx.py --template t.pptx --slot-map s.json --out o.pptx [--pending-human-ledger <path>]`
  - Verify: `python <core>/scripts/verify_pptx.py --output o.pptx --contract c.json [--source t.pptx]`
  - Matrix: `python <core>/run_matrix.py --out-dir <fresh-unique-dir>`
- **Exit-code contract** (the only thing the upper layer reads): PASS=0 / FAIL=1 / BLOCKED=2.

## What this entry must NOT contain

- No business logic (no PPTX parsing, no verification rules).
- No copy of the core scripts (`resolve_core.py` is a thin resolver, not core logic).
- No brand names, project paths, or machine-specific absolute paths.
- No COM / visual rendering / Excel / Word.

## Shared-core hash parity

The core scripts' SHA-256 baseline is pinned in `HASH_PARITY.md` (inside the
shared core). This entry points to them; it must not diverge.
Verify parity with: `Get-FileHash <core>/scripts/*.py -Algorithm SHA256`.