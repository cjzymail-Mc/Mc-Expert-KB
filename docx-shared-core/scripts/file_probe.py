#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""file_probe.py - typed magic-byte router for Office/DOCX inputs.

First action on ANY input file. Reads the first 8 bytes and routes:
  50 4B 03 04 -> plaintext OOXML      -> python  -> exit 0
  88 7D 1C    -> encrypted (Ldterm)   -> BLOCKED -> exit 2
  D0 CF 11 E0 -> OLE/CFB legacy .doc  -> BLOCKED -> exit 2 (unsupported, not python-docx)
  other/fail  -> unknown/unreadable   -> BLOCKED -> exit 2

Fail-safe: unknown/unreadable NEVER routes to python. A python-only core cannot
fall back to COM, so OLE/CFB legacy .doc containers are refused here rather than
handed to python-docx to guess-read. A future human-triggered COM extension may
handle them.

Source: office-com-helpers.detect_office_cipher (rule extracted, not imported).
Mirrors pptx-shared-core/scripts/file_probe.py with OLE explicitly named.

Usage: python file_probe.py <path>
Exit: 0 (python route) / 2 (blocked)
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

_PLAINTEXT_ZIP = b"PK\x03\x04"      # 50 4B 03 04
_LDTERM_CIPHER = b"\x88\x7d\x1c"    # 88 7D 1C
_OLE_CFB = b"\xD0\xCF\x11\xE0"      # D0 CF 11 E0  (legacy .doc / CFB storage)


def read_magic(path, n: int = 8) -> bytes:
    try:
        with open(path, "rb") as fh:
            return fh.read(n)
    except Exception:
        return b""


def sha256_of(path) -> str:
    h = hashlib.sha256()
    try:
        with open(path, "rb") as fh:
            for chunk in iter(lambda: fh.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()
    except Exception:
        return ""


def probe(path) -> dict:
    head = read_magic(path, 8)
    hex_str = " ".join(f"{b:02X}" for b in head) if head else "(unreadable)"
    if head.startswith(_PLAINTEXT_ZIP):
        route, reason = "python", f"plaintext OOXML (first bytes {hex_str}) -> python route"
    elif head.startswith(_LDTERM_CIPHER):
        route, reason = "BLOCKED", f"encrypted (first bytes {hex_str}) -> STOP, report path+hex"
    elif head.startswith(_OLE_CFB):
        route, reason = "BLOCKED", (f"OLE/CFB legacy .doc (first bytes {hex_str}) -> "
                                    "BLOCKED: unsupported, needs COM extension; not python-docx")
    else:
        route, reason = "BLOCKED", f"unknown/unreadable (first bytes {hex_str}) -> BLOCKED"
    return {"path": str(path), "route": route, "reason": reason, "hex": hex_str,
            "sha256": sha256_of(path)}


def main() -> int:
    if len(sys.argv) < 2:
        print(json.dumps({"error": "usage: file_probe.py <path>"}))
        return 2
    path = sys.argv[1]
    if not Path(path).is_file():
        print(json.dumps({"path": str(path), "route": "BLOCKED",
                          "reason": "file not found", "hex": ""}))
        return 2
    result = probe(path)
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["route"] == "python" else 2


if __name__ == "__main__":
    sys.exit(main())
