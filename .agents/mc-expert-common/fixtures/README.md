# mc-expert v2 fixtures

Run from the repository root:

```powershell
python .agents\mc-expert-common\fixtures\verify_review_contract.py --repo-root .
```

The verifier checks the shared-source references, both Codex TOML profiles, the Claude profile, active today/free/double/team-task caller bindings, team-task admission/final gates, ten routing cases, and an in-memory positive control. It is a deterministic structural/contract test; it does **not** prove that a probabilistic reviewer will obey the prompt in every run.
