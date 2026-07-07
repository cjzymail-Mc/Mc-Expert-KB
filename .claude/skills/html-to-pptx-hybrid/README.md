# html-to-pptx-hybrid — 自足独立 skill（user 级）

> **HTML→PPT「截图打底 + 可编辑叠层」内核**：把 1260×720 的 deck.html 转成 16:9 pptx，
> 视觉保真交给真实浏览器渲染、编辑性交给真实 PowerPoint。方法论全文见 `SKILL.md`。
>
> **2026-07-04 从项目剥离成自足独立件**：脚本全部住 `scripts/`，**无任何项目私有路径硬依赖**，
> 冷启动只读本目录即可跑最小管线。皮肤/体裁包**不随本内核打包**（见下「皮肤层」）。

## 目录布局

```
html-to-pptx-hybrid/
├── SKILL.md          # 内核方法论：坑表 C-1~C-16 + §5 换皮法 + §11 元素拆分
├── README.md         # 本文件
└── scripts/          # 引擎脚本族（自足可跑，相互只 import deck_common + split→export_deck_report 同目录内引）
    ├── deck_common.py            # CANVAS/SLIDE 常量 + LAYOUT_CSS/MASK_CSS（共享，C-2）
    ├── screenshot_deck_masked.py # 遮罩截图（文字透明/img 隐藏/device_scale_factor=3）
    ├── extract_deck_layout.py    # 【示例皮肤变体·红白竞品】extract
    ├── export_deck_pptx.py       # 【示例皮肤变体·红白竞品】win32com 装配
    ├── selfcheck_deck_pptx.py    # COM 自检（元素配对 + 坐标偏差 + 行列）
    ├── extract_deck_report.py    # 【示例皮肤变体·多章节汇报】extract（内含 §5 五旋钮 worked example）
    ├── export_deck_report.py     # 【示例皮肤变体·多章节汇报】win32com 装配（split 复用它渲染文字）
    ├── verify_deck_report.py     # python-pptx 读明文验收（禁词表 ★按项目红线配）
    ├── split_deck_elements.py    # 元素拆分模式（§11 / C-14），复用 export_deck_report
    ├── gate_deck_html.py         # HTML 开工门禁
    ├── preview_screenshot.py     # 截图 + 溢出检测
    └── probe/                    # 只读探针（渲染肉眼核 / chart 取数 / 视觉取证）
        ├── ppt_slides_to_png_clipboard.py
        ├── extract_chart_numcache.py
        └── dump_ppt_visual.py
```

## 依赖（可复现）

```bash
pip install playwright pywin32 python-pptx Pillow
playwright install chromium
```

- **playwright + chromium**：extract 量坐标 / screenshot 拍遮罩底图。
- **pywin32**（win32com）：装配 pptx 必走它（本机加密 I/O 底座，**禁 python-pptx 装配**）。
- **python-pptx**：仅**读明文**验收（`verify_deck_report.py`）；装配一律不用它。
- **Pillow**：probe 逐页渲染落 PNG。
- **仅 Windows**（win32com 限定）。

## 运行方式（最小管线）

脚本相互是同级 import，**在 `scripts/` 目录内运行**：

```bash
cd scripts
py -3 -X utf8 extract_deck_report.py    <deck.html> <manifest.json>
py -3 -X utf8 screenshot_deck_masked.py <deck.html> <shots_dir>
SLIDE_RANGE=1-3 py -3 -X utf8 export_deck_report.py <manifest.json> <shots_dir> <out.pptx>   # 先 3 页自检
SLIDE_RANGE=    py -3 -X utf8 export_deck_report.py <manifest.json> <shots_dir> <out.pptx>   # 全量
py -3 -X utf8 verify_deck_report.py     <out.pptx> <manifest.json>
```

> `extract_deck_report.py` 带的是「多章节汇报」体裁的 **worked example** 白名单/旋钮——
> **换你自己的 deck 时按 `SKILL.md` §5 换 `TEXT_SEL` / 暗底页选择器 / marker 处理**，别原样套到 class 名不同的 deck。

## 皮肤 / 体裁层（外层，不随内核打包）

本 skill 只含**皮肤/体裁无关的内核 + 引擎脚本 + 两套示例 extract 变体**。
具体某体裁的「怎么写 HTML + 怎么调内核旋钮 + 叙事骨架 + 事实源映射」= **可生长外层**，
按 `SKILL.md` §9 各项目按需就地建一个皮肤包、**指回本内核**，不塞进本 skill 目录（保内核纯度 + 自足）。

## 加密底座（保留，勿动）

- 碰任何 Office 二进制**先读 8 字节**：`88 7D 1C`=加密→按项目硬规则 STOP；`50 4B`=明文可续。
- 装配产 pptx 走 **win32com（真实 PowerPoint 进程）**，产物首字节可能是加密态（预期终态，对外交付需要）。
- **禁** python-pptx 装配 / COM-free 导出 / SVG→DrawingML（违加密硬规则）。读/验收可 python-pptx 读明文。
