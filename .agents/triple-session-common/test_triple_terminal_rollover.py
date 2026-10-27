#!/usr/bin/env python3

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
import unittest


STATE_TOOL = Path(__file__).parents[1] / "double-session-common" / "double-session-state.ps1"


class TripleTerminalRolloverTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name).resolve()
        subprocess.run(["git", "init", "--quiet", str(self.repo)], check=True, capture_output=True)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def contract(self, request: str) -> str:
        request_hash = hashlib.sha256(request.encode("utf-8")).hexdigest()
        request_json = json.dumps(request, ensure_ascii=False)
        return f"""DOUBLE_TASK_CONTRACT=v1

## original_request
original_request_sha256: {request_hash}
original_request_json: {request_json}

## authority
target_repo: {self.repo}
authority_sources: ["test"]

## terminal_state
result_state: verified

## scope
in_scope: ["test"]
out_of_scope: ["none"]
read_forbidden: ["none"]
write_forbidden: ["none"]

## guardrails
red_lines: ["two_same_failures"]
human_gates: ["none"]
authorization_boundary: ["temporary fixture only"]

## checkpoints
- id: C1
  depends_on: none
  claim: terminal rollover
  verification: state probe

## done_when
- id: D1
  claim: new run starts after archive
  verification: Init result
  expected: running
  failure_case: Init is rejected

## runtime
planner_runtime: unknown
review_gate: planner_plus_mc_expert
runtime_evidence: test_fixture

## triple_workflow
workflow_mode: planner-coder-tester
development_repo: {self.repo}
source_skill_root: {self.repo}
production_skill_root: {self.repo}
production_project_root: {self.repo}
golden_reference: {self.repo}
tester_may_read_golden: false
yaml_gate: user_sha256_approval
ppt_visual_gate: user_sha256_approval
word_gate: after_ppt_approval
doctor_policy: preserve_runtime_unless_guard_changed
"""

    def run_state(self, action: str, *args: str) -> dict:
        command = [
            "pwsh", "-NoProfile", "-File", str(STATE_TOOL),
            "-Action", action, *args,
        ]
        result = subprocess.run(
            command, cwd=self.repo, text=True, encoding="utf-8",
            capture_output=True, check=False,
        )
        self.assertEqual(0, result.returncode, msg=f"stdout={result.stdout}\nstderr={result.stderr}")
        return json.loads(result.stdout)

    def write_contract(self, request: str) -> str:
        body = self.contract(request)
        encoded = body.encode("utf-8")
        (self.repo / "temp.md").write_bytes(encoded)
        return hashlib.sha256(encoded).hexdigest()

    def test_archived_terminal_route_stays_terminal_but_init_accepts_new_contract(self) -> None:
        repo_arg = str(self.repo)
        old_hash = self.write_contract("old task")
        old_state = self.run_state(
            "Init", "-ExpectedRepo", repo_arg, "-WorkerToken", "old-coder-token",
            "-PreparedTaskSha256", old_hash, "-RuntimeClass", "unknown",
            "-RuntimeEvidence", "test_fixture",
        )
        old_run = old_state["run_id"]
        self.run_state(
            "Cancel", "-ExpectedRepo", repo_arg, "-ExpectedRunId", old_run,
            "-Reason", "test terminal rollover",
        )

        new_hash = self.write_contract("new triple task")
        future = time.time() + 2
        os.utime(self.repo / "temp.md", (future, future))
        before = self.run_state("BootstrapProbe", "-ExpectedRepo", repo_arg)
        self.assertEqual("TERMINAL_ARCHIVE_THEN_PREPARE", before["route"])
        self.assertEqual("CONTRACT_READY", before["terminal_next_route"])

        archived = self.run_state(
            "ArchiveRun", "-ExpectedRepo", repo_arg, "-ExpectedRunId", old_run,
        )
        self.assertTrue(Path(archived["archive"]["archive_path"]).is_file())
        after = self.run_state("BootstrapProbe", "-ExpectedRepo", repo_arg)
        self.assertEqual("TERMINAL_ARCHIVE_THEN_PREPARE", after["route"])
        self.assertEqual("CONTRACT_READY", after["terminal_next_route"])
        self.assertEqual(new_hash, after["task_validation"]["task_sha256"])

        new_state = self.run_state(
            "Init", "-ExpectedRepo", repo_arg, "-WorkerToken", "new-coder-token",
            "-PreparedTaskSha256", new_hash, "-RuntimeClass", "unknown",
            "-RuntimeEvidence", "test_fixture",
        )
        self.assertEqual("running", new_state["status"])
        self.assertNotEqual(old_run, new_state["run_id"])
        self.assertEqual(new_hash, new_state["task_sha256"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
