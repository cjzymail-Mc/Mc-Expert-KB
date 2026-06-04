#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""excel-acceptance-check —— Excel 自动化产线交付前验收 skill 的 CLI 入口。

把分层验收（L0 结构 / L1 数据 /（第二批）L3 空值）合到一份报告，输出
PASS / FAIL 二元结论 + 必修清单。是 ppt-acceptance-check 的 Excel 姊妹版
（contract.py / common.py 的 Finding·LayerResult 为其零改动副本，report 为 Excel 化改写）。

护栏（写进设计，不可违反）：
  ① 期望值只来自外部真相：L1 走 inline(仅结构) / excel: DSL(外部 xlsx)，禁 hardcode 工艺单值。
  ② auto-fix 不在本脚本：脚本只断言不改文件；连续 2 轮没修好 → ESCALATE 给人（主 Claude 编排）。
  ③ 编排权留主 Claude：本脚本 ReadOnly 打开、只读不写 xlsx、不读写契约。

用法:
  python excel_acceptance_check.py --xlsx "待验收.xlsx" \\
      --contract acceptance/rd48.json --layers L0,L1 \\
      --mode production --out-dir "out/"

  # 桥接当前打开的 Excel（避开文件锁）
  python excel_acceptance_check.py --active --xlsx "待验收.xlsx" --contract c.json

Exit codes:
  0 = PASS（无必修违反）
  1 = FAIL（有必修违反）
  2 = 配置错误 / 文件不存在 / COM 失败

COM 生存反射（com-survival-reflexes）：DispatchEx 起隔离进程、ReadOnly 打开、
finally 里 Close+Quit 兜底。**单次运行须由调用方套 20-30s 硬超时；连挂 2 次 CUTOVER**
（本脚本不内嵌 wall-clock timeout，沿用 inspect-excel-template 同款约定，超时归调用方编排）。
"""
from __future__ import annotations

import argparse
import datetime as dt
import os
import sys
import traceback
from pathlib import Path
from typing import List, Optional

HERE = Path(__file__).parent.resolve()
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

HELPERS_DIR = Path.home() / ".claude" / "skills" / "office-com-helpers"
if HELPERS_DIR.exists() and str(HELPERS_DIR) not in sys.path:
    sys.path.insert(0, str(HELPERS_DIR))

try:
    from office_com_helpers import safe_print
except Exception:
    def safe_print(*args, **kwargs):
        end = kwargs.get("end", "\n")
        line = " ".join(str(a) for a in args)
        try:
            print(line, end=end)
        except UnicodeEncodeError:
            print(line.encode("ascii", "replace").decode("ascii"), end=end)


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")


def parse_layers(spec: Optional[str]) -> List[str]:
    if not spec:
        return ["L0", "L1"]   # 默认第一批；L3 显式开启
    out: List[str] = []
    for tok in spec.replace(" ", "").split(","):
        if tok:
            out.append(tok.upper())
    return out


def _resolve_workbook(excel, *, active: bool, xlsx_path: Optional[str]):
    """获取 Workbook。返回 (wb, opened_by_us)。"""
    if active:
        if xlsx_path:
            target = str(Path(xlsx_path).resolve()).lower()
            cnt = int(getattr(excel.Workbooks, "Count", 0) or 0)
            for i in range(1, cnt + 1):
                w = excel.Workbooks(i)
                try:
                    if str(w.FullName).lower() == target:
                        return w, False
                except Exception:
                    continue
            raise RuntimeError(
                f"--active 找不到匹配 {xlsx_path} 的已打开 workbook；"
                f"当前打开的：{[excel.Workbooks(i).Name for i in range(1, cnt + 1)]}"
            )
        try:
            wb = excel.ActiveWorkbook
        except Exception:
            raise RuntimeError("无 ActiveWorkbook；请在 Excel 打开待验收 xlsx")
        if wb is None:
            raise RuntimeError("--active 模式：Excel 已开但没有 ActiveWorkbook")
        return wb, False
    if not xlsx_path:
        raise RuntimeError("文件模式需要 --xlsx 路径")
    wb = excel.Workbooks.Open(str(Path(xlsx_path).resolve()), 0, True)  # ReadOnly
    return wb, True


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Excel 验收（L0 结构 / L1 数据 / L3 空值 + 三态 severity + 单一报告）"
    )
    parser.add_argument("--xlsx", default="", help="待验收 .xlsx（--active 下用于精确定位）")
    parser.add_argument("--active", action="store_true",
                        help="桥接当前打开的 Excel（GetActiveObject，不 Quit 用户进程）")
    parser.add_argument("--contract", default=None,
                        help="acceptance_contract.json 路径；省略=无规则(全 PASS 空跑)")
    parser.add_argument("--layers", default=None,
                        help="逗号分隔层列表，如 'L0,L1,L3'；默认 'L0,L1'")
    parser.add_argument("--mode", default="production",
                        choices=["production", "smoke"],
                        help="契约模式；smoke 自动按 rule_overrides 豁免一批规则")
    parser.add_argument("--out-dir", default=None,
                        help="报告输出目录；默认 acceptance-<timestamp>/")
    args = parser.parse_args()

    if not args.xlsx and not args.active:
        safe_print("[ERR] 必须给 --xlsx 或 --active")
        return 2

    layers = parse_layers(args.layers)

    if args.out_dir:
        out_dir = Path(args.out_dir)
    else:
        ts = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
        out_dir = Path(f"acceptance-{ts}")
    out_dir = out_dir.resolve()

    from contract import Contract
    try:
        contract = Contract.load(args.contract, mode=args.mode)
    except Exception as e:
        safe_print(f"[ERR] 契约加载失败：{e}")
        return 2

    safe_print(f"[excel-acceptance-check] mode={args.mode} layers={','.join(layers)}")
    safe_print(f"  contract: {args.contract or '(default/empty)'}")
    safe_print(f"  xlsx: {args.xlsx or '(ActiveWorkbook)'}")
    safe_print(f"  out_dir: {out_dir}")

    import win32com.client
    if args.active:
        try:
            excel = win32com.client.GetActiveObject("Excel.Application")
        except Exception as e:
            safe_print(f"[ERR] --active 但 Excel 未运行: {e}")
            return 2
        app_opened_by_us = False
    else:
        excel = win32com.client.DispatchEx("Excel.Application")
        app_opened_by_us = True
    try:
        excel.Visible = False
    except Exception:
        pass
    try:
        excel.DisplayAlerts = False
    except Exception:
        pass

    wb = None
    wb_opened = False
    layer_results: list = []
    sheets_seen: list = []

    try:
        wb, wb_opened = _resolve_workbook(excel, active=args.active, xlsx_path=args.xlsx or None)
        try:
            sheets_seen = [str(wb.Sheets(i).Name)
                           for i in range(1, int(getattr(wb.Sheets, "Count", 0) or 0) + 1)]
        except Exception:
            sheets_seen = []

        if "L0" in layers:
            safe_print("\n[L0] 结构...")
            from layers import structure as layer_structure
            r = layer_structure.run(contract=contract, wb=wb)
            layer_results.append(r)
            safe_print(f"  L0: passed={r.passed_count} must_fix={r.must_fix_violations}")

        if "L1" in layers:
            safe_print("\n[L1] 数据...")
            from layers import data as layer_data
            r = layer_data.run(contract=contract, wb=wb)
            layer_results.append(r)
            safe_print(f"  L1: passed={r.passed_count} must_fix={r.must_fix_violations}")

        if "L3" in layers:
            safe_print("\n[L3] 空值...")
            try:
                from layers import blanks as layer_blanks
                r = layer_blanks.run(contract=contract, wb=wb)
            except ImportError:
                from layers.common import LayerResult
                r = LayerResult(layer="L3")
                r.degraded = True
                r.degraded_reason = "blanks.py 未实现（第二批）"
                r.notes.append("L3 未落地，跳过")
            layer_results.append(r)
            safe_print(f"  L3: passed={r.passed_count} must_fix={r.must_fix_violations}"
                       + ("  ⚠ degraded" if r.degraded else ""))

    except Exception as e:
        safe_print(f"\n[ERR] 验收过程异常：{e}")
        safe_print(traceback.format_exc())
        return 2
    finally:
        if wb_opened and wb is not None:
            try:
                wb.Close(False)
            except Exception:
                pass
        if app_opened_by_us:
            try:
                excel.Quit()
            except Exception:
                pass

    from report import aggregate, write_reports
    report = aggregate(
        layer_results, contract_path=args.contract or "",
        mode=args.mode, sheets=sheets_seen,
        args_summary={
            "xlsx": args.xlsx or "<active>",
            "layers": layers,
            "contract": args.contract or "",
        },
    )
    write_reports(report, out_dir)

    safe_print("")
    safe_print("=" * 60)
    safe_print(f"结论: {report['verdict']}  "
               f"(必修 {report['summary']['must_fix']} / "
               f"警告 {report['summary']['warn']} / "
               f"容忍 {report['summary']['tolerated']})")
    safe_print(f"报告: {out_dir / 'acceptance_report.md'}")
    safe_print(f"      {out_dir / 'acceptance_report.json'}")

    return 0 if report["verdict"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
