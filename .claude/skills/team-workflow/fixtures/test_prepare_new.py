"""Isolated cleanup mechanics; no production business or Claude messages."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import workflow as w
import prepare_new as p
import test_workflow as base


@unittest.skipUnless(os.name == "nt", "Windows process and named mutex checks")
class PrepareNewTests(base.RelayTests):
    # Do not rerun the inherited suite; it is run once by unittest discovery.
    def clean(self, **kwargs):
        opts = dict(request="new-business.md", reason="user explicitly starts a new task",
                    actor="isolated-test", run=self.s["run"] if self.s else None)
        opts.update(kwargs)
        return p.prepare_new(self.repo, **opts)

    def done(self):
        self.running(); self.finish(); self.review_input("pass", "PASS_DYNAMIC")
        self.op("review", report="review-input.json")

    def snap(self):
        return {n:(self.repo/n).read_bytes() if (self.repo/n).exists() else None
                for n in (w.STATE,)+p.ROOT_FILES}

    def quiet(self):
        return patch.object(p, "quiescence", return_value={"method":"isolated fixture"})

    def test_preflight_done_external_caller_and_bytes(self):
        self.done(); before=self.snap(); result=self.clean()
        dest=w.home(self.repo,self.s)
        self.assertTrue(result["archived"])
        self.assertEqual(result["final_phase"],"DONE")
        self.assertEqual((dest/"prepare-new/state-original.json").read_bytes(), before[w.STATE])
        for n in p.ROOT_FILES:
            self.assertEqual((dest/"final"/n).read_bytes(),before[n])
            self.assertEqual((self.repo/n).read_bytes(),b"")
        self.assertFalse((self.repo/w.STATE).exists())
        self.assertFalse(self.clean()["archived"])

    def test_preflight_legacy_archive_residue_then_new_init(self):
        self.done(); self.op("archive","B")
        self.assertTrue(self.clean()["archived"])
        self.put("team-task.md","## 本次任务\n新任务\n## done_when\n完成实际新要求")
        self.init()
        self.assertEqual(self.s["phase"],"B_READY")

    def test_preflight_terminal_incomplete_is_never_success(self):
        self.ready(); self.op("stop","B")
        result=self.clean()
        self.assertTrue(result["unfinished"])
        self.assertFalse(result["interrupted"])
        self.assertEqual(result["final_phase"],"CANCELLED")

    def test_preflight_cancelled_without_last_live_protects_new_draft(self):
        self.ready(); self.op("stop","B")
        self.put("team-task.md","## 本次任务\n新的草稿\n## done_when\n新验收")
        before=self.snap()
        with self.assertRaisesRegex(ValueError,"PUBLICATION_FILE_DRIFT"):self.clean()
        self.assertEqual(before,self.snap())

    def test_preflight_new_prepared_task_never_cleared(self):
        self.done(); self.op("archive","B")
        self.put("team-task.md","## 本次任务\n未执行的新任务\n## done_when\n新判据")
        before=self.snap(); result=self.clean()
        self.assertFalse(result["archived"])
        self.assertTrue(result["root_task_preserved"])
        self.assertEqual(before,self.snap())

    def test_preflight_interrupted_preserves_failure_history(self):
        self.running(); self.s["failures"]={"P2|failure|code|D1":2}
        w.save(self.repo,self.s); self.put("team-progress.md",f"> run_id: {self.s['team_run']}\n> source_block_id: {self.s['source_id']}\n> run_status: ACTIVE\nP3 未完成\n")
        before=self.snap()
        with self.quiet(): result=self.clean()
        self.assertTrue(result["unfinished"])
        final=w.read_json(w.home(self.repo,self.s)/"state-final.json")
        self.assertEqual(final["phase"],"CANCELLED")
        self.assertEqual(final["failures"],self.s["failures"])
        self.assertEqual(final["history"],self.s["history"])
        self.assertEqual((w.home(self.repo,self.s)/"prepare-new/state-original.json").read_bytes(),before[w.STATE])

    def test_preflight_all_supported_interrupted_phases(self):
        for phase in ("B_READY","PUBLISHING","B_RUNNING","A_REVIEW","A_PLAN","PAUSED"):
            with self.subTest(phase=phase), tempfile.TemporaryDirectory() as tmp:
                repo=Path(tmp).resolve(); s={"version":3,"repo":str(repo),"run":uuid.uuid4().hex,
                    "seq":1,"round":1,"max_round":None,"sessions":{"B":str(uuid.uuid4())},
                    "phase":phase,"failures":{"old":1},"history":[],"stop_requested":False}
                body="## 本次任务\n测试\n## done_when\n待完成"
                digest=w.digest(body.encode());sid="src-"+digest[:8]
                s.update(source_id=sid,source_sha256=digest,team_run="fixture-original")
                source=f'<!-- team-task-source id="{sid}" sha256="{digest}" status="open" -->\n{body}\n<!-- /team-task-source -->\n'.encode()
                progress=f"> run_id: fixture-original\n> source_block_id: {sid}\n> run_status: ACTIVE\n".encode()
                s["pending_old"]={"team-task.md":w.digest(source),"team-progress.md":w.digest(progress)}
                w.atomic(repo/w.STATE,w.encode(s));w.atomic(repo/"team-task.md",source);w.atomic(repo/"team-progress.md",progress)
                w.preserve(w.round_dir(repo,s)/"source.md",source)
                with self.quiet(): r=p.prepare_new(repo,request="new",reason="new requested task",actor="test",run=s["run"])
                self.assertEqual(r["final_phase"],"CANCELLED")

    def test_preflight_alive_or_unknown_never_changes_roots(self):
        self.running(); before=self.snap()
        for error in ("OLD_EXECUTORS_NOT_QUIESCENT","PROCESS_CENSUS_UNAVAILABLE"):
            with patch.object(p,"quiescence",side_effect=ValueError(error)):
                with self.assertRaisesRegex(ValueError,error): self.clean()
            self.assertEqual(before,self.snap())

    def test_preflight_waiter_mutex_blocks_orphan_cleanup(self):
        self.running(); before=self.snap()
        # Separate process owns the mutex (Windows mutexes are thread-reentrant).
        code="import sys,time;sys.path.insert(0,sys.argv[1]);import workflow as w;h=w.Handle(sys.argv[2],mutex=True);h.wait(0);print('ready',flush=True);time.sleep(20)"
        proc=subprocess.Popen([sys.executable,"-X","utf8","-c",code,str(Path(w.__file__).parent),
                               w.key(self.repo,self.s["run"]+"|waiter|A")],stdout=subprocess.PIPE)
        try:
            self.assertEqual(proc.stdout.readline().strip(),b"ready")
            with self.quiet(), self.assertRaisesRegex(ValueError,"OLD_WAITER_ALIVE"): self.clean()
            self.assertEqual(before,self.snap())
        finally:
            proc.terminate();proc.wait(timeout=5);proc.stdout.close()

    def test_preflight_wrong_run_missing_reason_and_same_gate(self):
        self.running(); before=self.snap()
        for opts, error in [({"run":"wrong"},"CURRENT_RUN"),({"reason":""},"REQUEST_REQUIRED"),
                            ({"actor":""},"ACTOR_REQUIRED")]:
            with self.assertRaisesRegex(ValueError,error): self.clean(**opts)
            self.assertEqual(before,self.snap())
        self.op("pause","B",reason="human gate")
        with self.assertRaisesRegex(ValueError,"SAME_BASELINE_HUMAN_GATE"):
            self.clean(request="baseline.md")

    def test_preflight_terminal_live_drift_refused(self):
        self.done(); self.put("team-task.md","a new prepared task or external change")
        before=self.snap()
        with self.assertRaisesRegex(ValueError,"ARTIFACT_CHANGED"): self.clean()
        self.assertEqual(before,self.snap())

    def test_preflight_interrupted_new_draft_and_foreign_progress_preserved(self):
        self.running(); original=(self.repo/"team-task.md").read_bytes()
        self.put("team-task.md","## 本次任务\n新草稿\n## done_when\n新要求")
        before=self.snap()
        with self.quiet(),self.assertRaisesRegex(ValueError,"SOURCE_BLOCK_AMBIGUOUS"):self.clean()
        self.assertEqual(before,self.snap())
        w.atomic(self.repo/"team-task.md",original)
        self.put("team-progress.md","> run_id: other-run\n> source_block_id: new-source\n")
        before=self.snap()
        with self.quiet(),self.assertRaisesRegex(ValueError,"OWNERSHIP_UNKNOWN"):self.clean()
        self.assertEqual(before,self.snap())

    def test_preflight_late_old_waiter_reads_archive_not_new_run(self):
        self.done(); old=dict(self.s);self.clean()
        self.put("team-task.md","## 本次任务\n新任务\n## done_when\n新的要求")
        self.init()
        result=w.wait(self.repo,self.a,old["run"],old["seq"],1)
        self.assertTrue(result["archived"])
        self.assertEqual(result["phase"],"DONE")
        self.assertEqual(w.load(self.repo)["run"],self.s["run"])

    def test_preflight_archive_conflict_refused(self):
        self.done(); dest=w.home(self.repo,self.s)
        w.preserve(dest/"final/team-task.md",b"conflicting historical archive")
        before=self.snap()
        with self.assertRaisesRegex(ValueError,"ARCHIVE_CONFLICT"): self.clean()
        self.assertEqual(before,self.snap())

    def test_preflight_partial_clear_and_crash_after_unlink_replay(self):
        self.done(); before=self.snap(); real=w.atomic
        failed=[False]
        def crash(path,data):
            if Path(path)==self.repo/"team-progress.md" and not failed[0]:
                failed[0]=True;raise OSError("injected clear crash")
            return real(path,data)
        with patch.object(w,"atomic",side_effect=crash):
            with self.assertRaisesRegex(OSError,"injected"): self.clean()
        self.assertTrue((self.repo/w.STATE).exists())
        def after_unlink(path,data):
            if Path(path).name=="receipt.json" and json.loads(data)["status"]=="complete":
                raise OSError("injected after unlink")
            return real(path,data)
        with patch.object(w,"atomic",side_effect=after_unlink):
            with self.assertRaisesRegex(OSError,"after unlink"): self.clean()
        self.assertFalse((self.repo/w.STATE).exists())
        self.assertTrue(self.clean()["archived"])
        self.assertEqual((w.home(self.repo,self.s)/"final/team-progress.md").read_bytes(),before["team-progress.md"])

    def test_preflight_retry_refuses_changed_new_task(self):
        self.done(); real=w.atomic
        def crash(path,data):
            if Path(path)==self.repo/"team-progress.md":raise OSError("injected")
            return real(path,data)
        with patch.object(w,"atomic",side_effect=crash):
            with self.assertRaises(OSError):self.clean()
        self.put("team-task.md","new caller wrote a different task")
        before=self.snap()
        with self.assertRaisesRegex(ValueError,"NEW_TASK_FILE_DRIFT"): self.clean()
        self.assertEqual(before,self.snap())

    def test_preflight_interrupted_recheck_after_cancel_crash(self):
        self.running(); real=w.atomic
        def crash(path,data):
            if Path(path)==self.repo/"team-task.md":raise OSError("injected")
            return real(path,data)
        with self.quiet(),patch.object(w,"atomic",side_effect=crash):
            with self.assertRaises(OSError):self.clean()
        self.assertEqual(w.load(self.repo)["phase"],"CANCELLED")
        with patch.object(p,"quiescence",side_effect=ValueError("active_again")):
            with self.assertRaisesRegex(ValueError,"active_again"):self.clean()
        with self.quiet():self.clean()

    def test_preflight_cli_current_actor_is_recorded_not_old_session(self):
        self.done()
        result=subprocess.run([sys.executable,"-X","utf8",str(Path(w.__file__)),"prepare-new",
            "--repo",str(self.repo),"--actor","codex-test","--run",self.s["run"],
            "--request","fresh.md","--reason","explicit new task"],capture_output=True,timeout=10)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        receipt=w.read_json(w.home(self.repo,self.s)/"prepare-new/receipt.json")
        self.assertEqual(receipt["actor"],{"kind":"external","id":"codex-test"})

    def test_preflight_process_start_positive_and_exited_control(self):
        self.assertIsNotNone(p.process_start(os.getpid()))
        proc=subprocess.Popen([sys.executable,"-c","pass"]);proc.wait(timeout=5)
        self.assertIsNone(p.process_start(proc.pid))

    def test_preflight_census_bound_alive_pid_reuse_and_descendants(self):
        self.running(); folder=self.config/"sessions";folder.mkdir()
        w.atomic(folder/"22.json",w.encode({"pid":22,"sessionId":self.b,"cwd":str(self.repo),"procStart":"old"}))
        w.atomic(folder/"44.json",w.encode({"pid":44,"sessionId":self.a,"cwd":str(self.repo),"procStart":"old-a"}))
        processes={os.getpid():{"ParentProcessId":0},22:{"ParentProcessId":0}}
        with patch.object(p,"session_roots",return_value=[self.config]),patch.object(p,"process_snapshot",return_value=processes):
            with patch.object(p,"process_start",side_effect=lambda pid:"old" if pid==22 else None):
                with self.assertRaisesRegex(ValueError,"NOT_QUIESCENT"):p.quiescence(self.repo,self.s)
            with patch.object(p,"process_start",side_effect=lambda pid:"reused" if pid==22 else None):
                self.assertEqual(p.quiescence(self.repo,self.s)["blockers"],[])
                processes[22]["CommandLine"]="python worker.py --run "+self.s["run"]
                with self.assertRaisesRegex(ValueError,"related_process_alive"):p.quiescence(self.repo,self.s)
                processes[22].pop("CommandLine")
            processes[33]={"ParentProcessId":22,"Name":"python.exe"}
            with patch.object(p,"process_start",return_value=None):
                with self.assertRaisesRegex(ValueError,"related_process_alive"):p.quiescence(self.repo,self.s)

    def test_preflight_missing_session_metadata_needs_captured_process_identity(self):
        self.running();(self.config/"sessions").mkdir()
        processes={os.getpid():{"ParentProcessId":0},33:{"ParentProcessId":22,"Name":"python.exe","CommandLine":"python worker.py"}}
        with patch.object(p,"session_roots",return_value=[self.config]),patch.object(p,"process_snapshot",return_value=processes),patch.object(p,"process_start",return_value=None):
            with self.assertRaisesRegex(ValueError,"BOUND_PROCESS_EVIDENCE_MISSING"):p.quiescence(self.repo,self.s)
            for role,pid in (("B",22),("A",44)):
                self.s["runtime_evidence"][role]["processes"]=[{"pid":pid,"procStart":"12345"}]
            with self.assertRaisesRegex(ValueError,"related_process_alive"):p.quiescence(self.repo,self.s)
            processes.pop(33)
            self.assertEqual(p.quiescence(self.repo,self.s)["blockers"],[])

    def test_preflight_binding_captures_minimal_process_identity(self):
        folder=self.config/"sessions";folder.mkdir()
        w.atomic(folder/"current.json",w.encode({"sessionId":self.b,"cwd":str(self.repo),"pid":os.getpid(),
            "procStart":p.process_start(os.getpid()),"irrelevant_secret":"must-not-be-copied"}))
        self.init()
        proof=self.s["runtime_evidence"]["B"]
        self.assertEqual(proof["processes"],[{"pid":os.getpid(),"procStart":p.process_start(os.getpid())}])
        self.assertNotIn("irrelevant_secret",json.dumps(proof))


# unittest would otherwise inherit and execute the 31 base tests again.
for name in list(vars(base.RelayTests)):
    if name.startswith("test_"): setattr(PrepareNewTests,name,None)

if __name__=="__main__":unittest.main(verbosity=2)
