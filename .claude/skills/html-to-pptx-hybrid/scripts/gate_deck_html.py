# -*- coding: utf-8 -*-
"""deck html 结构门（确定性检查，plan §3 的 html 层投影）。
用法: py -3 -X utf8 gate_deck_html.py <deck.html> --date 2025-06-24 --placeholders 8 \
      --slides 16 --chart-placeholders 9 \
      --require FE4.0 QD-262113M ... --forbid 毒牙 蜂刺 ...
检查: 页数 / 0 <img> / 占位框数 / chart占位数 / 黑名单 0 命中 / 身份字段全在 / 封面日期在 / 报告编号在。
"""
import argparse
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("html")
    ap.add_argument("--date", required=True)
    ap.add_argument("--report-no", default="")
    ap.add_argument("--slides", type=int, default=15)
    ap.add_argument("--placeholders", type=int, required=True)
    ap.add_argument("--chart-placeholders", type=int, default=0)
    ap.add_argument("--require", nargs="*", default=[])
    ap.add_argument("--forbid", nargs="*", default=[])
    ap.add_argument("--forbid-bare-dash", action="store_true",
                    help="对标表竞品列禁裸『—』(源缺须显式『待补』标注，呼应 D2/不造数红线)")
    a = ap.parse_args()

    text = Path(a.html).read_text(encoding="utf-8")
    # base64 素材里可能撞出任意子串，黑名单/身份检查剔除 data URI
    body = re.sub(r"data:image/[^\"]+", "", text)
    problems = []

    n_slides = body.count('<section class="slide')
    if n_slides != a.slides:
        problems.append(f"页数 {n_slides} != {a.slides}")
    if re.search(r"<img\b", body):
        problems.append("出现 <img>（图片零插入红线）")
    n_ph = body.count("[图片占位:")
    if n_ph != a.placeholders:
        problems.append(f"占位框数 {n_ph} != md 基准 {a.placeholders}")
    # chart 占位检查
    n_chart_ph = len(re.findall(r'data-chart-id="CHART-c\d+"', body))
    if a.chart_placeholders and n_chart_ph != a.chart_placeholders:
        problems.append(f"chart占位数 {n_chart_ph} != {a.chart_placeholders}")
    if a.date not in body:
        problems.append(f"封面日期 {a.date} 未找到")
    if a.report_no and a.report_no not in body:
        problems.append(f"报告编号 {a.report_no} 未找到")
    for tok in a.require:
        if tok not in body:
            problems.append(f"身份字段缺失: {tok}")
    for tok in a.forbid:
        if tok in body:
            problems.append(f"黑名单命中: {tok}")

    # D2 裸『—』门：对标表竞品列禁纯破折号占位（源缺须显式『待补』，合法出口）。
    # 仅命中 <td> 内容恰为 一个破折号/连字符 的单元格；带『待补』的注解格不匹配 = 放行。
    if a.forbid_bare_dash:
        bare = []
        for m in re.finditer(r"<td\b[^>]*>(.*?)</td>", body, flags=re.S):
            inner = re.sub(r"<[^>]+>", "", m.group(1))  # 去内层标签
            # 破折号常以 HTML 实体写，先归一再判（否则 &mdash; 漏判=假 PASS）
            for ent in ("&mdash;", "&#8212;", "&#x2014;"):
                inner = inner.replace(ent, "—")
            for ent in ("&ndash;", "&#8211;", "&#x2013;"):
                inner = inner.replace(ent, "–")
            inner = inner.replace("&nbsp;", "").strip()
            if inner in {"—", "–", "-", "--", "－"}:
                bare.append(inner)
        if bare:
            problems.append(
                f"裸『—』占位 {len(bare)} 处（对标表竞品列须填数值或显式『待补』，禁静默裸破折号）")

    name = Path(a.html).name
    if problems:
        print(f"FAIL {name}:")
        for p in problems:
            print(" -", p)
        sys.exit(1)
    print(f"PASS {name}: {a.slides}页/0img/占位{n_ph}/chart占位{n_chart_ph}/黑名单0/身份+日期齐")


if __name__ == "__main__":
    main()
