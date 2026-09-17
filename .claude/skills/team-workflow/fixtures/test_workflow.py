"""Isolated Windows mechanics tests, NOT a Claude-GLM production acceptance.

Synthetic transcripts exercise metadata parsing only. Real subprocesses exercise
Windows events, mutex ownership, timeout, and stdout silence.
"""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
import uuid

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/workflow.py"
spec = importlib.util.spec_from_file_location("workflow", SCRIPT)
w = importlib.util.module_from_spec(spec)
spec.loader.exec_module(w)


@unittest.skipUnless(os.name == "nt", "requires Windows named events")
class RelayTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="team-workflow-test-")
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name) / "repo [双窗口]"
        self.repo.mkdir()
        self.a, self.b = str(uuid.uuid4()), str(uuid.uuid4())
        self.config = Path(self.temp.name) / "synthetic-claude-config"
        self.env = patch.dict(os.environ, {"CLAUDE_CONFIG_DIR": str(self.config), "PYTHONIOENCODING": "utf-8"})
        self.env.start(); self.addCleanup(self.env.stop)
        for sid in (self.a, self.b): self.transcript(sid, "glm-test-fixture")
        self.put("draft.md", "## 本次任务\n生成 result.txt\n## done_when\nD1: 实物包含 target")
        self.put("team-task.md", (self.repo / "draft.md").read_text(encoding="utf-8"))
        self.json("criteria-input.json", {"items": [{"id": "D1", "requirement": "必须有 target", "source": "baseline.md 第1行", "verify": "读取实际 result.txt"}]})
        self.s = None

    def transcript(self, sid, model):
        p = self.config / "projects/fixture" / (sid + ".jsonl")
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps({"type": "assistant", "cwd": str(self.repo), "message": {"model": model}}) + "\n", encoding="utf-8")

    def put(self, name, body):
        p = self.repo / name; p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body, encoding="utf-8", newline="\n")

    def json(self, name, data): self.put(name, json.dumps(data, ensure_ascii=False))

    def op(self, action, role="A", **opts):
        if self.s and action != "init": opts.setdefault("run", self.s["run"])
        self.s = w.operation(self.repo, action, self.a if role == "A" else self.b, **opts)
        return self.s

    def init(self):
        self.op("init", "B")

    def join_a(self, maximum=3):
        if not (self.repo / "baseline.md").exists():
            self.put("baseline.md", "冻结要求：result.txt 中必须有 target。\n保留业务范围。")
        return self.op("join", baseline=str(self.repo / "baseline.md"),
                       max_round=maximum, criteria="criteria-input.json")

    def ready(self, maximum=3):
        self.init(); self.join_a(maximum)

    def running(self):
        self.ready(); self.op("enter", "B", round=1)

    def completed_files(self, outcome="complete"):
        s = self.s
        body = "### 冻结合同\n- done_when: result.txt 包含 target"
        cid = "ctr-" + w.digest(body.encode())[:8]
        p = self.repo / "team-task.md"
        with p.open("a", encoding="utf-8", newline="\n") as f:
            f.write(f'\n<!-- team-task-contract run_id="{s["team_run"]}" source_block_id="{s["source_id"]}" contract_id="{cid}" status="frozen" profile="minimal" -->\n{body}\n<!-- /team-task-contract -->\n')
        status, mark = ("COMPLETE", "P6✓") if outcome == "complete" else ("WAIT_HUMAN", "P6·")
        self.put("team-progress.md", f'> run_id: {s["team_run"]}\n> source_block_id: {s["source_id"]}\n> contract_id: {cid}\n> effective_contract_id: {cid}\n> run_status: {status}\n> 漏斗: P0✓ P0.5✓ P1✓ P2✓ P3✓ P4✓ P5✓ {mark}\n')
        self.put("result.txt", "target\n")
        self.put(f"evidence/exec-{s['round']}.txt", "observed target; fixture only")
        self.json("handoff-input.json", {"outcome": outcome, "summary": "fixture outcome", "artifacts": {"result.txt": w.sha(self.repo / "result.txt")}, "evidence": [f"evidence/exec-{s['round']}.txt"], "failure_counts": dict(s["failures"])})

    def finish(self, outcome="complete"):
        self.completed_files(outcome); self.op("finish", "B", report="handoff-input.json")

    def review_input(self, decision="rework", status="FAIL", counts=None):
        n = self.s["round"]
        self.put(f"evidence/review-{n}.txt", "independent fixture observation")
        self.json("review-input.json", {"decision": decision, "summary": "fixture acceptance", "failure_counts": self.s["failures"] if counts is None else counts, "checks": [{"id": "D1", "status": status, "evidence": [f"evidence/review-{n}.txt"]}]})

    def cli(self, action, role="A", **opts):
        args = [sys.executable, str(SCRIPT), action, "--repo", str(self.repo), "--session", self.a if role == "A" else self.b, "--run", self.s["run"]]
        for k, v in opts.items(): args += ["--" + k.replace("_", "-"), str(v)]
        return args

    def test_runtime_and_old_task_gate(self):
        self.transcript(self.b, "claude-opus")
        with self.assertRaisesRegex(ValueError, "RUNTIME_NOT_PROVEN"): self.init()
        self.transcript(self.b, "glm-test-fixture")
        self.put("team-progress.md", "> run_status: ACTIVE\n")
        with self.assertRaisesRegex(ValueError, "OLD_RUN_UNCLOSED"): self.init()
        self.assertFalse((self.repo / w.STATE).exists())

    def test_initial_archive_precedes_root_replacement(self):
        original = (self.repo / "team-task.md").read_bytes()
        self.put("team-progress.md", "> run_status: COMPLETE\n> 漏斗: P6✓\n")
        self.ready()
        self.assertEqual((w.home(self.repo, self.s) / "before-start/team-task.md").read_bytes(), original)
        self.assertEqual(w.SOURCE_RE.fullmatch((self.repo / "team-task.md").read_text(encoding="utf-8").rstrip("\n"))[3], original.decode())
        self.assertEqual((self.repo / "team-progress.md").read_bytes(), b"")

    def test_role_run_and_duplicate_enter(self):
        self.ready()
        with self.assertRaisesRegex(ValueError, "DISTINCT_SESSIONS"):
            w.operation(self.repo, "join", self.b, run=self.s["run"])
        with self.assertRaisesRegex(ValueError, "STALE_WORKFLOW_RUN"):
            w.operation(self.repo, "enter", self.b, run="old", round=1)
        with self.assertRaisesRegex(ValueError, "EXPECTED_RUN_REQUIRED"):
            w.operation(self.repo, "enter", self.b, round=1)
        self.op("enter", "B", round=1)
        with self.assertRaisesRegex(ValueError, "ALREADY_CLAIMED"): self.op("enter", "B", round=1)

    def test_concurrent_enter_only_one_wins(self):
        self.ready()
        ps = [subprocess.Popen(self.cli("enter", "B", round=1), stdout=subprocess.PIPE, stderr=subprocess.PIPE) for _ in range(2)]
        try:
            results = [p.communicate(timeout=10) for p in ps]
            self.assertEqual(sorted(p.returncode for p in ps), [0, 1], results)
            self.assertEqual(w.load(self.repo)["phase"], "B_RUNNING")
        finally:
            for p in ps:
                if p.poll() is None: p.kill(); p.wait()

    def test_source_blocks_b_and_baseline_blocks_a(self):
        self.ready()
        self.put("team-task.md", (self.repo / "team-task.md").read_text(encoding="utf-8").replace("生成", "修改"))
        with self.assertRaisesRegex(ValueError, "SOURCE_CHANGED"): self.op("enter", "B", round=1)
        self.put("baseline.md", "changed outside authorization")
        with self.assertRaisesRegex(ValueError, "BASELINE_CHANGED"): self.op("join")
        self.op("pause", "B", reason="source and baseline changed")
        self.assertEqual(self.s["phase"], "PAUSED")

    def test_early_pass_stops_at_one(self):
        self.running(); self.finish()
        self.review_input("pass", "PASS_DYNAMIC")
        self.op("review", report="review-input.json")
        self.assertEqual((self.s["phase"], self.s["round"]), ("DONE", 1))
        with self.assertRaisesRegex(ValueError, "TERMINAL"): self.op("publish", task="draft.md")

    def test_max_three_includes_third_review_and_no_fourth(self):
        self.ready()
        for n in range(1, 4):
            self.op("enter", "B", round=n); self.finish()
            self.assertEqual(self.s["phase"], "A_REVIEW")
            self.review_input(); self.op("review", report="review-input.json")
            if n < 3:
                self.assertEqual(self.s["round"], n + 1)
                self.op("publish", task="draft.md")
        self.assertEqual((self.s["phase"], self.s["round"], len(self.s["history"])), ("LIMIT", 3, 3))
        self.assertFalse((w.home(self.repo, self.s) / "round-04").exists())

    def test_failure_counts_survive_rounds_and_fuse(self):
        self.ready()
        for n in range(1, 4):
            self.op("enter", "B", round=n); self.finish()
            self.review_input(counts={"review|content|missing|D1": n})
            self.op("review", report="review-input.json")
            if n < 3: self.op("publish", task="draft.md")
        self.assertEqual(self.s["phase"], "PAUSED")
        self.assertEqual(self.s["failures"]["review|content|missing|D1"], 3)

    def test_failure_count_reset_rejected(self):
        self.running(); self.finish()
        self.review_input(counts={"review|content|missing|D1": 1})
        self.op("review", report="review-input.json"); self.op("publish", task="draft.md")
        self.op("enter", "B", round=2); self.completed_files()
        d = w.read_json(self.repo / "handoff-input.json"); d["failure_counts"] = {}
        self.json("handoff-input.json", d)
        with self.assertRaisesRegex(ValueError, "FAILURE_COUNT_RESET"): self.op("finish", "B", report="handoff-input.json")

    def test_incomplete_or_static_review_cannot_pass(self):
        self.running(); self.finish(); self.review_input("pass", "STATIC_ONLY")
        with self.assertRaisesRegex(ValueError, "GLOBAL_PASS_NOT_PROVEN"): self.op("review", report="review-input.json")
        d = w.read_json(self.repo / "review-input.json"); d["checks"] = []
        self.json("review-input.json", d)
        with self.assertRaisesRegex(ValueError, "COVERAGE_INCOMPLETE"): self.op("review", report="review-input.json")

    def test_human_gate_cannot_become_auto_rework(self):
        self.running(); self.finish("blocked"); self.review_input()
        with self.assertRaisesRegex(ValueError, "HUMAN_GATE_CANNOT"): self.op("review", report="review-input.json")
        self.review_input("pause", "BLOCKED"); self.op("review", report="review-input.json")
        self.assertEqual(self.s["phase"], "PAUSED")

    def test_artifact_drift_blocks_review(self):
        self.running(); self.finish(); self.review_input("pass", "PASS_DYNAMIC")
        self.put("result.txt", "changed after B handoff")
        with self.assertRaisesRegex(ValueError, "ARTIFACT_CHANGED"): self.op("review", report="review-input.json")
        self.assertEqual(w.load(self.repo)["phase"], "A_REVIEW")

    def test_contract_and_p6_are_live_not_report_claim(self):
        self.running(); self.completed_files()
        p = self.repo / "team-progress.md"
        correct = p.read_text(encoding="utf-8")
        self.put("team-progress.md", correct.replace("P6✓", "P6·") + "历史记录：P6✓\n")
        with self.assertRaisesRegex(ValueError, "P6_NOT_COMPLETE"): self.op("finish", "B", report="handoff-input.json")
        self.put("team-progress.md", correct)
        p = self.repo / "team-task.md"
        self.put("team-task.md", p.read_text(encoding="utf-8").replace("done_when: result.txt", "done_when: different.txt"))
        with self.assertRaisesRegex(ValueError, "CONTRACT_INVALID"): self.op("finish", "B", report="handoff-input.json")

    def test_archive_failure_never_hands_off(self):
        self.running(); self.completed_files()
        real = w.preserve
        def fail_archive(path, data):
            if Path(path).name == "team-progress.md": raise OSError("simulated disk failure")
            return real(path, data)
        with patch.object(w, "preserve", fail_archive):
            with self.assertRaisesRegex(OSError, "disk failure"): self.op("finish", "B", report="handoff-input.json")
        self.assertEqual(w.load(self.repo)["phase"], "B_RUNNING")
        self.op("finish", "B", report="handoff-input.json")
        self.assertEqual(self.s["phase"], "A_REVIEW")

    def test_publish_crash_replay_and_staged_hash(self):
        real = w.atomic
        def fail_progress(path, data):
            if Path(path).name == "team-progress.md": raise OSError("simulated publication crash")
            return real(path, data)
        with patch.object(w, "atomic", fail_progress):
            with self.assertRaises(OSError): self.init()
        self.s = w.load(self.repo)
        self.assertEqual(self.s["phase"], "PUBLISHING")
        source = w.round_dir(self.repo, self.s) / "source.md"
        original = source.read_bytes(); source.write_bytes(original.replace(b"D1", b"D2"))
        with self.assertRaisesRegex(ValueError, "INVALID_STAGED_SOURCE"): self.op("publish", "B")
        source.write_bytes(original); self.op("publish", "B")
        self.assertEqual(self.s["phase"], "B_READY")
        self.assertEqual((self.repo / "team-progress.md").read_bytes(), b"")

    def test_resume_token_once_preserves_run(self):
        self.running(); old_run = self.s["team_run"]
        self.put("team-progress.md", "interrupted progress")
        self.op("resume", "B", reason="user explicitly resumed same task")
        token = self.s["resume_token"]
        self.op("enter", "B", round=1, resume_token=token)
        self.assertEqual(self.s["team_run"], old_run)
        self.assertEqual((self.repo / "team-progress.md").read_text(), "interrupted progress")
        with self.assertRaisesRegex(ValueError, "ALREADY_CLAIMED"): self.op("enter", "B", round=1, resume_token=token)

    def test_stop_waits_for_b_quiescence(self):
        self.running(); self.op("stop")
        self.assertEqual(self.s["phase"], "B_RUNNING")
        with self.assertRaisesRegex(ValueError, "STALE_OR_STOPPED"): self.op("permit", "B", round=1)
        with self.assertRaisesRegex(ValueError, "QUIESCE"): self.op("pause", reason="A cannot release B")
        self.op("pause", "B", reason="all execution stopped safely")
        self.assertEqual(self.s["phase"], "CANCELLED")

    def test_event_before_listener_is_not_lost(self):
        self.running(); old_seq = self.s["seq"]; self.finish()
        result = w.wait(self.repo, self.a, self.s["run"], old_seq, 1)
        self.assertEqual(result["event"], "TEAM_WORKFLOW_WAKE")
        self.assertLess(result["elapsed_ms"], 500)

    def test_real_wait_is_silent_single_and_woken_cross_process(self):
        self.running()
        out = Path(self.temp.name) / "wait-output.txt"
        with out.open("wb") as stream:
            p = subprocess.Popen(self.cli("wait", observed_seq=self.s["seq"], timeout=10), stdout=stream, stderr=subprocess.PIPE)
            try:
                deadline = time.monotonic() + 5
                while True:
                    h = w.Handle(w.key(self.repo, self.s["run"] + "|waiter|A"), mutex=True)
                    acquired = h.wait(0)
                    if acquired: h.api.ReleaseMutex(h.handle)
                    h.close()
                    if not acquired: break
                    self.assertLess(time.monotonic(), deadline, "listener failed to arm")
                    time.sleep(.02)
                self.assertEqual(out.read_bytes(), b"", "waiting printed a heartbeat")
                duplicate = subprocess.run(self.cli("wait", observed_seq=self.s["seq"], timeout=1), capture_output=True, timeout=5)
                self.assertEqual(duplicate.returncode, 1)
                self.assertIn(b"WAITER_ALREADY_RUNNING", duplicate.stdout)
                self.finish()
                _, err = p.communicate(timeout=5)
                self.assertEqual(p.returncode, 0, err)
            finally:
                if p.poll() is None: p.kill(); p.wait()
        lines = out.read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(lines), 1)
        self.assertEqual(json.loads(lines[0])["phase"], "A_REVIEW")

    def test_one_second_timeout_without_round_increment(self):
        self.ready(); before = (self.repo / w.STATE).read_bytes()
        result = subprocess.run(self.cli("wait", observed_seq=self.s["seq"], timeout=1), capture_output=True, timeout=5)
        self.assertEqual(result.returncode, 0, result.stderr)
        lines = result.stdout.decode("utf-8").splitlines()
        self.assertEqual(len(lines), 1)
        msg = json.loads(lines[0]); self.assertEqual(msg["event"], "TEAM_WORKFLOW_TIMEOUT")
        self.assertGreaterEqual(msg["elapsed_ms"], 990)
        self.assertEqual((self.repo / w.STATE).read_bytes(), before)

    def test_b_waits_for_a_publication(self):
        self.running(); self.finish(); self.review_input()
        self.op("review", report="review-input.json")
        p = subprocess.Popen(self.cli("wait", "B", observed_seq=self.s["seq"], timeout=10), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            self.op("publish", task="draft.md", criteria="criteria-input.json")
            out, err = p.communicate(timeout=5)
            self.assertEqual(p.returncode, 0, err)
            self.assertEqual(json.loads(out)["phase"], "B_READY")
        finally:
            if p.poll() is None: p.kill(); p.wait()

    def test_b_completes_before_a_exists_and_late_review_does_not_rerun(self):
        self.init()
        self.assertEqual(set(self.s["sessions"]), {"B"})
        self.assertEqual(self.s["phase"], "B_READY")
        self.op("enter", "B", round=1); self.finish()
        before = {n: (self.repo / n).read_bytes() for n in ("team-task.md", "team-progress.md")}
        run_id = self.s["team_run"]
        result = w.wait(self.repo, self.b, self.s["run"], self.s["seq"], 1)
        self.assertEqual(result["event"], "TEAM_WORKFLOW_TIMEOUT")
        self.join_a()
        self.assertEqual((self.s["phase"], self.s["team_run"], self.s["round"]), ("A_REVIEW", run_id, 1))
        for n, data in before.items(): self.assertEqual((self.repo / n).read_bytes(), data)
        result = w.wait(self.repo, self.a, self.s["run"], self.s["seq"], 1)
        self.assertEqual(result["event"], "TEAM_WORKFLOW_WAKE")
        self.review_input("pass", "PASS_DYNAMIC"); self.op("review", report="review-input.json")
        self.assertEqual(self.s["phase"], "DONE")

    def test_a_joins_running_b_without_modifying_task_or_progress(self):
        self.init(); self.op("enter", "B", round=1)
        self.put("team-progress.md", "> run_status: ACTIVE\nB checkpoint\n")
        before = {n: (self.repo / n).read_bytes() for n in ("team-task.md", "team-progress.md")}
        self.join_a()
        self.assertEqual(self.s["phase"], "B_RUNNING")
        for n, data in before.items(): self.assertEqual((self.repo / n).read_bytes(), data)
        with self.assertRaisesRegex(ValueError, "NOT_PUBLICATION_TURN"):
            self.op("publish", task="draft.md")
        with self.assertRaisesRegex(ValueError, "A_WINDOW_ALREADY_BOUND"):
            w.operation(self.repo, "join", str(uuid.uuid4()), run=self.s["run"], criteria="criteria-input.json")

    def test_a_cannot_bootstrap_and_join_retry_keeps_criteria(self):
        with self.assertRaises(FileNotFoundError):
            w.operation(self.repo, "join", self.a, run="no-workflow", criteria="criteria-input.json")
        self.assertFalse((self.repo / w.STATE).exists())
        self.ready(); original = self.s["criteria_sha256"]
        self.json("criteria-input.json", {"items": []})
        self.join_a()
        self.assertEqual(self.s["criteria_sha256"], original)

    def test_completed_source_is_not_adopted_as_new_task(self):
        raw = (self.repo / "team-task.md").read_text(encoding="utf-8")
        sid = "src-" + w.digest(raw.encode())[:8]
        self.put("team-progress.md", f"> run_status: COMPLETE\n> source_block_id: {sid}\n> 漏斗: P6✓\n")
        with self.assertRaisesRegex(ValueError, "SOURCE_ALREADY_EXECUTED"): self.init()
        self.assertFalse((self.repo / w.STATE).exists())

    def test_b_lifecycle_needs_no_baseline_and_cannot_start_second_round_alone(self):
        self.assertFalse((self.repo / "baseline.md").exists())
        self.init()
        self.assertNotIn("baseline", self.s)
        self.assertIsNone(self.s["max_round"])
        self.op("enter", "B", round=1)
        self.op("permit", "B", round=1)
        self.op("resume", "B", reason="resume interrupted first task")
        self.op("enter", "B", round=1, resume_token=self.s["resume_token"])
        self.finish()
        with self.assertRaisesRegex(ValueError, "NOT_PUBLICATION_TURN"):
            self.op("publish", "B", task="draft.md")
        with self.assertRaisesRegex(ValueError, "NOT_READY"):
            self.op("enter", "B", round=2)
        self.assertEqual((self.s["phase"], self.s["round"]), ("A_REVIEW", 1))
        self.assertFalse((self.repo / "baseline.md").exists())

    def test_old_b_baseline_and_round_arguments_are_rejected_before_writes(self):
        before = (self.repo / "team-task.md").read_bytes()
        for opts in ({"baseline": str(self.repo / "missing.md")}, {"max_round": 3}):
            with self.assertRaisesRegex(ValueError, "B_ACCEPTS_TASK_ONLY"):
                self.op("init", "B", **opts)
        self.assertEqual((self.repo / "team-task.md").read_bytes(), before)
        self.assertFalse((self.repo / w.STATE).exists())

    def test_a_binds_baseline_and_limit_after_b_finishes(self):
        self.init(); self.op("enter", "B", round=1); self.finish()
        before = (self.repo / w.STATE).read_bytes()
        with self.assertRaisesRegex(ValueError, "A_BASELINE_REQUIRED"):
            self.op("join", criteria="criteria-input.json")
        self.assertEqual((self.repo / w.STATE).read_bytes(), before)
        self.join_a(maximum=1)
        self.assertEqual(self.s["max_round"], 1)
        self.review_input(); self.op("review", report="review-input.json")
        self.assertEqual((self.s["phase"], self.s["round"]), ("LIMIT", 1))

    def test_a_binding_cannot_change_baseline_or_maximum_on_retry(self):
        self.ready(); before = (self.repo / w.STATE).read_bytes()
        with self.assertRaisesRegex(ValueError, "MAX_ROUND_ALREADY_BOUND"):
            self.op("join", max_round=4)
        self.put("other.md", "another baseline")
        with self.assertRaisesRegex(ValueError, "A_BASELINE_ALREADY_BOUND"):
            self.op("join", baseline=str(self.repo / "other.md"))
        self.assertEqual((self.repo / w.STATE).read_bytes(), before)

    def test_later_b_round_never_opens_a_baseline(self):
        self.running(); self.finish(); self.review_input()
        self.op("review", report="review-input.json")
        self.op("publish", task="draft.md")
        task = (self.repo / "team-task.md").read_text(encoding="utf-8")
        self.assertNotIn(str(self.repo / "baseline.md"), task)
        self.assertNotIn("baseline_sha256:", task)
        self.assertNotIn("criteria:", task)
        base = self.repo / "baseline.md"
        a_inputs = {base, w.home(self.repo, self.s) / "criteria.json", self.repo / "criteria-input.json"}
        real_bytes, real_text = Path.read_bytes, Path.read_text
        def checked_bytes(path):
            if path in a_inputs: raise AssertionError("B opened A-only input")
            return real_bytes(path)
        def checked_text(path, *args, **kwargs):
            if path in a_inputs: raise AssertionError("B opened A-only input")
            return real_text(path, *args, **kwargs)
        with patch.object(Path, "read_bytes", checked_bytes), patch.object(Path, "read_text", checked_text):
            self.op("enter", "B", round=2)
            self.op("permit", "B", round=2)
            self.op("resume", "B", reason="user resumed")
            self.op("enter", "B", round=2, resume_token=self.s["resume_token"])
            self.finish()
        self.assertEqual(self.s["phase"], "A_REVIEW")
        self.put("baseline.md", "changed by external actor")
        self.review_input("pass", "PASS_DYNAMIC")
        with self.assertRaisesRegex(ValueError, "BASELINE_CHANGED"):
            self.op("review", report="review-input.json")

    def test_cli_b_init_without_parameters(self):
        args = [sys.executable, str(SCRIPT), "init", "--repo", str(self.repo), "--session", self.b]
        result = subprocess.run(args, capture_output=True, timeout=5)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.s = json.loads(result.stdout)
        self.assertEqual(self.s["phase"], "B_READY")
        self.assertIsNone(self.s["max_round"])
        self.assertNotIn("baseline", self.s)

    def test_a_default_and_invalid_round_limit(self):
        self.init(); self.put("baseline.md", "A baseline")
        for maximum in (0, -1, 21):
            with self.assertRaisesRegex(ValueError, "INVALID_MAX_ROUND"):
                self.op("join", baseline=str(self.repo / "baseline.md"), max_round=maximum,
                        criteria="criteria-input.json")
        self.assertNotIn("A", w.load(self.repo)["sessions"])
        self.assertNotIn("baseline", w.load(self.repo))
        self.op("join", baseline=str(self.repo / "baseline.md"), criteria="criteria-input.json")
        self.assertEqual(self.s["max_round"], 3)

    def test_criteria_drift_and_unfounded_exemption_rejected(self):
        self.running(); self.finish(); self.review_input("pass", "EXEMPT")
        with self.assertRaisesRegex(ValueError, "EXEMPTION_ORIGINAL_CLAUSE_REQUIRED"):
            self.op("review", report="review-input.json")
        cp = w.home(self.repo, self.s) / "criteria.json"
        cp.write_bytes(cp.read_bytes() + b" ")
        with self.assertRaisesRegex(ValueError, "CRITERIA_CHANGED"):
            self.op("review", report="review-input.json")


if __name__ == "__main__":
    unittest.main(verbosity=2)
