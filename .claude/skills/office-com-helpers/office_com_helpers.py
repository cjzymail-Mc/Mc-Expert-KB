#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Office COM 操作的通用基础设施.

从 3rd-ppt-prj/pipeline/ppt_pipeline_common.py 抽出的纯通用部分：
  - COM 属性 / 方法的安全访问（com_get / com_call / is_in_group）
  - UTF-8 安全 print（绕过 Windows cp1252 console）
  - Excel COM 读取（含模糊 sheet 匹配 + 加密文件支持）
  - 文本字数 / 行数 clamp
  - 数据类型归一化（safe_text / numeric / to_rows）
  - 颜色转换（hex → COM RGB long）

设计原则：
  - 绝不 raise，全部 try-except 兜底
  - 不持有 COM 对象，传入即用，避免 RPC 句柄过期
  - Excel 永远 read-only 打开，关闭时不保存

来源：3rd-ppt-prj/pipeline/ppt_pipeline_common.py（2026-05-26 提为用户级 skill）
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, List, Tuple


# ────────────────── 安全 print ──────────────────

def safe_print(*args, **kwargs) -> None:
    """print() that survives Windows cp1252 consoles.

    Encodes the line as UTF-8; falls back to ASCII-replace if console can't.
    Uses regular print() (not buffer.write) to avoid MINGW64 double-output.
    """
    end = kwargs.get("end", "\n")
    line = " ".join(str(a) for a in args)
    try:
        print(line, end=end)
    except UnicodeEncodeError:
        ascii_line = line.encode(sys.stdout.encoding or "ascii", "replace").decode(
            sys.stdout.encoding or "ascii"
        )
        print(ascii_line, end=end)


# ────────────────── Office 明文/密文检测 + 后端路由 ──────────────────
#
# 〔单点实测 2026-06-03 · 当前 Ldterm 配置 · 不是永久保证〕
# 本机 Ldterm 只对白名单 Office 进程（POWERPNT/WINWORD/EXCEL）的写做透明加密；
# python.exe 写出的是明文。所以 *已解密* 的 .xlsx/.pptx/.docx 可走 python 库
# （openpyxl/python-pptx/python-docx）读改写，比 COM 快 5–20×。
# 但 **不能假设文件默认解密** —— 碰文件第一步永远先读 8 字节判明文/密文。

# 首字节 magic
_PLAINTEXT_ZIP = b"PK\x03\x04"          # 50 4B 03 04 = OOXML 明文（zip 包）
_LDTERM_CIPHER = b"\x88\x7d\x1c"        # 88 7D 1C    = Ldterm 密文头


def read_magic(path, n: int = 8) -> bytes:
    """读文件前 n 个字节；读不到返回 b''（绝不 raise）。"""
    try:
        with open(path, "rb") as f:
            return f.read(n)
    except Exception:
        return b""


def detect_office_cipher(path) -> Tuple[str, str]:
    """碰 Office 文件的**第一动作**：读 8 字节判明文/密文，返回后端路由决策。

    这是「office-backend-router」原语：把"该走 python 还是 COM 还是 STOP"
    收成一个 canonical 入口，省得每次重推 8 字节检测、密文时统一礼貌处理。

    Returns:
        (route, reason)
        route ∈ {"python", "com", "stop"}:
          - "python" → 首字节确认 50 4B 03 04 明文 → 可走 openpyxl / python-pptx /
                       python-docx（快 5–20×）。仅限读/数据填充；视觉渲染/导 PNG 仍 COM。
          - "stop"   → 首字节确认 88 7D 1C Ldterm 密文 → 按硬规则 STOP：把路径+hex
                       报用户、等其用 DLP 工具解密。**禁** python 换库硬上。
                       （若调用方本就是 COM 路径，密文 COM 能透明读，按 COM 正常走即可。）
                       【cn/coder-api 链路例外】密文经 ~/.claude/skills/team-task-api/run_cn_task.ps1
                       由门脚本**确定性自动直穿 COM 读 helper、不停**（路由是脚本决策非模型
                       判断）；此函数仍返回 "stop" 不变——例外在门脚本侧，别据本返回值在 cn
                       链路里 STOP。主环境 / 原 coder 链路仍按 "stop" 停。见 SKILL.md 同条旁注。
          - "com"    → 既非明文也非已知密文头 / 读取失败 → 无法判定 → 保守回退 COM。
        reason: 人读的一句话，含首字节 hex，便于排查 / 报用户。

    设计：**fail-safe** —— 任何不确定（读不到、未知 magic）都**不**返回 "python"，
    宁可回退 COM。让 python 捷径只在"确认明文"时才开。
    """
    head = read_magic(path, 8)
    hex_str = " ".join(f"{b:02X}" for b in head) if head else "(读取失败)"
    if head.startswith(_PLAINTEXT_ZIP):
        return "python", f"明文 OOXML（首字节 {hex_str}）→ 可走 python 库"
    if head.startswith(_LDTERM_CIPHER):
        return "stop", f"Ldterm 密文（首字节 {hex_str}）→ STOP，报用户解密；如需读取改走 COM"
    return "com", f"未知/读取失败（首字节 {hex_str}）→ 无法判定，保守回退 COM"


# ────────────────── 数据类型归一化 ──────────────────

def safe_text(v: Any) -> str:
    """None → '', strip whitespace."""
    return "" if v is None else str(v).strip()


def numeric(v: Any):
    """Convert to float, return None on failure."""
    try:
        if v is None or v == "":
            return None
        return float(v)
    except Exception:
        return None


def to_rows(value: Any) -> List[List[Any]]:
    """Normalize COM return (tuple/scalar/list) to List[List[Any]]."""
    if value is None:
        return []
    if isinstance(value, tuple):
        rows = []
        for row in value:
            if isinstance(row, tuple):
                rows.append(list(row))
            else:
                rows.append([row])
        return rows
    if isinstance(value, list):
        if value and isinstance(value[0], list):
            return value
        return [value]
    return [[value]]


# ────────────────── COM 安全访问 ──────────────────

def com_get(obj, attr: str, default=None):
    """Safe getattr for COM objects.

    Only supports single-level attributes (e.g. 'Name', 'Left').
    For nested access (shape.TextFrame.TextRange), call in multiple steps.
    """
    try:
        return getattr(obj, attr)
    except Exception:
        return default


def com_call(obj, method: str, *args, **kwargs):
    """Safe method call on COM objects.

    Returns None on failure (callers must check).
    """
    try:
        fn = getattr(obj, method)
        return fn(*args, **kwargs)
    except Exception:
        return None


def is_in_group(shp) -> bool:
    """Check if a PowerPoint Shape is inside a group.

    BUG FIX: getattr(shape, 'ParentGroup', None) raises COM exception
    instead of returning None for non-grouped shapes. Must use try-except.
    """
    try:
        shp.ParentGroup
        return True
    except Exception:
        return False


# ────────────────── 颜色转换 ──────────────────

def hex_to_com_rgb(hex_color: str) -> int:
    """Convert 'RRGGBB' hex string to the COM RGB long integer (BGR order).

    PowerPoint/Excel COM uses BGR internally:
      COM_RGB = R + G*256 + B*65536
    """
    r = int(hex_color[0:2], 16)
    g = int(hex_color[2:4], 16)
    b = int(hex_color[4:6], 16)
    return r + g * 256 + b * 65536


# ────────────────── 文本 clamp ──────────────────

def clamp_text(text: str, max_chars: int, max_lines: int) -> str:
    """Clamp text to fit PPT shape: enforce both line count and character count.

    Line clamp: hard cut at max_lines.
    Char clamp: cut at nearest sentence boundary when exceeding max_chars
      (boundaries: 。！？\\n；，、 space), keeping at least 50% of max_chars.
    """
    t = safe_text(text)
    if max_lines > 0:
        lines = t.splitlines() or [t]
        t = "\n".join(lines[:max_lines])
    if max_chars > 0 and len(t) > max_chars:
        truncated = t[:max_chars]
        for sep in ['。', '！', '？', '\n', '；', '，', '、', ' ']:
            idx = truncated.rfind(sep)
            if idx > max_chars * 0.5:
                t = truncated[:idx + 1].rstrip()
                break
        else:
            t = truncated
    return t


# ────────────────── Excel COM 读取 ──────────────────

def load_excel_rows(excel_path: str,
                    sheet_name: str = "Sheet1",
                    fuzzy_keyword: str = "") -> Tuple[List[List[Any]], str, List[str]]:
    """Read an Excel sheet via COM (supports encrypted / Ldterm-protected files).

    Sheet matching strategy (in order):
      1. Exact name match
      2. Substring match on `fuzzy_keyword` (if provided)
      3. Fallback to first sheet

    Args:
        excel_path: absolute path to .xlsx / .xls.
        sheet_name: preferred sheet name.
        fuzzy_keyword: substring used in step 2 (e.g. '问卷' to match '问卷sheet').

    Returns:
        (rows, matched_name, notes)
        - rows: List[List[Any]], raw cell values (None for empty)
        - matched_name: actual sheet name resolved
        - notes: list of fallback reasons (empty if exact match)
    """
    import win32com.client

    notes: List[str] = []
    # 用 DispatchEx 强制启动隔离 Excel 进程实例（不复用用户单例进程）。
    # 2026-05-27 acceptance gate 实战暴露：Dispatch 复用用户 Excel 进程时，
    # finally 里的 excel.Quit() 会连带关掉用户所有 workbook。DispatchEx 解耦。
    excel = win32com.client.DispatchEx("Excel.Application")
    excel.Visible = False
    excel.DisplayAlerts = False

    try:
        wb = excel.Workbooks.Open(str(Path(excel_path).resolve()), 0, True)  # ReadOnly=True

        matched = None
        matched_name = ""
        for i in range(1, wb.Sheets.Count + 1):
            if wb.Sheets(i).Name == sheet_name:
                matched = wb.Sheets(i)
                matched_name = sheet_name
                break

        if matched is None and fuzzy_keyword:
            for i in range(1, wb.Sheets.Count + 1):
                sname = wb.Sheets(i).Name
                if fuzzy_keyword in sname:
                    matched = wb.Sheets(i)
                    matched_name = sname
                    notes.append(f"exact '{sheet_name}' not found, fuzzy match '{sname}'")
                    break

        if matched is None:
            matched = wb.Sheets(1)
            matched_name = matched.Name
            notes.append(f"sheet '{sheet_name}' not found, fallback to first '{matched_name}'")

        raw = matched.UsedRange.Value
        if raw is None:
            raise RuntimeError("Excel sheet is empty")

        rows = to_rows(raw)
        if not rows:
            raise RuntimeError("Excel sheet is empty")

        wb.Close(False)
        return rows, matched_name, notes
    finally:
        try:
            excel.Quit()
        except Exception:
            pass


# ────────────────── Pipeline trace logger (供 ppt-acceptance-check L4 用) ──────────────────

class TraceLogger:
    """jsonl pipeline trace logger.

    用法：
        trace = TraceLogger("debug/apparel_trace.jsonl")
        with trace.shape_write("Chart 63", "bar_stacked_temp_range") as ev:
            try:
                chart.ChartData.Activate()
                ev["ok"] = True
            except Exception:
                trace.event("com_api_failed_but_continued",
                            shape="Chart 63", api="ChartData.Activate",
                            attempts=3, continued=True)
                ev["ok"] = False
        trace.event("gpt_strengths", called=False, reason="mc_gpt=n")
        trace.close()

    所有 event 行包含 ts + event 名 + 任意 kwargs。
    ppt-acceptance-check 的 L4 行为层会读这份 jsonl 做 trace_event_present /
    no_trace_event 断言。

    设计原则：
      - 立即落盘（line-buffered + flush），任何 pipeline 崩溃也不丢日志
      - 失败不抛（写文件错误吞掉），不影响主流程
      - 上下文管理器（shape_write）方便嵌套和"成功 / 失败"二相事件
    """

    def __init__(self, out_path) -> None:
        import datetime as _dt
        self._dt = _dt
        self.out_path = Path(out_path)
        self.out_path.parent.mkdir(parents=True, exist_ok=True)
        # 'a' 模式：同一次 pipeline 多个调用方都能 append 进去
        self._fp = open(self.out_path, "a", encoding="utf-8", buffering=1)

    def _now(self) -> str:
        return self._dt.datetime.now().isoformat(timespec="seconds")

    def event(self, name: str, **fields) -> None:
        """Write one event line."""
        if self._fp is None:
            return
        rec = {"ts": self._now(), "event": name, **fields}
        try:
            self._fp.write(json.dumps(rec, ensure_ascii=False) + "\n")
            self._fp.flush()
        except Exception:
            pass

    class _ShapeWriteCtx:
        def __init__(self, parent, shape: str, strategy: str, slide=None):
            self.parent = parent
            self.shape = shape
            self.strategy = strategy
            self.slide = slide
            self.data: dict = {}

        def __enter__(self):
            self.parent.event("shape_write_start", shape=self.shape,
                              strategy=self.strategy, slide=self.slide)
            return self.data

        def __exit__(self, exc_type, exc_val, exc_tb):
            extras = {k: v for k, v in self.data.items() if k != "ok"}
            self.parent.event("shape_write_end", shape=self.shape,
                              strategy=self.strategy, slide=self.slide,
                              ok=self.data.get("ok", exc_type is None),
                              **extras)
            return False  # 不吞异常

    def shape_write(self, shape: str, strategy: str, slide=None):
        return TraceLogger._ShapeWriteCtx(self, shape, strategy, slide=slide)

    def close(self) -> None:
        if self._fp is not None:
            try:
                self._fp.close()
            except Exception:
                pass
            self._fp = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False


# ────────────────── I/O helpers ──────────────────

def write_md(path: Path, lines: List[str]) -> None:
    """Write a list of lines to a markdown file (UTF-8, LF + trailing newline)."""
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_json(path: Path, data: Any) -> None:
    """Write JSON to file (UTF-8, indent=2, ensure_ascii=False)."""
    Path(path).write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )


# ────────────────── 自检（直接跑这个文件可以测） ──────────────────

if __name__ == "__main__":
    safe_print("office_com_helpers self-test")
    assert safe_text(None) == ""
    assert safe_text("  hi  ") == "hi"
    assert numeric("3.14") == 3.14
    assert numeric("abc") is None
    assert to_rows(None) == []
    assert to_rows(((1, 2), (3, 4))) == [[1, 2], [3, 4]]
    assert hex_to_com_rgb("FF0000") == 0xFF
    assert hex_to_com_rgb("00FF00") == 0xFF * 256
    assert clamp_text("aaa。bbb。ccc。", 5, 0) == "aaa。"
    assert clamp_text("line1\nline2\nline3", 0, 2) == "line1\nline2"

    # detect_office_cipher 自检（写临时文件测三态 + fail-safe）
    import tempfile as _tf
    _tmpdir = Path(_tf.gettempdir())
    _pk = _tmpdir / "_router_pk.bin"
    _pk.write_bytes(b"PK\x03\x04rest")
    assert detect_office_cipher(_pk)[0] == "python"
    _ld = _tmpdir / "_router_ld.bin"
    _ld.write_bytes(b"\x88\x7d\x1c\x00rest")
    assert detect_office_cipher(_ld)[0] == "stop"
    _unk = _tmpdir / "_router_unk.bin"
    _unk.write_bytes(b"\x00\x01\x02\x03")
    assert detect_office_cipher(_unk)[0] == "com"
    assert detect_office_cipher(_tmpdir / "_does_not_exist.bin")[0] == "com"  # fail-safe
    for _f in (_pk, _ld, _unk):
        _f.unlink()

    # TraceLogger 自检
    import tempfile, os
    tmp = Path(tempfile.gettempdir()) / "trace_self_test.jsonl"
    if tmp.exists():
        tmp.unlink()
    with TraceLogger(tmp) as t:
        t.event("test_event", x=1)
        with t.shape_write("Chart 63", "strategy_a", slide=12) as ev:
            ev["ok"] = True
            t.event("com_api_failed_but_continued", api="foo", attempts=2)
    lines = tmp.read_text(encoding="utf-8").strip().split("\n")
    assert len(lines) == 4  # event + start + nested + end
    parsed = [json.loads(l) for l in lines]
    assert parsed[0]["event"] == "test_event" and parsed[0]["x"] == 1
    assert parsed[1]["event"] == "shape_write_start"
    assert parsed[2]["event"] == "com_api_failed_but_continued"
    assert parsed[3]["event"] == "shape_write_end" and parsed[3]["ok"] is True
    tmp.unlink()

    safe_print("  OK  纯函数 + TraceLogger 自检通过（COM 相关函数需手动测）")
