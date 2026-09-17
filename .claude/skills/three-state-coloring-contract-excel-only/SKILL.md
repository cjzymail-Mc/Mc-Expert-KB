---
name: three-state-coloring-contract-excel-only
description: 「染色驱动」的 **Excel** 模板填充/标记契约——用【底纹色 Interior.Color + 字色 Font.Color】**双通道组合**作为唯一识别标准，精确 RGB 等值判定（禁用 ColorIndex），把模板单元格分三态（红=必替换 / 黄=待确认 / 无色=不动）。**仅适用于 Excel**（Word 走 HighlightColorIndex 单通道独立高亮图层、PPT 靠 shape 名定位，均不走本契约）。双通道是为绕开「Excel 底纹位与业务底纹同属一个物理属性、会撞车」——单通道仍会误判业务底色，要求底纹+字色两个特殊色**同时命中**才算标记格，撞色概率近零。**用户只染单通道 = 违规**，脚本必须强制停下提醒用户补齐双通道，不得擅自当标记处理、也不得替用户补色。加密态无差别（COM 启白名单 EXCEL.EXE 透明读色，实测确认）。任何「同一 Excel 模板复用 + 部分单元格要换 + 部分保留」类项目用本契约能省「教 AI 这格改那格不改」的时间。
---

# three-state-coloring-contract-excel-only

> ## ⚠️ 适用范围：仅 Excel（only for Excel）
>
> 本契约**只服务 Excel 模板填充/标记**。Word / PPT 各有自己的标记法，**不走本契约**：
> - **Word** —— 走 `three-state-coloring-contract-word-only`：`HighlightColorIndex` 是**独立高亮图层**，与内容样式物理分离，单通道即够。
> - **PPT** —— 有稳定 shape COM 名定位，不需要染色当锚点。颜色是 `ppt-acceptance-check` L3 验收的事。
> - **Excel（本契约）** —— `Interior.Color` 就是单元格底纹**本身**，和业务表的表头色/斑马纹/警示红是**同一物理属性位**，单通道照搬纯红纯黄会把业务底色误判成标记（假阳性）。**所以 Excel 必须用「底纹 + 字色」双通道组合**——这是本契约区别于 Word 单通道的核心。

Excel 模板填充类项目最大的认知负担：**告诉 AI 哪个单元格要替换、哪个不能动**。Excel 没有 Word 那种独立高亮图层可借，底纹位又和业务色抢，所以用**双通道组合**把"标记"和"业务底色"在物理上拉开距离——一个 0 歧义、且撞业务色概率近零的协议。

## 唯一识别标准：底纹 + 字色 双通道组合（不可单用其一）

**一个单元格被判为「标记格」，当且仅当它的底纹色与字色 _同时_ 命中契约里某一态的 (fill_rgb, font_rgb) 配对。** 缺任一通道都不算标记格。

- 判定走 **`Interior.Color` / `Font.Color` 的精确 RGB 等值**（COM 返回 BGR long，转 RGB 后比对）。
- **禁用 `ColorIndex`**（理由见下「为什么禁 ColorIndex」——实测撞色）。

为什么强制双通道，不许单通道：
- **单通道（只底纹）** → 撞业务底纹。业务表大量用底纹色，纯红纯黄会被误判成标记 = 假阳性。这正是 Word 契约当年拒绝外推到 Excel 的原因。
- **单通道（只字色）** → 撞业务字色概率小一些，但仍非零（警示红字、链接蓝字）。
- **双通道组合** → 要求"底纹=特殊红 **且** 字色=特殊配对色"同时成立。业务表几乎不可能在同一格上同时撞中两个特殊色 → 误判概率压到近零。

## 契约定义（三态 × 双通道）

| 态 | 底纹 `Interior.Color` | 字色 `Font.Color` | 语义 | 脚本动作 |
|---|---|---|---|---|
| **红** | 特殊红（如 `#FF0000`） | 特殊配对字色（如 `#7030A0` 紫） | 必替换：占位，必须用数据填上 | 写入 |
| **黄** | 特殊黄（如 `#FFFF00`） | 特殊配对字色（如 `#00B0F0` 浅蓝） | 待确认：人审过再决定 / 数据缺失暂留 | **跳过 + 告警（ESCALATE）** |
| **无色** | 非任何配对色（普通业务格 / 无填充） | 普通字色 | 不动：业务数据 / 模板原生说明 | 跳过 |

> **配对色由各项目在 contract JSON 里声明**（见下 Schema），上表是**推荐默认**，不是写死值。原则：**字色那一格必须选一个业务表绝不会用的罕见色**——配对色是"防撞锁"，越罕见越安全。底纹可贴近语义色（红/黄），靠罕见字色把整对锁死。

### 为什么要黄态（不是只用红 / 无色）

很多模板字段处于"应该填但本次缺数据"的灰色地带。只有红/无色二态时这种字段无处安放（填红会写错、改无色会漏审）。黄态专门承载它：脚本见黄 → 跳过 + 告警 → 触发 ESCALATE（参考 `pipeline-self-check-loop`）。

## 强制纠错：单通道 = 违规，必须停下提醒（不得擅自处理）

用户在染模板时**必须底纹和字色一起染**。脚本遇到「半标记格」时的硬动作：

**半标记格定义** = 底纹命中某态的 fill_rgb，但字色不命中该态的 font_rgb（或反之，字色命中、底纹不命中）。

遇到半标记格，脚本**必须**：

1. **停下 + 强制提醒用户**：报出该格地址 + 当前 (fill, font) + 缺哪个通道。
2. **不得当标记处理**——不能"看着像红就当红写入"，破坏双通道可信度。
3. **不得当无色跳过**——半标记几乎一定是用户漏染了一个通道，静默跳过会漏填。
4. **不得替用户补色**——AI 不能自作主张"我帮你把字色也染上"。染色只能用户手工染（同 Word 契约：AI 不新增染色）。

```python
if fill_hit and not font_hit:
    raise MarkingViolation(f"{addr}: 只染了底纹({fill})、字色({font})未配对——"
                           f"双通道契约要求底纹+字色同时染。请补齐字色后重跑，"
                           f"我不会替你补色、也不会擅自把它当标记。")
if font_hit and not fill_hit:
    raise MarkingViolation(f"{addr}: 只染了字色({font})、底纹({fill})未配对——同上。")
```

> **Why 这么硬**：双通道的全部价值就在"两个都中才算数"。一旦允许"中一个就放行"，立刻退化回单通道、撞业务色的老坑就回来了。半标记必须当**错误**抛、逼用户在模板侧改对，而不是在脚本侧猜。

## 为什么禁 ColorIndex（实测撞色）

`ColorIndex` 是 Excel 旧的 56 色调色板索引，会把相近色**吸附到最近槽位**。本仓 `加密test.xlsx` 实测：

| 单元格 | 值 | `Interior.Color`（精确RGB） | `ColorIndex` |
|---|---|---|---|
| E19 | red | `#FF0000` | **idx3** |
| I8 | dark red | `#C00000` | **idx3** ← 撞了 |
| E9 | yellow | `#FFFF00` | idx6 |
| B2 | green | `#00B050` | idx14 |

`#FF0000`（纯红）和 `#C00000`（深红，常见业务警示色）**被 ColorIndex 都归并成 idx3**。若用 ColorIndex 判"是不是标记红"，深红业务底色会被误判成标记 → 假阳性。`.Color` 这一列四个色干干净净分得清。**所以判定永远用 `.Color` 精确 RGB 等值，禁用 ColorIndex。**

## 加密态无差别（COM 透明读色，实测确认）

> **前提注记（2026-09-11）**：本节加密态实测源自生产机（带 Ldterm）。当前开发机无加密，但**读色仍必须走 COM**——openpyxl 不解析 RGB 是库缺陷、与加密无关——故本节结论在本机同样成立，只是"加密/明文一视同仁"里的加密分支当前休眠。

本机 Ldterm 对 win32com 启动的白名单 `EXCEL.EXE` 透明解密（白名单进程）。`加密test.xlsx` 首字节 `88 7D 1C`（密文），但 COM `DispatchEx` 打开仅 **1.2s**，`Interior.Color` / `Font.Color` 全部读出**精确 RGB**（含 `#7030A0`、`#00B0F0` 这类非调色板标准色），与明文态零差异。

**所以：染色契约统一走 COM，加密/明文一视同仁，不需要为加密态做任何特殊处理。**（碰文件仍按 CLAUDE.md 硬规则先读 8 字节：`88 7D 1C` → 走 COM；`50 4B` → 明文也走 COM 读色，别图快用 openpyxl——openpyxl 读色返回 theme/indexed 原始态、不解析成 RGB，会漏判。**读色这一项不吃"解密提速"那条捷径。**）

## Schema 样板（每项目一份 contract 声明）

### 顶层 `coloring_contract` 声明（双通道版）

```json
{
  "coloring_contract": {
    "channel": "dual",
    "match": "exact_rgb",
    "forbid_colorindex": true,
    "states": {
      "red":    { "fill_rgb": "#FF0000", "font_rgb": "#7030A0", "semantics": "必替换",           "script_action": "写入" },
      "yellow": { "fill_rgb": "#FFFF00", "font_rgb": "#00B0F0", "semantics": "待确认（人审）",   "script_action": "跳过 + 告警" },
      "none":   { "semantics": "不动（业务数据/原生说明）", "script_action": "跳过" }
    },
    "on_half_marked": "raise"
  }
}
```

每份 mapping JSON 顶部必带这个声明，让 AI / 人审一眼知道这份契约用双通道、配对色是哪两个、半标记怎么处理。`fill_rgb`/`font_rgb` 按项目实际染的色填，**字色务必选业务表不用的罕见色**。

### 槽位级声明

```json
{
  "id": "xlsx_bom_t1",
  "strategy": "dual_channel_driven",
  "gate": "coloring",
  "locator": { "sheet": "BOM", "range": "$C$3:$F$30" },
  "cells": [
    { "addr": "C3", "state": "red",  "action": "write", "field": "material.name" },
    { "addr": "D3", "state": "none", "action": "skip",  "maps": "规格（业务标准化）" }
  ]
}
```

`gate: "coloring"` 表示这块用双通道染色驱动（vs `gate: "placeholder"` 用 `{{token}}`）。

## 双闸门并存（同 Word）

染色**不是**唯一定位方式，**应和占位符 `{{token}}` 双闸门并存**：占位符适合**程序定位**（精确机械），染色适合**人审**（一眼看出哪改哪别动）。二者互校：占位符没填上 → 脚本报错；染色少染了 / 半标记 → 强制纠错报错。

## 实现要点

### 1. 双通道检测代码（Excel · COM）

```python
def rgb_of(com_color):
    """COM Interior.Color / Font.Color 返回 BGR long → '#RRGGBB'。"""
    c = int(com_color)
    return f"#{c & 0xFF:02X}{(c >> 8) & 0xFF:02X}{(c >> 16) & 0xFF:02X}"

def classify(cell, contract):
    fill = rgb_of(cell.Interior.Color) if cell.Interior.ColorIndex != -4142 else None
    font = rgb_of(cell.Font.Color)
    for state, spec in contract["states"].items():
        if state == "none":
            continue
        fill_hit = (fill == spec["fill_rgb"])
        font_hit = (font == spec["font_rgb"])
        if fill_hit and font_hit:
            return state                      # 双通道命中 → 合法标记
        if fill_hit ^ font_hit:               # 半标记 → 违规
            raise MarkingViolation(
                f"{cell.Address}: 半标记（fill={fill} font={font}），"
                f"双通道契约要求 {state} 态底纹+字色同时染。请补齐后重跑。")
    return "none"                             # 都不中 → 业务格，不动
```

**性能护栏（必读）**：`Interior.Color` / `Font.Color` **没有 bulk 数组属性**，只能逐格读 = N 次 COM 往返。大表全扫会触发 COM storm（参考 `inspect-excel-template` 的 `cell_cap` 退化设计）。**只在 `locator` 圈定的范围内逐格读，别全表扫**；范围大时设上限 + 退化告警。这也是为什么本契约不并进 `inspect-excel-template`（那个探针围绕"1 次 bulk .Value"搭建，逐格读色会破坏它的性能模型）。

### 2. 自检环节必跑「黄态残留扫描 + 半标记扫描」

参考 `pipeline-self-check-loop` 的 Self-check：交付前所有黄态格应在 build 时被替换为红/无色；任何**黄态残留**或**半标记残留** = 自检不通过、不许交付。

### 3. 不要让 AI 自己新增 / 补全染色

染色只能**用户在模板里手工染**，且必须双通道一起染。AI 在 build 阶段：见红双通道 → 写数据；见黄双通道 → 跳过 + 告警；见无色 → 不动；**见半标记 → 强制纠错报错**。**绝不**自作主张补色或"猜这格应该是红"。

## 跟其他 skill 的关系

- **`inspect-excel-template`** —— Excel 结构探针，是处理 Excel 模板的强制前置。它的 `--blanks` 走「空值驱动」(物理空格=待填)，**故意不读色**（保持"1 次 bulk .Value"的性能模型）。本契约走「染色驱动」，是**与空值驱动并列的另一条标记路线**，二者按项目选用（人眼对颜色更敏感 → 复杂模板优先染色；纯"哪格空哪格填"→ 空值驱动够用）。**逐格读色的实现放本契约/各项目脚本里，不塞回探针**。
- **`three-state-coloring-contract-word-only`** —— 姊妹契约。Word 单通道（HighlightColorIndex 独立图层），Excel 双通道（底纹+字色）。差异根源：Word 有独立高亮图层、Excel 没有，底纹位与业务色抢，必须靠双通道组合拉开距离。
- **`office-com-helpers`** —— 读色前用它的 `detect_office_cipher` 判路由、`com_get` 安全访问；RGB↔BGR 转换、安全 print 复用它，别自己手撸。
- **加密文件** —— Ldterm 对 COM 启动的 EXCEL.EXE 透明，本契约直接处理加密 xlsx（实测 1.2s）。

## 不要做

- ❌ 不要单用一个通道当标记——**底纹+字色必须同时命中**才算标记格，半标记一律强制纠错报错
- ❌ 不要用 `ColorIndex` 判色——`#FF0000` 与 `#C00000` 同撞 idx3，会误判业务深红。永远 `.Color` 精确 RGB 等值
- ❌ 不要让脚本/AI 替用户补色或自动把黄改红——染色是用户手工的事，AI 只读不写色
- ❌ 不要在 build 完成后保留任何黄态 / 半标记——残留 = 自检不通过
- ❌ 不要逐格全表扫色——只扫 locator 圈定范围，大范围设 cell_cap 退化，避免 COM storm
- ❌ 不要图快用 openpyxl 读色（即便文件已解密）——它返回 theme/indexed 原始态、不解析 RGB，会漏判。读色走 COM
- ❌ 不要把本契约外推到 Word / PPT——Word 走单通道高亮图层、PPT 靠 shape 名，各有专属 skill
