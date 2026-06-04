---
name: inspect-word-template
description: 任何需要 AI 理解 .docx / .doc 内部结构的场景（模板填充、染色契约自检前的基线、占位符审计、表格槽位定位、改已有 docx 填充脚本）**开工前必须先跑**。用 win32com 探测 tables（含 HighlightColorIndex 三态分桶 / 合并单元格安全遍历）/ paragraphs / headers / footers / story_ranges / {{占位符}}，输出 inspect_word_report.json + .md，把 AI 对 docx 的感知盲区一次性堵掉。支持 `--tables "1,3-5"` 过滤 + `--active` 桥接当前打开的 Word。`inspect-ppt-template` / `inspect-excel-template` 的 docx 姊妹版（三者命名规则统一、职责单一）。
---

# inspect-word-template

**任何需要 AI 理解 .docx 结构的场景的强制前置步骤**。AI 看不到隐藏段落、表格里哪些 cell 染了红/黄/无色、占位符 `{{...}}` 残留在哪 —— 只看 docx = 在猜模板。这个 skill 是被迫造的"探针"，专为 docx 设计：**染色三态分桶 + 占位符审计 + headers 扫描 + 合并单元格安全遍历**，这些是 feature02 染色契约项目踩了 24 条违规的血泪经验沉淀。pptx 走 `inspect-ppt-template`、xlsx 走 `inspect-excel-template`。

## 何时使用（强制触发，命中任一就跑）

**模板填充类**：
- 用户给了一个新 docx 模板，要求 AI 写填充脚本 / 自动化生产线
- 用户说「这个模板长这样：……」但只提供了截图 / 截屏 / 文字描述
- 准备改一个已有的 docx 填充脚本，但模板可能变过（哪怕只是用户手改了一行）
- 准备写 `docx_mapping.json` / `template_mapping.py` / `slot_decisions.json` 这类槽位定义

**染色契约 / 双闸门审计类**（feature02 类项目的命脉，**不跑必翻车**）：
- 模板用了三态染色契约（🔴 红=必替换 / 🟡 黄=待确认 / ⬜ 无色=不动，CLAUDE.md §3）—— 必须先 inspect 才知道哪些 cell 是哪种色
- 准备写 / 改 docx 染色驱动的填充逻辑（`_set_cell_if_red` 闸） —— 必须知道红 cell 在哪些 (table, row, col)
- 准备做 docx 三态自检（`verify_docx_highlight_consistency.py`） —— 模板基线必须先 inspect
- 模板里有 `{{占位符}}` 双闸门 —— 必须先扫描占位符清单 + 染色清单，对照看哪些 token 落在哪个 cell

**结构反查 / 参考样本对比类**：
- 用户问"这个 docx 第 N 个表是哪个 / 第 X 行第 Y 列是啥 / 页眉页脚有没有水印"
- 准备对**当前正在用 Word 打开**的 docx 做结构分析（用 `--active`，见下）
- 想知道模板里某个段落的 style name（中文 style 名跨版本漂移很常见）

**反模式**（这些都是 Claude 历史上错误降级跳过 skill 的借口，**全部不成立**）：
- ❌ "用 python-docx 读一下就行" → 错。python-docx 读不了 Ldterm/IRM 加密的 docx；本 skill 走 COM 对加密透明
- ❌ "用 inspect-ppt-template 顺手扫一下 docx" → 错。inspect-ppt-template 只管 .pptx，不处理 docx。docx 唯一路径是本 skill（含合并单元格安全遍历 / HighlightColorIndex 三态分桶 / headers 扫描 / 占位符审计）
- ❌ "我只想看表格、不需要染色" → 错。表格 cell 的染色就是身份闸门，不读 highlight 等于把闸门糊住
- ❌ "Word 正在被用户打开，会冲突" → 错。用 `--active` 模式直接桥接到运行中的 Word，无文件锁
- ❌ "我只想看一两个表" → 错。用 `--tables "1,3"` 收窄即可

**不跑这个 skill 直接开干 = 在猜 docx**。feature02 plan05 §2 痛苦实录：**2026-05-13 一次违反三态契约 → 误染 6 段、半天工作打水漂**。先跑探针的 30 秒比后面调试的几小时便宜。

## 调用方式

### 文件模式（默认，新进程 ReadOnly 打开）

```powershell
python "C:\Users\<USER>\.claude\skills\inspect-word-template\inspect_word_template.py" `
    --docx "path\to\template.docx" `
    --out-dir "path\to\output\"
```

### 实时模式（桥接当前打开的 Word，避开文件锁冲突）

```powershell
# 扫 ActiveDocument（前台 Word 窗口）
python ".../inspect_word_template.py" --active --out-dir "out\"

# 多个 docx 同时打开时，用 --docx 精确定位
python ".../inspect_word_template.py" --active --docx "x.docx" --out-dir "out\"
```

`--active` 用 `GetActiveObject` 复用用户进程，**不会 Quit / 不会改文件**，专门解决"docx 正在被编辑、不能用文件模式 Open"的场景。底层桥接同 `inspect-ppt-template` / `inspect-excel-template` 的 `--active` 模式。

### 表格过滤（避免大文档全扫噪音 / 用于对比特定表）

```powershell
# 只扫指定 table（按 doc.Tables(N) 的索引）
python ".../inspect_word_template.py" --docx "x.docx" --tables "1,3-5" --out-dir "out\"
python ".../inspect_word_template.py" --active --tables "1-3" --out-dir "out\"
```

`--tables` 语法：`"1"` / `"1,3,5"` / `"1-3"` / `"1-3,5,7-9"`。仅作用于表格部分（paragraphs / story_ranges / placeholders 全扫）。

### 全段落转储（默认采样前 200 段，调大看更全的段落）

```powershell
# 默认采样前 200 段（已剔空段）；--all-paragraphs 转全部
python ".../inspect_word_template.py" --docx "x.docx" --all-paragraphs --out-dir "out\"
```

### 参数总览

- `--docx` / `--active` 至少给一个
- `--active` 桥接到运行中的 Word，省 `--docx` 时取 ActiveDocument
- `--tables "a,b-c,..."` 仅扫指定表
- `--all-paragraphs` 不限 200 段采样上限（慎用，大文档会很长）
- `--out-dir` 自动 mkdir。本机若被 Ldterm 加密，**输出目录避开被监控的盘符**（参考 `ldterm-decrypt-images` skill）

输出：
- `inspect_word_report.json` —— 结构化数据，给后续编 mapping / 染色自检的程序消费
- `inspect_word_report.md` —— 人类可读版本，AI 直接读这个写填充逻辑

## 输出内容（关键字段）

### 顶层摘要

| 字段 | 用途 |
|---|---|
| `path` | docx 绝对路径（FullName） |
| `mode` | `active` / `open` |
| `tables_filter` | 当前扫了哪几个表（null=全扫） |
| `summary.highlight` | 三态分桶总计：`{red, yellow, uncolored, other_color}` cell 数 |
| `summary.placeholders_unique` | 不重复占位符数（如 `{{project.name}}` 出现 5 次只算 1） |
| `summary.placeholders_total_occurrences` | 总出现次数（用作"删一处漏一处"诊断） |

### Tables（**染色三态契约的核心信号**）

| 字段 | 用途 |
|---|---|
| `tables[].index` | `doc.Tables(N)` 的 N |
| `tables[].rows × cols` | 表维度 |
| `tables[].cells[]` | 每个 cell 的 `(row, col)` / `highlight_index` / `highlight_label`（red/yellow/uncolored/other_N）/ `text_preview` |
| `tables[].highlight_summary` | 该表 red / yellow / uncolored / other_color 各几个 cell |
| `tables[].placeholders_in_table` | 该表内出现的 `{{...}}` token 集合 |

**遍历用 `tbl.Range.Cells`**（不是 `tbl.Cell(r, c)`），自动跨合并单元格 + 自带 `RowIndex/ColumnIndex` —— 合并单元格只出现一次，不会重复也不会抛。

### Paragraphs

| 字段 | 用途 |
|---|---|
| `paragraphs_total` | 总段数 |
| `paragraphs_sample[]` | 默认前 200 段（已剔空段）的 index / style / text 预览 |

**禁止用 paragraph 的 `start/end` 数字定位**（用户改排版会漂移，feature02 plan05 反复确认）—— 探针只暴露 index + style + text 让 AI 用 Find/Replace 语义锚点。

### Headers / Footers（页眉页脚 + 水印）

| 字段 | 用途 |
|---|---|
| `sections[].headers[]` | 每个 section 的三类 header（primary / first_page / even_pages） |
| `sections[].footers[]` | 同上三类 footer。**页脚三联水印通常在这** |

每条记录：`header_index` / `exists` / `text_preview`。

### StoryRanges

| 字段 | 用途 |
|---|---|
| `story_ranges[]` | story_index / story_type / text_preview。**漏处理 story = 模板填充最常见坑**（如 `{{project.name}}` 在页脚未被替换） |

### Placeholders（**双闸门契约的核心信号**）

| 字段 | 用途 |
|---|---|
| `placeholders_unique[]` | 模板里出现的所有 `{{...}}` token（去重排序）—— 用作 mapping json 的字段清单基线 |
| `placeholders_by_location[]` | 每个 token 出现在哪：`tables[(t,r,c)]` / `paragraphs[idx]` / `story[type]` —— 双闸门审计：占位符身份 + 落点交叉表 |

## 跟其他 skill 的关系

- 跑完 `inspect-word-template` 出报告后，对比模板 → 输出做自检，用 `verify_docx_highlight_consistency.py`（项目级脚本，feature02 plan05 #1b 沉淀）
- **染色契约不熟时**：先读 `three-state-coloring-contract-word-only` skill（CLAUDE.md §3 的语义层）+ `skills/docx-highlight-contract.md`（COM 检测片段 + 反例 stack trace）
- 加密文件场景：Ldterm 对 win32com 启动的 WINWORD.EXE 透明（白名单），所以**本 skill 能直接处理 Ldterm 加密的 docx**。若被 IRM/DLP 加密，先解密再跑
- 想知道某个 shape / inlineshape 的字体颜色 / 图片裁剪 → 配合 `read-selected-shape`（PowerPoint 专属，docx 暂无对应 skill；shape 详情留给 `read_selected_shape.py` 项目脚本）
- 写 win32com 代码前先看 `office-com-helpers` 的 `com_get / safe_print` 等共享 helper —— 本 skill 内部也走 sibling skill 注入 sys.path 复用

## 设计原则（看一眼避免误用）

1. **文件模式**：`ReadOnly=True` + `DispatchEx` 新进程，`finally` 里 Quit()，**永不改文件**。Word.Documents.Open **必须绝对路径**（相对路径按 Word 默认目录 C:\Windows 解析，非 cwd）
2. **实时模式（--active）**：`GetActiveObject` 复用用户进程，`opened_by_us=False`，**绝不 Close / 绝不 Quit**（动用户进程 = 用户当场炸 Word）
3. **try/except 读 COM 属性**，不用 `getattr`（COM 对象 getattr 也会抛错，参考 `office-com-helpers` skill）
4. **表格用 `tbl.Range.Cells` 遍历**，不用 `tbl.Cell(r, c)` 双层循环 —— 合并单元格在硬索引上会抛（feature02 T1 含合并单元格的实战教训）
5. **文本截断**：cell 80 字符 / paragraph 120 字符 / header/footer 100 字符 —— 探针不应该把全文倾倒出来；要全文用 `read_selected_shape.py` 或自己另开脚本
6. **paragraph 默认采样 200 段** —— 长合同 / 长报告全转储会让 .md 没法读。要全部用 `--all-paragraphs`
7. **highlight_index 严格按 Word COM 枚举**：6=red, 7=yellow, 0=none, 其它按 "other_color" 桶。**不要自创"灰色"等中间态** —— 三态契约就是三态
8. **占位符正则严格用 `\{\{[^{}]+\}\}`**（非贪婪、不嵌套）—— 跟 feature02 `verify_docx_highlight_consistency.py` 保持一致，否则双闸门审计会两边对不上

## 不要做

- ❌ 不要在文件模式下扫**正在被用户打开编辑**的 docx —— 会冲突；**改用 `--active`** 桥接
- ❌ 实时模式下不要试图调 `Quit() / Close()` —— 代码已经守住，但人为加回去就炸用户进程
- ❌ 不要跑完探针就开始猜 cell 颜色 —— **必须通读 `inspect_word_report.md`** 后再开始写染色逻辑 / mapping
- ❌ 不要因为"只想看几个表"就跳过 skill —— `--tables "1,3"` 就是解药，30 秒省后面几小时
- ❌ 不要因为"用 python-docx 也能读到字段"就跳过 skill —— python-docx 读不了 Ldterm/IRM 加密；本 skill COM 路径透明
- ❌ 不要把 `tbl.Cell(r, c)` 双层 for 循环搬到自己脚本里 —— 合并单元格直接炸；用 `tbl.Range.Cells` 一层遍历（自带 RowIndex/ColumnIndex）
- ❌ 不要在 docx 模板里依赖 paragraph 的 start/end 数字坐标做 Find/Replace —— 用户改排版会漂移；用 Find 语义锚点（`feedback_word_com_recolor_pitfalls`）
- ❌ 不要把"无色 cell"主动补染红 —— 用户没标的不要主动改，violation 最高 severity（CLAUDE.md §3 最高优先级原则）
