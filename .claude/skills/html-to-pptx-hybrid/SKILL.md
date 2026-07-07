# html-to-pptx-hybrid — HTML→PPT 折中 Hybrid 技术路线（皮肤/体裁无关内核）

> **📍 自足独立 skill（user 级 · 2026-07-04 从项目剥离）**：引擎脚本全部住本 skill 的 `scripts/`（+`scripts/probe/`），
> **无任何项目私有路径硬依赖**，冷启动只读本目录即可跑最小管线。下文正文路径一律指本 skill `scripts/*`（不再是任何 repo 的功能轴脚本目录）。
> **视觉皮肤/体裁包不随本内核打包**——本 skill 只含皮肤/体裁无关的内核 + 引擎脚本；皮肤是 §9 可生长外层，各项目按需就地建、指回本内核（移植边界见 `README.md`）。

> **本 skill = 不变内核**：把 1260×720 的 deck.html 转成"截图打底 + 可编辑叠层"的 16:9 pptx。
> 视觉皮肤 / 报告体裁 = **可扩展的外层**，各自一个皮肤包，**都指向本内核拿管线**：
> - 【竞品分析报告 · QD 红白】→ `skills/report-deck-qd-redwhite/`
> - 【现场评审报告 · RD38 皮】→ `skills/现场评审报告deck/`（自足体裁包：含本内核管线复用 + RD38 视觉皮肤 + `templates/`；归并自原 report-deck-rd38汇报 + 总结汇报deck-runbook，2026-06-26）
> - 未来体裁/皮肤继续加，**内核不动**。
>
> 渊源：本路线精髓最初实证于隔壁 Agent-3 Codex 项目的一份复刻指南（旧 `skills/html - PPT-claude.md`，
> 已报废重定向到本文件）。本 repo 借鉴其思想跑通 QD 红白(2026-06-11) + RD38 汇报(2026-06-23) 两套皮肤、
> 真正泛化了引擎后，提升为原生内核 skill。

---

## 0. 一句话原理（精髓，勿忘）

**Playwright 当眼睛量坐标，Playwright 当相机拍背景，PowerPoint 自己当画师摆元素，Python 只是个调度员。**

视觉保真度由**真实浏览器渲染**保证，编辑性由**真实 PowerPoint**保证 —— **不和这两个强大的引擎硬刚**。
这条路线所有"魔法"都来自这个分工：让浏览器干视觉的活，让 PPT 干交互的活，你只负责坐标对齐和数据搬运。

---

## 1. 为什么 win32com 而不是 python-pptx

| 维度 | python-pptx | win32com（本路线） |
|------|-------------|------------------|
| 本质 | 自己写 OOXML XML | 驱动本机 PowerPoint 进程的 COM API |
| 中文字体 | 须设 `Font.Name` + 多 namespace | `Font.NameFarEast` + `Font.Name` 即可 |
| 表格样式 | 手写 XML schemes | `AddTable` 后直接设属性 |
| 渐变/阴影/圆角 | 极难表达 | 仍然难，所以**根本不重建** —— 留给截图层 |
| 跨平台 | ✓ | ✗ 仅 Windows |

**核心权衡**：放弃跨平台，换 100% 保真。Windows 内部交付场景，这个代价值得。
（注：**验收/读** pptx 可用 python-pptx 读明文，无须 COM——见 `verify_deck_report.py`。**装配**才必走 COM。）

---

## 2. 核心架构：Hybrid 四层叠加 + 折中原则

每页 PPT = 4 层，自底向上：

```
④ 表格叠层 (PPT Table, 可编辑)        Shapes.AddTable
③ 图片叠层 (PPT Picture, 可替换)      object-fit:cover via PictureFormat.Crop
② 文字叠层 (PPT TextBox, 可编辑)      坐标从 manifest 读
① 截图层   (full-bleed Picture, 不可编辑)  渐变/装饰线/边框/圆角/水印；文字透明、图片隐藏；ZOrder=msoSendToBack(1)
```

**关键洞察**：
- 不要用 PPT API 重建装饰元素（渐变/阴影/圆角/折角块/巨字水印）——又丑又工作量爆炸。
- 用浏览器渲染的**遮罩截图**当"虚拟背景"，只覆盖装饰部分。
- 文字位置在截图里**透明占位**，所以叠层文字能精确对齐回原 HTML 位置。
- **`<canvas>`（Chart.js 图表）默认不进遮罩**（MASK_CSS 只 `img{visibility:hidden}`，不碰 canvas）→ 图表**静态烤入底图**。
  （chart 内容怎么取数/画法/放哪页 = 体裁层关注点，住 `skills/html-chart/`，本内核不持有，守皮肤/体裁无关纯度。）

### ★ 折中原则（本内核第二铁律，换皮也不变）★

**不是所有 shape 都重建。** 只把 **meaningful 内容**（标题/正文/列表/表格/指标/可替换图）叠成可编辑 overlay；
**装饰件**（渐变弧/折角块底/红竖条/巨字水印/虚线占位框轮廓）**一律留在截图层**烘进去。
判定标准 = "用户会不会想编辑它 / 它是不是承载信息"。装饰=否=留截图；内容=是=叠 overlay。
（违背折中、试图全 shape 重建 = 退化回硬刚 PPT 引擎，又丑又慢又脆。）

> **★ 例外路标（避免延伸时跑偏）**：以上"装饰一律烘进截图层"= 装饰是**一张整页不可编辑底图**的默认边界。
> 若需求升级为「让**某个装饰块**在 PPT 内独立可动 / 可缩放 / 加字撑大」——这超出本默认路线，**走 §11 元素拆分**
> （让浏览器 `element.screenshot(omit_background)` 精确抠出透明块 PNG，= §0「浏览器当相机」在单块上的应用）。
> **绝不要在 Python 里估 bbox 画白块去盖底**（= C-14 反模式：残留边框/彩条/marker、"背景一动残件跟着动"，
> 且违反 §0「Python 只是调度员、不和浏览器引擎硬刚」）。决策点在此、药方在 §11，别在岔口自己发明土法。

---

## 3. 三脚本管线 + 验收

```
deck.html ─┬─[Playwright] extract → _manifest.json   (每元素精确坐标+样式+runs)
           ├─[Playwright] screenshot_masked → *.png   (文字透明、img 隐藏的整页截图)
           └─[win32com]  export → deck.pptx           (截图打底 + 可编辑叠层)
                          ↓
            verify (python-pptx 读明文) → PASS/FAIL    (元素配对 + 禁词 grep)
```

---

## 4. 坐标系换算 + 装配要点（精髓代码，全量见脚本）

```python
CANVAS_W, CANVAS_H = 1260.0, 720.0     # HTML CSS px
SLIDE_W_PT, SLIDE_H_PT = 960.0, 540.0  # 16:9 = 13.333" × 7.5"
SX, SY = SLIDE_W_PT/CANVAS_W, SLIDE_H_PT/CANVAS_H   # 0.7619 / 0.75
def x(px): return px*SX
def y(px): return px*SY
def pt(px): return px*0.75              # CSS px(96dpi) → PPT pt(72dpi)
```

- **SlideSize 显式设**：`pres.PageSetup.SlideWidth=960; SlideHeight=540`（禁用 `SlideSize=4`，那是 35mm/3:2，见 C-1）。
- **中文字体**：`Font.NameFarEast = Font.Name = "Microsoft YaHei"`。
- **段落分隔 `\r`** 不是 `\n`（C-5）；**COM 常量用数值字面量**（C-7：`AddTextbox(1,…)`/`ppLayoutBlank=12`/`msoSendToBack=1`）。
- **路径含 `[ ]`**：`SaveAs` 先到 `tempfile.gettempdir()` 再 `shutil.move`；COM `Open`/`AddPicture` 收**绝对路径**（C-9）。
- **本机 Ldterm**：COM `SaveAs` 产物首字节 `88 7D 1C` 是**预期终态**，非故障；对外交付才需要这个加密态。

helper 函数族（`add_textbox / add_bullets / add_picture_cover(crop 模拟 object-fit) / add_bg_screenshot / add_table`）
全量实现见引擎脚本（§8），不在此重复贴 200 行；本节只锚住"绝不可错"的换算与常量。

---

## 5. ★换皮适配法（加一套皮肤/体裁时只动这里）★

内核管线不变，新皮肤只需在 extract/export 调这几个旋钮（RD38 汇报皮实证）：

1. **curated TEXT_SEL 白名单**：列出该皮肤"有意义文字块"的 class（标题条/小节/正文/卡片/指标/列表…），
   **不是通用全抓**（通用叶子遍历=过度工程，曾踩）。装饰 class 不入白名单 = 自动留截图层（**注**：仅纯装饰成立——**文字类**不入白名单 = 凭空消失，见 C-16）。
2. **暗底页配色混合**：`getComputedStyle` 拿到半透明色要按**该页有效背景**做 alpha blend（C-4）。
   按皮肤判定哪些页是暗底（QD：`.slide-red`；RD38：`.cover/.divider/.rdiv`），其余按白。
3. **被遮罩吃掉的 glyph 标记要补回**：遮罩 `*::before{color:transparent}` 会隐掉 `content:"✓/▲/▼"` 类
   **文字型**标记 → overlay 端按 role 补成染色 run；而 `content:""+background` 的**背景方块型**标记
   截图保留 → overlay markerless、文字内缩躲开。**两类处理相反，别一刀切**（C-12）。
4. **表格逐 cell 抓真实色**：extract 端记每 cell 的 `color` + 背景色进 manifest，export 忠实重绘 —— 皮肤无关，
   **别在 export 硬编码表头色**（QD 红 vs RD navy 不同）（C-13）。
5. **单行标题 NO_WRAP + 居中框满框重置**：见 C-11 / C-10。

> 加新皮肤的产出 = 一个 `skins/`-级皮肤包（视觉 token 表 + 模板/example + 该皮肤的 extract/export 变体或参数），
> 指回本内核。详见 §9。

---

## 6. 已知坑表 C-1 ~ C-16（全部踩过，开工前通读）

| # | 坑 | 根因 | 修复 |
|---|------|------|------|
| **C-1** | SlideSize 枚举陷阱 | `SlideSize=4`=35mm(810×540,3:2) 非 16:9 | 显式 `SlideWidth=960,SlideHeight=540` |
| **C-2** | extract 与 screenshot 必须共享 LAYOUT_CSS | 不同步→坐标系偏差(1236 vs 1260) | 两脚本同一段 CSS（`deck_common.LAYOUT_CSS`） |
| **C-3** | CSS padding 须映射 TextFrame.Margin | `getBoundingClientRect` 返 padding box | 提取 padding 应用为 PPT 边距；bullet 列表向内缩 |
| **C-4** | rgba 透明度须 alpha blend | 直接丢 alpha→颜色错 | JS 里按有效背景混合（暗底页按皮肤底色，白底按白） |
| **C-5** | `<br>`→`\n`→PPT 需 `\r` | innerText 返 `\n`，COM 段落分隔要 `\r` | `text.replace("\n","\r")` |
| **C-6** | 文本框宽度加 8% buffer | 浏览器 vs PPT 字体渲染差→溢出 | `buf_w=max(ew,ew*1.08)`（**居中框不加 buffer**，靠满框居中） |
| **C-7** | COM 常量须数值字面量 | 模块加载时 COM 未启动，枚举引用失败 | `ppLayoutBlank=12,msoTrue=-1,msoSendToBack=1,msoTextOrientationHorizontal=1` |
| **C-8** | 中文标点与引号冲突 | `、` 混入字符串→SyntaxError | 转义 / raw string |
| **C-9** | COM 文件参数须绝对路径 | PPT 进程 CWD≠脚本 CWD | 传 COM 前一律 `Path(...).resolve()` |
| **C-10** | 占位/折角等需垂直居中的框贴顶 | `AddTextbox` 默认 ShapeToFitText 把高度塌成一行，`VerticalAnchor=middle` 在塌掉的框里居中=贴顶 | 设完文字后对 `centered` 框**显式重置** `Left/Top/Width/Height` 回满框，再靠 `VerticalAnchor=3` 居中（2026-06-23 RD48 ph 占位实测） |
| **C-11** | 单行标题英文/末字被挤到第二行溢出装饰条 | 绝对定位/自适应宽标题框紧致，PPT YaHei 比 Chromium 略宽 | 单行 role（标题条/subhead/eyebrow/badge…）设 `WordWrap=msoFalse`（2026-06-23 RD48 "THREE STAGES" 实测） |
| **C-12** | 列表/标记符消失或重影 | 遮罩 `*::before{color:transparent}` 吃掉 glyph 型标记(✓/▲/▼)；但 background 方块型标记不受 color 影响、截图保留 | glyph 型 overlay 补染色 run；background 型 markerless+文字内缩。**两类相反别一刀切**（2026-06-23 RD48 实测） |
| **C-13** | 表格表头/单元格色串皮肤 | export 硬编码某皮肤表头色（QD 红） | extract 逐 cell 抓 `getComputedStyle` color+背景色进 manifest，export 忠实重绘=皮肤无关（2026-06-23 RD48 navy 表头实测） |
| **C-14** | 元素拆分时在 Python 里"估算 bbox 画白块"清底图→残留边框/彩条/marker（背景一动残件跟着动） | 违背 §0「浏览器当相机」哲学、Python 干像素活；文字 bbox≠真实块框（含 border/min-height/顶部 bar） | **浏览器精确抠图**：`element.screenshot(omit_background=True)` 抠透明精确 PNG + 扩 MASK_CSS `visibility:hidden` 出干净底图。★两态时序：**先拍 promoted 元素→再加 hide-mask 拍底图**（写反=空 PNG 静默假成功→PNG 非空自检兜底）；★坐标用浏览器内 `closest('section.slide')` 同帧算（`element.screenshot` 会滚动→缓存 slide.box 与后取 el.box 错位出负坐标）；★dsf=3 → `AddPicture` 显式 `bbox×SX/SY` pt。详见 §11（2026-06-25 RD49 3结构+RD48 全量27页实证） |
| **C-15** | `AddShape(5,…)` 圆角矩形（roundedRect）圆角"太夸张" | **没显式设圆角** → PPT 用默认 `Adjustments(1)=0.16667`（≈shorter_side 的 1/6，大框上几十 pt，远大于 CSS 的 10px） | 显式设：`adj = CSS_radius_px×0.75 / min(W_pt,H_pt)`（clamp ≤0.5）。★win32com **不支持** `Adjustments[1]=v`/`.Item(1)=v`（`TypeError: object does not support item assignment`）→ 走底层 property-put：`shp.Adjustments._oleobj_.Invoke(0,0,pythoncom.DISPATCH_PROPERTYPUT,False,1,adj)`（Item 是默认成员 DISPID=0，索引 1 + 值）。脚本 `split_deck_elements.py` 的 `set_corner()` 封装；所有 native 圆角件（面板框/卡片/marker bar）都过它（2026-06-29 RD48 25-27 用户实测「圆角夸张」） |
| **C-16** | 非 whitelist 的**文字**类在 PPT 里凭空消失 | 遮罩 `MASK_CSS` 把**所有**文字设透明（不只装饰）；只 whitelist 文字才有 overlay 补回 → 文字类（`.blockhead`/`.feat`/`.ft`/`.fd`/`.flow .arr`…）不入 whitelist = 既不进截图也不进 overlay = **消失**。§5 步1"不入白名单=留截图层"仅对纯装饰成立，文字类是陷阱 | extract 后**逐页核对 manifest role 清单 vs deck 实际 class**；deck 用了 whitelist 外的文字 class 就补进 `TEXT_SEL`（2026-07-01 RD48 项目背景调研附件实证：5 徽块 + 8 blockhead + 7 箭头差点消失） |

---

## 7. 强制自检流程（绝不一次生成全量就交付）

阶梯放量（RD48 实证有效）：**①前 3 页(封面/目录/分隔) → ②复杂页(最密页/表格/列表/▲▼框) → ③特例页(占位框) → ④全量**。
每级只验新增失败模式，过了才进下一级。

- **结构验收**（`verify_deck_report.py`，python-pptx 读明文无 COM）：页数=manifest / 每元素存在
  （**marker-aware**：列表 ▲▼ 前缀、bg 内缩不算缺失）/ 截图层图片=1 / 表格单元格匹配 / **禁词 grep=0**
  （按项目红线配：幻影/他项目泄漏/【推断】【替代】/源档污染/用户路径残留）。
- **COM 自检**（`selfcheck_deck_pptx.py`）：元素配对 + 坐标偏差≤3pt + 表格行列。
  ⚠ 读 `TextFrame.TextRange.Text` **不要 `[:80]` 截断**，否则 bullet 后续条目"消失"误报一片。
  ⚠ 设计内偏移（bg 列表内缩 / ▲▼ 前缀）会被报 flag——确认每条 flag 都落在已知设计类、**无未解释项**即放行。
- **逐页渲染肉眼核**：`probe/ppt_slides_to_png_clipboard.py`（COM 只读+`Slide.Copy`→剪贴板→Pillow 落明文 PNG，
  绕 Ldterm 反向加密；**对明文 pptx 走 COM 前先 copy 副本**）。比对每页 = 审过的 html。
- **Windows 坑**：`app.Visible=False` 抛 COM 错（"Hiding the application window is not allowed"），装配必须 `True`；
  验收脚本可 `Open(WithWindow=False)` 略过。
- **机器 PASS ≠ 人工验收**：交付措辞区分"自检 PASS"vs"待你人工肉眼验收"，附产物路径 + 重点看哪几页。

---

## 8. 引擎脚本（单一事实源，住本 skill `scripts/`）

> 脚本自足住 `scripts/`，相互只 `import deck_common`（+ `split_deck_elements` 引同目录 `export_deck_report`）；
> 冷启动只读本 skill 目录即可跑通，无项目私有路径依赖。

| 脚本 | 角色 | 皮肤 |
|------|------|------|
| `deck_common.py` | CANVAS/SLIDE 常量 + `LAYOUT_CSS`/`MASK_CSS`（共享，C-2） | 共享 |
| `screenshot_deck_masked.py` | 遮罩截图（文字透明/img 隐藏/device_scale_factor=3） | 共享 |
| `extract_deck_layout.py` + `export_deck_pptx.py` + `selfcheck_deck_pptx.py` | QD 红白皮 extract/装配/COM 自检 | 竞品(QD) |
| `extract_deck_report.py` + `export_deck_report.py` + `verify_deck_report.py` | RD38 汇报皮 extract/装配/明文验收（含 §5 五旋钮实现） | 结案汇报(RD38) |
| `split_deck_elements.py` | **元素拆分模式**驱动（§11 / C-14）：底图打底退化态 → 每页文字可编辑 + 装饰块逐个独立可动 | 共享（复用 export_deck_report 的 add_textbox/add_bullets 渲染文字保真） |

用法骨架：
```bash
py -3 -X utf8 extract_deck_report.py  <deck.html> <manifest.json>
py -3 -X utf8 screenshot_deck_masked.py <deck.html> <shots_dir>
SLIDE_RANGE=1-3 py -3 -X utf8 export_deck_report.py <manifest.json> <shots_dir> <out.pptx>   # 先 3 页自检
SLIDE_RANGE=   py -3 -X utf8 export_deck_report.py <manifest.json> <shots_dir> <out.pptx>   # 全量
py -3 -X utf8 verify_deck_report.py <out.pptx> <manifest.json>
```

---

## 9. 皮肤/体裁扩展层（外层，可持续生长）

> **关键分工**：皮肤 skill **不只管视觉**——它是"该体裁完整配方除具体数据" = 视觉语言 **+ 内容结构/叙事骨架
> + 体裁红线 + 事实源→章节映射**。两个体裁的**内容结构逻辑不同**（竞品=横向逐维度优劣对比；汇报=N 轮演进弧 + 四章骨架），
> 各自皮肤 skill 里独立记录，这样才能稳定产出**各自类型**的报告而非只复刻外观。
> 跨体裁的生命周期/审核门/数值数据契约住 `skills/竞品报告deck全生命周期/`；单项目具体内容住 FROZEN spec。

| 皮肤包 | 体裁 | 内容结构主轴 | 视觉语言 |
|--------|------|------|----------|
| `skills/report-deck-qd-redwhite/` | 竞品分析报告 | 本品 vs 竞品**逐维度优劣对比**（红蓝语义） | QD 红白（满红封面/分隔 + 黑标题条 + 红蓝优劣框 + jumpman 水印） |
| `skills/现场评审报告deck/` | 现场评审报告（证据/数据表为主、营销叙事最简） | **双主线 + 四章骨架（章04精简·砍营销/留证据）+ N 轮演进弧** | RD38 皮（navy 渐变封面 + 红折角目录块 + 红/navy 标题条 + 季度泳道 + 指标网格）；自足体裁包含管线+`templates/`，归并自原 report-deck-rd38汇报 + 总结汇报deck-runbook 2026-06-26 |

加新皮肤 = 新建 `skills/report-deck-XXX/`（**内容结构/叙事骨架 + 体裁红线 + 事实源映射** + 视觉 token 表 + 模板/example + 该皮肤 extract/export 变体），**指回本内核**。
**成熟度（§6.1 两轨）**：本内核已跑通 2 套独立皮肤（QD 红白 + RD38 汇报）→ 引擎泛化部分 = **stable**；
单个皮肤包是否再升模板库/命令，按其自身独立任务次数评估。

---

## 10. 编码 / 能力边界

- **编码**：Windows stdout 默认 GBK → 脚本顶 `sys.stdout.reconfigure(encoding="utf-8")` 或 `py -3 -X utf8`。
- **能搞定**：像素级视觉还原（渐变/装饰/徽章/表格框线）、可编辑中文文本、可替换图片(cover 裁剪)、可编辑表格、列表/KPI/时间线。
- **搞不定/需额外工**：复杂 SVG 动画(截图只拍静态)、视频(单独 AddMediaObject2)、跨平台(win32com 仅 Windows)、>30 页(COM 慢，全量数分钟)。

---

## 11. 元素拆分模式（split-decompose）★C-14 实证

> 何时用：deck 已是「整页栅格化、文字烤死」的**退化态**（截图没走 mask / export 没叠 overlay，常见旧路径产物），
> 或用户要在 PPT 里**手工微调/加字/独立挪动单个块**。目标终态 = **每页文字可编辑 + 装饰块逐个独立可动对象 + 干净底图**。
> 驱动脚本 `scripts/split_deck_elements.py`。**先按本节核对，别凭记忆改。**

### 一句话原理
还是 §0 那句——**让浏览器当相机精确抠图，别在 Python 里抠白块**（白块抠图=C-14 反模式）。
把内核第③层「图片叠层」边界**外移**：原本烘进底图的装饰块，改成 `element.screenshot(omit_background=True)` 抠出的**透明精确 PNG**（含 border/圆角/顶部彩条/内部虚线分隔，浏览器自己知道确切边界）；底图用扩展 MASK_CSS 把这些块 `visibility:hidden` 出**真干净底**。

### 四类元素处理（RD38 皮实证）
| 元素 | 处理 | 理由 |
|---|---|---|
| `.card` **无嵌套白名单子块** | **原生矩形 + 顶部彩条**（getComputedStyle 抓 bg/border/radius/btw；radius>2 用 roundedRect=5） | 可缩放（用户要加字撑大框）+ 保真，§2.5 折中「简单 rect 优先原生」 |
| 复合块（`.lane/.step/.arr/.metric/.box/.okc/.miss/.bad/.twobox/.callout/.num/.accentline/.cline…`）、`.titlebar`、`.subrule` | **透明 PNG**（element.screenshot omit_background，含块内虚线/彩条） | 复合/含内部结构/用户要图片→PNG 保真为一个可动单元（投影会被 border-box 裁→有投影也走 PNG 或原生权衡） |
| `ul.clean li::before` 方块 marker、`.note` 的 `border-left` accent 竖条 | **底图隐藏 + overlay 补绘原生小 shape** | `content:""+background` 型 C-12 截图保留，但拆分要彻底→补绘成独立件 |
| **内容图**（用 `background-image:url(data:image...)` 注入真图的块，非 `<img>`） | **加 WL → 透明 PNG**（同复合块机制：element.screenshot omit_background 抠出含真图） | ★盲区：扩展 MASK_CSS 的 `img{visibility:hidden}` **只盖 `<img>` 标签、不覆盖 CSS `background-image`**——这类块若不进 WL，底图会残留真图（本次正是这洞误判「0 图」）；进 WL 当一个可动图片单元 |
| **图表 `<canvas>`/`.cv` 容器** | **加 WL → 透明 PNG**（`element.screenshot omit_background` 抠出已绘图表；canvas 不受 `img{visibility:hidden}` 影响，同 background-image 近亲） | chart×拆分态：把图表当一个可动图片单元；详见 `skills/html-chart/SKILL.md` §交烤（2026-06-29 RD48 25-27 首次实证） |
| **图表面板框 `.cpanel`**（含 `<h4>` 标题 + `.cv`） | **专用 pass 原生圆角矩形**（贴合面板 ≈chart 大小；getComputedStyle 抓 bg/border/radius；`set_corner` 设圆角=C-15），底图 hide-mask 隐藏 | ★**不能入 WL**：`.cpanel` 进 WL 会让内部 `.cv` 被 NESTED 判定不促升、整块塌回一张 PNG（丢标题可编辑）→ 走**与 markers/accents 并列的独立 pass**：面板框=原生矩形（垫在 chart PNG 下、文字上），h4 标题走文本 overlay，`.cv` 走上一行透明 PNG，三者分离（2026-06-29 RD48 25-27 实证；底图随之空白丢） |
| `.cpanel h4::before` 标题红 bar | **底图隐藏 + overlay 补绘原生小 roundedRect**（5×15px·radius2，h4 左侧垂直居中） | 第三类 marker（前两类=`ul.clean li::before` 方块 / `.note` accent 竖条）；`content:""+background` 型截图保留，拆分要彻底→独立小 shape（圆角同走 C-15 set_corner） |
| 正文/标题/列表/表格文字 | **真量产 add_textbox/add_bullets**（读**新鲜** manifest） | 文字渲染保真=管线主业 |

### 三个致命坑（按序，全在 C-14）
1. **两态时序**：同一 page，**先**逐个 `element.screenshot` 拍 promoted 元素（仅 MASK_CSS 文字透明态）→ **再** `add_style_tag(hide-mask)` 拍底图。写反=拍到空 PNG 且不报错 → **自检必验每个 promoted PNG 非全透明**（不透明像素>阈值）。
2. **坐标错位**：`element.screenshot` 会把元素滚进视口；**别**缓存一次 `slide.bounding_box()` 再去减后取的 el box（两个滚动态→负坐标）。用浏览器内 JS `closest('section.slide')` 同帧算相对坐标（`RELJS`）。
3. **dsf=3 放大**：element PNG 是 3 倍像素密度；`AddPicture` 必须显式 `Width/Height = bbox×SX/SY`(pt)，别让 PPT 按 PNG 原生 px→pt（3 倍放大）。

### 嵌套 + 空白门 + 块白名单
- **嵌套**：只提升**最外层**白名单块（`e` 无白名单祖先），子块随父 PNG 一起进图，避免双重提升。`.card` 若含白名单子块→回退 PNG（原生矩形会丢子块）。
- **空白门**（确定性，别按页号硬编码）：扩 hide-mask 后测底图灰度 `extrema`；近匀且接近页背景色 → **真空白丢底图**（原生白底，全可编辑、文件更小）；有页级真装饰（封面/分隔渐变）→ **保留底图**。
- **块白名单 WL**：`split_deck_elements.py` 顶部 `WL` 为 RD38 皮实证集。**换 deck / 换皮先核 WL** —— Playwright 跑「每页最外层白名单块」探测（见脚本 NESTED 逻辑），补齐该皮独有装饰块 class，避免漏拆（曾漏 `.lane/.step/.arr/.note`→用户抓到"背景一动残件跟着动"）。
- **marker overlay 偏移是 per-皮 tuned 常量**：补绘 `li::before` 方块 marker 的逐 li `+2/+9`（脚本内）偏移按 RD38 皮的行高/字号手调，**不是通用量**。换页型/换皮→C-12 重影/漂移属 page-instance 失败模式，必**独立重验**（别假定沿用；jury 曾现读脚本 line 才发现是 tuned 常量）。

### 强制阶梯（沿用 §7）
①前 3 页(封面/目录/分隔) → ②各块型代表页(对比/指标/时间线) → ③特例(twobox/box) → ④全量。每页**渲染肉眼核 + PNG 非空自检**；机器 PASS≠人工验收。
**新鲜度红线**：manifest 必须是**当前 HTML** 抽的（HTML 晚于 manifest 就 `extract_deck_report.py` 重抽到新文件，别用旧 manifest 否则文字过时/token 残留）。

> 成熟度（§6.1 两轨）：2026-06-25 RD49（3 结构：空底+卡片/渐变封面/密集泳道）+ RD48（全量 27 页跨全块型）实证。
> 技法 = stable；`split_deck_elements.py` 的 WL 是 **RD38 皮专属**，换皮属 draft（需按"换 deck 清单"重核）。
> 2026-06-29 增 **chart 面板拆分**（`.cv` 透明 PNG + `.cpanel` 专用 pass 原生框 + h4::before marker + C-15 圆角）：RD48 现场评审 25-27 三图表页首次实证（柱/线/雷达全覆盖），draft（1 例·1 体裁，升 stable 需 2-3 次独立，见 html-chart §成熟度）。
