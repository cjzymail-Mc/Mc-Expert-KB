# -*- coding: utf-8 -*-
"""deck 元素拆分模式（split-decompose）：把 html-to-pptx-hybrid 退化态/扁平 deck 重建为
「每页文字可编辑 + 装饰块逐个独立可动对象 + 干净底图」。详见 SKILL §11 + 坑表 C-14。

核心：让 Playwright 当相机精确抠图（不在 Python 里抠白块=违背 §0 哲学）：
- promoted 块用 element.screenshot(omit_background) 抠成透明精确 PNG；.card 无嵌套→原生可缩放矩形
- ★两态时序：先 MASK_CSS 拍 promoted 元素 → 再 hide-mask 拍干净底图（写反=空PNG静默假成功，故 PNG 非空自检）
- ★坐标用浏览器内 RELJS(closest('section.slide') 同帧算)避开 element.screenshot 滚动错位
- ★dsf=3 → AddPicture 显式 bbox×SX/SY pt，别让 PPT 按 PNG 原生 px
- 空白门：扩 mask 后底图灰度近匀→丢底图改原生白底；有页级装饰(封面/分隔渐变)→保留
- 文字走真量产 add_textbox/add_bullets（读 manifest，需为当前 HTML 的新鲜 manifest）

用法: py -3 -X utf8 split_deck_elements.py --deck <deckdir> [--html x.html] [--manifest _manifest_fresh.json] [--out _rebuild_split.pptx] [--slides 1-3]
块白名单 WL 为 RD38 皮实证集；换皮/换 deck 先按本页 §11「换 deck 清单」核 WL 与 nesting。
"""
import os, sys, json, tempfile, shutil, re, argparse
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from deck_common import SLIDE_W_PT, SLIDE_H_PT, CANVAS_W, CANVAS_H, MASK_CSS
import export_deck_report as ER

ap = argparse.ArgumentParser()
ap.add_argument("--deck", required=True, help="deck 目录")
ap.add_argument("--html", default=None)
ap.add_argument("--manifest", default="_manifest_fresh.json")
ap.add_argument("--out", default="_rebuild_split.pptx")
ap.add_argument("--slides", default="")
A = ap.parse_args()
DECK = A.deck
HTML = os.path.join(DECK, A.html) if A.html else next(str(p) for p in Path(DECK).glob("*.html") if "before" not in p.name)
MANI = os.path.join(DECK, A.manifest) if not os.path.isabs(A.manifest) else A.manifest
OUT  = os.path.join(DECK, A.out) if not os.path.isabs(A.out) else A.out
TMPD = os.path.join(tempfile.gettempdir(), "_split_assets"); os.makedirs(TMPD, exist_ok=True)

def prng(s):
    out=set()
    for part in (s or "").split(","):
        if "-" in part: a,b=part.split("-"); out.update(range(int(a),int(b)+1))
        elif part.strip(): out.add(int(part))
    return out or None
ONLY = prng(A.slides)

def prgb(s):
    m=re.findall(r"[\d.]+", s or ""); return (int(float(m[0])),int(float(m[1])),int(float(m[2]))) if len(m)>=3 else (255,255,255)
def rgb(t): return t[0]+(t[1]<<8)+(t[2]<<16)
x,y=ER.x,ER.y

# RD38 皮装饰块白名单（最外层提升；.card 无嵌套→原生，余→透明PNG）
WL=['.card','.metric','.box','.step','.okc','.good','.miss','.bad','.twobox','.callout','.lane','.arr','.num','.accentline','.cline','.divider','.rdiv','.titlebar','.subrule','.imgframe','.cv']
# .cv = Chart.js canvas 容器：拆分态把图表当内容图块提升为透明 PNG（html-chart §交烤）；
# 只提升 .cv 不提升 .cpanel → h4 标题仍走文本 overlay 保持可编辑。
SELALL=",".join(WL)
RELJS="e=>{const s=e.closest('section.slide');const sr=s.getBoundingClientRect();const r=e.getBoundingClientRect();return{x:r.left-sr.left,y:r.top-sr.top,w:r.width,h:r.height};}"
NESTED="(e,sel)=>{let p=e.parentElement;const sl=e.closest('section.slide');while(p&&p!==sl){if(sel.split(',').some(c=>p.matches(c)))return true;p=p.parentElement;}return false;}"
HASDESC="(e,sel)=>!!e.querySelector(sel)"

from playwright.sync_api import sync_playwright
manifest=json.load(open(MANI,encoding="utf-8"))
idxs=[s["index"] for s in manifest["slides"] if (ONLY is None or s["index"] in ONLY)]
pages={}
with sync_playwright() as p:
    br=p.chromium.launch(); pg=br.new_page(viewport={"width":int(CANVAS_W),"height":int(CANVAS_H)},device_scale_factor=3)
    pg.goto(Path(HTML).resolve().as_uri(), wait_until="load")  # 'load'(非 domcontentloaded)=等 CDN Chart.js 下完，否则 canvas 空白
    if pg.query_selector("canvas"):  # 有 Chart.js 图表：等 window.Chart 就绪 + 一拍 RAF 确保已绘制（animation:false 同步绘）
        try: pg.wait_for_function("() => window.Chart !== undefined", timeout=8000); pg.evaluate("() => new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))")
        except Exception: pass
    pg.add_style_tag(content=MASK_CSS); pg.wait_for_timeout(700)
    rb=lambda d:(d["x"],d["y"],d["w"],d["h"]); slides=pg.query_selector_all("section.slide")
    for idx in idxs:
        s=slides[idx-1]; png_items=[]; cards=[]; markers=[]; accents=[]; marker_rgb=(229,50,56)
        cand=[e for e in s.query_selector_all(SELALL) if not e.evaluate(NESTED, SELALL)]
        for k,e in enumerate(cand):
            box=rb(e.evaluate(RELJS))
            if e.evaluate("e=>e.matches('.card')") and not e.evaluate(HASDESC, SELALL):
                cs=e.evaluate("e=>{const s=getComputedStyle(e);return{bg:s.backgroundColor,bt:s.borderTopColor,btw:parseFloat(s.borderTopWidth),bc:s.borderLeftColor,bw:parseFloat(s.borderLeftWidth),rad:parseFloat(s.borderTopLeftRadius)}}")
                cards.append((box,cs))
            else:
                fp=os.path.join(TMPD,f"p{idx}_{k}.png"); e.screenshot(path=fp, omit_background=True); png_items.append((fp,box))
        # .cpanel 图表面板：独立 native 圆角矩形（贴合面板≈chart 大小，非整页底图）+ h4::before 红 marker bar 独立 shape。
        # 走专用 pass 不入 WL：.cpanel 入 WL 会让内部 .cv 被 NESTED 判定不促升、整块塌回一张 PNG（丢标题可编辑）。
        panels=[]; pmarks=[]
        for e in s.query_selector_all(".cpanel"):
            bx=rb(e.evaluate(RELJS)); cs=e.evaluate("e=>{const g=getComputedStyle(e);return{bg:g.backgroundColor,bc:g.borderTopColor,bw:parseFloat(g.borderTopWidth),rad:parseFloat(g.borderTopLeftRadius)}}")
            panels.append((bx,cs))
        for h in s.query_selector_all(".cpanel h4"):
            hb=rb(h.evaluate(RELJS)); mk=h.evaluate("e=>{const g=getComputedStyle(e,'::before');return{w:parseFloat(g.width),h:parseFloat(g.height),bg:g.backgroundColor,rad:parseFloat(g.borderTopLeftRadius)}}")
            if mk["w"]>0 and mk["h"]>0: pmarks.append((hb[0],hb[1]+(hb[3]-mk["h"])/2,mk["w"],mk["h"],prgb(mk["bg"]),mk["rad"]))  # marker 在 h4 左、垂直居中
        present=[c for c in WL if s.query_selector(c)]
        lis=s.query_selector_all("ul.clean li")
        if lis:
            marker_rgb=prgb(lis[0].evaluate("e=>getComputedStyle(e,'::before').backgroundColor"))
            for li in lis: b=rb(li.evaluate(RELJS)); markers.append((b[0]+2,b[1]+9,8,8))
        ahide=[]
        for e in s.query_selector_all(".note"):
            b=rb(e.evaluate(RELJS)); cs=e.evaluate("e=>{const s=getComputedStyle(e);return{c:s.borderLeftColor,w:parseFloat(s.borderLeftWidth)}}")
            if cs["w"]>0: accents.append(((b[0],b[1],cs["w"],b[3]), prgb(cs["c"]))); ahide=[".note{border-left-color:transparent!important}"]
        css=(",".join(present)+"{visibility:hidden!important}" if present else "")+(" .cpanel{visibility:hidden!important}" if panels else "")+(" ul.clean li::before{visibility:hidden!important}" if lis else "")+(" "+" ".join(ahide) if ahide else "")
        sid=pg.add_style_tag(content=css) if css else None
        pg.wait_for_timeout(150)
        base=os.path.join(TMPD,f"p{idx}_base.png"); s.screenshot(path=base)
        if sid: sid.evaluate("e=>e.remove()")
        lo,hi=Image.open(base).convert("L").getextrema(); blank=(hi-lo)<8 and lo>240
        for fp,_ in png_items:
            a=Image.open(fp).convert("RGBA").getchannel("A")
            assert sum(1 for v in a.getdata() if v>10)>30, f"p{idx} 空PNG {fp}（时序写反?）"
        pages[idx]=dict(png_items=png_items,cards=cards,markers=markers,marker_rgb=marker_rgb,accents=accents,panels=panels,pmarks=pmarks,base=base,blank=blank)
        print(f"  p{idx}: PNG={len(png_items)} 原生卡片={len(cards)} 面板框={len(panels)} 面板marker={len(pmarks)} 方块={len(markers)} accent={len(accents)} 底图={'空白丢' if blank else '保留'}")
    br.close()

import win32com.client as win32
import pythoncom
def set_corner(shp, rad_px):  # roundedRect 圆角=CSS radius 绝对值(px→pt)；不显式设 PPT 用默认 adj=0.16667→圆角夸张(2026-06-29 用户实测)
    try:
        r_pt=float(rad_px)*0.75; mn=min(shp.Width,shp.Height)
        if r_pt>0 and mn>0: shp.Adjustments._oleobj_.Invoke(0,0,pythoncom.DISPATCH_PROPERTYPUT,False,1,min(r_pt/mn,0.5))
    except Exception: pass
mans={s["index"]:s for s in manifest["slides"]}
tmp=os.path.join(tempfile.gettempdir(), f"__tmp_splitdeck_{os.getpid()}.pptx")
app=win32.Dispatch("PowerPoint.Application"); app.Visible=True; pres=app.Presentations.Add()
try:
    pres.PageSetup.SlideWidth=SLIDE_W_PT; pres.PageSetup.SlideHeight=SLIDE_H_PT
    for pos,idx in enumerate(idxs,1):
        d=pages[idx]; sl=pres.Slides.Add(pos,12)
        if not d["blank"]: sl.Shapes.AddPicture(str(Path(d["base"]).resolve()),0,-1,0,0,SLIDE_W_PT,SLIDE_H_PT).ZOrder(1)
        for (bx,by,bw,bh),cs in d.get("panels",[]):  # 面板框：贴合面板的圆角矩形，垫在 chart PNG 之下、文字之上
            shp=5 if cs.get("rad",0)>2 else 1
            pp=sl.Shapes.AddShape(shp,x(bx),y(by),x(bw),y(bh)); pp.Fill.Solid(); pp.Fill.ForeColor.RGB=rgb(prgb(cs["bg"]))
            pp.Line.ForeColor.RGB=rgb(prgb(cs["bc"])); pp.Line.Weight=max(cs["bw"]*0.75,0.5); pp.Line.Visible=-1; pp.Shadow.Visible=0
            if shp==5: set_corner(pp, cs.get("rad",0))
        for (bx,by,bw,bh),cs in d["cards"]:
            shp=5 if cs.get("rad",0)>2 else 1
            b=sl.Shapes.AddShape(shp,x(bx),y(by),x(bw),y(bh)); b.Fill.Solid(); b.Fill.ForeColor.RGB=rgb(prgb(cs["bg"]))
            b.Line.ForeColor.RGB=rgb(prgb(cs["bc"])); b.Line.Weight=max(cs["bw"]*0.75,0.5); b.Line.Visible=-1; b.Shadow.Visible=0
            if shp==5: set_corner(b, cs.get("rad",0))
            if cs["btw"]>0:
                bar=sl.Shapes.AddShape(1,x(bx),y(by),x(bw),y(cs["btw"])); bar.Fill.Solid(); bar.Fill.ForeColor.RGB=rgb(prgb(cs["bt"])); bar.Line.Visible=0; bar.Shadow.Visible=0
        for fp,b in d["png_items"]: sl.Shapes.AddPicture(str(Path(fp).resolve()),0,-1,x(b[0]),y(b[1]),x(b[2]),y(b[3]))
        for mx,my,mw,mh in d["markers"]:
            sq=sl.Shapes.AddShape(5,x(mx),y(my),x(mw),y(mh)); sq.Fill.Solid(); sq.Fill.ForeColor.RGB=rgb(d["marker_rgb"]); sq.Line.Visible=0; sq.Shadow.Visible=0
        for mx,my,mw,mh,mcol,mrad in d.get("pmarks",[]):  # 面板标题 h4::before 红 bar，独立 shape（在面板框/chart 之上）
            pm=sl.Shapes.AddShape(5 if mrad>1 else 1,x(mx),y(my),x(mw),y(mh)); pm.Fill.Solid(); pm.Fill.ForeColor.RGB=rgb(mcol); pm.Line.Visible=0; pm.Shadow.Visible=0
            if mrad>1: set_corner(pm, mrad)
        for (ax,ay,aw,ah),acol in d["accents"]:
            ar=sl.Shapes.AddShape(1,x(ax),y(ay),x(aw),y(ah)); ar.Fill.Solid(); ar.Fill.ForeColor.RGB=rgb(acol); ar.Line.Visible=0; ar.Shadow.Visible=0
        for el in mans[idx]["elements"]:
            try:
                if el["type"]=="text": ER.add_textbox(sl,el)
                elif el["type"]=="bullets": ER.add_bullets(sl,el)
                elif el["type"]=="table": ER.add_table(sl,el)
            except Exception as e: print(f"  [WARN] p{idx} {el.get('role')}: {str(e)[:50]}")
    pres.SaveAs(tmp,24)
finally:
    try: pres.Close()
    except Exception: pass
    try: app.Quit()
    except Exception: pass
if os.path.exists(OUT): os.remove(OUT)
shutil.move(tmp,OUT)
print("SAVED",OUT,"| 页数",len(idxs),"| HEAD",open(OUT,"rb").read(4).hex(" ").upper())
