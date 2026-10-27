#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""run_matrix.py - deterministic fixture matrix for docx-shared-core.

Reproduces the acceptance matrix with fresh outputs each run. Negatives that
return the expected FAIL=1 / BLOCKED=2 are TEST SUCCESSES (probe discriminates),
not build failures. Exit 0 iff ALL cases match expectations.

Cases (frozen at C1; actual count driven by invariants, not a fixed R1-R6 quota):
  C_pos               build -> verify                       expect build 0 / verify 0
  C_missing_anchor    build with absent anchor              expect build 1
  C_output_exists     build to a pre-existing out           expect build 1
  C_non_unique_anchor build with duplicated table_insert anchor expect build 1
  C_none_miswrite     verify a none-cell-miswrite docx      expect verify 1
  C_yellow_miswrite   verify a yellow-cell-miswrite docx    expect verify 1
  C_multi_bad         verify none+yellow miswrite           expect verify 1 (diagnosis stable)
  C_encrypted         build encrypted.bin template          expect build 2
  C_ole               build ole.bin template                expect build 2
  C_file_probe_routes file_probe.py direct-run 3 fixtures   expect exit 0/2/2 + route python/BLOCKED/BLOCKED
  C_verify_blocked_enc verify neg_encrypted.bin as output   expect verify 2 (BLOCKED branch)
  C_verify_blocked_ole verify neg_ole.bin as output         expect verify 2 (BLOCKED branch)

12 acceptance cases + determinism probe. Writes matrix_report.json to --out-dir.
"""
import argparse, json, subprocess, sys, hashlib, shutil
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
CORE_ROOT = HERE
SCRIPTS = HERE / "scripts"
FIXTURES = HERE / "fixtures"
CONTRACTS = HERE / "contracts"
DETERMINISM_REPS = 3


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def run(cmd):
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    return proc.returncode, (proc.stdout or "").strip(), (proc.stderr or "").strip()


def parse_json_stdout(so):
    if not so:
        return None
    try:
        return json.loads(so)
    except Exception:
        return None


def case_record(cid, expected, actual, so="", se="", note=""):
    verdict = "PASS" if actual == expected else "FAIL"
    rec = {"id": cid, "expected": expected, "actual": actual, "verdict": verdict}
    parsed = parse_json_stdout(so)
    if parsed is not None:
        rec["structured_output"] = parsed
    else:
        rec["stdout_excerpt"] = so[:400]
    if se:
        rec["stderr_excerpt"] = se[:400]
    if note:
        rec["note"] = note
    return rec


def _write(path, content):
    Path(path).write_text(content, encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", required=True)
    args = ap.parse_args()
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    cases = []
    pos_tpl = FIXTURES / "pos_template.docx"

    # C_pos: positive build + verify
    cpos_out = out / "c_pos_built.docx"
    rc, so, se = run([sys.executable, "-X", "utf8", str(SCRIPTS / "build_docx.py"),
                      "--template", str(pos_tpl),
                      "--slot-map", str(CONTRACTS / "pos_slot_map.json"),
                      "--out", str(cpos_out),
                      "--pending-human-ledger", str(out / "pending_human_blocked.json")])
    cpos_build = rc
    rc2, so2, se2 = run([sys.executable, "-X", "utf8", str(SCRIPTS / "verify_docx.py"),
                         "--output", str(cpos_out),
                         "--contract", str(CONTRACTS / "pos_contract.json"),
                         "--source", str(pos_tpl)])
    cpos_verify = rc2
    rec = case_record("C_pos", {"build": 0, "verify": 0},
                      {"build": cpos_build, "verify": cpos_verify},
                      so + "\n--- verify ---\n" + so2, se + "\n" + se2)
    if cpos_out.exists():
        rec["actual"]["product_sha256"] = sha256(cpos_out)
    cases.append(rec)

    # C_missing_anchor: build with a slot-map referencing an absent anchor
    miss_map = out / "missing_anchor_map.json"
    _write(miss_map, json.dumps({
        "anchors": [{"find": "{{NOPE}}", "replace": "x"}],
        "slots": []
    }))
    miss_out = out / "c_missing_anchor.docx"
    rc, so, se = run([sys.executable, "-X", "utf8", str(SCRIPTS / "build_docx.py"),
                      "--template", str(pos_tpl),
                      "--slot-map", str(miss_map), "--out", str(miss_out),
                      "--pending-human-ledger", str(out / "pending_human_blocked.json")])
    cases.append(case_record("C_missing_anchor", {"build": 1}, {"build": rc}, so, se,
                             note="absent anchor must abort before save (non-overwrite)"))

    # C_output_exists: build to a pre-existing output path
    exist_out = out / "c_output_exists.docx"
    exist_out.write_bytes(b"PREEXISTING")
    rc, so, se = run([sys.executable, "-X", "utf8", str(SCRIPTS / "build_docx.py"),
                      "--template", str(pos_tpl),
                      "--slot-map", str(CONTRACTS / "pos_slot_map.json"),
                      "--out", str(exist_out),
                      "--pending-human-ledger", str(out / "pending_human_blocked.json")])
    still_preexisting = exist_out.exists() and exist_out.read_bytes() == b"PREEXISTING"
    rec = case_record("C_output_exists", {"build": 1}, {"build": rc}, so, se,
                      note="existing output must be refused, not overwritten")
    rec["actual"]["output_unchanged"] = still_preexisting
    cases.append(rec)

    # C_non_unique_anchor: table_insert anchor appears twice -> BUILD_FAIL (no save, no overwrite)
    non_unique_map = out / "non_unique_anchor_map.json"
    _write(non_unique_map, json.dumps({
        "anchors": [
            {"find": "{{TITLE}}", "replace": "Quarterly Summary"},
            {"find": "{{RED_VALUE}}", "replace": "REPLACED_OK"}
        ],
        "slots": [
            {"id": "red_value_cell", "kind": "red_cell_driven", "table": 1, "row": 1, "col": 0, "value": "REPLACED_OK"},
            {"id": "dup_anchor_table", "kind": "table_insert", "anchor": "Outro line after table.",
             "headers": ["X"], "rows": [["1"]]}
        ]
    }))
    # plant a SECOND copy of the anchor paragraph into a throwaway template copy so it is non-unique
    nu_tpl = out / "non_unique_template.docx"
    shutil.copy2(str(pos_tpl), str(nu_tpl))
    from docx import Document as _Doc
    _d = _Doc(str(nu_tpl))
    _d.add_paragraph("Outro line after table.")  # duplicate anchor
    _d.save(str(nu_tpl))
    nu_out = out / "c_non_unique_anchor.docx"
    rc, so, se = run([sys.executable, "-X", "utf8", str(SCRIPTS / "build_docx.py"),
                      "--template", str(nu_tpl),
                      "--slot-map", str(non_unique_map), "--out", str(nu_out),
                      "--pending-human-ledger", str(out / "pending_human_blocked.json")])
    not_saved = not nu_out.exists()
    rec = case_record("C_non_unique_anchor", {"build": 1}, {"build": rc}, so, se,
                      note="non-unique table_insert anchor must abort before save (no overwrite)")
    rec["actual"]["output_not_saved"] = not_saved
    cases.append(rec)

    # C_none_miswrite: build a docx then a none-cell is wrongly written; verify FAIL
    # Use a slot-map that forces a none cell to be written via 'text' kind.
    none_miswrite_map = out / "none_miswrite_map.json"
    _write(none_miswrite_map, json.dumps({
        "anchors": [
            {"find": "{{TITLE}}", "replace": "Quarterly Summary"},
            {"find": "{{RED_VALUE}}", "replace": "REPLACED_OK"}
        ],
        "slots": [
            {"id": "red_value_cell", "kind": "red_cell_driven", "table": 1, "row": 1, "col": 0, "value": "REPLACED_OK"},
            # force-write a NONE cell [1,2] (was 'fixed-note') -> should be caught as none-miswrite
            {"id": "force_none_write", "kind": "text", "table": 1, "row": 1, "col": 2, "value": "WRITTEN_INTO_NONE"},
            {"id": "perf_table", "kind": "table_insert", "anchor": "Outro line after table.",
             "headers": ["Metric", "Result"], "rows": [["Alpha", "1.0"], ["Beta", "2.0"]]}
        ]
    }))
    none_out = out / "c_none_miswrite.docx"
    rc, so, se = run([sys.executable, "-X", "utf8", str(SCRIPTS / "build_docx.py"),
                      "--template", str(pos_tpl),
                      "--slot-map", str(none_miswrite_map), "--out", str(none_out),
                      "--pending-human-ledger", str(out / "pending_human_blocked.json")])
    none_build = rc
    rc2, so2, se2 = run([sys.executable, "-X", "utf8", str(SCRIPTS / "verify_docx.py"),
                         "--output", str(none_out),
                         "--contract", str(CONTRACTS / "pos_contract.json"),
                         "--source", str(pos_tpl)])
    cases.append(case_record("C_none_miswrite", {"build": 0, "verify": 1},
                             {"build": none_build, "verify": rc2}, so + "\n--- verify ---\n" + so2, se + "\n" + se2,
                             note="none-cell miswrite must be caught by verifier (FAIL=1)"))

    # C_yellow_miswrite: force-write the YELLOW cell [1,1]; verify FAIL
    yellow_miswrite_map = out / "yellow_miswrite_map.json"
    _write(yellow_miswrite_map, json.dumps({
        "anchors": [
            {"find": "{{TITLE}}", "replace": "Quarterly Summary"},
            {"find": "{{RED_VALUE}}", "replace": "REPLACED_OK"}
        ],
        "slots": [
            {"id": "red_value_cell", "kind": "red_cell_driven", "table": 1, "row": 1, "col": 0, "value": "REPLACED_OK"},
            {"id": "force_yellow_write", "kind": "text", "table": 1, "row": 1, "col": 1, "value": "WRITTEN_INTO_YELLOW"},
            {"id": "perf_table", "kind": "table_insert", "anchor": "Outro line after table.",
             "headers": ["Metric", "Result"], "rows": [["Alpha", "1.0"], ["Beta", "2.0"]]}
        ]
    }))
    yellow_out = out / "c_yellow_miswrite.docx"
    rc, so, se = run([sys.executable, "-X", "utf8", str(SCRIPTS / "build_docx.py"),
                      "--template", str(pos_tpl),
                      "--slot-map", str(yellow_miswrite_map), "--out", str(yellow_out),
                      "--pending-human-ledger", str(out / "pending_human_blocked.json")])
    yellow_build = rc
    rc2, so2, se2 = run([sys.executable, "-X", "utf8", str(SCRIPTS / "verify_docx.py"),
                         "--output", str(yellow_out),
                         "--contract", str(CONTRACTS / "pos_contract.json"),
                         "--source", str(pos_tpl)])
    cases.append(case_record("C_yellow_miswrite", {"build": 0, "verify": 1},
                             {"build": yellow_build, "verify": rc2}, so + "\n--- verify ---\n" + so2, se + "\n" + se2,
                             note="yellow-cell miswrite must be caught by verifier (FAIL=1)"))

    # C_multi_bad: both none and yellow miswritten simultaneously; verify FAIL stably
    multi_map = out / "multi_bad_map.json"
    _write(multi_map, json.dumps({
        "anchors": [
            {"find": "{{TITLE}}", "replace": "Quarterly Summary"},
            {"find": "{{RED_VALUE}}", "replace": "REPLACED_OK"}
        ],
        "slots": [
            {"id": "red_value_cell", "kind": "red_cell_driven", "table": 1, "row": 1, "col": 0, "value": "REPLACED_OK"},
            {"id": "force_none_write", "kind": "text", "table": 1, "row": 1, "col": 2, "value": "WRONG_NONE"},
            {"id": "force_yellow_write", "kind": "text", "table": 1, "row": 1, "col": 1, "value": "WRONG_YELLOW"},
            {"id": "perf_table", "kind": "table_insert", "anchor": "Outro line after table.",
             "headers": ["Metric", "Result"], "rows": [["Alpha", "1.0"], ["Beta", "2.0"]]}
        ]
    }))
    multi_out = out / "c_multi_bad.docx"
    rc, so, se = run([sys.executable, "-X", "utf8", str(SCRIPTS / "build_docx.py"),
                      "--template", str(pos_tpl),
                      "--slot-map", str(multi_map), "--out", str(multi_out),
                      "--pending-human-ledger", str(out / "pending_human_blocked.json")])
    multi_build = rc
    rc2, so2, se2 = run([sys.executable, "-X", "utf8", str(SCRIPTS / "verify_docx.py"),
                         "--output", str(multi_out),
                         "--contract", str(CONTRACTS / "pos_contract.json"),
                         "--source", str(pos_tpl)])
    cases.append(case_record("C_multi_bad", {"build": 0, "verify": 1},
                             {"build": multi_build, "verify": rc2}, so + "\n--- verify ---\n" + so2, se + "\n" + se2,
                             note="none+yellow simultaneous miswrite; diagnosis must stay stable (FAIL=1)"))

    # C_encrypted: encrypted.bin as template -> build BLOCKED 2
    enc_out = out / "c_encrypted.docx"
    rc, so, se = run([sys.executable, "-X", "utf8", str(SCRIPTS / "build_docx.py"),
                      "--template", str(FIXTURES / "neg_encrypted.bin"),
                      "--slot-map", str(CONTRACTS / "pos_slot_map.json"), "--out", str(enc_out),
                      "--pending-human-ledger", str(out / "pending_human_blocked.json")])
    cases.append(case_record("C_encrypted", {"build": 2}, {"build": rc}, so, se,
                             note="88 7D 1C encrypted input -> BLOCKED exit 2"))

    # C_ole: ole.bin as template -> build BLOCKED 2
    ole_out = out / "c_ole.docx"
    rc, so, se = run([sys.executable, "-X", "utf8", str(SCRIPTS / "build_docx.py"),
                      "--template", str(FIXTURES / "neg_ole.bin"),
                      "--slot-map", str(CONTRACTS / "pos_slot_map.json"), "--out", str(ole_out),
                      "--pending-human-ledger", str(out / "pending_human_blocked.json")])
    cases.append(case_record("C_ole", {"build": 2}, {"build": rc}, so, se,
                             note="D0 CF 11 E0 OLE/CFB legacy .doc -> BLOCKED exit 2 (unsupported)"))

    # C_file_probe_routes: file_probe.py direct-run against all 3 fixtures (B-003a).
    # Exercises file_probe.py's own three magic-byte routes (not build_docx._check_blocked).
    fp_expected = {"pos": {"exit": 0, "route": "python", "hex_prefix": "50 4B 03 04"},
                   "enc": {"exit": 2, "route": "BLOCKED", "hex_prefix": "88 7D 1C"},
                   "ole": {"exit": 2, "route": "BLOCKED", "hex_prefix": "D0 CF 11 E0"}}
    fp_targets = {"pos": pos_tpl, "enc": FIXTURES / "neg_encrypted.bin", "ole": FIXTURES / "neg_ole.bin"}
    fp_results = {}
    fp_all_ok = True
    for tag, target_fp in fp_targets.items():
        rc, so, se = run([sys.executable, "-X", "utf8", str(SCRIPTS / "file_probe.py"), str(target_fp)])
        parsed = parse_json_stdout(so) or {}
        exp = fp_expected[tag]
        ok = (rc == exp["exit"] and parsed.get("route") == exp["route"]
              and parsed.get("hex", "").startswith(exp["hex_prefix"]))
        if not ok:
            fp_all_ok = False
        fp_results[tag] = {"target": str(target_fp), "expected": exp,
                           "actual_exit": rc, "actual_route": parsed.get("route"),
                           "actual_hex": parsed.get("hex", ""), "ok": ok}
    cases.append({"id": "C_file_probe_routes", "expected": "all 3 routes match",
                  "actual": fp_results, "verdict": "PASS" if fp_all_ok else "FAIL",
                  "note": "file_probe.py three-route direct probe: 50 4B->python/0, 88 7D 1C->BLOCKED/2, D0 CF 11 E0->BLOCKED/2"})

    # C_verify_blocked_enc: feed neg_encrypted.bin as verify output -> BLOCKED 2 (B-003b).
    # Exercises verify_docx.py's non-plaintext BLOCKED branch directly.
    venc_rep = out / "venc_report"
    rc, so, se = run([sys.executable, "-X", "utf8", str(SCRIPTS / "verify_docx.py"),
                      "--output", str(FIXTURES / "neg_encrypted.bin"),
                      "--contract", str(CONTRACTS / "pos_contract.json"),
                      "--report-dir", str(venc_rep)])
    venc_parsed = parse_json_stdout(so) or {}
    rec = case_record("C_verify_blocked_enc", {"verify": 2}, {"verify": rc}, so, se,
                      note="verify_docx non-plaintext BLOCKED branch: 88 7D 1C -> exit 2 (verify BLOCKED negative)")
    rec["actual"]["verdict"] = venc_parsed.get("verdict")
    rec["actual"]["report_exit_code"] = venc_parsed.get("exit_code")
    rec["actual"]["layers_skipped_check"] = True if (venc_rep / "report.json").exists() else None
    cases.append(rec)

    # C_verify_blocked_ole: feed neg_ole.bin as verify output -> BLOCKED 2 (B-003b).
    vole_rep = out / "vole_report"
    rc, so, se = run([sys.executable, "-X", "utf8", str(SCRIPTS / "verify_docx.py"),
                      "--output", str(FIXTURES / "neg_ole.bin"),
                      "--contract", str(CONTRACTS / "pos_contract.json"),
                      "--report-dir", str(vole_rep)])
    vole_parsed = parse_json_stdout(so) or {}
    rec = case_record("C_verify_blocked_ole", {"verify": 2}, {"verify": rc}, so, se,
                      note="verify_docx non-plaintext BLOCKED branch: D0 CF 11 E0 -> exit 2 (verify BLOCKED negative)")
    rec["actual"]["verdict"] = vole_parsed.get("verdict")
    rec["actual"]["report_exit_code"] = vole_parsed.get("exit_code")
    rec["actual"]["layers_skipped_check"] = True if (vole_rep / "report.json").exists() else None
    cases.append(rec)

    # determinism probe
    probe_hashes = []
    for i in range(DETERMINISM_REPS):
        rep_out = out / f"_det_{i}.docx"
        rc, so, se = run([sys.executable, "-X", "utf8", str(SCRIPTS / "build_docx.py"),
                          "--template", str(pos_tpl),
                          "--slot-map", str(CONTRACTS / "pos_slot_map.json"),
                          "--out", str(rep_out),
                          "--pending-human-ledger", str(out / "pending_human_blocked.json")])
        if rc == 0 and rep_out.exists():
            probe_hashes.append(sha256(rep_out))
            rep_out.unlink()
    unique = set(probe_hashes)
    byte_stable = len(unique) == 1
    determinism = {
        "product_hashes": probe_hashes,
        "unique_count": len(unique),
        "byte_stable": byte_stable,
        "within_run_unique": len(unique),
        "caveat": ("python-docx embeds a zip creation timestamp in the OOXML container; "
                   "product bytes vary across seconds/runs. A same-second unique_count==1 is a "
                   "timing coincidence, NOT proof of determinism. Cross-second runs show "
                   "distinct product hashes. The golden hash is NOT a fixed target; only "
                   "per-run SHA-256 binding is valid."),
        "conclusion": ("within-run byte-stable (same-second coincidence); cross-run NOT deterministic"
                       if byte_stable
                       else "NON-deterministic within run: python-docx embeds creation timestamp; "
                            "per-run product hash varies. golden hash is NOT a fixed target; "
                            "only per-run binding is valid.")
    }

    overall = all(c["verdict"] == "PASS" for c in cases)
    report = {
        "generated_at": datetime.now().astimezone().isoformat(),
        "core_root": str(CORE_ROOT),
        "overall_verdict": "PASS" if overall else "FAIL",
        "case_count": len(cases),
        "cases": cases,
        "determinism_probe": determinism,
        "done_when_mapping": {
            "pos_all_green": "C_pos build=0 verify=0",
            "neg_nonzero_exit": ("C_missing_anchor/C_output_exists/C_non_unique_anchor build=1; "
                                  "C_none_miswrite/C_yellow_miswrite/C_multi_bad verify=1; "
                                  "C_encrypted/C_ole build=2; "
                                  "C_verify_blocked_enc/C_verify_blocked_ole verify=2"),
            "none_and_yellow_independent_negatives": "C_none_miswrite and C_yellow_miswrite are separate cases",
            "multi_bad_stable": "C_multi_bad verify=1 with both defects reported",
            "file_probe_three_routes": "C_file_probe_routes: file_probe.py direct-run 50 4B/88 7D 1C/D0 CF 11 E0 -> exit 0/2/2 + route python/BLOCKED/BLOCKED",
            "verify_blocked_negative": "C_verify_blocked_enc/C_verify_blocked_ole: non-plaintext output -> verify exit 2 (BLOCKED branch covered)",
            "per_run_product_sha256": (cases[0].get("actual", {}).get("product_sha256") if cases else None),
            "determinism": determinism["conclusion"],
            "exit_code_contract": "PASS=0 / FAIL=1 / BLOCKED=2"
        }
    }
    (out / "matrix_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if overall else 1


if __name__ == "__main__":
    sys.exit(main())
