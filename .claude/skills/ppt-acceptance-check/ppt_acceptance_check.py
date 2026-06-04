#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ppt-acceptance-check —— 完整 PPT 验收 skill 的 CLI 入口.

把 6 层验收（L0 配对 / L1 数据 / L2 格式 / L3 染色 / L4 行为 / L5 视觉）
合到一份报告里，输出 PASS / FAIL 二元结论 + 必修清单。

详细设计：plan-2026-05-27-acceptance-skill.md

用法:
  python ppt_acceptance_check.py \\
      --new "v1.6.pptx" \\
      --template "apparel-page13-14-template.pptx" \\
      --slide-pairs "12:13,13:14" \\
      --contract acceptance/apparel.json \\
      --pipeline-trace debug/apparel_trace.jsonl \\
      --layers L0,L1,L2,L3,L4,L5 \\
      --mode production \\
      --out-dir debug/acceptance-apparel/

  # smoke 模式（自动豁免 GPT 相关规则）
  python ppt_acceptance_check.py --new x.pptx --template y.pptx \\
      --slide-pairs 12:13 --contract acceptance/apparel.json --mode smoke

  # 只跑 L0（验配对策略）
  python ppt_acceptance_check.py --new x.pptx --template y.pptx \\
      --slide-pairs 12:13 --layers L0

  # 桥接当前打开的 PPT（避开文件锁）
  python ppt_acceptance_check.py --active-new --pptx-new "v1.6.pptx" \\
      --template y.pptx --slide-pairs 12:13

Exit codes:
  0 = PASS（无必修违反）
  1 = FAIL（有必修违反）
  2 = 配置错误 / 文件不存在 / COM 失败
"""
from __future__ import annotations

import argparse
import datetime as dt
import os
import sys
import traceback
from pathlib import Path
from typing import List, Optional, Tuple

# 让 layers/ 子包能 import contract / pairing
HERE = Path(__file__).parent.resolve()
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

# 把 office-com-helpers 接进来（safe_print 等）
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


# ────────── slide_pairs 解析 ──────────

def parse_slide_pairs(spec: str) -> List[Tuple[int, int]]:
    """'12:13,13:14' -> [(12,13),(13,14)]."""
    out: List[Tuple[int, int]] = []
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if ":" not in part:
            raise ValueError(f"slide-pair 缺少 ':'：{part!r}")
        a, b = part.split(":", 1)
        out.append((int(a), int(b)))
    return out


def parse_layers(spec: Optional[str]) -> List[str]:
    if not spec:
        return ["L0", "L1", "L2", "L3", "L4", "L5"]
    out: List[str] = []
    for tok in spec.replace(" ", "").split(","):
        if tok:
            out.append(tok.upper())
    return out


# ────────── COM Presentation 解析 ──────────

def _resolve_presentation(ppt_app, *, active: bool, pptx_path: Optional[str]):
    """获取 Presentation。返回 (pres, opened_by_us)。沿用 ppt-visual-fidelity-check 的 pattern。"""
    if active:
        if pptx_path:
            target = str(Path(pptx_path).resolve()).lower()
            for pres in list(ppt_app.Presentations):
                try:
                    if str(pres.FullName).lower() == target:
                        return pres, False
                except Exception:
                    continue
            raise RuntimeError(
                f"--active 找不到匹配 {pptx_path} 的已打开 PPT；"
                f"当前打开的：{[p.Name for p in ppt_app.Presentations]}"
            )
        try:
            return ppt_app.ActivePresentation, False
        except Exception:
            raise RuntimeError("无 ActivePresentation；请在 PowerPoint 打开演示文稿")
    if not pptx_path:
        raise RuntimeError("文件模式需要 --pptx 路径")
    pres = ppt_app.Presentations.Open(
        str(Path(pptx_path).resolve()),
        ReadOnly=True, WithWindow=True,
    )
    return pres, True


# ────────── 主流程 ──────────

def main() -> int:
    parser = argparse.ArgumentParser(
        description="PPT 完整验收（6 层 L0-L5 + 三态 severity + 单一报告）"
    )
    parser.add_argument("--new", dest="new_path",
                        help="新生成的 PPT（待验收）")
    parser.add_argument("--template", dest="tpl_path",
                        help="标杆 PPT")
    parser.add_argument("--active-new", action="store_true",
                        help="新 PPT 用当前打开的（配合 --new 路径精确定位多份打开场景）")
    parser.add_argument("--active-template", action="store_true",
                        help="标杆 PPT 用当前打开的")
    parser.add_argument("--slide-pairs", required=True,
                        help="'new_idx:template_idx,...'，如 '12:13,13:14'")
    parser.add_argument("--contract", default=None,
                        help="acceptance_contract.json 路径；省略=全严格默认")
    parser.add_argument("--pipeline-trace", default=None,
                        help="pipeline 落盘的 jsonl trace；L4 行为层用，缺失则 L4 降级")
    parser.add_argument("--layers", default=None,
                        help="逗号分隔的层列表，如 'L0,L1,L4'；默认 6 层全跑")
    parser.add_argument("--mode", default="production",
                        choices=["production", "smoke"],
                        help="契约模式；smoke 会自动豁免一批规则（如 GPT 相关）")
    parser.add_argument("--out-dir", default=None,
                        help="报告输出目录；默认 debug/acceptance-<timestamp>/")
    args = parser.parse_args()

    # ────────── 入参校验 ──────────
    if not args.new_path and not args.active_new:
        safe_print("[ERR] 必须给 --new 或 --active-new")
        return 2
    if not args.tpl_path and not args.active_template:
        safe_print("[ERR] 必须给 --template 或 --active-template")
        return 2

    try:
        slide_pairs = parse_slide_pairs(args.slide_pairs)
    except ValueError as e:
        safe_print(f"[ERR] --slide-pairs 解析失败：{e}")
        return 2
    layers = parse_layers(args.layers)

    # 输出目录
    if args.out_dir:
        out_dir = Path(args.out_dir)
    else:
        ts = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
        out_dir = Path(f"debug/acceptance-{ts}")
    out_dir = out_dir.resolve()

    # ────────── 加载契约 ──────────
    from contract import Contract
    try:
        contract = Contract.load(args.contract, mode=args.mode)
    except Exception as e:
        safe_print(f"[ERR] 契约加载失败：{e}")
        return 2

    safe_print(f"[ppt-acceptance-check] mode={args.mode} layers={','.join(layers)}")
    safe_print(f"  contract: {args.contract or '(default)'}")
    safe_print(f"  slide_pairs: {slide_pairs}")
    safe_print(f"  out_dir: {out_dir}")

    # ────────── COM 启动 + Presentation 打开 ──────────
    import win32com.client
    use_active = args.active_new or args.active_template
    if use_active:
        try:
            ppt = win32com.client.GetActiveObject("PowerPoint.Application")
        except Exception as e:
            safe_print(f"[ERR] --active-* 但 PowerPoint 未运行: {e}")
            return 2
        app_opened_by_us = False
    else:
        # com-survival-reflexes R3：自动化场景 DispatchEx 起新进程
        ppt = win32com.client.DispatchEx("PowerPoint.Application")
        app_opened_by_us = True

    try:
        ppt.Visible = True
    except Exception:
        pass

    pres_new = pres_tpl = None
    pres_new_opened = pres_tpl_opened = False
    layer_results: list = []

    try:
        pres_new, pres_new_opened = _resolve_presentation(
            ppt, active=args.active_new, pptx_path=args.new_path)
        pres_tpl, pres_tpl_opened = _resolve_presentation(
            ppt, active=args.active_template, pptx_path=args.tpl_path)

        # ────────── 跑各层 ──────────
        l0_result = None
        if "L0" in layers:
            safe_print("\n[L0] 配对...")
            from layers import pairing as layer_pairing
            l0_result = layer_pairing.run(
                contract=contract, pres_new=pres_new, pres_template=pres_tpl,
                slide_pairs=slide_pairs,
            )
            layer_results.append(l0_result)
            safe_print(f"  L0: passed={l0_result.passed_count} "
                       f"warn={l0_result.warnings} must_fix={l0_result.must_fix_violations}")

        if "L1" in layers:
            safe_print("\n[L1] 数据...")
            from layers import data as layer_data
            r = layer_data.run(
                contract=contract, pres_new=pres_new, pres_template=pres_tpl,
                slide_pairs=slide_pairs, l0_result=l0_result,
            )
            layer_results.append(r)
            safe_print(f"  L1: passed={r.passed_count} must_fix={r.must_fix_violations}")

        if "L2" in layers:
            safe_print("\n[L2] 格式...")
            from layers import format as layer_format
            r = layer_format.run(
                contract=contract, pres_new=pres_new, pres_template=pres_tpl,
                slide_pairs=slide_pairs, l0_result=l0_result,
            )
            layer_results.append(r)
            safe_print(f"  L2: passed={r.passed_count} warn={r.warnings} "
                       f"must_fix={r.must_fix_violations}")

        if "L3" in layers:
            safe_print("\n[L3] 染色 / Runs...")
            from layers import runs as layer_runs
            r = layer_runs.run(
                contract=contract, pres_new=pres_new, pres_template=pres_tpl,
                slide_pairs=slide_pairs, l0_result=l0_result,
            )
            layer_results.append(r)
            safe_print(f"  L3: passed={r.passed_count} must_fix={r.must_fix_violations}")

        if "L4" in layers:
            safe_print("\n[L4] 行为 / Trace...")
            from layers import behavior as layer_behavior
            r = layer_behavior.run(
                contract=contract, trace_path=args.pipeline_trace,
            )
            layer_results.append(r)
            if r.degraded:
                safe_print(f"  L4: ⚠ degraded ({r.degraded_reason})")
            safe_print(f"  L4: passed={r.passed_count} must_fix={r.must_fix_violations}")

        if "L5" in layers:
            safe_print("\n[L5] 视觉...")
            from layers import visual as layer_visual
            r = layer_visual.run(
                contract=contract, ppt_app=ppt,
                pres_new=pres_new, pres_template=pres_tpl,
                slide_pairs=slide_pairs, out_dir=out_dir,
            )
            layer_results.append(r)
            safe_print(f"  L5: passed={r.passed_count} must_fix={r.must_fix_violations}")

    except Exception as e:
        safe_print(f"\n[ERR] 验收过程异常：{e}")
        safe_print(traceback.format_exc())
        return 2
    finally:
        if pres_new_opened and pres_new is not None:
            try: pres_new.Close()
            except Exception: pass
        if pres_tpl_opened and pres_tpl is not None:
            try: pres_tpl.Close()
            except Exception: pass
        if app_opened_by_us:
            try: ppt.Quit()
            except Exception: pass

    # ────────── 聚合 + 写报告 ──────────
    from report import aggregate, write_reports
    report = aggregate(
        layer_results, contract_path=args.contract or "",
        mode=args.mode, slide_pairs=slide_pairs,
        args_summary={
            "new": args.new_path or "<active>",
            "template": args.tpl_path or "<active>",
            "layers": layers,
            "pipeline_trace": args.pipeline_trace or "",
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
