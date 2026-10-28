"""Archive a previous workflow before an explicitly requested NEW task.

This abandons interrupted work with its evidence intact; it never resumes it,
claims success, kills a process, or impersonates an old bound session.
"""
from __future__ import annotations
import contextlib
import ctypes
from ctypes import wintypes as W
import json
import os
from pathlib import Path
import subprocess

import workflow as w

ROOT_FILES = ("team-task.md", "team-progress.md")
PHASES = w.TERMINAL | {"PUBLISHING", "B_READY", "B_RUNNING", "A_REVIEW", "A_PLAN", "PAUSED"}


def process_start(pid):
    """Return Windows creation FILETIME, None if gone; access errors are unknown."""
    api = ctypes.WinDLL("kernel32", use_last_error=True)
    api.OpenProcess.argtypes = [W.DWORD, W.BOOL, W.DWORD]
    api.OpenProcess.restype = W.HANDLE
    api.GetProcessTimes.argtypes = [W.HANDLE] + [ctypes.POINTER(W.FILETIME)] * 4
    api.GetProcessTimes.restype = W.BOOL
    api.WaitForSingleObject.argtypes = [W.HANDLE, W.DWORD]
    api.WaitForSingleObject.restype = W.DWORD
    api.CloseHandle.argtypes = [W.HANDLE]
    handle = api.OpenProcess(0x1000 | 0x100000, False, pid)
    if not handle:
        if ctypes.get_last_error() == 87: return None
        raise OSError("PROCESS_LIVENESS_UNKNOWN")
    try:
        wait = api.WaitForSingleObject(handle, 0)
        if wait == 0: return None
        w.need(wait == 258, "PROCESS_LIVENESS_UNKNOWN")
        times = [W.FILETIME() for _ in range(4)]
        w.need(api.GetProcessTimes(handle, *(ctypes.byref(t) for t in times)), "PROCESS_LIVENESS_UNKNOWN")
        return str((times[0].dwHighDateTime << 32) | times[0].dwLowDateTime)
    finally:
        api.CloseHandle(handle)


def process_snapshot():
    # Only the census uses PowerShell. Never log command lines or complete registry rows.
    cmd = ("[Console]::OutputEncoding=[System.Text.UTF8Encoding]::new(); "
           "@(Get-CimInstance Win32_Process -ErrorAction Stop | "
           "Select-Object ProcessId,ParentProcessId,Name,CommandLine) | ConvertTo-Json -Compress")
    result = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", cmd],
                            capture_output=True, timeout=20, creationflags=0x08000000)
    w.need(result.returncode == 0, "PROCESS_CENSUS_UNAVAILABLE")
    rows = json.loads(result.stdout.decode("utf-8-sig"))
    w.need(isinstance(rows, list) and any(r.get("ProcessId") == os.getpid() for r in rows),
           "PROCESS_CENSUS_INCOMPLETE")
    return {int(r["ProcessId"]): r for r in rows}


def session_roots():
    roots = [Path.home() / ".claude-glm", Path.home() / ".claude"]
    if os.environ.get("CLAUDE_CONFIG_DIR"): roots.insert(0, Path(os.environ["CLAUDE_CONFIG_DIR"]))
    return list(dict.fromkeys(p.resolve() for p in roots))


def quiescence(repo, s):
    """Conservative one-shot census. No heartbeat-age inference or polling."""
    processes = process_snapshot()
    ancestors, pid = set(), os.getpid()
    while pid and pid not in ancestors:
        ancestors.add(pid)
        pid = int(processes.get(pid, {}).get("ParentProcessId", 0))
    owner_ids = set(s["sessions"].values())
    blockers, relevant_pids, owners, live_session_pids = [], set(), [], set()
    found_registry, records = False, []
    for root in session_roots():
        directory = root / "sessions"
        if not directory.is_dir(): continue
        found_registry = True
        for path in directory.glob("*.json"):
            # Unreadable session records make absence unprovable.
            row = w.read_json(path)
            if Path(row.get("cwd", "")).resolve() == repo or row.get("sessionId") in owner_ids:
                records.append(row)
    w.need(found_registry, "SESSION_CENSUS_UNAVAILABLE")
    for role, sid in s["sessions"].items():
        for saved in s.get("runtime_evidence", {}).get(role, {}).get("processes", []):
            w.need(type(saved.get("pid")) is int and str(saved.get("procStart", "")).isdigit(),
                   "BOUND_PROCESS_EVIDENCE_INVALID")
            records.append(dict(saved, sessionId=sid, cwd=str(repo)))
        w.need(any(row.get("sessionId") == sid for row in records), "BOUND_PROCESS_EVIDENCE_MISSING: " + role)
    seen = set()
    for row in records:
        identity = (row.get("sessionId"), row.get("pid"), row.get("procStart"))
        if identity in seen: continue
        seen.add(identity)
        bound = row.get("sessionId") in owner_ids
        w.need(type(row.get("pid")) is int and row["pid"] > 0, "SESSION_PID_UNKNOWN")
        pid = row["pid"]
        actual_start = process_start(pid)
        expected = row.get("procStart")
        alive = actual_start is not None and (expected is None or str(expected) == actual_start)
        if alive and expected is not None: live_session_pids.add(pid)
        # Even dead parents may have surviving detached descendants.
        relevant_pids.add(pid)
        if bound:
            owners.append({"role": next(k for k,v in s["sessions"].items() if v == row["sessionId"]),
                           "pid": pid, "alive": alive})
            if alive: blockers.append({"kind": "bound_session_alive", "pid": pid})
        elif alive and pid not in ancestors and row.get("status") != "idle":
            blockers.append({"kind": "other_repo_session_busy", "pid": pid})
    # Exclude only the actual maintenance caller's ancestor chain, not a supplied session ID.
    related = relevant_pids - ancestors
    while True:
        expanded = related | {pid for pid,r in processes.items() if int(r.get("ParentProcessId",0)) in related}
        if expanded == related: break
        related = expanded
    repo_text = str(repo).replace("\\", "/").casefold()
    for pid, row in processes.items():
        if pid in ancestors or pid in live_session_pids: continue
        command = (row.get("CommandLine") or "").replace("\\", "/").casefold()
        if (pid in related and pid not in relevant_pids) or repo_text in command or s["run"] in command or any(sid in command for sid in owner_ids):
            blockers.append({"kind": "related_process_alive", "pid": pid, "name": row.get("Name")})
    w.need(not blockers, "OLD_EXECUTORS_NOT_QUIESCENT: " + json.dumps(blockers, ensure_ascii=False))
    return {"checked_at": w.stamp(), "method": "Windows process creation + Claude session census + descendants",
            "bound_processes": owners, "blockers": []}


@contextlib.contextmanager
def no_waiters(repo, s):
    handles = []
    try:
        for role in ("A", "B"):
            h = w.Handle(w.key(repo, s["run"] + "|waiter|" + role), mutex=True)
            acquired = h.wait(0)
            handles.append((h, acquired))
            w.need(acquired, "OLD_WAITER_ALIVE: " + role)
        yield
    finally:
        for h, acquired in reversed(handles):
            if acquired: h.api.ReleaseMutex(h.handle)
            h.close()


def file_bytes(repo):
    return {name: (repo / name).read_bytes() if (repo / name).exists() else None for name in ROOT_FILES}


def owned_roots(repo, s):
    """Never sweep a newly prepared task into an interrupted old run's archive."""
    if s["phase"] == "PUBLISHING" or (s["phase"] == "CANCELLED" and not s.get("entered", False)):
        staged = (w.round_dir(repo, s) / "source.md").read_bytes()
        match = w.SOURCE_RE.fullmatch(staged.decode().rstrip("\n"))
        w.need(match and match[1] == s["source_id"] and match[2] == s["source_sha256"] and
               w.digest(match[3].encode()) == s["source_sha256"], "INVALID_STAGED_SOURCE")
        for name, replacement in (("team-task.md", staged), ("team-progress.md", b"")):
            path = repo / name
            current = w.sha(path) if path.exists() else None
            w.need(current in {s["pending_old"][name], w.digest(replacement)}, "PUBLICATION_FILE_DRIFT")
    else:
        w.source_ok(repo, s)
        progress = (repo / "team-progress.md").read_text(encoding="utf-8-sig")
        if progress.strip():
            h = w.headers(progress)
            w.need(h.get("run_id") == s["team_run"] and h.get("source_block_id") == s["source_id"],
                   "OLD_PROGRESS_OWNERSHIP_UNKNOWN")


def clear_preserved(repo, before):
    # Verify BOTH before clearing either. Empty is a permitted partial-commit retry.
    for name, data in before.items():
        current = (repo / name).read_bytes() if (repo / name).exists() else None
        w.need(current == data or current == b"", "NEW_TASK_FILE_DRIFT: " + name)
    for name, data in before.items():
        if data is not None: w.atomic(repo / name, b"")


def prepare_new(repo, *, request, reason, actor="", session="", run=None, **unused):
    repo = Path(repo).resolve()
    w.need(repo.is_dir() and request and str(request).strip() and reason and str(reason).strip(),
           "EXPLICIT_NEW_TASK_REQUEST_REQUIRED")
    w.need(bool(session) != bool(actor), "CURRENT_SESSION_OR_EXTERNAL_ACTOR_REQUIRED")
    if session: w.glm_session(repo, session)
    caller = {"kind": "claude_glm" if session else "external", "id": session or actor}
    with w.locked(repo):
        state_path = repo / w.STATE
        active = state_path.exists()
        if active:
            s = w.load(repo)
            w.need(run == s["run"], "EXPECTED_CURRENT_RUN_REQUIRED")
            w.need(s["phase"] in PHASES, "UNSUPPORTED_WORKFLOW_PHASE")
        else:
            # Also finish an interrupted cleanup or recognize old official archive residue.
            candidates = []
            base = repo / "team-progress/team-workflow"
            for path in (base.glob("*/state-final.json") if base.exists() else []):
                candidate = w.read_json(path)
                if run and candidate.get("run") != run: continue
                if candidate.get("repo") != str(repo) or candidate.get("version") != 3: continue
                if candidate.get("phase") not in w.TERMINAL: continue
                dest = path.parent
                receipt = dest / "prepare-new/receipt.json"
                current = file_bytes(repo)
                pending = receipt.exists() and w.read_json(receipt).get("status") == "prepared"
                if pending or (any(current.values()) and all(
                    data is None or (dest / "final" / name).is_file() and
                    data == (dest / "final" / name).read_bytes() for name, data in current.items())):
                    candidates.append(candidate)
            w.need(len(candidates) <= 1, "ARCHIVED_RESIDUE_AMBIGUOUS")
            if not candidates:
                return {"event": "TEAM_WORKFLOW_NEW_TASK_READY", "archived": False,
                        "root_task_preserved": bool((repo / "team-task.md").exists() and
                                                    (repo / "team-task.md").read_bytes().strip())}
            s = candidates[0]
        dest = w.home(repo, s)
        receipt_path = dest / "prepare-new/receipt.json"
        interrupted = s["phase"] not in w.TERMINAL
        if receipt_path.exists(): interrupted = w.read_json(receipt_path)["interrupted"]
        # A new task cannot silently reopen a human gate for the SAME baseline.
        if s.get("baseline") and (s["phase"] in {"PAUSED", "LIMIT"} or any(v >= 3 for v in s["failures"].values())):
            w.need((repo / request).resolve() != Path(s["baseline"]).resolve(), "SAME_BASELINE_HUMAN_GATE_REQUIRES_DECISION")
        with no_waiters(repo, s) if interrupted else contextlib.nullcontext():
            if receipt_path.exists():
                receipt = w.read_json(receipt_path)
                w.need(receipt["request"] == request, "PREVIOUS_CLEANUP_REQUEST_MISMATCH")
                before = {name: (dest / "prepare-new" / name).read_bytes() if expected is not None else None
                          for name, expected in receipt["root_hashes"].items()}
                for name, data in before.items():
                    w.need((w.digest(data) if data is not None else None) == receipt["root_hashes"][name],
                           "CLEANUP_BACKUP_CHANGED")
                original = (dest / "prepare-new/state-original.json").read_bytes()
                w.need(w.digest(original) == receipt["state_sha256"], "CLEANUP_STATE_BACKUP_CHANGED")
                s = json.loads(original)
                interrupted = s["phase"] not in w.TERMINAL
                if interrupted: quiescence(repo, s)
                current = state_path.read_bytes() if state_path.exists() else None
                w.need(current in (None, original, w.encode(receipt["final_state"])), "CLEANUP_STATE_DRIFT")
            else:
                quiet = quiescence(repo, s) if interrupted else {"method": "terminal_state"}
                if active and (interrupted or not s.get("last_live")): owned_roots(repo, s)
                before = file_bytes(repo)
                if active and not interrupted and s.get("last_live"):
                    w.verify_manifest(repo, s["last_live"])
                original = state_path.read_bytes() if active else (dest / "state-final.json").read_bytes()
                w.preserve(dest / "prepare-new/state-original.json", original)
                for name, data in before.items():
                    if data is not None: w.preserve(dest / "prepare-new" / name, data)
                final = dict(s)
                if interrupted:
                    final.update(phase="CANCELLED", stop_requested=True, seq=s["seq"]+1, updated=w.stamp(),
                                 abandoned_for_new_task={"from_phase": s["phase"], "request": request,
                                                         "reason": reason, "actor": caller})
                receipt = {"version": 1, "status": "prepared", "run": s["run"], "request": request,
                           "reason": reason, "actor": caller, "created": w.stamp(), "from_phase": s["phase"],
                           "interrupted": interrupted, "quiescence": quiet,
                           "state_sha256": w.digest(original), "final_state": final,
                           "root_hashes": {n: w.digest(b) if b is not None else None for n,b in before.items()},
                           "unfinished_evidence": "Original progress, contracts, failures and round archives remain unchanged."}
                w.preserve(receipt_path, w.encode(receipt))
            # Replay is safe after any of the following writes; conflict never overwrites evidence.
            final = receipt["final_state"]
            for name, data in before.items():
                if data is not None: w.preserve(dest / "final" / name, data)
            w.preserve(dest / "state-final.json", w.encode(final))
            if active:
                expected = state_path.read_bytes()
                w.need(expected in (original, w.encode(final)), "CLEANUP_STATE_DRIFT")
                if interrupted: w.atomic(state_path, w.encode(final))
            clear_preserved(repo, before)
            if state_path.exists():
                w.need(state_path.read_bytes() in (original, w.encode(final)), "CLEANUP_STATE_DRIFT")
                state_path.unlink()
            receipt["status"] = "complete"
            w.atomic(receipt_path, w.encode(receipt))
    w.notify(repo, s["run"])
    return {"event": "TEAM_WORKFLOW_NEW_TASK_READY", "archived": True, "run": s["run"],
            "previous_phase": receipt["from_phase"], "final_phase": final["phase"],
            "unfinished": final["phase"] != "DONE", "interrupted": receipt["interrupted"], "root_task_preserved": False,
            "receipt": str(receipt_path.relative_to(repo))}
