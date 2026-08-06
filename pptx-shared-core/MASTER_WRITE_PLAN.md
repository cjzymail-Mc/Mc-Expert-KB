# MASTER_WRITE_PLAN.md — Mc-Expert-repo write plan (B-CP3-PACKAGE)

> Generated 2026-08-05. This is a **plan only** — no master writes have occurred.
> User has NOT authorized master writes this run. This document exists so the
> planner/user can review the exact pre-write state, write actions, and rollback
> before any authorization.

## Pre-write master state (read-only scan, 2026-08-05)

| target dir | state |
|---|---|
| `Mc-Expert-repo/.claude/skills/pptx-golden-build/` | **NEW** (does not exist) |
| `Mc-Expert-repo/.agents/skills/pptx-golden-build/` | **NEW** (does not exist) |
| `Mc-Expert-repo/pptx-shared-core/` | **NEW** (does not exist) |

No existing `pptx-golden-build` or `pptx-shared-core` found anywhere in master.
All three targets are clean creates — zero overwrite risk.

## Write plan (25 files, all CREATE — no overwrite)

Source: `INSTALL_MANIFEST.json` (frozen, SHA-256 per file).

| target | action | source |
|---|---|---|
| `.claude/skills/pptx-golden-build/SKILL.md` | CREATE | `entries/claude/SKILL.md` |
| `.claude/skills/pptx-golden-build/resolve_core.py` | CREATE | `entries/claude/resolve_core.py` |
| `.agents/skills/pptx-golden-build/SKILL.md` | CREATE | `entries/codex/SKILL.md` |
| `.agents/skills/pptx-golden-build/resolve_core.py` | CREATE | `entries/codex/resolve_core.py` |
| `pptx-shared-core/scripts/*.py` (6 files) | CREATE | `scripts/*.py` |
| `pptx-shared-core/run_matrix.py` | CREATE | `run_matrix.py` |
| `pptx-shared-core/quick_validate.py` | CREATE | `quick_validate.py` |
| `pptx-shared-core/contracts/*.json` (4 files) | CREATE | `contracts/*.json` |
| `pptx-shared-core/fixtures/*` (6 files) | CREATE | `fixtures/*` |
| `pptx-shared-core/*.md` (4 docs) | CREATE | `README/HASH_PARITY/FEATURE07-BOUNDARY/INSTALL_MANIFEST` |

**Excluded** (never written): `output/`, `__pycache__/`, `pending_human_blocked*.json`,
`staging-install/`, `entries/` (entries are distributed to skill dirs, not copied as-is),
`tmp_planner_*`, `patch_*`.

## Conflict handling

Since all targets are NEW, there are no conflicts. If a future re-install hits an
existing target, the rule is: **skip if SHA-256 matches, abort if SHA differs**
(fail-loud, never silent overwrite).

## Rollback plan

If the master write needs to be undone:
1. Delete the 3 created directories (they did not exist before):
   - `Mc-Expert-repo/.claude/skills/pptx-golden-build/`
   - `Mc-Expert-repo/.agents/skills/pptx-golden-build/`
   - `Mc-Expert-repo/pptx-shared-core/`
2. Since these are all NEW creates, deletion fully restores pre-write state.
   No file-level restore needed (nothing was overwritten).

**Rollback safety**: because all targets are NEW creates with no prior content,
rollback is a clean directory removal. The staging core in feature-08 remains
untouched as the recovery source.

## Post-write verification plan (for when user authorizes CP3 real write)

1. Re-scan the 3 target dirs; confirm 25 files match manifest SHA-256.
2. Run `resolve_core.py` from both entry positions in the real master paths.
3. Run `run_matrix.py` from the real master shared core → expect 6/6 PASS.
4. Run real fresh-session discovery (new Claude/Codex session discovers the skill
   from the platform surface) — this is the true CP3 discovery test, deferred
   from the mirror-resolution smoke.

## Authorization status

- **NOT authorized** this run (user declined master writes).
- This plan is a pre-write artifact for review.
- B-CP3-PACKAGE (install package freeze gate) PASS unblocks the authorization
  decision; it does not grant it.