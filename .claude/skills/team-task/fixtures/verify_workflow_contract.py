#!/usr/bin/env python3
"""Deterministic contract fixtures for the team-task funnel.

This validates the prompt/schema layer, not probabilistic Claude compliance.
It also runs an isolated positive control that must fail before the suite passes.
"""

from __future__ import annotations

import argparse
import hashlib
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

ATTR_RE = re.compile(r'(\w+)="([^"]*)"')
BASE_BLOCK_RE = re.compile(
    r'<!-- team-task-contract (?P<attrs>[^>]*) -->\r?\n(?P<body>.*?)\r?\n<!-- /team-task-contract -->',
    re.DOTALL,
)
ADDENDUM_BLOCK_RE = re.compile(
    r'<!-- team-task-contract-addendum (?P<attrs>[^>]*) -->\r?\n(?P<body>.*?)\r?\n<!-- /team-task-contract-addendum -->',
    re.DOTALL,
)


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


def risk_registration(author_runtime: str, explicit: str | None = None) -> tuple[str, str, str]:
    runtimes = {"NATIVE_CODEX", "CODEX_GLM", "NATIVE_CLAUDE", "CLAUDE_GLM", "OTHER"}
    if author_runtime not in runtimes:
        raise ValueError("runtime")
    if explicit not in {None, "MEDIUM", "HIGH"}:
        raise ValueError("risk")
    if explicit:
        risk, source = explicit, "USER_EXPLICIT"
    elif author_runtime in {"CODEX_GLM", "CLAUDE_GLM"}:
        risk, source = "MEDIUM", "USER_STANDING_POLICY_20260904"
    else:
        raise ValueError("WAIT_USER_RISK_CLASSIFICATION")
    if risk == "HIGH" and author_runtime in {"CODEX_GLM", "CLAUDE_GLM", "OTHER"}:
        raise ValueError("CUTOVER_NATIVE_REQUIRED")
    policy = "NATIVE_ONLY" if risk == "HIGH" else "GLM_ALLOWED"
    return risk, source, policy


def controlled_repo_write_escalates(
    *, in_frozen_scope: bool, backup_verified: bool, trace_present: bool,
    oracle_present: bool, applicable_gate_passed: bool, external_or_privileged: bool
) -> bool:
    return external_or_privileged or not all((
        in_frozen_scope, backup_verified, trace_present, oracle_present, applicable_gate_passed
    ))


def failure_disposition(
    failure_count: int, *, immediate_redline: bool,
    mxp_available: bool = True, mxp_option_present: bool = True
) -> str:
    if failure_count < 1:
        raise ValueError("failure_count")
    if immediate_redline:
        return "HALT_IMMEDIATE"
    if failure_count >= 3:
        return "HALT_THREE_FAILURES"
    if not mxp_available or not mxp_option_present:
        return "WAIT_HUMAN"
    return "MXP_RETRY_PRIMARY" if failure_count == 1 else "MXP_RETRY_SECONDARY"


def normalize_block_body(body: str) -> str:
    lines = body.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    return "\n".join(lines)


def block_id(prefix: str, body: str) -> str:
    digest = hashlib.sha256(normalize_block_body(body).encode("utf-8")).hexdigest()[:8]
    return f"{prefix}-{digest}"


def is_placeholder(value: str) -> bool:
    normalized = value.strip().strip('"“”「」').strip()
    folded = normalized.casefold()
    return (
        not normalized
        or (normalized.startswith("<") and normalized.endswith(">"))
        or folded in {"待填", "待补", "占位", "placeholder", "tbd", "todo", "n/a"}
        or bool(re.fullmatch(r"[.。·…]+", normalized))
    )


def parse_attrs(raw: str) -> dict[str, str]:
    pairs = ATTR_RE.findall(raw)
    attrs = dict(pairs)
    if len(attrs) != len(pairs):
        raise ValueError("duplicate attribute")
    if ATTR_RE.sub("", raw).strip():
        raise ValueError("unexpected/unquoted attribute")
    return attrs


def validate_contract_document(
    text: str, run_id: str | None = None, source_block_id: str | None = None
) -> tuple[list[str], dict[tuple[str, str], tuple[str, str]]]:
    """Validate immutable base contracts and their ordered append-only addendum chains."""
    errors: list[str] = []
    bases: list[tuple[int, dict[str, str], str]] = []
    addenda: list[tuple[int, dict[str, str], str]] = []

    base_matches = list(BASE_BLOCK_RE.finditer(text))
    addendum_matches = list(ADDENDUM_BLOCK_RE.finditer(text))
    if (text.count("<!-- team-task-contract ") != len(base_matches)
            or text.count("<!-- /team-task-contract -->") != len(base_matches)):
        errors.append("contract: malformed/unclosed base marker")
    if (text.count("<!-- team-task-contract-addendum ") != len(addendum_matches)
            or text.count("<!-- /team-task-contract-addendum -->") != len(addendum_matches)):
        errors.append("contract: malformed/unclosed addendum marker")

    for match in base_matches:
        try:
            attrs = parse_attrs(match.group("attrs"))
        except ValueError as exc:
            errors.append(f"contract: base {exc}")
            continue
        if not attrs.get("run_id") or not attrs.get("source_block_id"):
            errors.append("contract: base missing/blank run/source identity")
        bases.append((match.start(), attrs, match.group("body")))
    for match in addendum_matches:
        try:
            attrs = parse_attrs(match.group("attrs"))
        except ValueError as exc:
            errors.append(f"contract: addendum {exc}")
            continue
        if not attrs.get("run_id") or not attrs.get("source_block_id"):
            errors.append("contract: addendum missing/blank run/source identity")
        addenda.append((match.start(), attrs, match.group("body")))

    # Validate every parsed chain before selecting the requested identity. Otherwise
    # a damaged/orphan addendum can disappear behind the run/source filter and make
    # a P3/COMPLETE CLI check falsely pass.
    groups: dict[tuple[str, str], dict[str, list[tuple[int, dict[str, str], str]]]] = {}
    for kind, items in (("bases", bases), ("addenda", addenda)):
        for item in items:
            attrs = item[1]
            key = (attrs.get("run_id", ""), attrs.get("source_block_id", ""))
            groups.setdefault(key, {"bases": [], "addenda": []})[kind].append(item)

    contracts: dict[tuple[str, str], tuple[str, str]] = {}
    for key, grouped in groups.items():
        if not all(key):
            errors.append(f"contract: missing run/source identity {key}")
            continue
        if len(grouped["bases"]) != 1:
            errors.append(f"contract: expected exactly one base for {key}, got {len(grouped['bases'])}")
            continue
        base_position, base_attrs, base_body = grouped["bases"][0]
        required_base = {"run_id", "source_block_id", "contract_id", "status", "profile"}
        if not required_base.issubset(base_attrs):
            errors.append(f"contract: base attributes missing for {key}")
            continue
        if base_attrs["status"] != "frozen":
            errors.append(f"contract: base not frozen for {key}")
        expected_base = block_id("ctr", base_body)
        if base_attrs["contract_id"] != expected_base:
            errors.append(f"contract: base hash mismatch for {key}")
        current = base_attrs["contract_id"]
        seen = {current}
        for position, attrs, body in sorted(grouped["addenda"], key=lambda item: item[0]):
            required_add = {
                "run_id", "source_block_id", "parent_effective_id", "addendum_id", "status"
            }
            if not required_add.issubset(attrs):
                errors.append(f"contract: addendum attributes missing for {key}")
                continue
            if position < base_position:
                errors.append(f"contract: addendum precedes base for {key}")
            add_fields: dict[str, str] = {}
            for label in ("授权指令原文", "授权时间/会话", "被取代条款", "生效新条款"):
                field = re.search(rf"(?m)^-\s*{label}[：:]\s*(.*)$", body)
                value = field.group(1).strip() if field else ""
                add_fields[label] = value
                if is_placeholder(value):
                    errors.append(f"contract: addendum missing/blank {label} for {key}")
                elif label == "授权时间/会话":
                    has_date = bool(re.search(r"\d{4}-\d{2}-\d{2}", value))
                    session_match = re.search(r"(?:session|会话)\s*=\s*(\S+)", value, re.IGNORECASE)
                    has_session = bool(session_match and not is_placeholder(session_match.group(1)))
                    if not has_date and not has_session:
                        errors.append(f"contract: addendum authorization context lacks time/session evidence for {key}")
            instruction = add_fields.get("授权指令原文", "")
            quote_pairs = (("\"", "\""), ("“", "”"), ("「", "」"))
            quoted = next((
                instruction[len(left):-len(right)].strip()
                for left, right in quote_pairs
                if instruction.startswith(left) and instruction.endswith(right)
            ), "")
            if (is_placeholder(quoted)
                    or re.fullmatch(r"\d{4}-\d{2}-\d{2}(?:[T ].*)?", quoted)
                    or re.fullmatch(r"(?:session|会话)\s*=.*", quoted, re.IGNORECASE)):
                errors.append(f"contract: addendum authorization instruction lacks quoted user text for {key}")
            addendum_id = attrs["addendum_id"]
            if attrs["status"] != "frozen":
                errors.append(f"contract: addendum not frozen for {key}")
            if addendum_id != block_id("add", body):
                errors.append(f"contract: addendum hash mismatch for {key}")
            if addendum_id in seen:
                errors.append(f"contract: duplicate effective id {addendum_id} for {key}")
            if attrs["parent_effective_id"] != current:
                errors.append(f"contract: addendum parent mismatch for {key}")
            seen.add(addendum_id)
            current = addendum_id
        contracts[key] = (base_attrs["contract_id"], current)
    if run_id or source_block_id:
        requested = [
            key for key in contracts
            if (not run_id or key[0] == run_id)
            and (not source_block_id or key[1] == source_block_id)
        ]
        if not requested:
            errors.append("contract: requested identity not found")
    return errors, contracts


def validate_progress_effective(
    text: str, run_id: str, source_block_id: str,
    expected_contract_id: str, expected_effective_id: str
) -> list[str]:
    pairs = re.findall(r"^>[ \t]*([A-Za-z_]+)([ \t]*[:：])[ \t]*([^\r\n]*)$", text, re.MULTILINE)
    errors: list[str] = []
    expected = {
        "run_id": run_id,
        "source_block_id": source_block_id,
        "contract_id": expected_contract_id,
        "effective_contract_id": expected_effective_id,
    }
    for key, value in expected.items():
        matches = [
            (item_key, separator, item_value.strip())
            for item_key, separator, item_value in pairs
            if item_key.casefold() == key
        ]
        values = [item[2] for item in matches]
        if len(values) != 1:
            errors.append(f"progress: {key} expected exactly once, got {len(values)}")
        elif matches[0][0] != key or matches[0][1] != ":":
            errors.append(f"progress: {key} uses noncanonical field syntax")
        elif values[0] != value:
            errors.append(f"progress: {key} expected {value!r}, got {values[0]!r}")
    return errors


def validate_files(
    team: Path, chop: Path, gate: Path, kickoff: Path, free: Path, review: Path
) -> list[str]:
    errors: list[str] = []
    texts = {"team": team.read_text(encoding="utf-8"), "chop": chop.read_text(encoding="utf-8"),
             "gate": gate.read_text(encoding="utf-8"), "kickoff": kickoff.read_text(encoding="utf-8"),
             "free": free.read_text(encoding="utf-8"), "review": review.read_text(encoding="utf-8")}
    lines = {name: text.count("\n") + 1 for name, text in texts.items()}
    if lines["team"] > 190:
        errors.append(f"team lines {lines['team']} > 190")
    if lines["chop"] > 95:
        errors.append(f"chop lines {lines['chop']} > 95")

    required = {
        "team": [
            "disable-model-invocation: true", "$ARGUMENTS", "P0 · run bootstrap", "run_id/source_block_id/contract_id",
            "continue-defaults", "P5 前不得冒记", "coordination_score", "assurance_profile=BASE|ENHANCED",
            "默认 `routing_mode=AUTO`", "realized_topology", "T2=常驻 coder+mxp", "强制一次性 planner",
            "PENDING_INDEPENDENT_REVIEW", "WAIT_HUMAN|HALTED + P6·", "effective_contract_id",
            "USER_STANDING_POLICY_20260904", "P5 · 登记门", "RESUME_AUTHORIZED", "COMPLETE+P6·",
            "run_status=COMPLETE + P6✓", "逐段写入 `## 收尾复盘`", "默认 B 下非阻断 PREFERENCE",
            "CONTRACT_CHANGE_RESUME_ORDER=WAIT_HUMAN→ADDENDUM_VALIDATED→RESUME_AUTHORIZED→ACTIVE",
            "FIRST_FAILURE_MXP_REVIEW", "failure_count=1", "failure_count=2", "failure_count=3",
        ],
        "chop": [
            "$ARGUMENTS", "八键", "CALL_CONTRACT_ERROR", "input_policy∈{initial,answered,continue-defaults}",
            "NEED_INPUT", "run_id+source_block_id", "REUSED", "FROZEN", "跳过落点 AskUserQuestion",
            "`contract-only` 下不询问 A/B、team/solo 或队形",
        ],
        "gate": [
            "OLD_RUN_UNCLOSED", "questionnaire-<run_id>.md", "FACT 必须 `default:null`", "无墙钟 timeout",
            "coordination_score", "不得合成一个总分", "ENHANCED 只增加", "routing_mode=AUTO|MANUAL",
            "T2 没有常驻 planner", "continue-defaults` 不是 B 授权", "team-task-contract-addendum",
            "effective_contract_id", "P0✓ P0.5·", "RESUME_AUTHORIZED", "COMPLETE + P6·",
            "run_status=COMPLETE + P6✓", "逐段落 `## 收尾复盘`",
            "CONTRACT_CHANGE_RESUME_ORDER=WAIT_HUMAN→ADDENDUM_VALIDATED→RESUME_AUTHORIZED→ACTIVE",
            "授权指令原文", "授权时间/会话",
            "FIRST_FAILURE_MXP_REVIEW", "failure_count=1", "failure_count=2", "failure_count=3",
        ],
        "kickoff": ["questionnaire-<run_id>.md", "FACT 不默认", "continue-defaults"],
        "free": [
            "RESUME_AUTHORIZED", "run_status=WAIT_HUMAN", "改回 `ACTIVE`",
            "effective_contract_id", "本 `/free` 收尾 loop 不重复触发",
            "CONTRACT_CHANGE_RESUME_ORDER=WAIT_HUMAN→ADDENDUM_VALIDATED→RESUME_AUTHORIZED→ACTIVE",
        ],
        "review": [
            "USER_STANDING_POLICY_20260904", "受控可回滚例外（保持 MEDIUM）",
            "不得仅因“真实数据写入”四字升标", "超出入口授权", "NATIVE_*|OTHER", "`OTHER` | `HIGH`",
        ],
    }
    for name, needles in required.items():
        for needle in needles:
            if needle not in texts[name]:
                errors.append(f"{name}: missing {needle!r}")

    forbidden = ["强制走 team 工作流", "三角色协调小队", "并确认实际拓扑与 A/B"]
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

    cases.append(("N2 GLM default risk uses standing MEDIUM", risk_registration("CLAUDE_GLM") == (
        "MEDIUM", "USER_STANDING_POLICY_20260904", "GLM_ALLOWED"
    )))
    try:
        risk_registration("CLAUDE_GLM", "HIGH")
        cases.append(("N2 CLAUDE_GLM HIGH cuts over", False))
    except ValueError as exc:
        cases.append(("N2 CLAUDE_GLM HIGH cuts over", str(exc) == "CUTOVER_NATIVE_REQUIRED"))
    for runtime in ("CODEX_GLM", "CLAUDE_GLM"):
        cases.append((f"N2 {runtime} implicit MEDIUM valid", risk_registration(runtime) == (
            "MEDIUM", "USER_STANDING_POLICY_20260904", "GLM_ALLOWED"
        )))
    for runtime in ("NATIVE_CODEX", "NATIVE_CLAUDE", "OTHER"):
        try:
            risk_registration(runtime)
            cases.append((f"N2 {runtime} missing risk waits", False))
        except ValueError as exc:
            cases.append((f"N2 {runtime} missing risk waits", str(exc) == "WAIT_USER_RISK_CLASSIFICATION"))
    for runtime in ("NATIVE_CODEX", "NATIVE_CLAUDE"):
        for explicit, expected_policy in (("MEDIUM", "GLM_ALLOWED"), ("HIGH", "NATIVE_ONLY")):
            cases.append((f"N2 {runtime} explicit {explicit} valid", risk_registration(runtime, explicit) == (
                explicit, "USER_EXPLICIT", expected_policy
            )))
    cases.append(("N2 OTHER explicit MEDIUM valid", risk_registration("OTHER", "MEDIUM") == (
        "MEDIUM", "USER_EXPLICIT", "GLM_ALLOWED"
    )))
    try:
        risk_registration("OTHER", "HIGH")
        cases.append(("N2 OTHER explicit HIGH cuts over", False))
    except ValueError as exc:
        cases.append(("N2 OTHER explicit HIGH cuts over", str(exc) == "CUTOVER_NATIVE_REQUIRED"))
    for runtime in ("CODEX_GLM", "CLAUDE_GLM"):
        cases.append((f"N2 {runtime} explicit MEDIUM valid", risk_registration(runtime, "MEDIUM") == (
            "MEDIUM", "USER_EXPLICIT", "GLM_ALLOWED"
        )))
        try:
            risk_registration(runtime, "HIGH")
            cases.append((f"N2 {runtime} explicit HIGH cuts over", False))
        except ValueError as exc:
            cases.append((f"N2 {runtime} explicit HIGH cuts over", str(exc) == "CUTOVER_NATIVE_REQUIRED"))
    controlled = dict(
        in_frozen_scope=True, backup_verified=True, trace_present=True,
        oracle_present=True, applicable_gate_passed=True, external_or_privileged=False,
    )
    cases.append(("N2 controlled repo write stays MEDIUM", not controlled_repo_write_escalates(**controlled)))
    cases.append(("N2 missing backup escalates", controlled_repo_write_escalates(
        **{**controlled, "backup_verified": False}
    )))
    cases.append(("N2 outside scope escalates", controlled_repo_write_escalates(
        **{**controlled, "in_frozen_scope": False}
    )))
    cases.append(("N2 external/privileged write escalates", controlled_repo_write_escalates(
        **{**controlled, "external_or_privileged": True}
    )))
    cases.append(("N2 first non-redline failure gets mxp primary retry", failure_disposition(
        1, immediate_redline=False
    ) == "MXP_RETRY_PRIMARY"))
    cases.append(("N2 second non-redline failure gets mxp secondary retry", failure_disposition(
        2, immediate_redline=False
    ) == "MXP_RETRY_SECONDARY"))
    cases.append(("N2 third same-key failure halts", failure_disposition(
        3, immediate_redline=False
    ) == "HALT_THREE_FAILURES"))
    cases.append(("N2 immediate redline bypasses mxp", failure_disposition(
        1, immediate_redline=True
    ) == "HALT_IMMEDIATE"))
    cases.append(("N2 missing mxp evidence waits", failure_disposition(
        1, immediate_redline=False, mxp_available=False
    ) == "WAIT_HUMAN"))
    cases.append(("N2 missing mxp option waits", failure_disposition(
        2, immediate_redline=False, mxp_option_present=False
    ) == "WAIT_HUMAN"))
    try:
        failure_disposition(0, immediate_redline=False)
        cases.append(("N2 invalid failure count rejects", False))
    except ValueError:
        cases.append(("N2 invalid failure count rejects", True))

    half = [
        {"id": "Q01", "type": "FACT", "blocking": "true", "default": "", "answer": "given"},
        {"id": "Q02", "type": "PREFERENCE", "blocking": "false", "default": "safe", "answer": ""},
    ]
    cases.append(("N4 half-fill preserves answer/defaults rest", resolve_questionnaire(half, "continue-defaults") == ("DEFAULTED", ["Q02"])))

    base_body = "### 冻结合同\n- done_when: result"
    contract_id = block_id("ctr", base_body)
    base = (
        f'<!-- team-task-contract run_id="run-1" contract_id="{contract_id}" '
        f'source_block_id="src-1" status="frozen" profile="minimal" -->\n'
        f"{base_body}\n<!-- /team-task-contract -->"
    )
    add_body = "### 合同增补\n- 授权指令原文: \"继续执行并把 old 改成 new\"\n- 授权时间/会话: 2026-09-04T13:00:00+08:00\n- 被取代条款: old\n- 生效新条款: new"
    addendum_id = block_id("add", add_body)
    addendum = (
        f'<!-- team-task-contract-addendum run_id="run-1" source_block_id="src-1" '
        f'parent_effective_id="{contract_id}" addendum_id="{addendum_id}" status="frozen" -->\n'
        f"{add_body}\n<!-- /team-task-contract-addendum -->"
    )
    base_errors, base_contracts = validate_contract_document(base, "run-1", "src-1")
    cases.append(("N5 base contract valid", not base_errors and base_contracts[("run-1", "src-1")] == (
        contract_id, contract_id
    )))
    chain_errors, chain_contracts = validate_contract_document(base + "\n" + addendum, "run-1", "src-1")
    cases.append(("N5 addendum chain valid", not chain_errors and chain_contracts[("run-1", "src-1")] == (
        contract_id, addendum_id
    )))
    add2_body = "### 合同增补\n- 授权指令原文: \"将 new 改为 newest\"\n- 授权时间/会话: session=session-2\n- 被取代条款: new\n- 生效新条款: newest"
    addendum2_id = block_id("add", add2_body)
    addendum2 = (
        f'<!-- team-task-contract-addendum run_id="run-1" source_block_id="src-1" '
        f'parent_effective_id="{addendum_id}" addendum_id="{addendum2_id}" status="frozen" -->\n'
        f"{add2_body}\n<!-- /team-task-contract-addendum -->"
    )
    multi_errors, multi_contracts = validate_contract_document(
        base + "\n" + addendum + "\n" + addendum2, "run-1", "src-1"
    )
    cases.append(("N5 ordered multi-addendum chain valid", not multi_errors and multi_contracts[("run-1", "src-1")] == (
        contract_id, addendum2_id
    )))
    bad_parent = addendum.replace(f'parent_effective_id="{contract_id}"', 'parent_effective_id="ctr-deadbeef"')
    cases.append(("N5 bad addendum parent rejects", bool(validate_contract_document(base + "\n" + bad_parent)[0])))
    bad_hash = addendum.replace(f'addendum_id="{addendum_id}"', 'addendum_id="add-deadbeef"')
    cases.append(("N5 bad addendum hash rejects", bool(validate_contract_document(base + "\n" + bad_hash)[0])))
    cases.append(("N5 duplicate base rejects", bool(validate_contract_document(base + "\n" + base)[0])))
    cases.append(("N5 addendum before base rejects", bool(validate_contract_document(addendum + "\n" + base)[0])))
    duplicate_add = addendum.replace(f'parent_effective_id="{contract_id}"', f'parent_effective_id="{addendum_id}"')
    cases.append(("N5 duplicate addendum id rejects", bool(validate_contract_document(base + "\n" + addendum + "\n" + duplicate_add)[0])))
    blank_body = "### 合同增补\n- 授权指令原文: \"\"\n- 授权时间/会话: \n- 被取代条款: <待填>\n- 生效新条款: "
    blank_id = block_id("add", blank_body)
    blank_addendum = (
        f'<!-- team-task-contract-addendum run_id="run-1" source_block_id="src-1" '
        f'parent_effective_id="{contract_id}" addendum_id="{blank_id}" status="frozen" -->\n'
        f"{blank_body}\n<!-- /team-task-contract-addendum -->"
    )
    cases.append(("N5 blank addendum fields reject", bool(validate_contract_document(base + "\n" + blank_addendum)[0])))
    date_only_body = "### 合同增补\n- 授权指令原文: \"2026-09-04\"\n- 授权时间/会话: 2026-09-04T13:00:00+08:00\n- 被取代条款: old\n- 生效新条款: new"
    date_only_id = block_id("add", date_only_body)
    date_only_addendum = (
        f'<!-- team-task-contract-addendum run_id="run-1" source_block_id="src-1" '
        f'parent_effective_id="{contract_id}" addendum_id="{date_only_id}" status="frozen" -->\n'
        f"{date_only_body}\n<!-- /team-task-contract-addendum -->"
    )
    cases.append(("N5 date-only authorization rejects", bool(validate_contract_document(
        base + "\n" + date_only_addendum
    )[0])))
    for placeholder in ("待填", "...", "TBD"):
        placeholder_body = (
            f'### 合同增补\n- 授权指令原文: "{placeholder}"\n'
            '- 授权时间/会话: 2026-09-04T13:00:00+08:00\n- 被取代条款: old\n- 生效新条款: new'
        )
        placeholder_id = block_id("add", placeholder_body)
        placeholder_addendum = (
            f'<!-- team-task-contract-addendum run_id="run-1" source_block_id="src-1" '
            f'parent_effective_id="{contract_id}" addendum_id="{placeholder_id}" status="frozen" -->\n'
            f"{placeholder_body}\n<!-- /team-task-contract-addendum -->"
        )
        cases.append((f"N5 placeholder authorization {placeholder} rejects", bool(validate_contract_document(
            base + "\n" + placeholder_addendum
        )[0])))
    placeholder_session_body = (
        '### 合同增补\n- 授权指令原文: "把 old 改为 new"\n'
        '- 授权时间/会话: session=<标识>\n- 被取代条款: old\n- 生效新条款: new'
    )
    placeholder_session_id = block_id("add", placeholder_session_body)
    placeholder_session_addendum = (
        f'<!-- team-task-contract-addendum run_id="run-1" source_block_id="src-1" '
        f'parent_effective_id="{contract_id}" addendum_id="{placeholder_session_id}" status="frozen" -->\n'
        f"{placeholder_session_body}\n<!-- /team-task-contract-addendum -->"
    )
    cases.append(("N5 placeholder session rejects", bool(validate_contract_document(
        base + "\n" + placeholder_session_addendum
    )[0])))
    missing_identity_addendum = addendum.replace(' source_block_id="src-1"', "")
    cases.append(("N5 filtered missing addendum identity rejects", bool(validate_contract_document(
        base + "\n" + missing_identity_addendum, "run-1", "src-1"
    )[0])))
    orphan_identity_addendum = addendum.replace('source_block_id="src-1"', 'source_block_id="src-orphan"')
    cases.append(("N5 altered addendum identity rejects as orphan", bool(validate_contract_document(
        base + "\n" + orphan_identity_addendum, "run-1", "src-1"
    )[0])))
    extra_close = base + "\n<!-- /team-task-contract -->"
    cases.append(("N5 orphan closing marker rejects", bool(validate_contract_document(extra_close)[0])))
    progress = (
        f"> run_id: run-1\n> source_block_id: src-1\n"
        f"> contract_id: {contract_id}\n> effective_contract_id: {addendum_id}\n"
    )
    cases.append(("N5 progress contract pointers valid", not validate_progress_effective(
        progress, "run-1", "src-1", contract_id, addendum_id
    )))
    wrong_base_progress = progress.replace(f"> contract_id: {contract_id}", "> contract_id: ctr-deadbeef")
    cases.append(("N5 wrong progress base pointer rejects", bool(validate_progress_effective(
        wrong_base_progress, "run-1", "src-1", contract_id, addendum_id
    ))))
    for field in ("run_id", "source_block_id", "contract_id", "effective_contract_id"):
        duplicate_progress = progress + f"> {field}: duplicate-value\n"
        cases.append((f"N5 duplicate progress {field} rejects", bool(validate_progress_effective(
            duplicate_progress, "run-1", "src-1", contract_id, addendum_id
        ))))
        blank_duplicate_progress = progress + f"> {field}:\n"
        cases.append((f"N5 blank duplicate progress {field} rejects", bool(validate_progress_effective(
            blank_duplicate_progress, "run-1", "src-1", contract_id, addendum_id
        ))))
        spaced_duplicate_progress = progress + f"> {field}: duplicate extra\n"
        cases.append((f"N5 spaced duplicate progress {field} rejects", bool(validate_progress_effective(
            spaced_duplicate_progress, "run-1", "src-1", contract_id, addendum_id
        ))))
        precolon_space_progress = progress + f"> {field} : duplicate-value\n"
        cases.append((f"N5 pre-colon-space progress {field} rejects", bool(validate_progress_effective(
            precolon_space_progress, "run-1", "src-1", contract_id, addendum_id
        ))))
    return cases


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skill-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--contract-file", type=Path)
    parser.add_argument("--progress-file", type=Path)
    parser.add_argument("--run-id")
    parser.add_argument("--source-block-id")
    args = parser.parse_args()
    root = args.skill_root.resolve()
    team, gate = root / "SKILL.md", root / "funnel-gate.md"
    chop_root = root.parent / "chop-task"
    chop, kickoff = chop_root / "SKILL.md", chop_root / "kickoff-gate.md"
    free = root.parent / "free" / "SKILL.md"
    review = root.parents[2] / ".agents" / "mc-expert-common" / "review-contract-v2.md"

    errors = validate_files(team, chop, gate, kickoff, free, review)
    cases = run_cases()
    errors.extend(name for name, ok in cases if not ok)

    if args.contract_file:
        contract_errors, contracts = validate_contract_document(
            args.contract_file.read_text(encoding="utf-8"), args.run_id, args.source_block_id
        )
        errors.extend(contract_errors)
        if args.progress_file:
            if not args.run_id or not args.source_block_id:
                errors.append("progress: --run-id and --source-block-id are required")
            else:
                expected = contracts.get((args.run_id, args.source_block_id))
                if not expected:
                    errors.append("progress: effective contract not found")
                else:
                    errors.extend(validate_progress_effective(
                        args.progress_file.read_text(encoding="utf-8"),
                        args.run_id,
                        args.source_block_id,
                        expected[0],
                        expected[1],
                    ))
    elif args.progress_file:
        errors.append("progress: --contract-file is required")

    with tempfile.TemporaryDirectory(prefix="team-task-positive-control-") as td:
        tmp = Path(td)
        for source in (team, chop, gate, kickoff, free):
            shutil.copy2(source, tmp / source.name.replace("SKILL", source.parent.name + "-SKILL"))
        bad_team = tmp / "team-task-SKILL.md"
        temp_chop = tmp / "chop-task-SKILL.md"
        temp_gate = tmp / "funnel-gate.md"
        temp_kickoff = tmp / "kickoff-gate.md"
        temp_free = tmp / "free-SKILL.md"
        bad_team.write_text(bad_team.read_text(encoding="utf-8").replace("disable-model-invocation: true", ""), encoding="utf-8")
        control_errors = validate_files(
            bad_team, temp_chop, temp_gate, temp_kickoff, temp_free, review
        )
        positive_control_ok = any("disable-model-invocation" in item for item in control_errors)
        bad_gate = tmp / "bad-funnel-gate.md"
        bad_gate.write_text(temp_gate.read_text(encoding="utf-8").replace("run_status=COMPLETE + P6✓", "run_status=COMPLETE + P6?"), encoding="utf-8")
        p6_control_errors = validate_files(team, chop, bad_gate, kickoff, free, review)
        p6_control_ok = any("P6✓" in item for item in p6_control_errors)
        bad_free = tmp / "bad-free-SKILL.md"
        bad_free.write_text(temp_free.read_text(encoding="utf-8").replace("RESUME_AUTHORIZED", ""), encoding="utf-8")
        free_control_errors = validate_files(team, chop, gate, kickoff, bad_free, review)
        free_control_ok = any("RESUME_AUTHORIZED" in item for item in free_control_errors)
    cases.append(("positive control sees deliberate failure", positive_control_ok))
    cases.append(("positive control sees missing P6 atomic close", p6_control_ok))
    cases.append(("positive control sees missing free resume", free_control_ok))
    if not positive_control_ok:
        errors.append("positive control did not fail")
    if not p6_control_ok:
        errors.append("P6 positive control did not fail")
    if not free_control_ok:
        errors.append("free resume positive control did not fail")

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
