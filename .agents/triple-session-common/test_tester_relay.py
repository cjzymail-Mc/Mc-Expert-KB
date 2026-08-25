#!/usr/bin/env python3

from __future__ import annotations

import json
import hashlib
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest


SCRIPT = Path(__file__).with_name("tester-relay.py")


class RelayTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve()
        self.dev = self.root / "dev"
        self.prod = self.root / "prod"
        self.dev.mkdir()
        self.prod.mkdir()
        (self.prod / "temp.md").write_text("", encoding="utf-8")
        self.planner = "planner-token"
        self.tester = "tester-token"

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def run_relay(self, action: str, *args: str, expected: int = 0) -> dict:
        command = [sys.executable, "-X", "utf8", str(SCRIPT), action, "--root", str(self.prod), *args]
        result = subprocess.run(command, text=True, encoding="utf-8", capture_output=True, check=False)
        self.assertEqual(expected, result.returncode, msg=f"stdout={result.stdout}\nstderr={result.stderr}")
        return json.loads(result.stdout) if result.stdout.strip() else {"stderr": result.stderr.strip()}

    def write_temp(self, body: str) -> None:
        (self.prod / "temp.md").write_text(body, encoding="utf-8")

    def message(self, seq: int, action: str, release_id: str = "release-1", extra: str = "") -> str:
        return (
            "TRIPLE_TEST_RELAY=v1\n"
            "run_id: run-1\n"
            f"relay_seq: {seq}\n"
            f"release_id: {release_id}\n"
            f"action: {action}\n"
            "source_manifest_sha256: manifest-hash\n"
            "approved_artifact_sha256: N/A\n"
            f"{extra}"
        )

    def write_artifact(self, name: str, body: bytes) -> tuple[Path, str]:
        path = self.prod / name
        path.write_bytes(body)
        return path, hashlib.sha256(body).hexdigest()

    def init_run(self) -> None:
        self.write_temp(self.message(0, "DEPLOY_AND_BUILD_YAML"))
        self.run_relay(
            "init",
            "--run-id", "run-1",
            "--dev-repo", str(self.dev),
            "--release-id", "release-1",
            "--worker-token", self.planner,
        )

    def test_full_relay_cycle_and_temp_clear(self) -> None:
        self.init_run()
        self.assertEqual(0, (self.prod / "temp.md").stat().st_size)
        self.run_relay("claim", "--role", "tester", "--worker-token", self.tester, "--expected-run-id", "run-1")
        self.run_relay("consume", "--role", "tester", "--worker-token", self.tester, "--expected-run-id", "run-1")
        self.write_temp(self.message(1, "RESULT", extra="status: YAML_PENDING_USER_REVIEW\n"))
        state = self.run_relay(
            "handoff", "--role", "tester", "--to", "planner", "--worker-token", self.tester,
            "--expected-run-id", "run-1",
        )["state"]
        self.assertEqual("planner", state["turn"])
        self.assertEqual(0, (self.prod / "temp.md").stat().st_size)
        self.run_relay("consume", "--role", "planner", "--worker-token", self.planner, "--expected-run-id", "run-1")
        yaml_path, yaml_hash = self.write_artifact("metadata.yaml", b"project: demo\n")
        pending = self.run_relay(
            "wait-human", "--role", "planner", "--worker-token", self.planner,
            "--expected-run-id", "run-1", "--approval-kind", "yaml",
            "--artifact-path", str(yaml_path), "--artifact-sha256", yaml_hash,
            "--reason", "Review YAML",
        )
        approval_id = pending["state"]["pending_approval"]["id"]
        self.run_relay(
            "resolve-human", "--role", "planner", "--worker-token", self.planner,
            "--expected-run-id", "run-1", "--decision", "approve", "--approval-id", approval_id,
        )
        self.write_temp(self.message(2, "CONTINUE_PPT"))
        self.run_relay(
            "handoff", "--role", "planner", "--to", "tester", "--worker-token", self.planner,
            "--expected-run-id", "run-1", "--release-id", "release-1",
        )
        self.run_relay("consume", "--role", "tester", "--worker-token", self.tester, "--expected-run-id", "run-1")
        self.write_temp(self.message(3, "RESULT", extra="status: PPT_VISUAL_PENDING\n"))
        self.run_relay(
            "handoff", "--role", "tester", "--to", "planner", "--worker-token", self.tester,
            "--expected-run-id", "run-1",
        )
        self.run_relay("consume", "--role", "planner", "--worker-token", self.planner, "--expected-run-id", "run-1")
        ppt_path, ppt_hash = self.write_artifact("report.pptx", b"fake-pptx")
        pending = self.run_relay(
            "wait-human", "--role", "planner", "--worker-token", self.planner,
            "--expected-run-id", "run-1", "--approval-kind", "ppt",
            "--artifact-path", str(ppt_path), "--artifact-sha256", ppt_hash,
            "--reason", "Review PPT",
        )
        approval_id = pending["state"]["pending_approval"]["id"]
        self.run_relay(
            "resolve-human", "--role", "planner", "--worker-token", self.planner,
            "--expected-run-id", "run-1", "--decision", "approve", "--approval-id", approval_id,
        )
        self.write_temp(self.message(4, "CONTINUE_WORD"))
        self.run_relay(
            "handoff", "--role", "planner", "--to", "tester", "--worker-token", self.planner,
            "--expected-run-id", "run-1", "--release-id", "release-1",
        )
        self.run_relay("consume", "--role", "tester", "--worker-token", self.tester, "--expected-run-id", "run-1")
        self.write_temp(self.message(5, "RESULT", extra="status: PRODUCTION_TEST_PASS\n"))
        self.run_relay(
            "handoff", "--role", "tester", "--to", "planner", "--worker-token", self.tester,
            "--expected-run-id", "run-1",
        )
        self.run_relay("consume", "--role", "planner", "--worker-token", self.planner, "--expected-run-id", "run-1")
        done = self.run_relay("done", "--role", "planner", "--worker-token", self.planner, "--expected-run-id", "run-1")
        self.assertEqual("done", done["state"]["status"])

    def test_human_approval_rejects_changed_artifact(self) -> None:
        self.init_run()
        self.run_relay("claim", "--role", "tester", "--worker-token", self.tester, "--expected-run-id", "run-1")
        self.run_relay("consume", "--role", "tester", "--worker-token", self.tester, "--expected-run-id", "run-1")
        self.write_temp(self.message(1, "RESULT", extra="status: YAML_PENDING_USER_REVIEW\n"))
        self.run_relay(
            "handoff", "--role", "tester", "--to", "planner", "--worker-token", self.tester,
            "--expected-run-id", "run-1",
        )
        self.run_relay("consume", "--role", "planner", "--worker-token", self.planner, "--expected-run-id", "run-1")
        yaml_path, yaml_hash = self.write_artifact("metadata.yaml", b"v1")
        pending = self.run_relay(
            "wait-human", "--role", "planner", "--worker-token", self.planner,
            "--expected-run-id", "run-1", "--approval-kind", "yaml",
            "--artifact-path", str(yaml_path), "--artifact-sha256", yaml_hash,
            "--reason", "Review YAML",
        )
        yaml_path.write_bytes(b"v2")
        rejected = self.run_relay(
            "resolve-human", "--role", "planner", "--worker-token", self.planner,
            "--expected-run-id", "run-1", "--decision", "approve",
            "--approval-id", pending["state"]["pending_approval"]["id"], expected=2,
        )
        self.assertIn("ARTIFACT_HASH_MISMATCH", rejected["stderr"])

    def test_new_release_updates_binding_and_invalidates_approvals(self) -> None:
        self.init_run()
        self.run_relay("claim", "--role", "tester", "--worker-token", self.tester, "--expected-run-id", "run-1")
        self.run_relay("consume", "--role", "tester", "--worker-token", self.tester, "--expected-run-id", "run-1")
        self.write_temp(self.message(1, "RESULT", extra="status: REWORK_REQUIRED\n"))
        self.run_relay(
            "handoff", "--role", "tester", "--to", "planner", "--worker-token", self.tester,
            "--expected-run-id", "run-1",
        )
        self.run_relay("consume", "--role", "planner", "--worker-token", self.planner, "--expected-run-id", "run-1")
        state_path = self.prod / ".triple-tester-state.json"
        state = json.loads(state_path.read_text(encoding="utf-8"))
        state["approvals"] = {"yaml": {"artifact_sha256": "old"}}
        state_path.write_text(json.dumps(state), encoding="utf-8")
        self.write_temp(self.message(2, "DEPLOY_AND_BUILD_YAML", release_id="release-2"))
        result = self.run_relay(
            "handoff", "--role", "planner", "--to", "tester", "--worker-token", self.planner,
            "--expected-run-id", "run-1", "--release-id", "release-2",
        )
        self.assertEqual("release-2", result["state"]["release_id"])
        self.assertEqual({}, result["state"]["approvals"])

    def test_wrong_turn_and_token_fail_closed(self) -> None:
        self.init_run()
        wrong_turn = self.run_relay(
            "consume", "--role", "planner", "--worker-token", self.planner,
            "--expected-run-id", "run-1", expected=2,
        )
        self.assertIn("TURN_MISMATCH", wrong_turn["stderr"])
        self.run_relay("claim", "--role", "tester", "--worker-token", self.tester, "--expected-run-id", "run-1")
        wrong_token = self.run_relay(
            "consume", "--role", "tester", "--worker-token", "not-the-token",
            "--expected-run-id", "run-1", expected=2,
        )
        self.assertIn("WORKER_TOKEN_MISMATCH", wrong_token["stderr"])

    def test_terminal_archive_allows_clean_next_run(self) -> None:
        self.init_run()
        self.run_relay("cancel", "--role", "planner", "--worker-token", self.planner, "--expected-run-id", "run-1")
        archived = self.run_relay("archive", "--expected-run-id", "run-1")
        self.assertTrue(Path(archived["archive_path"]).is_dir())
        self.assertFalse((self.prod / ".triple-tester-state.json").exists())
        self.write_temp(self.message(0, "DEPLOY_AND_BUILD_YAML", release_id="release-2").replace("run_id: run-1", "run_id: run-2"))
        second = self.run_relay(
            "init", "--run-id", "run-2", "--dev-repo", str(self.dev), "--release-id", "release-2",
            "--worker-token", self.planner,
        )
        self.assertEqual("run-2", second["state"]["run_id"])

    def test_goal_contracts_bind_both_repositories(self) -> None:
        planner = self.run_relay(
            "goal-contract", "--role", "planner", "--dev-repo", str(self.dev),
            "--double-worker-token", self.planner, "--relay-worker-token", "relay-token",
            "--prepared-task-sha256", "abc123",
        )
        self.assertEqual("TRIPLE_PLANNER_GOAL_ENVELOPE=v1", planner["envelope"])
        self.assertEqual("RESOLVED_PATH_IDENTITY_V1", planner["path_identity"])
        self.assertIn("PATH_IDENTITY=RESOLVED_PATH_IDENTITY_V1", planner["goal_objective"])
        self.assertIn("development_repo=", planner["goal_objective"])
        tester = self.run_relay("goal-contract", "--role", "tester", "--worker-token", self.tester)
        self.assertEqual("TRIPLE_TESTER_GOAL_ENVELOPE=v1", tester["envelope"])
        self.assertEqual("RESOLVED_PATH_IDENTITY_V1", tester["path_identity"])

    def test_config_inherits_double_session_values(self) -> None:
        result = self.run_relay("config")["config"]
        double_config_path = SCRIPT.parents[1] / "double-session-common" / "double-session-config.json"
        expected = json.loads(double_config_path.read_text(encoding="utf-8"))
        self.assertEqual(expected["planner_interval_seconds"], result["role_intervals"]["planner"])
        self.assertEqual(expected["coder_interval_seconds"], result["role_intervals"]["tester"])
        self.assertEqual(expected["max_budget_seconds"], result["max_budget_seconds"])

    def move_turn_to_planner(self) -> None:
        self.init_run()
        self.run_relay("claim", "--role", "tester", "--worker-token", self.tester, "--expected-run-id", "run-1")
        self.run_relay("consume", "--role", "tester", "--worker-token", self.tester, "--expected-run-id", "run-1")
        self.write_temp(self.message(1, "RESULT", extra="status: REWORK_REQUIRED\n"))
        self.run_relay(
            "handoff", "--role", "tester", "--to", "planner", "--worker-token", self.tester,
            "--expected-run-id", "run-1",
        )

    def test_wait_turn_uses_bounded_timeout_without_polling(self) -> None:
        self.move_turn_to_planner()
        started = time.monotonic()
        result = self.run_relay(
            "wait-turn", "--role", "tester", "--expected-run-id", "run-1",
            "--observed-seq", "1", "--timeout-seconds", "1",
        )
        elapsed = time.monotonic() - started
        self.assertEqual("TIMEOUT", result["result"])
        self.assertGreaterEqual(elapsed, 0.8)
        self.assertLess(elapsed, 3.0)

    @unittest.skipUnless(sys.platform.startswith("win"), "Windows named-event tickle")
    def test_handoff_tickles_waiting_tester(self) -> None:
        self.move_turn_to_planner()
        command = [
            sys.executable, "-X", "utf8", str(SCRIPT), "wait-turn", "--root", str(self.prod),
            "--role", "tester", "--expected-run-id", "run-1", "--observed-seq", "1",
            "--timeout-seconds", "5",
        ]
        waiter = subprocess.Popen(command, text=True, encoding="utf-8", stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        time.sleep(0.4)
        self.run_relay("consume", "--role", "planner", "--worker-token", self.planner, "--expected-run-id", "run-1")
        self.write_temp(self.message(2, "DEPLOY_AND_BUILD_YAML", release_id="release-2"))
        self.run_relay(
            "handoff", "--role", "planner", "--to", "tester", "--worker-token", self.planner,
            "--expected-run-id", "run-1", "--release-id", "release-2",
        )
        stdout, stderr = waiter.communicate(timeout=5)
        self.assertEqual(0, waiter.returncode, msg=f"stdout={stdout}\nstderr={stderr}")
        result = json.loads(stdout)
        self.assertEqual("STATE_READY", result["result"])
        self.assertLess(result["elapsed_ms"], 4500)

    @unittest.skipUnless(sys.platform.startswith("win"), "Windows path separator regression")
    def test_goal_contract_treats_windows_separator_variants_as_one_path(self) -> None:
        dev_with_forward_slashes = str(self.dev).replace("\\", "/")
        planner = self.run_relay(
            "goal-contract", "--role", "planner", "--dev-repo", dev_with_forward_slashes,
            "--double-worker-token", self.planner, "--relay-worker-token", "relay-token",
            "--prepared-task-sha256", "abc123",
        )
        self.assertNotEqual(dev_with_forward_slashes, planner["development_repo"])
        self.assertEqual(self.dev.resolve(), Path(planner["development_repo"]).resolve())


if __name__ == "__main__":
    unittest.main(verbosity=2)
