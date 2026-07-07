# -*- coding: utf-8 -*-
"""QD 红白 deck html 坐标提取（Playwright + getBoundingClientRect）→ _layout_manifest.json
用法: py -3 -X utf8 extract_deck_layout.py <deck.html> [out.json]
run 级颜色提取：em.r/em.b/.en/b 等行内染色作为 runs 落进 manifest，pptx 端按字符区间还原。
"""
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

from playwright.sync_api import sync_playwright

from deck_common import CANVAS_W, CANVAS_H, LAYOUT_CSS

EXTRACT_JS = r"""
() => {
  function rgbToHex(c, el) {
    const m = c.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)(?:,\s*([\d.]+))?\)/);
    if (!m) return '#000000';
    let r = +m[1], g = +m[2], b = +m[3];
    const a = m[4] !== undefined ? +m[4] : 1;
    if (a < 0.99 && el) {
      // 满红页文字背景按 --red #D82640 混合，白底页按白混合（教训 C-4）
      const onRed = el.closest('.slide-red');
      const bg = onRed ? [216, 38, 64] : [255, 255, 255];
      r = Math.round(r * a + bg[0] * (1 - a));
      g = Math.round(g * a + bg[1] * (1 - a));
      b = Math.round(b * a + bg[2] * (1 - a));
    }
    return '#' + [r, g, b].map(n => n.toString(16).padStart(2, '0')).join('');
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
      line_ratio: isNaN(lh) ? 1.2 : +(lh / fs).toFixed(3),
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
          walk(ch, rgbToHex(cs.color, ch), parseInt(cs.fontWeight) >= 600);
        }
      });
    }
    const st = styleOf(el);
    walk(el, st.color, st.bold);
    // 首尾空白修剪（保持 run 边界）
    while (runs.length && !runs[0].text.trim()) runs.shift();
    if (runs.length) runs[0].text = runs[0].text.replace(/^\s+/, '');
    while (runs.length && !runs[runs.length - 1].text.trim()) runs.pop();
    if (runs.length) runs[runs.length - 1].text = runs[runs.length - 1].text.replace(/\s+$/, '');
    return runs;
  }

  const TEXT_SEL = 'h1,h2,h3,p,.toc-cn,.toc-en,.toc-num,.toc-tt,.divider-no,' +
    '.tbar,.sec,.qd-badge,.info-y,.sum,.ph .m,.ph .n,.pagefoot span,' +
    '.pagefoot-red,.cover-foot span,.metric li';

  const slides = Array.from(document.querySelectorAll('section.slide'));
  return slides.map((slide, i) => {
    const sr = slide.getBoundingClientRect();
    const rel = el => {
      const r = el.getBoundingClientRect();
      return { x: +(r.left - sr.left).toFixed(1), y: +(r.top - sr.top).toFixed(1),
               w: +r.width.toFixed(1), h: +r.height.toFixed(1) };
    };
    const elements = [];

    slide.querySelectorAll(TEXT_SEL).forEach(el => {
      const runs = collectRuns(el);
      if (!runs.length) return;
      const role = (el.className && typeof el.className === 'string')
        ? el.className.trim() : el.tagName.toLowerCase();
      // .sec 的 ✓ 来自 CSS ::before，innerText 取不到，手工补
      if (el.classList.contains('sec')) {
        runs.unshift({ text: '✓  ', color: runs[0].color, bold: runs[0].bold });
      }
      elements.push({
        type: 'text', role,
        text: runs.map(r => r.text).join(''),
        runs, ...rel(el), ...styleOf(el),
      });
    });

    slide.querySelectorAll('.box ol, .box ul').forEach(list => {
      const items = Array.from(list.querySelectorAll('li')).map(li => {
        const runs = collectRuns(li);
        return { runs, text: runs.map(r => r.text).join('') };
      }).filter(it => it.text);
      if (!items.length) return;
      const li0 = list.querySelector('li');
      elements.push({
        type: 'bullets', ordered: list.tagName === 'OL', items,
        ...rel(list), ...styleOf(li0 || list),
      });
    });

    slide.querySelectorAll('table.data').forEach(table => {
      const trs = Array.from(table.querySelectorAll('tr'));
      const rows = trs.map(tr =>
        Array.from(tr.querySelectorAll('th,td')).map(cell => ({
          text: cell.innerText.replace(/\s+/g, ' ').trim(),
          is_header: cell.tagName === 'TH',
          bold: parseInt(getComputedStyle(cell).fontWeight) >= 600,
        }))
      );
      const tw = table.getBoundingClientRect().width;
      const col_fracs = Array.from(trs[0].querySelectorAll('th,td'))
        .map(c => +(c.getBoundingClientRect().width / tw).toFixed(4));
      const row_heights = trs.map(tr => +tr.getBoundingClientRect().height.toFixed(1));
      elements.push({ type: 'table', rows, col_fracs, row_heights, ...rel(table) });
    });

    // chart 占位提取（data-chart-id + 坐标，供 inject_com_charts.py 使用）
    const chart_placeholders = [];
    slide.querySelectorAll('[data-chart-id]').forEach(el => {
      chart_placeholders.push({
        chart_id: el.getAttribute('data-chart-id'),
        ...rel(el),
      });
    });

    return { index: i + 1, elements, chart_placeholders };
  });
}
"""


def main():
    html = Path(sys.argv[1]).resolve()
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else html.parent / f"_manifest_{html.stem[-9:-4]}.json"
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": int(CANVAS_W), "height": int(CANVAS_H)})
        page.goto(html.as_uri(), wait_until="domcontentloaded")
        page.add_style_tag(content=LAYOUT_CSS)
        page.wait_for_timeout(800)
        # 画幅核验（C-2）
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
