# team-task workflow contract fixtures

Run from any directory:

```powershell
python verify_workflow_contract.py --skill-root "<path-to-team-task>"
```

The suite validates the deterministic contract layer: line budgets, caller key set, P0 identity/re-entry, questionnaire default boundaries, two-axis routing, B preconditions, T2 reviewer requirement, stale wording, and an isolated positive control that must observe a deliberate failure. It does **not** claim that a probabilistic Claude runtime followed the prose; T1-T4 live routing still needs a cold-session transcript.
