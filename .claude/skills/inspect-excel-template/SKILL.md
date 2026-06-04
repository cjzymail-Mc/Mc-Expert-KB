---
name: inspect-excel-template
description: 任何需要 AI 理解 .xlsx / .xls 内部结构的场景（数据源调研、模板填充、列名定位、问卷字段映射、改已有 load_excel_rows 调用）**开工前必须先跑**。用 win32com 探测每个 sheet 的 name / used_range / 表头列名清单 / 行数 / 前 N 行预览，输出 inspect_excel_report.json + .md，把 AI 对 Excel 的感知盲区一次性堵掉。支持 `--sheets "问卷,跑量"` 关键词模糊筛 + `--active` 桥接当前打开的 Excel，避开文件锁 + `--blanks` 空值（待填）单元格薄层（合并格按主格只记一次，不虚高）。inspect-ppt-template / inspect-word-template 的 Excel 姊妹版。
---

# inspect-excel-template

**任何需要 AI 理解 .xlsx 结构的场景的强制前置步骤**。AI 看不到 sheet 名 / 列名 / 数据格式，只看 Excel = 在猜数据源。这个 skill 就是被迫造的"探针"，是 `inspect-ppt-template` / `inspect-word-template` 的 Excel 姊妹版（三者命名规则统一、职责单一）。

## 何时使用（强制触发，命中任一就跑）

**数据源调研类**：
- 拿到一个新的 .xlsx 数据源，要决定怎么读（列名是哪些 / 是否有表头 / 数据从第几行开始）
- 写 / 改 `load_excel_rows()` 等 Excel 读取调用前，定位 sheet 名 + 关键字段所在列
- 问卷类 Excel：要定位"哪个 sheet 哪一列是 X 字段"（评分 / 跑量 / 温度 / 训练定位 等）
- 任何包含「源 Excel 字段映射」「数据列定位」「sheet 名模糊匹配选哪个」字样的需求

**模板填充类**：
- 准备写 Excel 报告模板填充脚本，要知道目标模板有几个 sheet / 每 sheet 表头是什么
- 准备改一个已有的 Excel 填充脚本，但模板可能变过

**结构反查 / 实时排错类**：
- 用户问"这个 Excel 的 sheet 叫啥 / 第 N 列是啥 / used_range 多大"
- 准备对**当前正在用 Excel 打开**的 xlsx 做结构分析（用 `--active`，见下）
- 怀疑上一轮跑脚本污染了源 Excel（used_range 比实际数据区大很多） —— 跑探针看 stray cells 警告

**反模式**（这些都是 Claude 错误降级跳过 skill 的借口，**全部不成立**）：
- ❌ "我用 openpyxl / pandas 读一下就知道列名了" → 错。openpyxl 读不了 Ldterm / IRM 加密文件，pandas 同理；本 skill 走 COM 路径，对加密文件透明
- ❌ "我直接调 `load_excel_rows` 试一下就行" → 错。`load_excel_rows` 是个读取函数，失败信息不够诊断；探针先扫一次再决定读哪个 sheet / 哪一列效率高得多
- ❌ "Excel 正在被用户打开，会冲突" → 错。用 `--active` 模式直接桥接到运行中的 Excel，无文件锁
- ❌ "Excel 太大全扫多余" → 错。用 `--sheets "问卷,跑量"` 关键词模糊筛即可
- ❌ "用户只是要看几个字段，不是模板填充" → 错。description 已显式覆盖数据源调研 / 列名定位

**不跑这个 skill 直接开干 = 在猜 Excel**。猜错了之后调试成本远高于先跑探针的 20 秒。

## 调用方式

### 文件模式（默认，新进程 ReadOnly 打开）

```powershell
python "C:\Users\<USER>\.claude\skills\inspect-excel-template\inspect_excel_template.py" `
    --xlsx "path\to\source.xlsx" `
    --out-dir "path\to\output\"
```

### 实时模式（桥接当前打开的 Excel，避开文件锁冲突）

```powershell
# 扫 ActiveWorkbook（前台 Excel 窗口）
python ".../inspect_excel_template.py" --active --out-dir "out\"

# 多个 xlsx 同时打开时，用 --xlsx 精确定位
python ".../inspect_excel_template.py" --active --xlsx "x.xlsx" --out-dir "out\"
```

`--active` 用 `GetActiveObject` 复用用户进程，**不会 Quit / 不会改文件**，专门解决"xlsx 正在被编辑、不能用文件模式 Open"的场景。底层桥接同 `inspect-ppt-template` / `inspect-word-template` 的 `--active` 模式。

### sheet 关键词模糊筛（避免大 workbook 全扫噪音）

```powershell
# 只扫含"问卷"或"跑量"的 sheet（OR 语义子串匹配）
python ".../inspect_excel_template.py" --xlsx "x.xlsx" --sheets "问卷,跑量" --out-dir "out\"
python ".../inspect_excel_template.py" --active --sheets "问卷" --out-dir "out\"
```

`--sheets` 语法：`"问卷"` / `"问卷,跑量"` / `"问卷,跑量,数据"`。多关键词 OR 语义，任何 sheet 名含其中一个就保留。

### 自定义预览行数

```powershell
# 默认 5 行；调大看更全的数据格式
python ".../inspect_excel_template.py" --xlsx "x.xlsx" --preview-rows 10 --out-dir "out\"
```

### 空值（待填）单元格薄层（`--blanks`）

```powershell
# 统计每 sheet 的 空 / 已填 / 合并空格，列出空格地址（合并格按主格只记一次）
python ".../inspect_excel_template.py" --xlsx "工艺单.xlsx" --blanks --out-dir "out\"
python ".../inspect_excel_template.py" --active --blanks --out-dir "out\"
```

`--blanks` **默认关；关时输出与历史 100% 一致（向后兼容）**。开启后追加一层"哪些格是空的（待填）"信号——专给"模板部分字段待填"类场景反推填充范围用，也是 `excel-acceptance-check` L3「无空格残留」断言的上游信号源。详见下「空值检测」节。

### 参数总览

- `--xlsx` / `--active` 至少给一个
- `--active` 桥接到运行中的 Excel，省 `--xlsx` 时取 ActiveWorkbook
- `--sheets "a,b,..."` 关键词模糊筛，OR 语义子串匹配
- `--preview-rows N` 每 sheet 数据预览行数（默认 5，不含表头）
- `--blanks` 追加空值（待填）单元格薄层（默认关；不读 Interior.Color）
- `--out-dir` 自动 mkdir。本机若被 Ldterm 加密，**输出目录避开被监控的盘符**

输出：
- `inspect_excel_report.json` —— 结构化数据，给后续编 mapping / `load_excel_rows` 调用的程序消费
- `inspect_excel_report.md` —— 人类可读版本，AI 直接读这个写读取逻辑

## 输出内容（关键字段）

### Sheet 索引表（开头总表）

| 字段 | 用途 |
|---|---|
| `sheet_index` | `wb.Sheets(N)` 的 N |
| `name` | sheet 真实名（直接 `wb.Sheets('name')` 用） |
| `type_label` | worksheet / chart / other —— 非 worksheet 自动跳过 UsedRange 扫描 |
| `visible_label` | visible / hidden / very_hidden —— 隐藏 sheet 也会被列出，避免漏 |
| `rows × cols` | UsedRange 维度 |
| `used_range` | 如 `$A$1:$Z$200` |

### 每 sheet 详情

| 字段 | 用途 |
|---|---|
| `header_row[]` | 第 1 行列名清单，带 Excel 列字母（A/B/C/AA/AB）—— **写 `_extract_*` 时定位列索引就看这** |
| `preview[]` | 前 N 行原始数据 —— 看格式（"15~25℃" vs 数字 / "671km" vs 671） |
| `stray.stray_count` | **主数据块外的非空单元格数（脏数据残留）** —— 见下"Stray cells 检测" |
| `stray.main_block` | 自动判定的主数据块地址（如 `$A$1:$AJ$10`） |
| `stray.stray_preview[]` | 前 20 个 stray 单元格的 address + value 预览 |
| `blank_summary{blank,filled,merged_blank}` | **仅 `--blanks` 开启时**：空 / 已填 / 合并空格 计数 |
| `blank_cells[]{address,merged}` | **仅 `--blanks`**：空格地址清单（截断 200；`merged=true` 为合并空格主格） |
| `note` | 兜底说明（sheet 为空 / 非 worksheet / UsedRange 读取失败） |

顶层 `summary.blanks{blank,filled,merged_blank}` 为全 sheet 汇总（仅 `--blanks`）。

## Stray cells 检测（脏数据残留警告）

**场景**：跑 pipeline 时脚本往源 Excel 写过临时数据 → 用户后来手动删了数据但 Excel 把 used_range 撑大了 → 下次跑 pipeline 读 `UsedRange.Value` 拿到一堆 `None` 行/列污染处理逻辑。

**判定策略**（保守、可解释）：
- **主块列宽** = 第 1 行从 A1 起连续非空的列数
- **主块行高** = 在主块列宽范围内连续非空行的行数
- **主块** = `$A$1:$<主块列字母>$<主块行号>`
- **Stray cells** = used_range 内但主块外的非空单元格

**典型报告片段**（sheet 索引表自带 stray 列）：

```markdown
| # | name | type | visible | rows × cols | used_range | stray? |
|---|------|------|---------|-------------|-----------|--------|
| 5 | `服装试穿问卷--紧身背心` | worksheet | visible | 100 × 50 | `$A$1:$AX$100` | ⚠️ 23 |
```

**详情区块**：

```markdown
### Sheet 5: `服装试穿问卷--紧身背心`
- used_range: `$A$1:$AX$100`  (100 行 × 50 列)
- 表头 / 预览 ...

**⚠️ Stray 单元格警告**：
- 主数据块：`$A$1:$AJ$10`（10 行 × 36 列）
- used_range：`$A$1:$AX$100`（100 行 × 50 列）
- 主块外非空单元格：**23 个**（极可能是上一轮临时数据残留）
- 预览（前 20 个）：

  | address | value |
  |---------|-------|
  | `AK5`   | 671   |
  | `AL5`   | 5~15  |
  | ...     | ...   |

  > **建议**：跑 pipeline 前清掉这些单元格...
```

**limitation**：判定策略对"表头无空白列、数据从第 1 行起连续"的标准问卷格式 100% 准确。如果模板第 1 行表头中有空白列，主块列宽会判得偏小，可能产生误报——此时 stray_preview 看 address 即可分辨真假残留。

## 空值（待填）单元格检测（`--blanks`）

**场景**：同一 Excel 模板复用、部分字段待填——想知道"哪些格还空着（待填）""空格占比多大"，用作填充范围反推或交付前「无漏填」断言的信号源。

**判定**：复用 `_is_blank`（None / "" / 纯空白 / `\x07` 均算空），**不读 Interior.Color**（路线"空值驱动"）。Excel 标记有两条**并列可选**路线，按项目选用：本探针的「空值驱动」(物理空格=待填) vs 独立 skill **`three-state-coloring-contract-excel-only`** 的「染色驱动」(底纹+字色双通道)。本探针**故意不读色**——`Interior.Color`/`Font.Color` 没有 bulk 数组属性、逐格读会破坏这里"1 次 bulk `.Value`"的性能模型并触发 COM storm；所以**逐格读色的实现放那个契约 skill / 各项目脚本里，不塞回本探针**。

**合并格处理（关键，防虚高）**：Excel 合并区只有主格（左上）在 `UsedRange.Value` 里有值，成员格返回 `None`——纯 bulk 判空会把填充的合并区成员误判为空。本薄层对每个"候选空格"探一次 `MergeCells`：合并区按主格只记一次，成员格跳过。所以 `blank + filled` 通常 **小于** `rows × cols`（差额 = 被去重的合并成员格），这是**正常**的，不是漏数。

**典型报告片段**：

```markdown
- 空值扫描（--blanks）：空 **255** / 已填 767（空格占比 25.0%；其中合并空格 58）
...
**空值（待填）单元格**：
- 空 **255** / 已填 767（空格占比 25.0%；合并空格 58，按主格只记一次）
- 空格地址（前 200 个）：`B2`, `C2`, ..., `P11`(merged), `P12`(merged), ...
  > ⚠️ 清单已截断至 200 个，总数见上方计数。
```

**性能护栏**：blank 判定走 bulk（1 次 COM），仅候选空格探 merge；总格数超 `cell_cap`（20000）时退化为纯 bulk 判空（不探 merge，加 note 标风险），避免大表 COM storm。

**limitation（指路版，第一版不解决）**：本薄层只认"物理空格 = 待填"。若工艺单**大量必填格预填了参考默认值**（看着填了实则待人确认），单纯数空格会漏判这些"伪填充必填格"。第一版不处理；若遇到此形态，再引入 `-` / `TODO` 占位符约定（`mc-debug/mc-debug02` L426 已留方案）把"待确认"也标成可识别状态。跑样本时**顺手看"空格 vs 预填格比例"**反推风险——如 RD48 BOM 实测 25% 空 / 75% 填，是已填实例（非空模板），此风险不立即触发。

## 跟其他 skill 的关系

- 跑完 `inspect-excel-template` 出报告后，用 `office-com-helpers` 的 `load_excel_rows(excel_path, sheet_name, fuzzy_keyword)` 实际读数据
- 跟 `inspect-ppt-template` / `inspect-word-template` 的关系：**三个姊妹 skill 各管一类格式**，本 skill 扫 .xlsx，sibling 扫 .pptx / .docx。Excel 单独拆出来是因为 sheet / used_range / 表头列名这些概念与 Word/PPT 完全不同
- 加密文件场景：Ldterm 对 win32com 启动的 EXCEL.EXE 透明（白名单），所以**本 skill 能直接处理 Ldterm 加密的 xlsx**。若被 IRM/DLP 加密，先解密再跑

## 设计原则（看一眼避免误用）

1. **文件模式**：`ReadOnly=True` + `DispatchEx` 新进程，`finally` 里 Quit()，**永不改文件**
2. **实时模式（--active）**：`GetActiveObject` 复用用户进程，`opened_by_us=False`，**绝不 Close / 绝不 Quit**（动用户进程 = 用户当场炸 Excel）
3. **复用 `office-com-helpers`**：sibling skill 路径自动注入 sys.path，统一用 `com_get / safe_print / to_rows / safe_text`，不自己重复手撸
4. **预览行数 clamp**：默认 5 行 + 单元格 60 字符截断 —— 探针输出不应该把全部数据倾倒出来；要全量数据用 `load_excel_rows` 拉
5. **--sheets 模糊筛** —— 多 sheet 大 workbook 全扫输出 noise 多，明确知道要看哪几个就用关键词筛
6. **隐藏 sheet 仍列出** —— 避免漏数据源（隐藏 sheet 经常是"原始数据"，明面 sheet 是"汇总"）
7. **非 worksheet 跳过 UsedRange** —— chart sheet / macro sheet / dialog sheet 没有有意义的 UsedRange，标记类型后跳过

## 不要做

- ❌ 不要在文件模式下扫**正在被用户打开编辑**的 xlsx —— 会冲突；**改用 `--active`** 桥接
- ❌ 实时模式下不要试图调 `Quit() / Close()` —— 代码已经守住，但人为加回去就炸用户进程
- ❌ 不要跑完探针就直接开始猜列名 —— 必须**通读 inspect_excel_report.md** 后再开始写 `load_excel_rows` 调用 / 字段映射
- ❌ 不要因为"只想看一个 sheet"就跳过 skill —— `--sheets "name"` 就是解药，20 秒省后面几小时
- ❌ 不要因为"用户给的不是模板是数据源"就跳过 skill —— description 已明确覆盖数据源调研 / 列名定位
- ❌ 不要把 `--sheets` 当成精确匹配 —— 它是子串模糊匹配，OR 语义。要精确名直接读报告里的 `name` 字段
