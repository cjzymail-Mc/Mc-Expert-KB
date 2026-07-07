# -*- coding: utf-8 -*-
"""deck html 坐标提取（Playwright + getBoundingClientRect）→ manifest.json
用法: py -3 -X utf8 extract_deck_report.py <deck.html> [out.json]

★ 本文件 = extract 的一个【示例皮肤变体】（体裁：多章节汇报报告）。extract 天然是皮肤相关的
（它要认得你 deck 的 class 词汇），这里带的是一套worked example 白名单/暗底选择器——
**换你自己的 deck 时按 SKILL.md §5「换皮适配法」替换下面的 TEXT_SEL / 暗底页选择器 / marker 处理**，
不要原样套到 class 名不同的 deck 上。另一套示例变体见 extract_deck_layout.py（红白竞品皮）。

折中 Hybrid：只把 meaningful 内容（文字/表格/列表）落 overlay，装饰件（巨字水印 / 渐变弧 /
折角块底 / 竖条 / 虚线占位框轮廓）留截图层。本示例变体的皮肤专属旋钮：
- TEXT_SEL = 本示例皮肤的 class 白名单；blend 背景按本示例暗底页（.cover/.divider/.rdiv）判定。
- 截图会吃掉的 glyph 标记（.subhead::before ✓ / .box li::before ▲▼）→ overlay 端补回（marker run）。
- ul.clean li::before 方块是 background（截图保留）→ markerless、文字内缩（marker_mode=bg）。
- table.t 逐 cell 抓 color/bg/header → export 端忠实重绘（皮肤无关）。
"""
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

from playwright.sync_api import sync_playwright

from deck_common import CANVAS_W, CANVAS_H, LAYOUT_CSS

EXTRACT_JS = r"""
() => {
  // L3 治本：从注入的 :root token 读 RGB（跟随配色模板，非硬编码）。供 alpha-blend 暗底基色用。
  const _rootCache = {};
  function rootRgb(name, fallback) {
    if (name in _rootCache) return _rootCache[name];
    const v = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
    let out = fallback;
    const h = v.replace('#', '');
    if (/^[0-9a-fA-F]{6}$/.test(h)) {
      out = [parseInt(h.slice(0, 2), 16), parseInt(h.slice(2, 4), 16), parseInt(h.slice(4, 6), 16)];
    } else {
      const m = v.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)/);
      if (m) out = [+m[1], +m[2], +m[3]];
    }
    _rootCache[name] = out;
    return out;
  }
  function hexOfColor(c) {
    const m = c.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)/);
    if (!m) return null;
    return '#' + [+m[1], +m[2], +m[3]].map(n => n.toString(16).padStart(2, '0')).join('');
  }
  function rgbToHex(c, el) {
    const m = c.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)(?:,\s*([\d.]+))?\)/);
    if (!m) return '#000000';
    let r = +m[1], g = +m[2], b = +m[3];
    const a = m[4] !== undefined ? +m[4] : 1;
    if (a < 0.99 && el) {
      // 示例皮肤暗底页（封面/章节分隔/轮次分隔）按 palette 底色 alpha blend，其余按白（教训 C-4）。
      // L3 治本：blend 基色从 :root token 读，换配色模板时自动跟随（不再硬编码红/navy）。
      const dark = el.closest('.cover, .divider, .rdiv');
      let bg = [255, 255, 255];
      if (dark) {
        if (dark.classList.contains('divider')) bg = rootRgb('--red', [200, 40, 47]);   // 红底 ≈ --red
        else bg = rootRgb('--navy2', [0, 43, 90]);                                       // navy ≈ --navy2
      }
      r = Math.round(r * a + bg[0] * (1 - a));
      g = Math.round(g * a + bg[1] * (1 - a));
      b = Math.round(b * a + bg[2] * (1 - a));
    }
    return '#' + [r, g, b].map(n => n.toString(16).padStart(2, '0')).join('');
  }

  function bgHexOf(el) {
    // 取元素自身渲染背景色；透明则向上探到第一处非透明（cell 条纹/表头用）
    let cur = el;
    while (cur) {
      const c = getComputedStyle(cur).backgroundColor;
      const m = c.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)(?:,\s*([\d.]+))?\)/);
      if (m && (m[4] === undefined || +m[4] > 0.01)) {
        return '#' + [+m[1], +m[2], +m[3]].map(n => n.toString(16).padStart(2, '0')).join('');
      }
      cur = cur.parentElement;
    }
    return '#ffffff';
  }

  function styleOf(el) {
    const cs = getComputedStyle(el);
    const fs = parseFloat(cs.fontSize);
    const lh = parseFloat(cs.lineHeight);
    return {
      font_size_px: fs,
      color: rgbToHex(cs.color, el),
      bold: parseInt(cs.fontWeight) >= 600,
      align: { left: 1, start: 1, center: 2, right: 3 }[cs.textAlign] || 1,
      line_ratio: isNaN(lh) ? 1.4 : +(lh / fs).toFixed(3),
      pad_l: parseFloat(cs.paddingLeft), pad_t: parseFloat(cs.paddingTop),
      pad_r: parseFloat(cs.paddingRight), pad_b: parseFloat(cs.paddingBottom),
    };
  }

  function collectRuns(el) {
    const runs = [];
    function push(text, color, bold) {
      if (!text) return;
      const last = runs[runs.length - 1];
      if (last && last.color === color && last.bold === bold) { last.text += text; return; }
      runs.push({ text, color, bold });
    }
    function walk(node, color, bold) {
      node.childNodes.forEach(ch => {
        if (ch.nodeType === 3) {
          push(ch.textContent.replace(/\s+/g, ' '), color, bold);
        } else if (ch.nodeType === 1) {
          if (ch.tagName === 'BR') { push('\n', color, bold); return; }
          const cs = getComputedStyle(ch);
          if (parseFloat(cs.marginLeft) > 0) push(' ', color, bold);   // 荣誉 margin-left 作分隔（.tb .en CN/EN 不贴在一起）
          walk(ch, rgbToHex(cs.color, ch), parseInt(cs.fontWeight) >= 600);
        }
      });
    }
    const st = styleOf(el);
    walk(el, st.color, st.bold);
    while (runs.length && !runs[0].text.trim()) runs.shift();
    if (runs.length) runs[0].text = runs[0].text.replace(/^\s+/, '');
    while (runs.length && !runs[runs.length - 1].text.trim()) runs.pop();
    if (runs.length) runs[runs.length - 1].text = runs[runs.length - 1].text.replace(/\s+$/, '');
    return runs;
  }

  // 折中白名单：meaningful 文字块；装饰件（巨字水印/弧/折角底）不入。
  // ★示例皮肤专属——换 deck 按 SKILL.md §5 步1 替换整张白名单（含 C-16：文字类漏入=消失）。
  const TEXT_SEL = [
    'h1', 'h4',
    '.eyebrow', '.subtitle', '.carrier', '.footrow > div', '.brand-foot', '.pageno',
    '.badge', '.toc .cn', '.toc .en', '.it-t', '.it-d', '.num',
    '.bignum', '.ctitle', '.csub',
    '.rt', '.rs',
    '.tb', '.subhead', 'p.lead', 'p',
    '.blockhead',                              // 章节小标题（navy 加粗 + 左红条 border 留截图层）
    '.card .big',
    '.metric .v', '.metric .l',
    '.ft', '.fd',                              // .feat 徽块标题/描述（.feat 盒子 bg+红顶 border 留截图层，只提叶子）
    '.lane .lh', '.lane .li',
    '.flow .step', '.flow .arr',               // .arr 时间轴 → 连接符（截图文字透明会吃掉，须 overlay 补）
    '.callout', '.note',
    '.cread',
    '.ph',
  ].join(',');

  const slides = Array.from(document.querySelectorAll('section.slide'));
  return slides.map((slide, i) => {
    const sr = slide.getBoundingClientRect();
    const rel = el => {
      const r = el.getBoundingClientRect();
      return { x: +(r.left - sr.left).toFixed(1), y: +(r.top - sr.top).toFixed(1),
               w: +r.width.toFixed(1), h: +r.height.toFixed(1) };
    };
    const seen = new Set();
    const elements = [];

    slide.querySelectorAll(TEXT_SEL).forEach(el => {
      if (seen.has(el)) return;
      // .lead 同时命中 'p.lead' 与 'p'，querySelectorAll 已去重；此处防嵌套块重复
      // 跳过：被当作 list / table / 已含子文本块的容器，避免与子项重叠
      if (el.querySelector('ul, ol, table')) return;     // .ph(.col) 含 ul 的列不在此（.ph 无 ul）
      const runs = collectRuns(el);
      if (!runs.length) return;
      seen.add(el);
      const cls = (el.className && typeof el.className === 'string') ? el.className.trim() : '';
      const role = cls || el.tagName.toLowerCase();
      // .subhead::before 的 ✓（截图透明）→ overlay 补回
      if (el.classList.contains('subhead')) {
        runs.unshift({ text: '✓ ', color: runs[0].color, bold: true });
      }
      const st = styleOf(el);
      elements.push({
        type: 'text', role,
        text: runs.map(r => r.text).join(''),
        runs,
        centered: el.classList.contains('num') || el.classList.contains('bignum')
                  || el.classList.contains('lh') || el.classList.contains('ph'),
        ...rel(el), ...st,
      });
    });

    // 列表：ul.clean（红方块=background，截图保留→markerless 内缩）/ .box ul（▲▼=glyph，截图吃掉→补 run）
    slide.querySelectorAll('ul.clean, .box ul, .box ol').forEach(list => {
      const isBox = !!list.closest('.box');
      const boxKind = list.closest('.box.good') ? 'good' : (list.closest('.box.bad') ? 'bad' : null);
      const marker_mode = isBox ? (boxKind === 'good' ? 'up' : 'down') : 'bg';
      const li0 = list.querySelector('li');
      // L3 治本：▲▼ marker 色从 li::before computed color 抓进 manifest（extract 时点无遮罩→取真实色，
      // 实证 .box.good=红/.box.bad=蓝），export 端读它而非硬编码 MARKER 色，换 palette 自动跟随。
      let marker_color = null;
      if (isBox && li0) marker_color = hexOfColor(getComputedStyle(li0, '::before').color);
      const items = Array.from(list.querySelectorAll('li')).map(li => {
        const runs = collectRuns(li);
        return { runs, text: runs.map(r => r.text).join('') };
      }).filter(it => it.text);
      if (!items.length) return;
      elements.push({
        type: 'bullets', marker_mode, marker_color, items,
        ...rel(list), ...styleOf(li0 || list),
      });
    });

    // 表格 table.t：逐 cell 抓 color/bg/header（皮肤无关，export 忠实重绘）
    slide.querySelectorAll('table.t').forEach(table => {
      const trs = Array.from(table.querySelectorAll('tr'));
      const rows = trs.map(tr =>
        Array.from(tr.querySelectorAll('th,td')).map(cell => ({
          text: cell.innerText.replace(/\s+/g, ' ').trim(),
          is_header: cell.tagName === 'TH',
          bold: parseInt(getComputedStyle(cell).fontWeight) >= 600,
          color: rgbToHex(getComputedStyle(cell).color, cell),
          bg: bgHexOf(cell),
          border: hexOfColor(getComputedStyle(cell).borderTopColor),   // L3 治本：表头/格线色随 palette
        }))
      );
      const tw = table.getBoundingClientRect().width;
      const col_fracs = Array.from(trs[0].querySelectorAll('th,td'))
        .map(c => +(c.getBoundingClientRect().width / tw).toFixed(4));
      const row_heights = trs.map(tr => +tr.getBoundingClientRect().height.toFixed(1));
      elements.push({ type: 'table', rows, col_fracs, row_heights, ...rel(table) });
    });

    return { index: i + 1, elements };
  });
}
"""


def main():
    html = Path(sys.argv[1]).resolve()
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else html.parent / "_manifest_report.json"
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": int(CANVAS_W), "height": int(CANVAS_H)})
        page.goto(html.as_uri(), wait_until="domcontentloaded")
        page.add_style_tag(content=LAYOUT_CSS)
        page.wait_for_timeout(800)
        dims = page.evaluate(
            "() => Array.from(document.querySelectorAll('section.slide'))"
            ".map(s => { const r = s.getBoundingClientRect(); return [r.width, r.height]; })")
        slides = page.evaluate(EXTRACT_JS)
        browser.close()

    bad = [(i + 1, d) for i, d in enumerate(dims) if abs(d[0] - CANVAS_W) > 0.5 or abs(d[1] - CANVAS_H) > 0.5]
    if bad:
        print(f"FAIL: 画幅异常 {bad}")
        sys.exit(1)

    manifest = {"canvas_w": CANVAS_W, "canvas_h": CANVAS_H, "source_html": html.name, "slides": slides}
    out.write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    counts = [(s["index"], len(s["elements"])) for s in slides]
    print(f"slides={len(slides)} 画幅全部 {CANVAS_W:.0f}x{CANVAS_H:.0f} ✓")
    print(f"每页元素数: {counts}")
    print(f"manifest -> {out}")


if __name__ == "__main__":
    main()
