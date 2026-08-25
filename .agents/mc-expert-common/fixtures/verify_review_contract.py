#!/usr/bin/env python3
"""Deterministic structural checks for mc-expert review contract v2.

This verifies routing cases, source-of-truth references and required tokens. It
does not claim to prove probabilistic model compliance.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python < 3.11
    tomllib = None


GLM_RUNTIMES = {"CODEX_GLM", "CLAUDE_GLM"}
NATIVE_RUNTIMES = {"NATIVE_CODEX", "NATIVE_CLAUDE"}


def route(runtime: str, risk: str | None, owner: str | None, profile: str, impact: bool) -> str:
    if not risk:
        return "WAIT_USER_RISK_CLASSIFICATION"
    if owner != "USER":
        return "REVIEW_CONTRACT_INVALID"
    if runtime in GLM_RUNTIMES:
        if risk == "HIGH" or impact:
            return "CUTOVER_NATIVE_REQUIRED"
        return "ADMITTED" if profile == "ENHANCED_FINAL" else "ENHANCED_FINAL_REQUIRED"
    if runtime in NATIVE_RUNTIMES:
        if risk == "HIGH" or impact:
            return "ADMITTED" if profile == "ENHANCED_FINAL" else "ENHANCED_FINAL_REQUIRED"
        return "ADMITTED"
    return "ENHANCED_FINAL_REQUIRED"


def require_tokens(path: Path, tokens: list[str]) -> list[str]:
    text = path.read_text(encoding="utf-8")
    return [token for token in tokens if token not in text]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, required=True)
    args = parser.parse_args()
    root = args.repo_root.resolve()

    contract = root / ".agents/mc-expert-common/review-contract-v2.md"
    claude = root / ".claude/agents/mc-expert.md"
    codex = root / ".codex/agents/mc-expert.toml"
    codex_glm = root / ".codex-glm/agents/mc-expert.toml"
    binding = root / ".agents/skills/_mc-common/codex-runtime-bindings.md"
    team = root / ".claude/skills/team-task/SKILL.md"
    funnel = root / ".claude/skills/team-task/funnel-gate.md"
    callers = [
        root / ".agents/double-session-common/protocol.md",
        root / ".agents/skills/today/SKILL.md",
        root / ".agents/skills/double-planner/SKILL.md",
        root / ".agents/skills/double-coder/SKILL.md",
        root / ".claude/skills/today-core/SKILL.md",
        root / ".claude/skills/today-loop/SKILL.md",
        root / ".claude/skills/free/SKILL.md",
        root / ".claude/skills/double-planner/SKILL.md",
        root / ".claude/skills/double-coder/SKILL.md",
    ]
    files = [contract, claude, codex, codex_glm, binding, team, funnel, *callers]

    failures: list[str] = []
    for path in files:
        if not path.is_file():
            failures.append(f"missing file: {path}")

    if failures:
        for item in failures:
            print(f"FAIL {item}")
        return 1

    contract_tokens = [
        "REVIEW_PROFILE", "AUTHOR_RUNTIME", "RISK_OWNER: USER",
        "CUTOVER_NATIVE_REQUIRED", "HIGH_SUSPECTED", "ARTIFACT_MANIFEST",
        "lifecycle_identity", "idempotency_retry", "executor_matrix",
        "type_cross_product", "fixture_truth", "GO_WITH_CHANGES",
        "HASH_VALIDITY=VALID", "UNVERIFIED_SCOPE=NONE",
    ]
    missing = require_tokens(contract, contract_tokens)
    if missing:
        failures.append(f"contract missing tokens: {missing}")

    ref = "review-contract-v2.md"
    for path in [claude, codex, codex_glm, binding, team, funnel]:
        missing = require_tokens(path, [ref])
        if missing:
            failures.append(f"{path} does not reference shared contract")

    for path in [claude, codex, codex_glm]:
        missing = require_tokens(path, ["HISTORY", "ENHANCED_FINAL", "ENHANCED_FINAL_REQUIRED"])
        if missing:
            failures.append(f"{path} missing profile enforcement: {missing}")

    missing = require_tokens(codex_glm, ["PROVIDER_ROUTE", "glm-5.3 / z-ai/glm-5.2", "CUTOVER_NATIVE_REQUIRED"])
    if missing:
        failures.append(f"codex-glm lost provider/existing-edit/risk tokens: {missing}")

    missing = require_tokens(team, ["P0.5", "risk_owner=USER", "CUTOVER_NATIVE_REQUIRED", "ENHANCED_FINAL"])
    if missing:
        failures.append(f"team-task missing admission/final gate: {missing}")

    missing = require_tokens(funnel, ["risk_class=MEDIUM|HIGH", "runtime_policy=GLM_ALLOWED|NATIVE_ONLY", "HIGH_SUSPECTED"])
    if missing:
        failures.append(f"funnel missing frozen risk schema: {missing}")

    missing = require_tokens(binding, [".codex-glm/agents/mc-expert.toml", ".codex/agents/mc-expert.toml", "CODEX_GLM_PROVIDER_ROUTE"])
    if missing:
        failures.append(f"binding missing route-specific user profile: {missing}")

    for path in callers:
        text = path.read_text(encoding="utf-8")
        if "review-contract-v2.md" not in text:
            failures.append(f"active caller missing v2 shared-contract reference: {path}")
        if "四字段合同" in text or "公共四字段" in text or "规定的四字段" in text:
            failures.append(f"active caller retains stale four-field interface: {path}")

    for path in [
        root / ".agents/double-session-common/protocol.md",
        root / ".agents/skills/double-planner/SKILL.md",
        root / ".claude/skills/double-planner/SKILL.md",
    ]:
        missing = require_tokens(path, ["ENHANCED_FINAL", "WAIT_USER_RISK_CLASSIFICATION"])
        if missing:
            failures.append(f"final-gate caller missing enhanced/risk gate: {path}: {missing}")

    if tomllib is not None:
        for path in [codex, codex_glm]:
            try:
                parsed = tomllib.loads(path.read_text(encoding="utf-8"))
                if parsed.get("name") != "mc-expert" or not parsed.get("developer_instructions"):
                    failures.append(f"invalid custom agent fields: {path}")
            except Exception as exc:  # noqa: BLE001
                failures.append(f"TOML parse failed: {path}: {exc}")

    cases = [
        ("glm-medium-enhanced", ("CODEX_GLM", "MEDIUM", "USER", "ENHANCED_FINAL", False), "ADMITTED"),
        ("glm-medium-history", ("CLAUDE_GLM", "MEDIUM", "USER", "HISTORY", False), "ENHANCED_FINAL_REQUIRED"),
        ("glm-high", ("CODEX_GLM", "HIGH", "USER", "ENHANCED_FINAL", False), "CUTOVER_NATIVE_REQUIRED"),
        ("glm-medium-veto", ("CLAUDE_GLM", "MEDIUM", "USER", "ENHANCED_FINAL", True), "CUTOVER_NATIVE_REQUIRED"),
        ("native-high-enhanced", ("NATIVE_CODEX", "HIGH", "USER", "ENHANCED_FINAL", False), "ADMITTED"),
        ("native-high-history", ("NATIVE_CLAUDE", "HIGH", "USER", "HISTORY", False), "ENHANCED_FINAL_REQUIRED"),
        ("native-medium-history", ("NATIVE_CODEX", "MEDIUM", "USER", "HISTORY", False), "ADMITTED"),
        ("native-medium-impact", ("NATIVE_CODEX", "MEDIUM", "USER", "HISTORY", True), "ENHANCED_FINAL_REQUIRED"),
        ("missing-risk", ("NATIVE_CODEX", None, "USER", "ENHANCED_FINAL", False), "WAIT_USER_RISK_CLASSIFICATION"),
        ("ai-risk-owner", ("NATIVE_CODEX", "MEDIUM", "AI", "ENHANCED_FINAL", False), "REVIEW_CONTRACT_INVALID"),
    ]
    for name, inputs, expected in cases:
        actual = route(*inputs)
        if actual != expected:
            failures.append(f"routing {name}: expected {expected}, got {actual}")
        else:
            print(f"PASS routing {name} -> {actual}")

    # In-memory positive control: deletion of a load-bearing token must fail.
    positive = contract.read_text(encoding="utf-8").replace("HASH_VALIDITY=VALID", "REMOVED")
    if "HASH_VALIDITY=VALID" in positive:
        failures.append("positive control did not remove the load-bearing token")
    else:
        detected = [token for token in contract_tokens if token not in positive]
        if "HASH_VALIDITY=VALID" not in detected:
            failures.append("positive control validator failed to detect removed token")
        else:
            print("PASS positive control detects removed load-bearing token")

    for path in files:
        print(f"SHA256 {path.relative_to(root)} {sha256(path)}")

    if failures:
        for item in failures:
            print(f"FAIL {item}")
        return 1
    print("PASS structural contract checks (not probabilistic model-compliance proof)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
