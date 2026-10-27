"""Claude-GLM two-session relay. Windows, stdlib only; no model/API calls.

Named auto-reset events + a repo mutex reuse the double-session WaitTurn design.
Signals are hints; disk state owns the turn. No temp.md, leases, or Codex bridge.
"""
from __future__ import annotations
import argparse
import contextlib
import ctypes
from ctypes import wintypes as W
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import time
import uuid
from datetime import datetime

TERMINAL = {"DONE", "LIMIT", "CANCELLED"}
STATE = ".team-workflow-state.json"
SOURCE_RE = re.compile(r'<!-- team-task-source id="([^"]+)" sha256="([0-9a-f]{64})" status="open" -->\n(.*?)\n<!-- /team-task-source -->', re.S)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def sha(path):
    return digest(Path(path).read_bytes())


def need(ok, message):
    if not ok:
        raise ValueError(message)


def stamp():
    return datetime.now().astimezone().isoformat(timespec="seconds")


def unique(pairs):
    result = {}
    for k, v in pairs:
        need(k not in result, "DUPLICATE_JSON_KEY: " + k)
        result[k] = v
    return result


def read_json(path):
    value = json.loads(Path(path).read_text(encoding="utf-8-sig"), object_pairs_hook=unique)
    need(isinstance(value, dict), "JSON_OBJECT_REQUIRED")
    return value


def encode(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")


def atomic(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(dir=path.parent, prefix=path.name + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def preserve(path, data):
    """Immutable archive: identical retry is allowed; different bytes never replace."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        need(path.read_bytes() == data, "ARCHIVE_CONFLICT: " + str(path))
        return
    fd, name = tempfile.mkstemp(dir=path.parent, prefix="archive-", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        try:
            os.link(name, path)
        except FileExistsError:
            need(path.read_bytes() == data, "ARCHIVE_CONFLICT: " + str(path))
    finally:
        os.unlink(name)
    need(sha(path) == digest(data), "ARCHIVE_VERIFY_FAILED")


def local(repo, name):
    p = (repo / name).resolve()
    need(p.is_relative_to(repo) and p != repo, "PATH_OUTSIDE_REPO")
    return p


class Handle:
    def __init__(self, name, mutex=False):
        need(os.name == "nt", "WINDOWS_REQUIRED")
        self.api = ctypes.WinDLL("kernel32", use_last_error=True)
        for fn, args, result in [
            ("CreateEventW", [W.LPVOID, W.BOOL, W.BOOL, W.LPCWSTR], W.HANDLE),
            ("CreateMutexW", [W.LPVOID, W.BOOL, W.LPCWSTR], W.HANDLE),
            ("WaitForSingleObject", [W.HANDLE, W.DWORD], W.DWORD),
            ("SetEvent", [W.HANDLE], W.BOOL),
            ("ReleaseMutex", [W.HANDLE], W.BOOL),
            ("CloseHandle", [W.HANDLE], W.BOOL),
        ]:
            f = getattr(self.api, fn); f.argtypes = args; f.restype = result
        self.mutex = mutex
        self.handle = (self.api.CreateMutexW(None, False, name) if mutex else
                       self.api.CreateEventW(None, False, False, name))
        if not self.handle:
            raise ctypes.WinError(ctypes.get_last_error())

    def wait(self, milliseconds):
        result = self.api.WaitForSingleObject(self.handle, max(0, int(milliseconds)))
        if result == 258:
            return False
        need(result == 0 or (self.mutex and result == 128), "WINDOWS_WAIT_FAILED")
        return True

    def signal(self):
        need(self.api.SetEvent(self.handle), "WINDOWS_SIGNAL_FAILED")

    def close(self):
        self.api.CloseHandle(self.handle)


def key(repo, suffix):
    return "Local\\mc_team_workflow_" + digest((str(repo).casefold() + "|" + suffix).encode())[:40]


@contextlib.contextmanager
def locked(repo):
    h = Handle(key(repo, "mutex"), mutex=True)
    acquired = False
    try:
        acquired = h.wait(10000)
        need(acquired, "WORKFLOW_BUSY")
        yield
    finally:
        if acquired:
            h.api.ReleaseMutex(h.handle)
        h.close()


def notify(repo, run):
    # State is committed first. Signal failure must not undo an actual handoff.
    for role in ("A", "B"):
        try:
            h = Handle(key(repo, run + "|" + role))
            try: h.signal()
            finally: h.close()
        except (OSError, ValueError):
            pass


def glm_session(repo, session):
    """Read only this actual Claude session's first-party assistant model metadata."""
    need(re.fullmatch(r"[0-9a-fA-F-]{36}", session or ""), "CLAUDE_SESSION_ID_REQUIRED")
    roots = [Path.home() / ".claude-glm", Path.home() / ".claude"]
    if os.environ.get("CLAUDE_CONFIG_DIR"):
        roots.insert(0, Path(os.environ["CLAUDE_CONFIG_DIR"]))
    for root in dict.fromkeys(roots):
        projects = root / "projects"
        if not projects.is_dir(): continue
        for project in projects.iterdir():
            path = project / (session + ".jsonl")
            if not path.is_file(): continue
            model = None
            with path.open(encoding="utf-8") as stream:
                for line in stream:
                    try: row = json.loads(line)
                    except ValueError: continue
                    if row.get("type") != "assistant": continue
                    if Path(row.get("cwd", "")).resolve() != repo: continue
                    value = row.get("message", {}).get("model")
                    if value: model = value
            need(model and "glm" in model.lower(), "CLAUDE_GLM_RUNTIME_NOT_PROVEN")
            return {"runtime": "CLAUDE_GLM", "model": model, "transcript": str(path)}
    raise ValueError("CLAUDE_SESSION_TRANSCRIPT_NOT_FOUND")


def load(repo):
    s = read_json(repo / STATE)
    need(s.get("version") == 3 and s.get("repo") == str(repo), "STATE_REPO_OR_VERSION_MISMATCH")
    need(isinstance(s.get("seq"), int) and isinstance(s.get("round"), int), "STATE_SCHEMA_ERROR")
    need(re.fullmatch(r"[0-9a-f]{32}", s.get("run", "")), "STATE_SCHEMA_ERROR")
    if "A" in s["sessions"]:
        need(type(s.get("max_round")) is int and 1 <= s["round"] <= s["max_round"] <= 20,
             "STATE_SCHEMA_ERROR")
    else:
        need(s["round"] == 1 and s.get("max_round") is None and "baseline" not in s,
             "UNREVIEWED_RUN_MUST_STAY_AT_ROUND_ONE")
    return s


def bound(s, session, role=None, run=None):
    if run: need(s["run"] == run, "STALE_WORKFLOW_RUN")
    actual = next((r for r, sid in s["sessions"].items() if sid == session), None)
    need(actual is not None and (role is None or role == actual), "WINDOW_ROLE_MISMATCH")
    return actual


def baseline_ok(s):
    need(sha(s["baseline"]) == s["baseline_sha256"], "BASELINE_CHANGED: pause; explicit new authorization required")


def save(repo, s):
    s["seq"] += 1
    s["updated"] = stamp()
    atomic(repo / STATE, encode(s))


def home(repo, s):
    return local(repo, "team-progress/team-workflow/" + s["run"])


def round_dir(repo, s):
    return home(repo, s) / f"round-{s['round']:02d}"


def headers(text):
    values = {}
    for k, separator, v in re.findall(r"^>[ \t]*([A-Za-z_]+)([ \t]*[:：])[ \t]*([^\r\n]*)$", text, re.M):
        need(k == k.lower() and separator == ":", "NONCANONICAL_PROGRESS_HEADER: " + k)
        need(k not in values, "DUPLICATE_PROGRESS_HEADER: " + k)
        values[k] = v.strip()
    return values


def p6_closed(text):
    lines = re.findall(r"^>[ \t]*漏斗:[ \t]*([^\r\n]*)$", text, re.M)
    return len(lines) == 1 and "P6✓" in lines[0] and "P6·" not in lines[0]


def prepared_task(repo):
    """Adopt a prepared, unexecuted source; never resume a bare active team-task."""
    original = (repo / "team-task.md").read_bytes()
    raw = original.decode("utf-8-sig").replace("\r\n", "\n").strip("\n")
    need(raw.strip() and "本次任务" in raw and "done_when" in raw, "PREPARED_TASK_REQUIRED")
    need("<!-- team-task-contract" not in raw, "OLD_CONTRACT_PRESENT: prepare a fresh task first")
    if "<!-- team-task-source" in raw:
        m = SOURCE_RE.fullmatch(raw)
        need(m is not None and raw.count("<!-- team-task-source ") == 1, "SOURCE_BLOCK_AMBIGUOUS")
        body = m[3]
        need(m[2] == digest(body.encode()) and m[1] == "src-" + m[2][:8], "PREPARED_SOURCE_HASH_MISMATCH")
    else:
        body = raw
    source_hash = digest(body.encode())
    source_id = "src-" + source_hash[:8]
    p = repo / "team-progress.md"
    if p.exists() and p.read_text(encoding="utf-8-sig").strip():
        text = p.read_text(encoding="utf-8-sig")
        h = headers(text)
        need(h.get("run_status") in {"COMPLETE", "HALTED"}, "OLD_RUN_UNCLOSED")
        if h["run_status"] == "COMPLETE": need(p6_closed(text), "OLD_P6_NOT_FINISHED")
        need(h.get("source_block_id") != source_id, "SOURCE_ALREADY_EXECUTED")
    return body, source_id, source_hash, digest(original)


def freeze_criteria(repo, s, name):
    criteria = read_json(local(repo, name))
    items = criteria.get("items")
    need(isinstance(items, list) and items, "CRITERIA_REQUIRED")
    ids = []
    for item in items:
        need(isinstance(item, dict) and all(isinstance(item.get(k), str) and item[k].strip() for k in ("id", "requirement", "source", "verify")), "CRITERION_SCHEMA")
        ids.append(item["id"])
    need(len(ids) == len(set(ids)), "DUPLICATE_CRITERIA")
    preserve(home(repo, s) / "criteria.json", encode(criteria))
    s["criteria_sha256"] = sha(home(repo, s) / "criteria.json")


def archive_live(repo, dest):
    for name in ("team-task.md", "team-progress.md"):
        p = repo / name
        if p.exists(): preserve(dest / name, p.read_bytes())


def counts(s, supplied):
    need(isinstance(supplied, dict), "FAILURE_COUNTS_REQUIRED")
    for k, v in supplied.items():
        need(k and isinstance(v, int) and not isinstance(v, bool) and v >= 0, "INVALID_FAILURE_COUNT")
    for k, v in s["failures"].items():
        need(supplied.get(k, -1) >= v, "FAILURE_COUNT_RESET: " + k)
    return supplied


def evidence(repo, names):
    need(isinstance(names, list) and names, "EVIDENCE_REQUIRED")
    result = {}
    for name in names:
        need(isinstance(name, str), "INVALID_EVIDENCE_PATH")
        p = local(repo, name)
        need(p.is_file() and p.stat().st_size > 0, "EVIDENCE_MISSING: " + name)
        result[str(p.relative_to(repo))] = sha(p)
    return result


def verify_manifest(repo, manifest):
    need(isinstance(manifest, dict), "ARTIFACT_MAP_REQUIRED")
    for name, expected in manifest.items():
        need(isinstance(expected, str) and re.fullmatch(r"[0-9a-f]{64}", expected), "INVALID_ARTIFACT_HASH")
        need(sha(local(repo, name)) == expected, "ARTIFACT_CHANGED: " + name)


def source_ok(repo, s):
    text = (repo / "team-task.md").read_text(encoding="utf-8-sig").replace("\r\n", "\n")
    matches = list(SOURCE_RE.finditer(text))
    need(len(matches) == 1 and text.count("<!-- team-task-source ") == 1 and
         text.count("<!-- /team-task-source -->") == 1, "SOURCE_BLOCK_AMBIGUOUS")
    m = matches[0]
    need(m[1] == s["source_id"] and m[2] == s["source_sha256"] and
         digest(m[3].encode()) == s["source_sha256"], "ROUND_SOURCE_CHANGED")
    return text


def contract_ok(repo, s, text, progress):
    path = Path(__file__).resolve().parents[2] / "team-task/fixtures/verify_workflow_contract.py"
    spec = importlib.util.spec_from_file_location("team_task_contract", path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    errors, chains = module.validate_contract_document(text, s["team_run"], s["source_id"])
    expected = chains.get((s["team_run"], s["source_id"]))
    need(not errors and expected, "TEAM_CONTRACT_INVALID: " + "; ".join(errors))
    errors = module.validate_progress_effective(progress, s["team_run"], s["source_id"], *expected)
    need(not errors, "TEAM_PROGRESS_INVALID: " + "; ".join(errors))


def operation(repo, action, session, **opts):
    repo = Path(repo).resolve()
    need(repo.is_dir(), "REPO_REQUIRED")
    with locked(repo):
        if action == "init":
            need(opts.get("baseline") is None and opts.get("max_round") is None,
                 "B_ACCEPTS_TASK_ONLY: baseline and max-round belong to A join")
            proof = glm_session(repo, session)
            need(not (repo / STATE).exists(), "WORKFLOW_EXISTS: use status/resume or archive terminal run")
            body, source_id, source_hash, original_hash = prepared_task(repo)
            s = {"version": 3, "repo": str(repo), "run": uuid.uuid4().hex, "seq": 0,
                 "phase": "PUBLISHING", "round": 1, "max_round": None, "sessions": {"B": session},
                 "runtime_evidence": {"B": proof}, "failures": {}, "history": [], "stop_requested": False,
                 "authorization": {"B": "/team-workflow run", "created": stamp()},
                 "source_id": source_id, "source_sha256": source_hash,
                 "team_run": datetime.now().strftime("%Y%m%d-%H%M%S-") + source_hash[:8]}
            s["pending_old"] = {n: sha(repo / n) if (repo / n).exists() else None for n in ("team-task.md", "team-progress.md")}
            s["pending_old"]["team-task.md"] = original_hash
            archive_live(repo, home(repo, s) / "before-start")
            for n, expected in s["pending_old"].items():
                p = home(repo, s) / "before-start" / n
                need((sha(p) if p.exists() else None) == expected, "INITIAL_FILE_CHANGED")
            task = f'<!-- team-task-source id="{source_id}" sha256="{source_hash}" status="open" -->\n{body}\n<!-- /team-task-source -->\n'
            preserve(round_dir(repo, s) / "source.md", task.encode())
            save(repo, s)
            _publish(repo, s, opts)
        else:
            s = load(repo)
            if opts.get("run"): need(opts["run"] == s["run"], "STALE_WORKFLOW_RUN")
            if action == "status": return s
            need(opts.get("run"), "EXPECTED_RUN_REQUIRED")
            if action == "join":
                need(s["phase"] not in TERMINAL and s["phase"] != "PAUSED", "WORKFLOW_NOT_JOINABLE")
                need(session != s["sessions"]["B"], "A_AND_B_MUST_BE_DISTINCT_SESSIONS")
                need(s["sessions"].get("A", session) == session, "A_WINDOW_ALREADY_BOUND")
                proof = glm_session(repo, session)
                if "A" not in s["sessions"]:
                    need(opts.get("baseline"), "A_BASELINE_REQUIRED")
                    base = Path(opts["baseline"]).resolve()
                    need(base.is_file() and base.stat().st_size > 0, "BASELINE_REQUIRED")
                    need(base not in {repo / "team-task.md", repo / "team-progress.md", repo / STATE}, "BASELINE_MUST_BE_SEPARATE")
                    maximum = opts.get("max_round") if opts.get("max_round") is not None else 3
                    need(type(maximum) is int and s["round"] <= maximum <= 20, "INVALID_MAX_ROUND")
                    s.update(baseline=str(base), baseline_sha256=sha(base), max_round=maximum)
                    freeze_criteria(repo, s, opts.get("criteria"))
                else:
                    if opts.get("baseline"):
                        need(str(Path(opts["baseline"]).resolve()) == s["baseline"], "A_BASELINE_ALREADY_BOUND")
                    if opts.get("max_round") is not None:
                        need(opts["max_round"] == s["max_round"], "MAX_ROUND_ALREADY_BOUND")
                    baseline_ok(s)
                    need(sha(home(repo, s) / "criteria.json") == s["criteria_sha256"], "CRITERIA_CHANGED")
                s["runtime_evidence"]["A"] = proof
                s["sessions"]["A"] = session
                s["authorization"]["A"] = "/team-workflow review"
                save(repo, s)
            else:
                role = bound(s, session)
                if action == "stop":
                    if s["phase"] not in TERMINAL:
                        s["stop_requested"] = True
                        if s["phase"] != "B_RUNNING": s["phase"] = "CANCELLED"
                        save(repo, s)
                elif action == "archive":
                    need(s["phase"] in TERMINAL, "ONLY_TERMINAL_CAN_ARCHIVE")
                    archive_live(repo, home(repo, s) / "final")
                    preserve(home(repo, s) / "state-final.json", encode(s))
                    (repo / STATE).unlink()
                elif action == "pause":
                    need(s["phase"] not in TERMINAL and opts.get("reason"), "PAUSE_REASON_REQUIRED")
                    need(s["phase"] != "B_RUNNING" or role == "B", "B_MUST_QUIESCE_BEFORE_PAUSE")
                    s["pause_reason"] = opts["reason"]
                    s["phase"] = "CANCELLED" if s["stop_requested"] else "PAUSED"
                    save(repo, s)
                else:
                    need(s["phase"] not in TERMINAL, "WORKFLOW_TERMINAL")
                    if role == "A": baseline_ok(s)
                    if action == "publish":
                        owner = "B" if s["round"] == 1 else "A"
                        need(role == owner and s["phase"] in {"A_PLAN", "PUBLISHING"}, "NOT_PUBLICATION_TURN")
                        need(not s["stop_requested"], "STOP_REQUESTED")
                        _publish(repo, s, opts)
                    elif action == "enter":
                        token = opts.get("resume_token")
                        resuming = s["phase"] == "B_RUNNING" and token and token == s.get("resume_token")
                        need(role == "B" and (s["phase"] == "B_READY" or resuming), "ROUND_ALREADY_CLAIMED_OR_NOT_READY")
                        need(not s["stop_requested"], "STOP_REQUESTED")
                        need(opts.get("round") == s["round"], "STALE_ROUND")
                        source_ok(repo, s)
                        if not resuming:
                            need(not (repo / "team-progress.md").read_bytes(), "UNEXPECTED_PROGRESS_BEFORE_ENTER")
                        s["runtime_evidence"]["B"] = glm_session(repo, session)
                        s.pop("resume_token", None)
                        s["phase"] = "B_RUNNING"; s["entered"] = True
                        save(repo, s)
                    elif action == "permit":
                        need(role == "B" and s["phase"] == "B_RUNNING" and s.get("entered"), "NO_EXECUTION_PERMIT")
                        need(not s["stop_requested"] and opts.get("round") == s["round"], "STALE_OR_STOPPED_ROUND")
                        source_ok(repo, s)
                        return s  # read-only checks do not signal sleeping windows
                    elif action == "finish":
                        need(role == "B" and s["phase"] == "B_RUNNING", "NOT_B_EXECUTION_TURN")
                        _finish(repo, s, opts)
                    elif action == "review":
                        need(role == "A" and s["phase"] == "A_REVIEW", "NOT_A_REVIEW_TURN")
                        _review(repo, s, opts)
                    elif action == "resume":
                        need(opts.get("reason"), "EXPLICIT_RESUME_REASON_REQUIRED")
                        # Only original B can re-enter its interrupted run; never start it twice automatically.
                        need(role == "B" and s["phase"] == "B_RUNNING" and not s["stop_requested"], "RESUME_REQUIRES_ORIGINAL_RUNNING_B")
                        source_ok(repo, s)
                        s["resume_authorization"] = {"session": session, "at": stamp(), "reason": opts["reason"]}
                        s["resume_token"] = uuid.uuid4().hex
                        save(repo, s)
                    else: raise ValueError("UNKNOWN_ACTION")
    notify(repo, s["run"])
    return s


def _publish(repo, s, opts):
    rd = round_dir(repo, s)
    if s["phase"] == "A_PLAN":
        draft = local(repo, opts["task"]).read_text(encoding="utf-8-sig").strip()
        need("本次任务" in draft and "done_when" in draft and "team-task-source" not in draft, "TASK_DRAFT_SCHEMA")
        need(s["round"] > 1, "FIRST_TASK_MUST_BE_PREPARED_EXTERNALLY")
        verify_manifest(repo, s["last_live"])
        need(sha(home(repo, s) / "criteria.json") == s["criteria_sha256"], "CRITERIA_CHANGED")
        prefix = (f"workflow_run: {s['run']}\nworkflow_round: {s['round']}\n"
                  f"failure_counts: {json.dumps(s['failures'],ensure_ascii=False)}\n\n")
        body = prefix + draft
        h = digest(body.encode())
        s["source_id"] = "src-" + h[:8]; s["source_sha256"] = h
        s["team_run"] = datetime.now().strftime("%Y%m%d-%H%M%S-") + h[:8]
        task = f'<!-- team-task-source id="{s["source_id"]}" sha256="{h}" status="open" -->\n{body}\n<!-- /team-task-source -->\n'
        preserve(rd / "source.md", task.encode())
        s["phase"] = "PUBLISHING"
        s["pending_old"] = {n: sha(repo / n) if (repo / n).exists() else None for n in ("team-task.md", "team-progress.md")}
        save(repo, s)  # A stopped mid-publication can replay this committed intent.
    data = (rd / "source.md").read_bytes()
    m = SOURCE_RE.fullmatch(data.decode().rstrip("\n"))
    need(m is not None and m[1] == s["source_id"] and m[2] == s["source_sha256"] and
         digest(m[3].encode()) == s["source_sha256"], "INVALID_STAGED_SOURCE")
    for name, new in (("team-task.md", data), ("team-progress.md", b"")):
        p = repo / name
        current = sha(p) if p.exists() else None
        need(current in {s["pending_old"][name], digest(new)}, "PUBLICATION_FILE_DRIFT")
    atomic(repo / "team-task.md", data)
    atomic(repo / "team-progress.md", b"")
    s["phase"] = "B_READY"; s["entered"] = False
    save(repo, s)


def _finish(repo, s, opts):
    report = read_json(local(repo, opts["report"]))
    outcome = report.get("outcome")
    need(outcome in {"complete", "blocked", "halted"}, "INVALID_OUTCOME")
    need(isinstance(report.get("summary"), str) and report["summary"].strip(), "SUMMARY_REQUIRED")
    s["failures"] = counts(s, report.get("failure_counts"))
    text = source_ok(repo, s)
    progress = (repo / "team-progress.md").read_text(encoding="utf-8-sig")
    h = headers(progress)
    need(h.get("run_id") == s["team_run"] and h.get("source_block_id") == s["source_id"], "TEAM_IDENTITY_MISMATCH")
    if outcome == "complete":
        need(h.get("run_status") == "COMPLETE" and p6_closed(progress), "TEAM_P6_NOT_COMPLETE")
        contract_ok(repo, s, text, progress)
    else:
        need(h.get("run_status") in {"WAIT_HUMAN", "HALTED", "BLOCKED"}, "BLOCKED_PROGRESS_REQUIRED")
    manifest = report.get("artifacts")
    need(isinstance(manifest, dict) and (manifest or outcome != "complete"), "NONEMPTY_ARTIFACTS_REQUIRED")
    verify_manifest(repo, manifest)
    report["evidence_hashes"] = evidence(repo, report.get("evidence"))
    rd = round_dir(repo, s)
    archive_live(repo, rd / "execution")
    preserve(rd / "handoff.json", encode(report))
    s["handoff_sha256"] = sha(rd / "handoff.json")
    s["phase"] = "CANCELLED" if s["stop_requested"] else "A_REVIEW"
    s["last_live"] = {n: sha(repo / n) for n in ("team-task.md", "team-progress.md")}
    save(repo, s)


def _review(repo, s, opts):
    rd = round_dir(repo, s)
    need(sha(rd / "handoff.json") == s["handoff_sha256"], "HANDOFF_CHANGED")
    handoff = read_json(rd / "handoff.json")
    verify_manifest(repo, s["last_live"])
    verify_manifest(repo, handoff["artifacts"])
    verify_manifest(repo, handoff["evidence_hashes"])
    cp = home(repo, s) / "criteria.json"
    need(sha(cp) == s["criteria_sha256"], "CRITERIA_CHANGED")
    criteria = read_json(cp)["items"]
    review = read_json(local(repo, opts["report"]))
    checks = review.get("checks")
    need(isinstance(checks, list) and all(isinstance(x, dict) for x in checks), "CHECKS_REQUIRED")
    ids = [x.get("id") for x in checks]
    need(len(ids) == len(set(ids)) and set(ids) == {x["id"] for x in criteria}, "REVIEW_COVERAGE_INCOMPLETE")
    for check in checks:
        need(check.get("status") in {"PASS_DYNAMIC", "FAIL", "BLOCKED", "STATIC_ONLY", "EXEMPT"}, "INVALID_CHECK_STATUS")
        check["evidence_hashes"] = evidence(repo, check.get("evidence"))
        if check["status"] == "EXEMPT": need(check.get("clause"), "EXEMPTION_ORIGINAL_CLAUSE_REQUIRED")
    decision = review.get("decision")
    need(decision in {"pass", "rework", "pause"}, "INVALID_REVIEW_DECISION")
    need(review.get("summary"), "REVIEW_SUMMARY_REQUIRED")
    s["failures"] = counts(s, review.get("failure_counts"))
    if decision == "pass":
        need(handoff["outcome"] == "complete" and all(x["status"] in {"PASS_DYNAMIC", "EXEMPT"} for x in checks), "GLOBAL_PASS_NOT_PROVEN")
    if handoff["outcome"] != "complete": need(decision == "pause", "TEAM_HUMAN_GATE_CANNOT_AUTO_REWORK")
    preserve(rd / "review.json", encode(review))
    s["history"].append({"round": s["round"], "decision": decision, "review_sha256": sha(rd / "review.json")})
    if decision == "pass": s["phase"] = "DONE"
    elif decision == "pause" or any(v >= 3 for v in s["failures"].values()): s["phase"] = "PAUSED"
    elif s["round"] >= s["max_round"]: s["phase"] = "LIMIT"
    else: s["round"] += 1; s["phase"] = "A_PLAN"
    save(repo, s)


def wait(repo, session, run, observed, seconds=3600):
    repo = Path(repo).resolve()
    need(type(seconds) is int and 1 <= seconds <= 3600, "WAIT_TIMEOUT_RANGE")
    need(type(observed) is int and observed >= 0, "OBSERVED_SEQ_REQUIRED")
    need(run, "EXPECTED_RUN_REQUIRED")
    with locked(repo):
        s = load(repo); role = bound(s, session, run=run)
    event = Handle(key(repo, run + "|" + role))
    # One waiter per bound role; duplicate background notifications cannot multiply listeners.
    single = Handle(key(repo, run + "|waiter|" + role), mutex=True)
    acquired = False
    start = time.monotonic()
    try:
        acquired = single.wait(0)
        need(acquired, "WAITER_ALREADY_RUNNING")
        while True:
            with locked(repo):
                s = load(repo); bound(s, session, role, run)
            need(s["seq"] >= observed, "SEQ_REGRESSION")
            publishing = s["phase"] == "PUBLISHING" and role == ("B" if s["round"] == 1 else "A")
            actionable = publishing or (role == "A" and s["phase"] in {"A_PLAN", "A_REVIEW"}) or (role == "B" and s["phase"] == "B_READY")
            if actionable or s["phase"] in TERMINAL or s["phase"] == "PAUSED" or s["stop_requested"]:
                return {"event": "TEAM_WORKFLOW_WAKE", "run": run, "role": role, "phase": s["phase"], "round": s["round"], "seq": s["seq"], "elapsed_ms": int((time.monotonic()-start)*1000)}
            remaining = seconds - (time.monotonic() - start)
            if remaining <= 0:
                return {"event": "TEAM_WORKFLOW_TIMEOUT", "run": run, "role": role, "seq": s["seq"], "elapsed_ms": int((time.monotonic()-start)*1000)}
            event.wait(remaining * 1000)  # no polling, no stdout while waiting
    finally:
        if acquired: single.api.ReleaseMutex(single.handle)
        single.close(); event.close()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("action", choices=["init", "join", "status", "publish", "enter", "permit", "finish", "review", "wait", "resume", "stop", "archive", "pause"])
    ap.add_argument("--repo", required=True); ap.add_argument("--session", default="")
    ap.add_argument("--run"); ap.add_argument("--baseline"); ap.add_argument("--max-round", type=int)
    ap.add_argument("--task"); ap.add_argument("--criteria"); ap.add_argument("--report")
    ap.add_argument("--round", type=int); ap.add_argument("--observed-seq", type=int); ap.add_argument("--timeout", type=int, default=3600)
    ap.add_argument("--reason"); ap.add_argument("--resume-token")
    a = vars(ap.parse_args()); action = a.pop("action"); repo = a.pop("repo"); session = a.pop("session")
    try:
        if action == "wait": result = wait(repo, session, a["run"], a["observed_seq"], a["timeout"])
        else: result = operation(repo, action, session, **a)
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print(json.dumps({"event": "TEAM_WORKFLOW_ERROR", "error": str(exc)}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"): sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
