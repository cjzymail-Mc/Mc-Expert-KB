# -*- coding: utf-8 -*-
"""
extract_chart_numcache.py — 从 PPT 原生 chart 的 numCache 取真值（路线无关取数探针）

皇冠能力：PPT 里 OLE 原生 chart 对象的真值缓存在 chart XML 的 <c:numCache>，
**不依赖内嵌/外链 Excel**。main-src 引擎产的 chart 用外链 workbook（TargetMode=External
指 file:///…xlsx），ppt/embeddings/ 常为空、源 Excel 是死链，但 numCache 已缓存全部数值。

消费者 = Chart.js 画图 / 原生 chart 重建 / table / verify 任一（**不只为画图**）。
与 inspect-ppt-template 同族（读既有 pptx 的探针），不是渲染产线脚本 → 落 scripts/probe/。

用法：
    py -3 -X utf8 extract_chart_numcache.py <deck.pptx> [--chart N] [--json out.json]

规约（CLAUDE.md §2 / 现场评审 §14）：
  - 碰文件第一动作核 8 字节首字节：明文 ZIP=50 4B 03 04 才动；密文 88 7D 1C 则 STOP。
  - 「原生 chart vs 已烤平 PNG」判别 = 数 ppt/charts/ 部件；0 chart = 只剩像素、取不出。
  - ★强制步（代价 1）：拿外人 PPT 取数后必抽样对一眼图面（numCache 是缓存，可能不同步）。
"""
import sys, os, re, json, zipfile
import xml.etree.ElementTree as ET

C = "{http://schemas.openxmlformats.org/drawingml/2006/chart}"
CHART_TYPES = ("barChart", "bar3DChart", "lineChart", "line3DChart",
               "radarChart", "doughnutChart", "pieChart", "pie3DChart",
               "scatterChart", "areaChart")


def safe_print(*a):
    s = " ".join(str(x) for x in a)
    try:
        print(s)
    except UnicodeEncodeError:
        print(s.encode("utf-8", "replace").decode("cp1252", "replace"))


def check_plaintext(path):
    """碰文件第一动作：核首字节。明文 ZIP=True；密文 88 7D 1C=STOP。"""
    with open(path, "rb") as f:
        head = f.read(8)
    if head[:4] == b"PK\x03\x04":
        return True
    if head[:3] == b"\x88\x7d\x1c":
        safe_print(f"[STOP] 密文（首字节 {head[:3].hex()}）→ 交用户手工解密后再跑：{path}")
        return False
    safe_print(f"[STOP] 非 ZIP（首字节 {head[:4].hex()}），不是有效 pptx：{path}")
    return False


def _cache_points(parent_tag_elem):
    """从 strCache/numCache 取 idx→value 的点；按 idx 排序回 list。"""
    pts = {}
    for cache in parent_tag_elem:
        if cache.tag not in (C + "strCache", C + "numCache"):
            continue
        for pt in cache.findall(C + "pt"):
            idx = int(pt.get("idx", "0"))
            v = pt.find(C + "v")
            pts[idx] = v.text if v is not None else None
    if not pts:
        return []
    n = max(pts) + 1
    return [pts.get(i) for i in range(n)]


def _series_name(ser):
    tx = ser.find(C + "tx")
    if tx is None:
        return None
    ref = tx.find(C + "strRef")
    if ref is not None:
        pts = _cache_points(ref)
        if pts:
            return pts[0]
    v = tx.find(C + "v")
    return v.text if v is not None else None


def _categories(ser):
    cat = ser.find(C + "cat")
    if cat is None:
        return []
    for ref in cat:
        if ref.tag in (C + "strRef", C + "numRef", C + "multiLvlStrRef"):
            pts = _cache_points(ref)
            if pts:
                return pts
    return []


def _values(ser):
    val = ser.find(C + "val")
    if val is None:
        return []
    for ref in val:
        if ref.tag in (C + "numRef", C + "strRef"):
            return _cache_points(ref)
    return []


def _as_num(s):
    if s is None:
        return None
    try:
        f = float(s)
        return int(f) if f.is_integer() else f
    except ValueError:
        return s


def parse_chart_xml(xml_bytes):
    root = ET.fromstring(xml_bytes)
    out = {"chart_kinds": [], "categories": None, "series": []}
    for plot in root.iter(C + "plotArea"):
        for child in plot:
            local = child.tag[len(C):] if child.tag.startswith(C) else child.tag
            if local not in CHART_TYPES:
                continue
            out["chart_kinds"].append(local)
            for ser in child.findall(C + "ser"):
                cats = _categories(ser)
                if cats and out["categories"] is None:
                    out["categories"] = cats
                out["series"].append({
                    "name": _series_name(ser),
                    "values": [_as_num(v) for v in _values(ser)],
                })
    return out


def extract(pptx_path):
    with zipfile.ZipFile(pptx_path) as z:
        names = z.namelist()
        chart_parts = sorted(
            [n for n in names if re.fullmatch(r"ppt/charts/chart\d+\.xml", n)],
            key=lambda n: int(re.search(r"chart(\d+)", n).group(1)))
        embeddings = [n for n in names if n.startswith("ppt/embeddings/")]
        imgs = [n for n in names if re.match(r"ppt/media/.*\.(png|jpe?g|emf|wmf)$", n, re.I)]
        charts = []
        for part in chart_parts:
            data = parse_chart_xml(z.read(part))
            data["part"] = part
            charts.append(data)
    return {
        "pptx": os.path.basename(pptx_path),
        "native_chart_count": len(chart_parts),
        "embeddings_count": len(embeddings),
        "media_image_count": len(imgs),
        "is_baked_png": len(chart_parts) == 0,
        "charts": charts,
    }


def main():
    args = sys.argv[1:]
    if not args:
        safe_print(__doc__)
        sys.exit(1)
    pptx = args[0]
    only = None
    out_json = None
    if "--chart" in args:
        only = int(args[args.index("--chart") + 1])
    if "--json" in args:
        out_json = args[args.index("--json") + 1]

    if not check_plaintext(pptx):
        sys.exit(2)

    res = extract(pptx)
    safe_print(f"== {res['pptx']} ==")
    safe_print(f"原生 chart 部件: {res['native_chart_count']}  |  内嵌 workbook: {res['embeddings_count']}"
               f"  |  media 图: {res['media_image_count']}")
    if res["is_baked_png"]:
        safe_print("[WARN] 0 原生 chart → 已烤平成 PNG，取不出数值（换『仍带原生 chart 的那一版』源）。")
    for i, ch in enumerate(res["charts"], 1):
        if only and i != only:
            continue
        safe_print(f"\n  chart{i} [{ch['part']}] 类型={','.join(ch['chart_kinds']) or '?'}")
        safe_print(f"    类别 cat = {ch['categories']}")
        for s in ch["series"]:
            safe_print(f"    series「{s['name']}」= {s['values']}")
    if out_json:
        with open(out_json, "w", encoding="utf-8") as f:
            json.dump(res, f, ensure_ascii=False, indent=2)
        safe_print(f"\n[json] {out_json}")
    safe_print("\n★ 代价1 强制步：拿外人 PPT 须取数后抽样对一眼图面（缓存可能不同步），非软提醒。")


if __name__ == "__main__":
    main()
