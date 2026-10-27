# feature-07 source cluster — maintenance boundary (read-only)

> Written 2026-08-05 during feature-08 CP0/CP1. Records the read-only
> maintenance boundary between the feature-07 source cluster and the
> feature-08 shared core, so future sessions don't accidentally edit the
> wrong side.

## Source cluster (READ-ONLY)

Location: `[feature-07-codex-workshop-Adv]/tools/build-pptx-from-template/`

This is the **debranded source** from which the feature-08 `pptx-shared-core`
scripts were lifted. It is a verified tool cluster with its own fixture matrix
(`output/build-pptx-from-template/c2/`).

**Rule: this cluster is read-only for feature-08 work.** The feature-08 core is
the new single source of truth; feature-07 stays frozen as lineage evidence.

## What was lifted (feature-07 → feature-08)

| feature-07 source | feature-08 core | changes |
|---|---|---|
| `scripts/build_pptx.py` | `pptx-shared-core/scripts/build_pptx.py` | debranded; B-CP1-05: ledger path now caller-supplied (`--pending-human-ledger`) |
| `scripts/file_probe.py` | `pptx-shared-core/scripts/file_probe.py` | debranded; unchanged logic |
| `scripts/inspect_template.py` | `pptx-shared-core/scripts/inspect_template.py` | debranded; unchanged logic |
| `scripts/verify_pptx.py` | `pptx-shared-core/scripts/verify_pptx.py` | debranded; unchanged logic |
| `scripts/report.py` | `pptx-shared-core/scripts/report.py` | debranded; unchanged logic |
| c2 fixture matrix | `pptx-shared-core/fixtures/` + `contracts/` | rebuilt project-neutral; false-PASS bug fixed |

## What was NOT lifted

- feature-07 brand names, project-private paths, machine-specific paths — all removed
- the latent false-PASS in the c2 matrix (R2 neg-semantic used a builder slot-map
  as verifier contract) — fixed in feature-08 via `neg_semantic_contract.json`
  asserting `required_anchors:["Hello World"]`

## Boundary rule

If a bug is found in the feature-08 core, fix it **in the feature-08 core**.
Do not backport to feature-07 (it is frozen lineage). If the same bug exists in
feature-07, note it here but do not edit feature-07 without an explicit user
request to maintain that cluster.

## Hash divergence (expected)

The feature-08 core scripts have diverged from feature-07 due to debranding +
B-CP1-05. This is intentional and correct. The feature-07 hashes are NOT a
parity target for feature-08.
