---
name: three-state-coloring-contract-word-only
description: 「染色驱动」的 **Word** 模板填充契约——用 Word 高亮色（HighlightColorIndex）把模板内容分成三态（红=必替换 / 黄=待确认 / 无色=不动），让自动化脚本只动该动的、人审只看该看的。**仅适用于 Word**（Word 文本流缺稳定锚点，染色是唯一既便于机器识别又便于人工识别的标记法）；PPT 靠 shape 名定位、Excel 标记方式另行探索，均不走本契约。任何「同一 Word 模板复用 + 部分字段要换 + 部分字段保留」类项目用这个契约能省 70% 的「教 AI 这里改那里不改」时间。
---

# three-state-coloring-contract

> ## ⚠️ 适用范围：仅 Word（only for Word）
>
> 本契约**只服务 Word 模板填充**，不是通用 Office 方案。
> **为什么只有 Word**：Word 是文本流文档，**缺稳定锚点**（CLAUDE.md 红线禁用字符偏移坐标），染色是唯一一个**同时便于机器识别（COM 读 `HighlightColorIndex`）和人工识别（肉眼看颜色）**的标记途径。
> **其他 Office 不走本契约**：
> - **PPT** —— 有稳定的 shape COM 名可定位，不需要染色当锚点（PPT 的颜色验收是 `ppt-acceptance-check` L3 的事，与本「填充标记契约」不是一回事）。
> - **Excel** —— `Interior.Color` 与单元格业务底纹是同一物理属性位，照搬纯红纯黄会与业务底色冲突。**已落地为独立姊妹 skill `three-state-coloring-contract-excel-only`**（走「底纹+字色」双通道组合，绕开底纹位撞业务色），不并入本契约。

Word 模板填充类项目最大的认知负担：**告诉 AI 哪里要替换、哪里不能动**。三态染色契约把这个判断从"靠 AI 理解 + 用户口头解释"换成"看模板上的颜色标记"——一个 0 歧义的协议。

## 何时使用

- 一份模板要复用到多个项目，但**只有部分字段要换**（如：项目名、负责人、日期换，流程描述、章节标题不换）
- 用户经常说「这次记得别把第 3 段也改了」「上次你把页脚水印也覆盖了」
- 准备写 `template_mapping.json` / `reference_mapping.json` 这类槽位定义
- 已有的填充脚本会误覆盖不该改的内容

**不适用场景**：模板要整体重排版 / 大部分字段都要重写 → 直接用全新模板，不要走染色契约

## 契约定义

| 颜色 | 文档 wd_index | 语义 | 脚本动作 |
|---|---|---|---|
| **红** (`red`) | 6 | 必替换：这块是占位，必须用数据填上 | 写入 |
| **黄** (`yellow`) | 7 | 临时标记：人审过再决定 / 数据缺失暂留 | **跳过 + 告警** |
| **无色** (`none`) | 0 | 不动：流程标准化文本 / 模板原生说明 | 跳过 |

`wd_index` 是 Word COM `Range.HighlightColorIndex` 的枚举值（6=红 / 7=黄 / 0=无色）。**这是 Word 专有的高亮图层 API**，独立于段落底纹、单元格填充等其他颜色属性——这正是它适合做标记的原因（标记色与内容样式不串台）。**不要假设其他 Office 工具有等价语义**（PPT/Excel 的颜色 API 是单元格/字体填充本身，不是独立高亮图层）。

### 为什么要黄色（不是只用红 / 无色）

**关键洞察**：很多模板字段处于"应该填但本次缺数据"的状态。如果只有红 / 无色二态，这种字段没地方放——填红色脚本会写错（没数据），改无色脚本会忽略（实际需要人审）。

黄色专门承载这种"灰色地带"。脚本看到黄色 → 跳过 + 告警 → 触发 ESCALATE（参考 `pipeline-self-check-loop` skill）。

## Schema 样板（来自 fangcaixia/pipeline/docx_mapping.json）

### 顶层 `highlight_contract` 声明

```json
{
  "highlight_contract": {
    "red":    { "wd_index": 6, "semantics": "必替换",           "script_action": "写入" },
    "yellow": { "wd_index": 7, "semantics": "临时标记（待用户确认）", "script_action": "跳过 + 告警" },
    "none":   { "wd_index": 0, "semantics": "不动",             "script_action": "跳过" }
  }
}
```

每份 mapping JSON 顶部必带这个声明，让 AI / 人审一眼知道这份契约的语义。

### 槽位级 `highlight` 字段

```json
{
  "id": "docx_t3_progress",
  "strategy": "red_cell_driven",
  "gate": "highlight",
  "locator": { "table": 3, "rows": [2, 3, 4, 5, 6, 7] },
  "cells": [
    { "col": 1, "highlight": "none", "action": "skip",  "maps": "序号（流程标准化）" },
    { "col": 2, "highlight": "none", "action": "skip",  "maps": "工作内容（流程标准化文本）" },
    { "col": 3, "highlight": "red",  "action": "write", "field": "schedule[].date" },
    { "col": 4, "highlight": "red",  "action": "write", "field": "schedule[].owner" },
    { "col": 6, "highlight": "red_partial", "rows_red": [4, 5], "action": "write",
      "field": "SCHEDULE_SUMMARY_RULES" }
  ]
}
```

**关键设计**：
- `gate: "highlight"` —— 这个槽位用染色驱动（vs `gate: "placeholder"` 用 `{{token}}`）
- `cells[].highlight` —— 单元格级颜色声明，让 AI / 人审能逐 cell 核对
- `red_partial` —— 同列里部分行红、部分行无色（避免一刀切）

## 双闸门并存

染色契约**不是**唯一定位方式。**应该和占位符（`{{token}}`）双闸门并存**：

```json
{
  "_highlight_note": "封面 single_value 占位符的 value 段在模板里【同时染红色 hl=6】——
                      双闸门并存：占位符闸 + 染色闸不可删其一。
                      脚本对占位符靠 token 字面做 Find/Replace 定位，
                      染色在此服务于人审 + realign 排版。"
}
```

**Why**：
- 占位符（`{{project.name}}`）适合**程序定位**——精确、机械
- 染色适合**人审**——一眼能看出哪里要改 / 哪里别动

二者并存能各自校验对方：占位符没填上 → 脚本报错；染色少染了 → 人审报错。

## 实现要点

### 1. 染色检测代码（Word）

```python
import win32com.client

word = win32com.client.DispatchEx("Word.Application")
doc = word.Documents.Open(path, ReadOnly=True)

for table in doc.Tables:
    for row_idx in range(1, table.Rows.Count + 1):
        for col_idx in range(1, table.Columns.Count + 1):
            cell = table.Cell(row_idx, col_idx)
            try:
                hl_index = cell.Range.HighlightColorIndex
            except Exception:
                hl_index = 0
            if hl_index == 6:    # 红
                # 走 write 路径
                pass
            elif hl_index == 7:  # 黄
                # 跳过 + 告警
                print(f"[WARN] 黄色待审单元格：表 {t}.{row_idx}.{col_idx}")
```

### 2. 自检环节必跑「黄色残留扫描」

参考 `pipeline-self-check-loop` skill 的 Self-check：

```python
def check_no_yellow_left(output_doc) -> list[dict]:
    """交付前必跑：所有黄色单元格应在 build 时被替换为红/无色。"""
    issues = []
    # ... 遍历所有 cell + paragraph + shape
    for cell in iter_yellow_cells(output_doc):
        issues.append({
            "severity": "严重",
            "dim": "染色契约",
            "desc": f"黄色未消除：{cell.location}",
            "status": "未修复",
        })
    return issues
```

**Why**：黄色残留 = 还有数据没人审 / 还有字段没填，不应该交付。

### 3. 不要让 AI 自己**新增**染色

染色只能**用户在模板里手工染**。AI 在 build 阶段：
- 看到红 → 写数据（红保留 or 改为无色）
- 看到黄 → 跳过 + 告警
- 看到无色 → 不动

**不要**让 AI 自己决定「这里应该是红色，我帮你染上」——破坏契约的可信度。

## 为什么本契约不外推到 PPT / Excel

> 历史版本曾列「跨工具一致性表」声称 Word/PPT/Excel 共用染色契约——**那是过度泛化，已撤销**。本契约只服务 Word，理由如下：

- **Word（适用）**：`HighlightColorIndex` 是**独立高亮图层**，与段落/单元格底纹分属不同属性位，染色当标记不会和内容样式串台；且 Word 文本流缺稳定锚点，染色是唯一「机器可读 + 人可读」的标记途径。**这是染色契约的最佳土壤。**
- **PPT（不适用）**：shape 有稳定 COM 内部名，定位靠名字即可，不需要染色当锚点。PPT 里颜色的事是 `ppt-acceptance-check` L3 的**验收**职责（断言 run 颜色是否符合预期），与本「填充标记契约」不是一回事——别把两者混为一个跨工具契约。
- **Excel（不适用，已另立 skill）**：`Range.Interior.Color` 就是单元格底纹**本身**，和业务表的表头色/斑马纹/警示红是**同一物理属性位**，照搬纯红纯黄会把业务底色误判成标记 → 假阳性。Excel 的标记方式已落地为独立姊妹 skill **`three-state-coloring-contract-excel-only`**：用**「底纹 Interior.Color + 字色 Font.Color」双通道组合**作唯一识别标准（两个特殊色同时命中才算标记，绕开底纹位撞业务色），精确 RGB 判定禁用 ColorIndex，半标记强制纠错。不并入本契约。

> 一句话：染色契约的可行性取决于「标记色是否与内容样式物理分离」。只有 Word 的高亮图层满足，所以只有 Word 适用。

## 不要做

- ❌ 不要把"必替换"和"待确认"混用一种颜色——会破坏 ESCALATE 触发逻辑
- ❌ 不要省略 `highlight_contract` 顶层声明——下游 AI / 人审会猜错语义
- ❌ 不要让脚本**自动把黄改成红**——黄→红 必须经过人审决策
- ❌ 不要在 build 完成后**保留任何黄色**——黄色残留 = 自检不通过
- ❌ 不要单用染色契约不带占位符——双闸门并存的容错性远高于单闸门
