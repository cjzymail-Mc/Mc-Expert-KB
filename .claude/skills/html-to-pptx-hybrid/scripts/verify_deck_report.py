# -*- coding: utf-8 -*-
"""deck pptx 明文验收（python-pptx 读明文，无 COM）：
1) 页数 = manifest；2) 每个 manifest 文本/列表/表格元素在该页存在（marker-aware：列表 ▲▼ 前缀 / bg 内缩不算缺失）；
3) 禁词 grep（FORBIDDEN 表，★按你项目红线配置）：幻觉占位词 / 他项目名泄漏 / 【推断】【替代】 / 用户路径残留。
用法: py -3 -X utf8 verify_deck_report.py <out.pptx> <manifest.json>
"""
import json
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

from pptx import Presentation

# ★禁词 = 按你项目红线配置（本表为示例骨架）。典型三类：
#   ①幻觉/占位词  ②他项目/竞品名泄漏（换成你自己要拦的产品/项目名）  ③推断标记 + 路径残留。
# 通用结构类（推断标记 / 路径残留 regex）可直接留用；具体产品名占位项请替换成你项目的真实红线词。
FORBIDDEN = {
    "幻觉占位词(示例)": r"幻影|【占位】",
    "他项目名泄漏(示例·按项目替换)": r"(?!x)x",   # ← 换成你要拦的竞品/他项目名，如 r"ProductX|ProjectY"
    "【推断】": r"【推断】",
    "【替代】": r"【替代】",
    "用户路径残留": r"[A-Za-z]:\\Users\\|file:///|\d{4}年\d{1,2}月.*工作",
}
MARKER_RE = re.compile(r"[▲▼]\s*")          # overlay 补回的 box glyph，全局剥离


def norm(s):
    return " ".join(str(s).replace("\r", "\n").split())


def strip_marker_lines(s):
    return MARKER_RE.sub("", s)             # ▲▼ 不出现在合法内容，全局剥离再比对


def slide_texts(slide):
    """返回 (textbox 文本 list, table 文本 list)。"""
    tboxes, tables = [], []
    for shp in slide.shapes:
        if shp.has_table:
            cells = []
            for row in shp.table.rows:
                for cell in row.cells:
                    cells.append(norm(cell.text))
            tables.append(cells)
        elif shp.has_text_frame and shp.text_frame.text.strip():
            tboxes.append(norm(shp.text_frame.text))
    return tboxes, tables


def main():
    pptx = Path(sys.argv[1]).resolve()
    manifest = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
    prs = Presentation(str(pptx))
    slides = list(prs.slides)
    exp = manifest["slides"]
    problems = []

    if len(slides) != len(exp):
        problems.append(f"页数 {len(slides)} != 期望 {len(exp)}")

    all_text = []
    content_imgs = 0          # D4：超出每页 1 张截图底的「真实内容图」张数
    for pos, (slide, sd) in enumerate(zip(slides, exp), 1):
        idx = sd["index"]
        tboxes, tables = slide_texts(slide)
        all_text.extend(tboxes)
        all_text.extend(c for t in tables for c in t)
        # 图片层：每页至少 1 张截图底；超出部分计入真实内容图（D4 允许插真实图）
        # ⚠盲区：若某页"截图底丢失 + 又插了 ≥1 内容图"则 n_pic=1 仍过(底实缺却不报)；
        #   现实里底图丢失多为整页 n_pic=0(截图步骤整页失败)，由 <1 兜住主线。两件事同发概率低。
        n_pic = sum(1 for shp in slide.shapes if shp.shape_type == 13)
        if n_pic < 1:
            problems.append(f"p{idx}: 截图层图片 {n_pic} < 1（缺底图）")
        content_imgs += max(0, n_pic - 1)
        # marker-aware 文本归一池
        pool = [strip_marker_lines(t) for t in tboxes]
        for e in sd["elements"]:
            if e["type"] == "text":
                want = norm(e["text"])
                if want not in [norm(x) for x in pool]:
                    problems.append(f"p{idx}: 缺文本 [{want[:34]}…]")
            elif e["type"] == "bullets":
                want = norm("\n".join(it["text"] for it in e["items"]))
                if want not in [norm(x) for x in pool]:
                    problems.append(f"p{idx}: 缺列表 [{want[:34]}…]")
            elif e["type"] == "table":
                exp_cells = [norm(c["text"]) for row in e["rows"] for c in row]
                ok = any(exp_cells == t for t in tables)
                if not ok:
                    problems.append(f"p{idx}: 表格单元格不匹配")

    # 禁词 grep（全片 overlay 文本）
    blob = "\n".join(all_text)
    for name, pat in FORBIDDEN.items():
        hits = re.findall(pat, blob)
        if hits:
            problems.append(f"禁词命中 {name}: {len(hits)} 处 -> {hits[:3]}")

    # D4 机器红旗（漏 A）：整片真实内容图 == 0 且存在占位框 → 报警（非 FAIL，提示先回 docx/pptx 抽内嵌图）
    n_ph = sum(t.count("[图片占位:") for t in all_text)
    warns = []
    if content_imgs == 0 and n_ph > 0:
        warns.append(
            f"真实内容图=0 且占位框={n_ph} → 先尝试从源文档（docx/pptx）抽内嵌图再判『待补』(D4)")

    print(f"slides={len(slides)} / 期望 {len(exp)}；overlay 文本块={len(all_text)}；"
          f"真实内容图={content_imgs}；占位框={n_ph}")
    if warns:
        print(f"WARN ({len(warns)} 项，非阻断，需人复核):")
        for w in warns:
            print(" ~", w)
    if problems:
        print(f"FAIL ({len(problems)} 项):")
        for p in problems:
            print(" -", p)
        sys.exit(1)
    print("PASS: 页数 + 全元素存在(marker-aware) + 禁词全 0")


if __name__ == "__main__":
    main()
