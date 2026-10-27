---
name: simplify-state
description: Simplify and compact a repository root STATE.md into a minimal, evidence-backed cross-session snapshot while preserving resumable routes, dynamic boundaries, and history. Use when the user invokes $simplify-state or asks to 精简、清理、压缩、瘦身 the repo root STATE.md. Do not use for state.json, runtime state, plan progress files, or arbitrary Markdown.
---

# Simplify STATE

Turn the current repository's root `STATE.md` into a small, trustworthy recovery anchor. Preserve truth and recoverability; do not optimize for line count at their expense.

## Scope

- Resolve only `<repo>/STATE.md`. Do not edit same-named files in subdirectories.
- If the root file is missing, report that fact; do not create one unless the user asks.
- Follow the repository's startup instructions and placement rules before acting.
- Treat plans, result reports, closure documents, and frozen run artifacts as evidence sources, not rewrite targets.

## Workflow

### 1. Audit before editing

1. Record the file's byte size, line count, headings, and Git status.
2. Read the complete `STATE.md`.
3. Follow its live links only as needed to verify:
   - whether work is active, paused, or closed;
   - the unique recovery entry;
   - the next authorized action;
   - facts that must not be overstated.
4. Detect conflicting or stale pointers. Resolve them from authoritative source documents, never from memory or likelihood.
   - Distinguish a plan's normative phase definitions and old progress notes from current execution status.
   - When a plan marker conflicts with `STATE.md`, search the plan's named report/output artifacts for first-hand completion evidence before stopping.
   - Do not let a file timestamp or a later sentence alone override stronger run evidence. If the conflict remains unresolved, stop and ask.
5. Classify each passage:
   - **keep**: current default, resumable route, next action, non-claim boundary, restart trigger;
   - **archive**: chronology, completed milestones, evidence detail, hashes, implementation narrative;
   - **drop as duplicate**: rules already guaranteed by startup instructions, repeated next steps, repeated status summaries.

If the user explicitly requests parallel agents and the tool surface permits it, use at most three cheap read-only agents for independent redundancy, fact, and cold-start audits. Do not add reviewers by default.

### 2. Preserve the pre-edit state

1. Treat root `STATE.md` as an important state/config file.
2. Before rewriting it, create a unique sibling backup such as `STATE.md.bak-pre-simplify-YYYYMMDD-HHMMSS`.
3. Verify the source and backup SHA-256 hashes match.
4. If unique historical material will leave the live file, preserve it first:
   - prefer an existing history target already named by the repo;
   - otherwise use a destination allowed by the repo's placement rules;
   - never invent a new top-level folder or overwrite an existing archive;
   - if no safe archive location exists, keep the material or ask for a location.
5. Preserve pre-existing user edits in the backup and archive; never reconstruct the old state from Git alone.

### 3. Rewrite as a current snapshot

Target roughly 15–25 lines by default. Exceed that only when additional lines are required for safe recovery.

Use this minimal shape:

```markdown
# STATE.md — <repo> Current State

> Cross-session current snapshot; history: `<path>`.
> Updated: <date>

## Default

<Whether anything advances automatically.>

## Resumable routes

- **<route>** — <current state>; <next action>; <non-claim boundary>. Entry: `<path>`

## Recovery boundaries

- <Only dynamic, task-specific boundaries not already guaranteed by startup rules.>
```

Apply these rules:

- Keep only routes that a fresh session could reasonably resume now.
- Give each route one bullet containing status, next action, non-claim boundary, and one entry path.
- Keep closed work only when its restart trigger is still operationally important; compress it to one boundary line.
- Remove recent-change timelines, completed-plan inventories, evidence dumps, hashes, fixture details, and long implementation summaries.
- Remove backlog and pending proposals unless the user has selected them as current work.
- Do not duplicate static repository rules already loaded before `STATE.md`.
- Do not turn several independent routes into an implied sequence or default plan.

### 4. Validate

Before reporting completion:

1. Re-read the resulting file from start to finish.
2. Verify every retained path exists.
3. Search for stale phase numbers, conflicting next steps, and claims stronger than their evidence.
4. Confirm removed historical material remains recoverable from the archive or exact backup.
5. Run `git diff --check` on the touched Markdown files.
6. Confirm no files changed outside `STATE.md`, its new backup, and the approved history target.
7. Report:
   - before/after lines and bytes;
   - corrected stale or ambiguous status;
   - backup and history paths;
   - validation result.

Do not commit or push unless the user separately asks.

## Stop conditions

- Stop and ask when authoritative sources conflict on a fact that changes the recovery route.
- Stop rather than deleting history when no safe archive destination exists.
- Stop after two failed edit or validation attempts.
- Never delete or rewrite runtime state, frozen runs, plans, reports, or evidence while simplifying `STATE.md`.
