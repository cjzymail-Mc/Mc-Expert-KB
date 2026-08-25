#!/usr/bin/env python3
"""Deterministic planner<->tester relay using the production repo temp.md."""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import time
import uuid
from datetime import datetime, timezone


VERSION = 1
PATH_IDENTITY_CONTRACT = "RESOLVED_PATH_IDENTITY_V1"
STATE_NAME = ".triple-tester-state.json"
MESSAGE_NAME = ".triple-tester-message.md"
LOCK_NAME = ".triple-tester.lock"
TEMP_NAME = "temp.md"
ROLES = {"planner", "tester"}
TRIPLE_CONFIG_PATH = Path(__file__).with_name("triple-session-config.json")
DOUBLE_CONFIG_FIELDS = {"coder_interval_seconds", "planner_interval_seconds", "max_budget_seconds"}


class RelayError(RuntimeError):
    pass


def fail(code: str, detail: str = "") -> None:
    suffix = f": {detail}" if detail else ""
    raise RelayError(f"{code}{suffix}")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def load_runtime_config() -> dict:
    try:
        bridge = json.loads(read_text(TRIPLE_CONFIG_PATH))
    except (OSError, json.JSONDecodeError) as exc:
        fail("TRIPLE_CONFIG_INVALID", str(exc))
    if set(bridge) != {"inherits", "role_interval_fields"}:
        fail("TRIPLE_CONFIG_FIELDS_INVALID", ",".join(sorted(bridge)))
    mapping = bridge.get("role_interval_fields")
    if not isinstance(mapping, dict) or set(mapping) != ROLES:
        fail("TRIPLE_CONFIG_ROLE_MAPPING_INVALID")
    if mapping.get("planner") != "planner_interval_seconds" or mapping.get("tester") != "coder_interval_seconds":
        fail("TRIPLE_CONFIG_ROLE_MAPPING_INVALID")
    inherited = bridge.get("inherits")
    if not isinstance(inherited, str) or not inherited.strip():
        fail("TRIPLE_CONFIG_INHERIT_PATH_INVALID")
    source = (TRIPLE_CONFIG_PATH.parent / inherited).resolve()
    try:
        raw = json.loads(read_text(source))
    except (OSError, json.JSONDecodeError) as exc:
        fail("SHARED_CONFIG_INVALID", str(exc))
    if set(raw) != DOUBLE_CONFIG_FIELDS:
        missing = sorted(DOUBLE_CONFIG_FIELDS - set(raw))
        extra = sorted(set(raw) - DOUBLE_CONFIG_FIELDS)
        fail("SHARED_CONFIG_FIELDS_INVALID", f"missing={','.join(missing)} extra={','.join(extra)}")
    normalized: dict[str, int | str | dict[str, int]] = {"source": str(source)}
    for name in sorted(DOUBLE_CONFIG_FIELDS):
        value = raw[name]
        if isinstance(value, bool) or not isinstance(value, int):
            fail("SHARED_CONFIG_VALUE_NOT_INTEGER", name)
        minimum = 1 if name == "max_budget_seconds" else 60
        maximum = 86400 if name == "max_budget_seconds" else 3600
        if value < minimum or value > maximum:
            fail("SHARED_CONFIG_VALUE_OUT_OF_RANGE", f"{name}={value}")
        if name != "max_budget_seconds" and value % 60 != 0:
            fail("SHARED_CONFIG_INTERVAL_NOT_WHOLE_MINUTE", f"{name}={value}")
        normalized[name] = value
    normalized["role_intervals"] = {
        role: int(normalized[field]) for role, field in mapping.items()
    }
    return normalized


def wake_event_name(root: Path, role: str) -> str:
    identity = f"{canonical(root)}|{role}"
    return f"Local\\mc_triple_session_wake_{sha256_text(identity)[:32]}"


def open_wake_event(root: Path, role: str):
    if os.name != "nt":
        return None
    import ctypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateEventW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_wchar_p]
    kernel32.CreateEventW.restype = ctypes.c_void_p
    kernel32.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
    kernel32.WaitForSingleObject.restype = ctypes.c_uint32
    kernel32.SetEvent.argtypes = [ctypes.c_void_p]
    kernel32.SetEvent.restype = ctypes.c_int
    kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
    kernel32.CloseHandle.restype = ctypes.c_int
    handle = kernel32.CreateEventW(None, 0, 0, wake_event_name(root, role))
    if not handle:
        return None
    return kernel32, handle


def close_wake_event(event) -> None:
    if event is not None:
        kernel32, handle = event
        kernel32.CloseHandle(handle)


def wait_for_wake(event, timeout_seconds: float) -> bool:
    if timeout_seconds <= 0:
        return False
    if event is None:
        time.sleep(timeout_seconds)
        return False
    kernel32, handle = event
    milliseconds = min(int(timeout_seconds * 1000), 0xFFFFFFFE)
    return kernel32.WaitForSingleObject(handle, milliseconds) == 0


def send_wake_signal(root: Path, role: str) -> None:
    event = None
    try:
        event = open_wake_event(root, role)
        if event is not None:
            kernel32, handle = event
            kernel32.SetEvent(handle)
    except Exception:
        # Advisory only; the inherited timeout remains the fail-safe.
        pass
    finally:
        close_wake_event(event)


def canonical(path: Path) -> str:
    return os.path.normcase(str(path.resolve()))


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_text(text: str) -> str:
    return sha256_bytes(text.encode("utf-8"))


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp")
    try:
        with tmp.open("w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            tmp.unlink()


def atomic_write_json(path: Path, payload: dict) -> None:
    atomic_write_text(path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


def root_paths(root_arg: str) -> dict[str, Path]:
    raw = Path(root_arg)
    if not raw.is_absolute():
        fail("ROOT_NOT_ABSOLUTE", root_arg)
    root = raw.resolve()
    if not root.is_dir():
        fail("ROOT_NOT_FOUND", str(root))
    return {
        "root": root,
        "state": root / STATE_NAME,
        "message": root / MESSAGE_NAME,
        "lock": root / LOCK_NAME,
        "temp": root / TEMP_NAME,
    }


@contextlib.contextmanager
def repo_lock(lock_path: Path, timeout_seconds: float = 5.0):
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    handle = lock_path.open("a+b")
    handle.seek(0, os.SEEK_END)
    if handle.tell() == 0:
        handle.write(b"0")
        handle.flush()
    deadline = time.monotonic() + timeout_seconds
    locked = False
    try:
        while not locked:
            try:
                handle.seek(0)
                if os.name == "nt":
                    import msvcrt

                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                locked = True
            except OSError:
                if time.monotonic() >= deadline:
                    fail("RELAY_LOCK_TIMEOUT", str(lock_path))
                time.sleep(0.05)
        yield
    finally:
        if locked:
            handle.seek(0)
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        handle.close()


def load_state(path: Path, required: bool = True) -> dict | None:
    if not path.exists():
        if required:
            fail("RELAY_STATE_MISSING", str(path))
        return None
    try:
        state = json.loads(read_text(path))
    except (OSError, json.JSONDecodeError) as exc:
        fail("RELAY_STATE_INVALID", str(exc))
    if state.get("version") != VERSION:
        fail("RELAY_VERSION_UNSUPPORTED", str(state.get("version")))
    if state.get("turn") not in ROLES:
        fail("RELAY_ROLE_INVALID", str(state.get("turn")))
    if state.get("status") not in {"running", "wait_human", "done", "cancelled"}:
        fail("RELAY_STATUS_INVALID", str(state.get("status")))
    if state.get("phase") not in {"ready", "working"}:
        fail("RELAY_PHASE_INVALID", str(state.get("phase")))
    return state


def save_state(path: Path, state: dict) -> None:
    state["updated"] = now_iso()
    atomic_write_json(path, state)


def public_state(state: dict | None) -> dict:
    if state is None:
        return {"exists": False}
    hidden = {"worker_token_hashes"}
    return {"exists": True, **{k: v for k, v in state.items() if k not in hidden}}


def require_role(role: str | None) -> str:
    if role not in ROLES:
        fail("ROLE_REQUIRED", str(role))
    return role


def require_token(token: str | None) -> str:
    if not token:
        fail("WORKER_TOKEN_REQUIRED")
    return token


def require_run(state: dict, expected_run_id: str | None) -> None:
    if not expected_run_id or expected_run_id == "PENDING":
        return
    if state.get("run_id") != expected_run_id:
        fail("RUN_MISMATCH", f"expected={expected_run_id} actual={state.get('run_id')}")


def assert_active(state: dict) -> None:
    if state["status"] != "running":
        fail("RELAY_NOT_ACTIVE", state["status"])


def assert_artifact(root: Path, artifact_arg: str | None, expected_sha256: str | None) -> tuple[Path, str]:
    if not artifact_arg or not expected_sha256:
        fail("ARTIFACT_BINDING_REQUIRED")
    artifact = Path(artifact_arg)
    if not artifact.is_absolute() or not artifact.is_file():
        fail("ARTIFACT_NOT_FOUND", artifact_arg)
    resolved = artifact.resolve()
    try:
        resolved.relative_to(root)
    except ValueError:
        fail("ARTIFACT_OUTSIDE_PRODUCTION_PROJECT", str(resolved))
    actual = sha256_bytes(resolved.read_bytes())
    if actual != expected_sha256.lower():
        fail("ARTIFACT_HASH_MISMATCH", f"expected={expected_sha256.lower()} actual={actual}")
    return resolved, actual


def assert_worker(state: dict, role: str, token: str) -> None:
    expected = state["worker_token_hashes"].get(role, "")
    actual = sha256_text(token)
    if not expected:
        fail("WORKER_NOT_CLAIMED", role)
    if expected != actual:
        fail("WORKER_TOKEN_MISMATCH", role)


def read_nonempty_temp(paths: dict[str, Path]) -> str:
    temp = paths["temp"]
    if not temp.exists():
        fail("TEMP_MISSING", str(temp))
    body = read_text(temp)
    if not body.strip():
        fail("TEMP_EMPTY", str(temp))
    return body


def parse_message(body: str) -> dict[str, str]:
    normalized = body.replace("\r\n", "\n").replace("\r", "\n")
    lines = normalized.split("\n")
    if not lines or lines[0].strip() != "TRIPLE_TEST_RELAY=v1":
        fail("RELAY_MESSAGE_MARKER_INVALID")
    fields: dict[str, str] = {}
    for line in lines[1:]:
        if not line.strip() or ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        if key and key not in fields:
            fields[key] = value.strip()
    required = {"run_id", "relay_seq", "release_id", "action", "source_manifest_sha256", "approved_artifact_sha256"}
    missing = sorted(key for key in required if not fields.get(key))
    if missing:
        fail("RELAY_MESSAGE_FIELDS_MISSING", ",".join(missing))
    try:
        fields["relay_seq_int"] = str(int(fields["relay_seq"]))
    except ValueError:
        fail("RELAY_MESSAGE_SEQ_INVALID", fields["relay_seq"])
    return fields


def validate_message(
    body: str,
    *,
    run_id: str,
    release_id: str,
    relay_seq: int,
    allowed_actions: set[str],
) -> dict[str, str]:
    fields = parse_message(body)
    if fields["run_id"] != run_id:
        fail("RELAY_MESSAGE_RUN_MISMATCH", f"expected={run_id} actual={fields['run_id']}")
    if fields["release_id"] != release_id:
        fail("RELAY_MESSAGE_RELEASE_MISMATCH", f"expected={release_id} actual={fields['release_id']}")
    if int(fields["relay_seq_int"]) != relay_seq:
        fail("RELAY_MESSAGE_SEQ_MISMATCH", f"expected={relay_seq} actual={fields['relay_seq']}")
    if fields["action"] not in allowed_actions:
        fail("RELAY_MESSAGE_ACTION_INVALID", fields["action"])
    return fields


def freeze_temp(paths: dict[str, Path], body: str) -> tuple[str, int]:
    normalized = body.replace("\r\n", "\n").replace("\r", "\n")
    atomic_write_text(paths["message"], normalized)
    atomic_write_text(paths["temp"], "")
    if paths["temp"].stat().st_size != 0:
        fail("TEMP_CLEAR_VERIFY_FAILED", str(paths["temp"]))
    encoded = normalized.encode("utf-8")
    return sha256_bytes(encoded), len(encoded)


def verify_message(paths: dict[str, Path], state: dict) -> None:
    if not paths["message"].exists():
        fail("MESSAGE_MISSING", str(paths["message"]))
    actual = sha256_bytes(paths["message"].read_bytes())
    if actual != state.get("message_sha256"):
        fail("MESSAGE_HASH_MISMATCH", f"expected={state.get('message_sha256')} actual={actual}")


def emit(payload: dict) -> None:
    print(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))


def action_probe(args: argparse.Namespace, paths: dict[str, Path]) -> None:
    state = load_state(paths["state"], required=False)
    config = load_runtime_config()
    temp_exists = paths["temp"].exists()
    data = paths["temp"].read_bytes() if temp_exists else b""
    emit(
        {
            "result": "PROBE",
            "root": str(paths["root"]),
            "config": config,
            "state": public_state(state),
            "temp": {
                "exists": temp_exists,
                "length": len(data),
                "sha256": sha256_bytes(data) if data else "",
            },
        }
    )


def action_config(args: argparse.Namespace, paths: dict[str, Path]) -> None:
    emit({"result": "CONFIG", "config": load_runtime_config()})


def action_goal_contract(args: argparse.Namespace, paths: dict[str, Path]) -> None:
    role = require_role(args.role)
    config = load_runtime_config()
    wait_seconds = int(config["role_intervals"][role])
    if role == "planner":
        double_token = require_token(args.double_worker_token)
        relay_token = require_token(args.relay_worker_token)
        if not args.dev_repo or not Path(args.dev_repo).is_absolute():
            fail("DEV_REPO_REQUIRED")
        if not args.prepared_task_sha256:
            fail("PREPARED_TASK_SHA_REQUIRED")
        objective = "\n".join(
            [
                "TRIPLE_PLANNER_GOAL_CONTRACT=v1",
                "workflow_mode=planner-coder-tester",
                f"development_repo={Path(args.dev_repo).resolve()}",
                f"production_project_repo={paths['root']}",
                f"dev_run_id={args.expected_run_id or 'PENDING'}",
                "role=planner",
                f"double_worker_token={double_token}",
                f"relay_worker_token={relay_token}",
                f"prepared_task_sha256={args.prepared_task_sha256}",
                f"wait_seconds_at_creation={wait_seconds}",
                f"max_budget_seconds_at_creation={config['max_budget_seconds']}",
                f"PATH_IDENTITY={PATH_IDENTITY_CONTRACT}",
                "TOKEN_RULE=Both worker tokens above are durable truth; reconstruct them every turn and never expose them to the user.",
                "LIVE_RULE=Before every continuation reread triple-planner, both common protocols, and live state; live files override old text.",
                "TERMINAL_RULE=Complete only after both the development run and production relay are terminal with all frozen done_when satisfied.",
            ]
        )
        envelope = {
            "envelope": "TRIPLE_PLANNER_GOAL_ENVELOPE=v1",
            "path_identity": PATH_IDENTITY_CONTRACT,
            "role": role,
            "development_repo": str(Path(args.dev_repo).resolve()),
            "production_project_repo": str(paths["root"]),
            "goal_objective": objective,
        }
    else:
        token = require_token(args.worker_token)
        objective = "\n".join(
            [
                "TRIPLE_TESTER_GOAL_CONTRACT=v1",
                "workflow_mode=planner-coder-tester",
                f"production_project_repo={paths['root']}",
                f"relay_run_id={args.expected_run_id or 'PENDING'}",
                "role=tester",
                f"worker_token={token}",
                f"wait_seconds_at_creation={wait_seconds}",
                f"max_budget_seconds_at_creation={config['max_budget_seconds']}",
                f"PATH_IDENTITY={PATH_IDENTITY_CONTRACT}",
                "TOKEN_RULE=worker_token above is durable truth; reconstruct it every turn and never expose it to the user.",
                "LIVE_RULE=Before every continuation reread production-tester, triple protocol, and live relay state.",
                "TERMINAL_RULE=Do not complete for planner turn, pending user approval, or unchanged state; complete only for done or cancelled.",
            ]
        )
        envelope = {
            "envelope": "TRIPLE_TESTER_GOAL_ENVELOPE=v1",
            "path_identity": PATH_IDENTITY_CONTRACT,
            "role": role,
            "production_project_repo": str(paths["root"]),
            "goal_objective": objective,
        }
    emit(envelope)


def action_init(args: argparse.Namespace, paths: dict[str, Path]) -> None:
    token = require_token(args.worker_token)
    if not args.run_id:
        fail("RUN_ID_REQUIRED")
    if not args.dev_repo or not Path(args.dev_repo).is_absolute():
        fail("DEV_REPO_REQUIRED")
    if not args.release_id:
        fail("RELEASE_ID_REQUIRED")
    with repo_lock(paths["lock"]):
        existing = load_state(paths["state"], required=False)
        if existing is not None:
            fail("RELAY_ALREADY_EXISTS", f"status={existing['status']} run={existing['run_id']}")
        body = read_nonempty_temp(paths)
        validate_message(
            body,
            run_id=args.run_id,
            release_id=args.release_id,
            relay_seq=0,
            allowed_actions={"DEPLOY_AND_BUILD_YAML"},
        )
        message_hash, message_length = freeze_temp(paths, body)
        state = {
            "version": VERSION,
            "workflow": "planner-coder-tester",
            "run_id": args.run_id,
            "development_repo": canonical(Path(args.dev_repo)),
            "production_project_repo": canonical(paths["root"]),
            "release_id": args.release_id,
            "status": "running",
            "turn": "tester",
            "phase": "ready",
            "seq": 0,
            "message_seq": 0,
            "message_sha256": message_hash,
            "message_length": message_length,
            "worker_token_hashes": {"planner": sha256_text(token), "tester": ""},
            "approvals": {},
            "pending_approval": None,
            "last_action": "Init",
            "last_action_role": "planner",
            "created": now_iso(),
            "updated": now_iso(),
        }
        save_state(paths["state"], state)
    send_wake_signal(paths["root"], "tester")
    emit({"result": "INIT", "state": public_state(state)})


def action_show(args: argparse.Namespace, paths: dict[str, Path]) -> None:
    state = load_state(paths["state"])
    require_run(state, args.expected_run_id)
    verify_message(paths, state)
    emit({"result": "SHOW", "state": public_state(state)})


def action_wait_turn(args: argparse.Namespace, paths: dict[str, Path]) -> None:
    role = require_role(args.role)
    config = load_runtime_config()
    timeout_seconds = args.timeout_seconds
    if timeout_seconds is None:
        timeout_seconds = int(config["role_intervals"][role])
    if timeout_seconds < 1 or timeout_seconds > 3600:
        fail("WAIT_TIMEOUT_RANGE", str(timeout_seconds))
    started = time.monotonic()
    deadline = started + timeout_seconds
    last = None
    spurious_signals = 0
    event = open_wake_event(paths["root"], role)
    try:
        while True:
            state = load_state(paths["state"], required=False)
            if state is not None:
                require_run(state, args.expected_run_id)
                last = public_state(state)
                if state["status"] in {"done", "cancelled"}:
                    emit({"result": "TERMINAL", "elapsed_ms": int((time.monotonic() - started) * 1000), "state": last})
                    return
                if state["status"] == "running" and state["turn"] == role and state["phase"] == "ready" and state["seq"] >= args.observed_seq:
                    emit({"result": "STATE_READY", "elapsed_ms": int((time.monotonic() - started) * 1000), "spurious_signals": spurious_signals, "state": last})
                    return
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                emit({"result": "TIMEOUT", "elapsed_ms": int((time.monotonic() - started) * 1000), "spurious_signals": spurious_signals, "state": last or {"exists": False}})
                return
            if not wait_for_wake(event, remaining):
                emit({"result": "TIMEOUT", "elapsed_ms": int((time.monotonic() - started) * 1000), "spurious_signals": spurious_signals, "state": last or {"exists": False}})
                return
            spurious_signals += 1
    finally:
        close_wake_event(event)


def action_claim(args: argparse.Namespace, paths: dict[str, Path]) -> None:
    role = require_role(args.role)
    token = require_token(args.worker_token)
    with repo_lock(paths["lock"]):
        state = load_state(paths["state"])
        require_run(state, args.expected_run_id)
        assert_active(state)
        if state["turn"] != role or state["phase"] != "ready":
            fail("CLAIM_BOUNDARY_REQUIRED", f"turn={state['turn']} phase={state['phase']}")
        current = state["worker_token_hashes"].get(role, "")
        token_hash = sha256_text(token)
        if current and current != token_hash:
            fail("WORKER_ACTIVE", role)
        state["worker_token_hashes"][role] = token_hash
        state["last_action"] = "Claim"
        state["last_action_role"] = role
        save_state(paths["state"], state)
    emit({"result": "CLAIM", "state": public_state(state)})


def action_consume(args: argparse.Namespace, paths: dict[str, Path]) -> None:
    role = require_role(args.role)
    token = require_token(args.worker_token)
    with repo_lock(paths["lock"]):
        state = load_state(paths["state"])
        require_run(state, args.expected_run_id)
        assert_active(state)
        assert_worker(state, role, token)
        if state["turn"] != role:
            fail("TURN_MISMATCH", f"expected={role} actual={state['turn']}")
        if state["phase"] != "ready":
            fail("PHASE_MISMATCH", f"expected=ready actual={state['phase']}")
        verify_message(paths, state)
        state["phase"] = "working"
        state["last_action"] = "Consume"
        state["last_action_role"] = role
        save_state(paths["state"], state)
    emit(
        {
            "result": "CONSUME",
            "message_path": str(paths["message"]),
            "message_sha256": state["message_sha256"],
            "state": public_state(state),
        }
    )


def action_handoff(args: argparse.Namespace, paths: dict[str, Path]) -> None:
    role = require_role(args.role)
    target = require_role(args.to)
    token = require_token(args.worker_token)
    if (role, target) not in {("planner", "tester"), ("tester", "planner")}:
        fail("HANDOFF_DIRECTION_INVALID", f"{role}->{target}")
    with repo_lock(paths["lock"]):
        state = load_state(paths["state"])
        require_run(state, args.expected_run_id)
        assert_active(state)
        assert_worker(state, role, token)
        if state["turn"] != role:
            fail("TURN_MISMATCH", f"expected={role} actual={state['turn']}")
        if state["phase"] != "working":
            fail("PHASE_MISMATCH", f"expected=working actual={state['phase']}")
        body = read_nonempty_temp(paths)
        next_message_seq = int(state["message_seq"]) + 1
        if role == "planner":
            if not args.release_id:
                fail("RELEASE_ID_REQUIRED")
            next_release_id = args.release_id
            allowed_actions = {"DEPLOY_AND_BUILD_YAML", "CONTINUE_PPT", "CONTINUE_WORD"}
        else:
            next_release_id = str(state["release_id"])
            allowed_actions = {"RESULT"}
        validate_message(
            body,
            run_id=str(state["run_id"]),
            release_id=next_release_id,
            relay_seq=next_message_seq,
            allowed_actions=allowed_actions,
        )
        message_hash, message_length = freeze_temp(paths, body)
        state["seq"] += 1
        state["message_seq"] = next_message_seq
        state["message_sha256"] = message_hash
        state["message_length"] = message_length
        state["turn"] = target
        if role == "planner" and next_release_id != str(state["release_id"]):
            state["approvals"] = {}
            state["pending_approval"] = None
        state["release_id"] = next_release_id
        state["phase"] = "ready"
        state["last_action"] = "Handoff"
        state["last_action_role"] = role
        save_state(paths["state"], state)
    send_wake_signal(paths["root"], target)
    emit({"result": "HANDOFF", "state": public_state(state)})


def action_done(args: argparse.Namespace, paths: dict[str, Path]) -> None:
    role = require_role(args.role)
    token = require_token(args.worker_token)
    if role != "planner":
        fail("ONLY_PLANNER_CAN_COMPLETE")
    with repo_lock(paths["lock"]):
        state = load_state(paths["state"])
        require_run(state, args.expected_run_id)
        assert_active(state)
        assert_worker(state, role, token)
        if state["turn"] != role or state["phase"] != "working":
            fail("DONE_BOUNDARY_REQUIRED", f"turn={state['turn']} phase={state['phase']}")
        state["status"] = "done"
        state["phase"] = "ready"
        state["last_action"] = "Done"
        state["last_action_role"] = role
        save_state(paths["state"], state)
    send_wake_signal(paths["root"], "tester")
    emit({"result": "DONE", "state": public_state(state)})


def action_wait_human(args: argparse.Namespace, paths: dict[str, Path]) -> None:
    role = require_role(args.role)
    token = require_token(args.worker_token)
    if role != "planner":
        fail("ONLY_PLANNER_CAN_WAIT_HUMAN")
    if args.approval_kind not in {"yaml", "ppt"}:
        fail("APPROVAL_KIND_REQUIRED")
    if not args.reason:
        fail("REASON_REQUIRED")
    with repo_lock(paths["lock"]):
        state = load_state(paths["state"])
        require_run(state, args.expected_run_id)
        assert_active(state)
        assert_worker(state, role, token)
        if state["turn"] != role or state["phase"] != "working":
            fail("WAIT_HUMAN_BOUNDARY_REQUIRED", f"turn={state['turn']} phase={state['phase']}")
        artifact, artifact_hash = assert_artifact(paths["root"], args.artifact_path, args.artifact_sha256)
        state["status"] = "wait_human"
        state["phase"] = "ready"
        state["pending_approval"] = {
            "id": uuid.uuid4().hex,
            "kind": args.approval_kind,
            "artifact_path": str(artifact),
            "artifact_sha256": artifact_hash,
            "reason": args.reason,
            "created": now_iso(),
        }
        state["seq"] += 1
        state["last_action"] = "WaitHuman"
        state["last_action_role"] = role
        save_state(paths["state"], state)
    emit({"result": "WAIT_HUMAN", "state": public_state(state)})


def action_resolve_human(args: argparse.Namespace, paths: dict[str, Path]) -> None:
    role = require_role(args.role)
    token = require_token(args.worker_token)
    if role != "planner":
        fail("ONLY_PLANNER_CAN_RESOLVE_HUMAN")
    if args.decision not in {"approve", "rework", "cancel"}:
        fail("HUMAN_DECISION_REQUIRED")
    if not args.approval_id:
        fail("APPROVAL_ID_REQUIRED")
    with repo_lock(paths["lock"]):
        state = load_state(paths["state"])
        require_run(state, args.expected_run_id)
        assert_worker(state, role, token)
        if state["status"] != "wait_human":
            fail("STATE_NOT_WAIT_HUMAN", state["status"])
        pending = state.get("pending_approval") or {}
        if pending.get("id") != args.approval_id:
            fail("APPROVAL_ID_MISMATCH")
        if args.decision == "approve":
            artifact, artifact_hash = assert_artifact(
                paths["root"], pending.get("artifact_path"), pending.get("artifact_sha256")
            )
            approvals = state.setdefault("approvals", {})
            approvals[pending["kind"]] = {
                "artifact_path": str(artifact),
                "artifact_sha256": artifact_hash,
                "approved": now_iso(),
            }
            state["status"] = "running"
            state["phase"] = "working"
        elif args.decision == "rework":
            state["status"] = "running"
            state["phase"] = "working"
        else:
            state["status"] = "cancelled"
            state["phase"] = "ready"
        state["pending_approval"] = None
        state["seq"] += 1
        state["last_action"] = "ResolveHuman"
        state["last_action_role"] = role
        save_state(paths["state"], state)
    emit({"result": "HUMAN_RESOLVED", "decision": args.decision, "state": public_state(state)})


def action_cancel(args: argparse.Namespace, paths: dict[str, Path]) -> None:
    role = require_role(args.role)
    token = require_token(args.worker_token)
    if role != "planner":
        fail("ONLY_PLANNER_CAN_CANCEL")
    with repo_lock(paths["lock"]):
        state = load_state(paths["state"])
        require_run(state, args.expected_run_id)
        assert_worker(state, role, token)
        if state["status"] == "done":
            fail("CANCEL_NOT_ALLOWED_DONE")
        state["status"] = "cancelled"
        state["phase"] = "ready"
        state["last_action"] = "Cancel"
        state["last_action_role"] = role
        save_state(paths["state"], state)
    for wake_role in ROLES:
        send_wake_signal(paths["root"], wake_role)
    emit({"result": "CANCELLED", "state": public_state(state)})


def action_archive(args: argparse.Namespace, paths: dict[str, Path]) -> None:
    with repo_lock(paths["lock"]):
        state = load_state(paths["state"])
        require_run(state, args.expected_run_id)
        if state["status"] not in {"done", "cancelled"}:
            fail("ARCHIVE_REQUIRES_TERMINAL", state["status"])
        if paths["temp"].exists() and paths["temp"].stat().st_size != 0:
            fail("ARCHIVE_TEMP_NOT_EMPTY", str(paths["temp"]))
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        archive = paths["root"] / "team-progress" / "triple-workflow" / f"{stamp}-{state['run_id']}"
        archive.mkdir(parents=True, exist_ok=False)
        shutil.move(str(paths["state"]), str(archive / STATE_NAME))
        if paths["message"].exists():
            shutil.move(str(paths["message"]), str(archive / MESSAGE_NAME))
    emit({"result": "ARCHIVED", "archive_path": str(archive)})


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action",
        choices=["config", "probe", "goal-contract", "init", "show", "wait-turn", "claim", "consume", "handoff", "wait-human", "resolve-human", "done", "cancel", "archive"],
    )
    parser.add_argument("--root", required=True)
    parser.add_argument("--role", choices=sorted(ROLES))
    parser.add_argument("--to", choices=sorted(ROLES))
    parser.add_argument("--worker-token")
    parser.add_argument("--double-worker-token")
    parser.add_argument("--relay-worker-token")
    parser.add_argument("--run-id")
    parser.add_argument("--expected-run-id", default="PENDING")
    parser.add_argument("--dev-repo")
    parser.add_argument("--release-id")
    parser.add_argument("--prepared-task-sha256")
    parser.add_argument("--approval-kind", choices=["yaml", "ppt"])
    parser.add_argument("--artifact-path")
    parser.add_argument("--artifact-sha256")
    parser.add_argument("--approval-id")
    parser.add_argument("--decision", choices=["approve", "rework", "cancel"])
    parser.add_argument("--reason")
    parser.add_argument("--observed-seq", type=int, default=-1)
    parser.add_argument("--timeout-seconds", type=int)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        paths = root_paths(args.root)
        actions = {
            "config": action_config,
            "probe": action_probe,
            "goal-contract": action_goal_contract,
            "init": action_init,
            "show": action_show,
            "wait-turn": action_wait_turn,
            "claim": action_claim,
            "consume": action_consume,
            "handoff": action_handoff,
            "wait-human": action_wait_human,
            "resolve-human": action_resolve_human,
            "done": action_done,
            "cancel": action_cancel,
            "archive": action_archive,
        }
        actions[args.action](args, paths)
        return 0
    except RelayError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"RELAY_INTERNAL_ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
