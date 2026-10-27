#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""run_matrix.py - deterministic fixture matrix for pptx-shared-core.

Reproduces the 6-case acceptance matrix with fresh outputs each run:
  R1 pos       build -> verify        expect build 0 / verify 0
  R2 neg-sem   wrong title -> verify  expect build 0 / verify 1
  R3 neg-dup   verify duplicate pics  expect verify 1
  R4 neg-tbl   wrong table cell -> v  expect build 0 / verify 1
  R5 neg-rels  verify orphan media    expect verify 1
  R6 neg-enc   file_probe encrypted   expect exit 2

Exit: 0 if ALL cases match expectations, else 1.
Writes matrix_report.json (structured per-case stdout/verdict/reason) to --out-dir.

Hash semantics (B-CP1-04 fix):
  - per-run product hash: R1.actual.product_sha256 = SHA-256 of THIS run's built pptx.
    Bound to this run only; varies across runs because python-pptx embeds a
    creation timestamp in the OOXML core props.
  - determinism probe: builds the same input N times and compares product hashes
    to test whether the build is byte-stable. Result recorded, not assumed.
"""
import argparse, json, subprocess, sys, hashlib
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent          # .../pptx-shared-core/
CORE_ROOT = HERE                                 # the core directory itself
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
    """Best-effort parse of the script's JSON stdout; None if not JSON."""
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
        if isinstance(parsed, dict) and "verdict" in parsed:
            rec["tool_verdict"] = parsed["verdict"]
    else:
        rec["stdout_excerpt"] = so[:400]
    if se:
        rec["stderr_excerpt"] = se[:400]
    if note:
        rec["note"] = note
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", required=True, help="fresh unique output dir for this run")
    args = ap.parse_args()
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)

    cases = []

    # R1 positive build + verify
    r1out = out / "r1_pos_built.pptx"
    rc, so, se = run([sys.executable, "-X", "utf8", str(SCRIPTS / "build_pptx.py"),
                      "--template", str(FIXTURES / "pos_template.pptx"),
                      "--slot-map", str(CONTRACTS / "pos_slot_map.json"),
                      "--out", str(r1out)])
    r1build = rc
    rc2, so2, se2 = run([sys.executable, "-X", "utf8", str(SCRIPTS / "verify_pptx.py"),
                         "--output", str(r1out),
                         "--contract", str(CONTRACTS / "pos_contract.json"),
                         "--source", str(FIXTURES / "pos_template.pptx")])
    r1verify = rc2
    r1 = case_record("R1_pos", {"build": 0, "verify": 0},
                     {"build": r1build, "verify": r1verify}, so + "\n--- verify ---\n" + so2, se + "\n" + se2)
    if r1out.exists():
        r1["actual"]["product_sha256"] = sha256(r1out)
    cases.append(r1)

    # R2 negative semantic (wrong title)
    wrong_map = out / "r2_wrong_map.json"
    wrong_map.write_text(json.dumps({
        "anchors": [{"find": "{{NAME}}", "replace": "WRONG"}, {"find": "{{N}}", "replace": "v2"}],
        "slots": [{"slide": 1, "shape": "Title 1", "kind": "text", "expected": "Hello WRONG"},
                  {"slide": 2, "shape": "Table 1", "kind": "table", "row": 1, "col": 1, "expected": "Alpha"}]
    }), encoding="utf-8")
    r2out = out / "r2_neg_sem.pptx"
    rc, so, se = run([sys.executable, "-X", "utf8", str(SCRIPTS / "build_pptx.py"),
                      "--template", str(FIXTURES / "pos_template.pptx"),
                      "--slot-map", str(wrong_map), "--out", str(r2out)])
    r2build = rc
    rc2, so2, se2 = run([sys.executable, "-X", "utf8", str(SCRIPTS / "verify_pptx.py"),
                         "--output", str(r2out),
                         "--contract", str(CONTRACTS / "pos_contract.json")])
    cases.append(case_record("R2_neg_semantic", {"build": 0, "verify": 1},
                             {"build": r2build, "verify": r2verify if False else rc2},
                             so + "\n--- verify ---\n" + so2, se + "\n" + se2,
                             note="fake-PASS class: wrong slot text must FAIL"))

    # R3 negative duplicate pics
    rc, so, se = run([sys.executable, "-X", "utf8", str(SCRIPTS / "verify_pptx.py"),
                      "--output", str(FIXTURES / "neg_duplicate_pics.pptx"),
                      "--contract", str(CONTRACTS / "neg_duplicate_contract.json")])
    cases.append(case_record("R3_neg_duplicate", {"verify": 1}, {"verify": rc}, so, se,
                             note="image-pool stacking class"))

    # R4 negative wrong table
    wrong_tbl_map = out / "r4_wrong_tbl_map.json"
    wrong_tbl_map.write_text(json.dumps({
        "anchors": [{"find": "{{NAME}}", "replace": "World"}, {"find": "{{N}}", "replace": "v2"}],
        "slots": [{"slide": 1, "shape": "Title 1", "kind": "text", "expected": "Hello World"},
                  {"slide": 2, "shape": "Table 1", "kind": "table", "row": 1, "col": 1, "expected": "WRONG_VALUE"}]
    }), encoding="utf-8")
    r4out = out / "r4_neg_tbl.pptx"
    rc, so, se = run([sys.executable, "-X", "utf8", str(SCRIPTS / "build_pptx.py"),
                      "--template", str(FIXTURES / "pos_template.pptx"),
                      "--slot-map", str(wrong_tbl_map), "--out", str(r4out)])
    r4build = rc
    rc2, so2, se2 = run([sys.executable, "-X", "utf8", str(SCRIPTS / "verify_pptx.py"),
                         "--output", str(r4out),
                         "--contract", str(CONTRACTS / "pos_contract.json")])
    cases.append(case_record("R4_neg_wrong_table", {"build": 0, "verify": 1},
                             {"build": r4build, "verify": rc2},
                             so + "\n--- verify ---\n" + so2, se + "\n" + se2,
                             note="wrong-table-cell class"))

    # R5 negative rels residue
    rc, so, se = run([sys.executable, "-X", "utf8", str(SCRIPTS / "verify_pptx.py"),
                      "--output", str(FIXTURES / "neg_rels_residue.pptx"),
                      "--contract", str(CONTRACTS / "neg_duplicate_contract.json")])
    cases.append(case_record("R5_neg_rels_residue", {"verify": 1}, {"verify": rc}, so, se,
                             note="rels/media orphan residue class"))

    # R6 negative encrypted (via production chain build_pptx -> BLOCKED record)
    # B-CP1-05: ledger path is caller-supplied; pass explicit out-dir path so
    # the BLOCKED record lands in this matrix run evidence dir, not the core root.
    r6_ledger = out / "pending_human_blocked.json"
    rc, so, se = run([sys.executable, "-X", "utf8", str(SCRIPTS / "build_pptx.py"),
                      "--template", str(FIXTURES / "neg_encrypted.bin"),
                      "--slot-map", str(CONTRACTS / "pos_slot_map.json"),
                      "--out", str(out / "r6_should_not_exist.pptx"),
                      "--pending-human-ledger", str(r6_ledger)])
    cases.append(case_record("R6_neg_encrypted", {"build": 2}, {"build": rc}, so, se,
                             note="encrypted input -> BLOCKED exit 2 + structured record; uses build chain not file_probe alone"))

    overall = all(c["verdict"] == "PASS" for c in cases)

    # Determinism probe: same input built N times, compare product hashes
    probe_hashes = []
    for i in range(DETERMINISM_REPS):
        po = out / f"determinism_probe_{i}.pptx"
        rc, so, se = run([sys.executable, "-X", "utf8", str(SCRIPTS / "build_pptx.py"),
                          "--template", str(FIXTURES / "pos_template.pptx"),
                          "--slot-map", str(CONTRACTS / "pos_slot_map.json"),
                          "--out", str(po)])
        probe_hashes.append(sha256(po) if po.exists() else None)
    unique_hashes = sorted(set(h for h in probe_hashes if h))
    determinism = {
        "reps": DETERMINISM_REPS,
        "product_hashes": probe_hashes,
        "unique_count": len(unique_hashes),
        "byte_stable": len(unique_hashes) == 1,
        "conclusion": ("deterministic: same input -> identical product bytes across reps"
                       if len(unique_hashes) == 1
                       else "NON-deterministic: python-pptx embeds creation timestamp; per-run product hash varies. golden hash is NOT a fixed target; only per-run binding is valid.")
    }

    report = {
        "generated_at": datetime.now().astimezone().isoformat(),
        "core_root": str(CORE_ROOT),
        "overall_verdict": "PASS" if overall else "FAIL",
        "case_count": len(cases),
        "cases": cases,
        "determinism_probe": determinism,
        "done_when_mapping": {
            "neg_nonzero_exit": "R2/R3/R4/R5 exit 1 (FAIL verdict), R6 exit 2 (BLOCKED); all negatives non-zero",
            "R5_neg_rels_residue": "rels/media orphan residue detection (R5) is in the matrix case list and must exit 1",
            "pos_all_green": "R1 build=0 verify=0 (tool_verdict=PASS)",
            "per_run_product_sha256": (r1.get("actual", {}).get("product_sha256") if r1 else None),
            "determinism": determinism["conclusion"],
            "exit_code_contract": "PASS=0 / FAIL=1 / BLOCKED=2"
        }
    }
    (out / "matrix_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if overall else 1


if __name__ == "__main__":
    sys.exit(main())