---
name: excel-acceptance-check
description: Excel 自动化产线交付前的分层验收 skill —— L0 结构（sheet 存在 / 维度下限 / 必有列名）+ L1 数据（cell/列值 vs 外部真相）+ L3 空值（必填区无漏填残留）+ 三态 severity（must_fix / warn / tolerate）+ 一份 PASS/FAIL 报告。任何"AI/脚本自动生成或填充 xlsx → 交付前"都该跑一遍，避免"看着填了实则是模板默认值 / 必填格漏填 / 关键字段与规格表对不上"这类暗坑。项目规则写进 acceptance_contract.json，skill 是引擎。ppt-acceptance-check 的 Excel 姊妹版；与 inspect-excel-template `--blanks` 配套（那是体检盘点，这是红线断言）。
---

# excel-acceptance-check

**Excel 产线交付前的"红线验收"引擎**。把"这个 xlsx 到底填对没填对"从人肉逐格核对，变成一份 PASS/FAIL 报告 + 必修清单。是 `ppt-acceptance-check` 的 Excel 姊妹版——`contract.py` / `common.py`(Finding·LayerResult) 是其零改动副本，`report.py` 为 Excel 化改写，层逻辑按 Excel 重写。

## 何时使用

- AI / 脚本自动**填充 Excel 模板**（工艺单 / 报表 / 台账）后，交付前要确认"该填的填了、填对了"
- 担心"视觉看着对、值其实是模板默认值 / 没被写进去"
- 要断言"某些必填格不能空"（漏填 = 退回）
- 要断言"关键字段（型号 / 大底 / 楦型…）与规格表 / 评审表登记的一致"（跨文件一致性）

**与 `inspect-excel-template --blanks` 的分工**：`--blanks` 是**体检**（全量盘点哪些格空着，给人看比例反推风险）；本 skill 是**红线断言**（契约声明的必填区里有空 = must_fix FAIL）。先用 `--blanks` 摸清形态、定必填区，再用本 skill 写进契约做关卡。

## 三护栏（不可违反，写进设计）

1. **期望值只来自外部真相**：L1 业务期望走 `expected_from` 的 `excel_cell:` / `excel:` DSL 从外部 xlsx（规格表/评审表）取，**禁在契约或脚本里 hardcode 工艺单具体业务值**。结构性断言（L0：sheet 名 / 维度 / 列名）豁免，可 inline。
2. **auto-fix 不在脚本里**：脚本**只断言不改文件**。修复留给主 Claude 编排；**同一问题连改 2 轮没好 → ESCALATE 给人**，不在脚本里无限自动改。
3. **编排权留主 Claude**：脚本 ReadOnly 打开 xlsx、不写回、不读写契约。

## 调用方式

```powershell
python "C:\Users\<USER>\.claude\skills\excel-acceptance-check\excel_acceptance_check.py" `
    --xlsx "待验收.xlsx" `
    --contract "acceptance\rd48.json" `
    --layers L0,L1,L3 `
    --mode production `
    --out-dir "out\"

# 桥接当前打开的 Excel（避开文件锁）
python ".../excel_acceptance_check.py" --active --xlsx "待验收.xlsx" --contract c.json
```

参数：`--xlsx`(待验收) / `--active`(桥接运行中 Excel) / `--contract` / `--layers`(默认 `L0,L1`，L3 显式开) / `--mode`(production|smoke) / `--out-dir`。

**Exit code**：`0`=PASS（无必修违反）/ `1`=FAIL（有必修违反）/ `2`=配置错·文件不存在·COM 失败。

**COM 生存反射**：DispatchEx 起隔离进程 + ReadOnly 打开 + finally Close/Quit 兜底。脚本**不内嵌 wall-clock 超时**——单次运行须由**调用方套 20-30s 硬超时；连挂 2 次 CUTOVER**（参见 `com-survival-reflexes`），同 `inspect-excel-template` 约定。

## 契约（acceptance_contract.json）

完整示例见 `examples/excel_acceptance_contract.example.json`。骨架：

```jsonc
{
  "version": 1,
  "data_sources": { "excel": "<绝对路径>/评审表.xlsx" },  // excel_cell:/excel: DSL 的外部真相源
  "structure": { "header_row": 1 },                       // 表头行号(列名解析用)
  "rules": [ { "id", "layer", "check", ...锚点..., "expected"/"expected_from", "severity" } ],
  "modes": { "smoke": {"rule_overrides": {"<rule_id>": "tolerate"}}, "production": {} }
}
```

**锚点优先级（硬约束）**：`name`(NamedRange) > `sheet`+列名 / `sheet`+`cell`(A1) > 行列数字(`Cells(r,c)` 裸数字**禁**出现在业务逻辑)。**Excel 不禁 A1**（A1 是原生稳定锚点）。

**三态 severity**：`must_fix`(必修，计入 exit 1) / `warn`(记录不阻断) / `tolerate`(豁免)。`modes.<mode>.rule_overrides` 可按模式改写某规则的 severity（如 smoke 把某规则降 tolerate）。

## 三层 check 速查

### L0 结构（`layers/structure.py`）—— 结构性断言，豁免护栏①

| check | 锚点字段 | 断言 |
|---|---|---|
| `sheet_exists` | `sheet`(精确或模糊子串) | sheet 能解析到 |
| `dimensions_min` | `sheet` + `expected:{rows,cols}` | UsedRange 维度 >= 下限 |
| `has_columns` | `sheet` + `expected:["列名",...]` | header_row 行含全部列名（子串匹配） |
| `named_range_exists` | `name` | 定义名存在 |

### L1 数据（`layers/data.py`）—— 期望走外部真相（护栏①）

| check | 锚点 | 断言 |
|---|---|---|
| `cell_equals` | `name` / `sheet`+`cell` | 单格值 == expected（trim 后） |
| `cell_contains` | `name` / `sheet`+`cell` | 单格值含 expected 子串 |
| `column_agg_equals` | `sheet`+`column`+`agg` | 列聚合值 == expected |

**`expected_from` DSL**（取外部真相）：
- `excel_cell:<sheet_kw>:<A1>` —— 取外部 xlsx 单格值（**推荐**，单值真相最常用）。
- `excel:<sheet_kw>:<col_or_cols>:<agg>` —— 列聚合：`mode`/`sum`/`mean`/`count_contains=<子串>`/`list`/`range`。
- `hardcoded:<json>` —— 仅限测试/结构性，业务值勿用。
- 直接 `expected: <值>`（inline）—— 仅限结构性期望，业务值勿用（护栏①）。

> `column`/`cell` 既接列字母（'C'）/A1（'H4'），`column` 也接表头列名（按 `structure.header_row` 解析）。

### L3 空值（`layers/blanks.py`）—— 必填区无漏填残留

| check | 必填区声明（锚点优先级 name>range>cells） | 断言 |
|---|---|---|
| `no_blank_in_required` | `name` / `range`('A4:E9') / `cells`(['C4','H4']) | 区内出现空格 = 漏填（默认 must_fix） |

**非必填区的空不报**。判空语义同 `inspect-excel --blanks`（None/""/纯空白/`\x07` 算空）+ 合并格读主格（防成员格假空）。必填区应**小而显式**（超 5000 格兜底跳过并降级提示）。

## 报告

`acceptance_report.md`（人看）+ `acceptance_report.json`（程序消费）。结构：结论 PASS/FAIL → 摘要表（每层 通过/警告/容忍/必修违反/降级）→ 必修违反清单（先看这里）→ 警告 / 容忍清单 → 详细清单（含通过项，便于审计）。定位串用 `sheet!cell` / `sheet!col:X` / `name:X` 形式。

## 跟其他 skill 的关系

- **`inspect-excel-template --blanks`**：先盘点（体检），再据此写本 skill 的 L3 必填区契约（红线）。
- **`ppt-acceptance-check`**：姊妹引擎。`contract.py` / `common.py`(Finding·LayerResult) 是从它**零改动复制**来的（文件头有 `# COPIED FROM ... @日期` 同步标记，改这些数据结构要两处同步）；`report.py` 是 Excel 化改写。
- **`office-com-helpers`**：COM 读取（`com_get`/`safe_text`/`load_excel_rows`）全复用，未自撸。
- **`three-state-coloring-contract-word-only`**：那是 **Word** 染色驱动契约，与本 skill 的"空值驱动"是两条独立路线，**互不混用**（Excel 不读 Interior.Color）。

## limitation

- **第一版只认"物理空格 = 漏填"**：若必填格预填了参考默认值（看着填了实则待确认），数空格会漏判。后续可引 `-`/`TODO` 占位符约定把"待确认"也标成可识别态（同 `inspect-excel --blanks` 的 D2 指路版 limitation）。
- `excel_cell:` 假设外部 sheet 的 UsedRange 自 A1 起（本 repo 评审/规格表均如此）；不从 A1 起会偏移。
- 验收**只读不改**：发现问题不自动修（护栏②③），修复与复跑由主 Claude 编排。
