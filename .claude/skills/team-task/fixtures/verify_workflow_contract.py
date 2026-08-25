#!/usr/bin/env python3
"""Deterministic contract fixtures for the team-task funnel.

This validates the prompt/schema layer, not probabilistic Claude compliance.
It also runs an isolated positive control that must fail before the suite passes.
"""

from __future__ import annotations

import argparse
import re
import shutil
import tempfile
from pathlib import Path


REQUIRED_CALL_KEYS = {
    "caller",
    "mode",
    "run_id",
    "source_block_id",
    "source",
    "output",
    "profile",
    "input_policy",
}


def parse_call(raw: str) -> dict[str, str]:
    pairs: dict[str, str] = {}
    for token in raw.split():
        if "=" not in token:
            raise ValueError("CALL_CONTRACT_ERROR: non-key token")
        key, value = token.split("=", 1)
        if not key or not value or key in pairs:
            raise ValueError("CALL_CONTRACT_ERROR: empty/duplicate")
        pairs[key] = value
    if set(pairs) != REQUIRED_CALL_KEYS:
        raise ValueError("CALL_CONTRACT_ERROR: key set")
    fixed = {
        "caller": "team-task",
        "mode": "contract-only",
        "source": "team-task.md",
        "output": "team-task.md",
        "profile": "auto",
    }
    if any(pairs[k] != v for k, v in fixed.items()):
        raise ValueError("CALL_CONTRACT_ERROR: fixed value")
    if pairs["input_policy"] not in {"initial", "answered", "continue-defaults"}:
        raise ValueError("CALL_CONTRACT_ERROR: input_policy")
    return pairs


def resolve_questionnaire(questions: list[dict[str, str]], policy: str) -> tuple[str, list[str]]:
    defaults: list[str] = []
    for q in questions:
        answer = q.get("answer", "").strip()
        if answer:
            continue
        if policy == "continue-defaults" and q["type"] == "PREFERENCE" and q.get("default"):
            q["answer"] = q["default"]
            defaults.append(q["id"])
            continue
        if q["type"] == "FACT" or q.get("blocking") == "true":
            return "NEED_INPUT", defaults
        if policy != "continue-defaults":
            return "NEED_INPUT", defaults
    return ("DEFAULTED" if defaults else "ANSWERED"), defaults


def route(coordination_score: int, assurance_hits: int) -> tuple[str, str]:
    if not 0 <= coordination_score <= 8:
        raise ValueError("score")
    topology = "T3" if coordination_score <= 2 else "T2" if coordination_score <= 5 else "T1"
    return topology, "ENHANCED" if assurance_hits else "BASE"


def can_resume(progress: tuple[str, str, str], current: tuple[str, str, str]) -> bool:
    return progress == current


def b_allowed(contract_status: str, blockers: int, blocking_facts: int) -> bool:
    return contract_status == "frozen" and blockers == 0 and blocking_facts == 0


def validate_files(team: Path, chop: Path, gate: Path, kickoff: Path) -> list[str]:
    errors: list[str] = []
    texts = {"team": team.read_text(encoding="utf-8"), "chop": chop.read_text(encoding="utf-8"),
             "gate": gate.read_text(encoding="utf-8"), "kickoff": kickoff.read_text(encoding="utf-8")}
    lines = {name: text.count("\n") + 1 for name, text in texts.items()}
    if lines["team"] > 190:
        errors.append(f"team lines {lines['team']} > 190")
    if lines["chop"] > 95:
        errors.append(f"chop lines {lines['chop']} > 95")

    required = {
        "team": [
            "disable-model-invocation: true", "$ARGUMENTS", "P0 · run bootstrap", "run_id/source_block_id/contract_id",
            "continue-defaults", "P5 前不得冒记", "coordination_score", "assurance_profile=BASE|ENHANCED",
            "T4 只表示", "realized_topology", "T2=常驻 coder+mxp", "强制一次性 planner",
            "PENDING_INDEPENDENT_REVIEW", "run_status=COMPLETE|WAIT_HUMAN|HALTED",
        ],
        "chop": [
            "$ARGUMENTS", "八键", "CALL_CONTRACT_ERROR", "input_policy∈{initial,answered,continue-defaults}",
            "NEED_INPUT", "run_id+source_block_id", "REUSED", "FROZEN", "跳过落点 AskUserQuestion",
        ],
        "gate": [
            "OLD_RUN_UNCLOSED", "questionnaire-<run_id>.md", "FACT 必须 `default:null`", "无墙钟 timeout",
            "coordination_score", "不得合成一个总分", "ENHANCED 只增加", "routing_mode=AUTO|MANUAL",
            "T2 没有常驻 planner", "continue-defaults` 不是 B 授权",
        ],
        "kickoff": ["questionnaire-<run_id>.md", "FACT 不默认", "continue-defaults"],
    }
    for name, needles in required.items():
        for needle in needles:
            if needle not in texts[name]:
                errors.append(f"{name}: missing {needle!r}")

    forbidden = ["强制走 team 工作流", "三角色协调小队"]
    for needle in forbidden:
        if needle in texts["team"] or needle in texts["chop"]:
            errors.append(f"stale wording: {needle}")

    call_match = re.search(r"caller=team-task mode=contract-only run_id=<run_id>.*?input_policy=<initial\|answered\|continue-defaults>", texts["team"])
    if not call_match:
        errors.append("team: exact caller invocation missing")
    if texts["gate"].count("routing_mode=AUTO|MANUAL") != 1:
        errors.append("gate: routing record must have one canonical schema")
    return errors


def run_cases() -> list[tuple[str, bool]]:
    good_call = (
        "caller=team-task mode=contract-only run_id=20260825-120000-1234abcd "
        "source_block_id=src-1234abcd source=team-task.md output=team-task.md "
        "profile=auto input_policy=initial"
    )
    cases: list[tuple[str, bool]] = []
    cases.append(("N1 caller good", parse_call(good_call)["caller"] == "team-task"))
    try:
        parse_call(good_call.replace(" output=team-task.md", ""))
        cases.append(("N1 missing key rejects", False))
    except ValueError:
        cases.append(("N1 missing key rejects", True))

    qs = [{"id": "Q01", "type": "PREFERENCE", "blocking": "false", "default": "safe", "answer": ""}]
    status, defaults = resolve_questionnaire(qs, "continue-defaults")
    cases.append(("F1 empty preference defaults", status == "DEFAULTED" and defaults == ["Q01"]))
    fact = [{"id": "Q01", "type": "FACT", "blocking": "true", "default": "", "answer": ""}]
    cases.append(("F1 FACT never defaults", resolve_questionnaire(fact, "continue-defaults")[0] == "NEED_INPUT"))

    cases.append(("F2 lower boundary T3", route(2, 0) == ("T3", "BASE")))
    cases.append(("F2 upper boundary T2", route(3, 0) == ("T2", "BASE")))
    cases.append(("F2 risk does not thicken topology", route(1, 3) == ("T3", "ENHANCED")))

    identity = ("run-1", "src-1", "ctr-1")
    cases.append(("F3 exact identity resumes", can_resume(identity, identity)))
    cases.append(("F3 mismatched run cannot resume", not can_resume(identity, ("run-2", "src-1", "ctr-1"))))

    cases.append(("N2 B rejects unfrozen", not b_allowed("pending", 0, 0)))
    cases.append(("N2 B rejects blockers", not b_allowed("frozen", 1, 0)))
    cases.append(("N3 T2 reviewer contract", True))  # prose token is checked in validate_files

    half = [
        {"id": "Q01", "type": "FACT", "blocking": "true", "default": "", "answer": "given"},
        {"id": "Q02", "type": "PREFERENCE", "blocking": "false", "default": "safe", "answer": ""},
    ]
    cases.append(("N4 half-fill preserves answer/defaults rest", resolve_questionnaire(half, "continue-defaults") == ("DEFAULTED", ["Q02"])))
    return cases


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skill-root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    root = args.skill_root.resolve()
    team, gate = root / "SKILL.md", root / "funnel-gate.md"
    chop_root = root.parent / "chop-task"
    chop, kickoff = chop_root / "SKILL.md", chop_root / "kickoff-gate.md"

    errors = validate_files(team, chop, gate, kickoff)
    cases = run_cases()
    errors.extend(name for name, ok in cases if not ok)

    with tempfile.TemporaryDirectory(prefix="team-task-positive-control-") as td:
        tmp = Path(td)
        for source in (team, chop, gate, kickoff):
            shutil.copy2(source, tmp / source.name.replace("SKILL", source.parent.name + "-SKILL"))
        bad_team = tmp / "team-task-SKILL.md"
        bad_team.write_text(bad_team.read_text(encoding="utf-8").replace("disable-model-invocation: true", ""), encoding="utf-8")
        control_errors = validate_files(bad_team, tmp / "chop-task-SKILL.md", tmp / "funnel-gate.md", tmp / "kickoff-gate.md")
        positive_control_ok = any("disable-model-invocation" in item for item in control_errors)
    cases.append(("positive control sees deliberate failure", positive_control_ok))
    if not positive_control_ok:
        errors.append("positive control did not fail")

    for name, ok in cases:
        print(f"[{'PASS' if ok else 'FAIL'}] {name}")
    if errors:
        for error in errors:
            print(f"[FAIL] {error}")
        print(f"TOTAL: FAIL ({len(errors)} errors)")
        return 1
    print(f"TOTAL: PASS ({len(cases)} contract cases + structural checks)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
