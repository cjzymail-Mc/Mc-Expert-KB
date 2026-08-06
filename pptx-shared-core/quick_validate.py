#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""quick_validate.py - entry reachability + minimal positive chain.

Run from an entry skill directory (entries/claude or entries/codex). It resolves
the shared core by the documented relative path (../../), confirms the core
scripts physically exist, runs a minimal file_probe + build + verify chain on the
shipped fixtures, and prints a structured JSON result.

Exit: 0 if the entry can reach and run the core; 1 otherwise.

Usage:
  python <entry_dir>/../../quick_validate.py            # auto-resolves entry via --entry
  python quick_validate.py --entry <path-to-entry-skill-dir> --out-dir <fresh>
"""
import argparse, json, subprocess, sys, hashlib
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent          # pptx-shared-core/
SCRIPTS = HERE / "scripts"
FIXTURES = HERE / "fixtures"
CONTRACTS = HERE / "contracts"


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def run(cmd):
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    return proc.returncode, (proc.stdout or "").strip(), (proc.stderr or "").strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--entry", required=True, help="absolute path to the entry skill dir")
    ap.add_argument("--out-dir", required=True, help="fresh unique output dir")
    args = ap.parse_args()
    entry = Path(args.entry).resolve()
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)

    result = {
        "entry": str(entry),
        "generated_at": datetime.now().astimezone().isoformat(),
        "steps": [],
    }

    # Step 1: resolve core by documented relative path ../../  (entry -> entries/ -> core/)
    resolved_core = (entry / ".." / "..").resolve()
    result["documented_relative"] = "../../"
    result["resolved_core_dir"] = str(resolved_core)
    core_ok = (resolved_core / "scripts" / "file_probe.py").exists()
    result["core_file_probe_exists"] = core_ok
    result["steps"].append({"step": "resolve_core_relative", "ok": core_ok,
                            "resolved": str(resolved_core / "scripts" / "file_probe.py")})
    if not core_ok:
        result["overall"] = "FAIL"
        result["reason"] = "documented relative path ../../ does not resolve to the shared core"
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 1

    # Step 2: file_probe on pos_template (expect exit 0, route python)
    rc, so, se = run([sys.executable, "-X", "utf8", str(SCRIPTS / "file_probe.py"),
                      str(FIXTURES / "pos_template.pptx")])
    probe_ok = (rc == 0)
    result["steps"].append({"step": "file_probe_positive", "ok": probe_ok,
                            "exit": rc, "stdout": so[:300]})

    # Step 3: minimal build + verify chain
    built = out / "quick_pos_built.pptx"
    rc, so, se = run([sys.executable, "-X", "utf8", str(SCRIPTS / "build_pptx.py"),
                      "--template", str(FIXTURES / "pos_template.pptx"),
                      "--slot-map", str(CONTRACTS / "pos_slot_map.json"),
                      "--out", str(built)])
    build_ok = (rc == 0 and built.exists())
    result["steps"].append({"step": "build_positive", "ok": build_ok,
                            "exit": rc, "product_sha256": sha256(built) if built.exists() else None})

    rc2, so2, se2 = run([sys.executable, "-X", "utf8", str(SCRIPTS / "verify_pptx.py"),
                         "--output", str(built),
                         "--contract", str(CONTRACTS / "pos_contract.json"),
                         "--source", str(FIXTURES / "pos_template.pptx")])
    verify_ok = (rc2 == 0)
    result["steps"].append({"step": "verify_positive", "ok": verify_ok,
                            "exit": rc2, "stdout": so2[:300]})

    overall = probe_ok and build_ok and verify_ok
    result["overall"] = "PASS" if overall else "FAIL"
    (out / "quick_validate_report.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if overall else 1


if __name__ == "__main__":
    sys.exit(main())