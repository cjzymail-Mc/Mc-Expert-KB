---
name: ppt-acceptance-check
description: 完整的 PPT 验收 skill —— 6 层验收（L0 配对 / L1 数据 / L2 格式 / L3 染色 / L4 行为 / L5 视觉）+ 三态 severity（must_fix / warn / tolerate）+ 一份 PASS/FAIL 报告。任何 PPT 自动化生产线在交付前都该跑一遍，避免「视觉看着对、数据是模板默认值」「GPT 没调走了 fallback」「Chart Activate 失败但代码继续走」这类暗坑。项目规则写进 acceptance_contract.json，skill 是引擎。吸收并取代 ppt-visual-fidelity-check。
---

# ppt-acceptance-check

PPT 自动化的「整体验收」——不光看视觉，把数据 / 格式 / 染色 / 行为也一起断言，最后给一个 PASS/FAIL。

> 设计原则：**断言不修复**、**配对鲁棒性是地基**、**项目契约外置**、**一份报告一次决策**。
> 详见 `plan-2026-05-27-acceptance-skill.md`。

## 何时使用（命中任一就跑）

- PPT 自动化 pipeline（模板填充 / 数据拼装 / 跨页移植）跑出一份新 PPT，想在交付前**断言**它该长成的样子
- 用户问「这一版和模板差在哪」「哪些 shape 漏填了」「数据是不是又走了 fallback」
- 想验证 GPT 调用 / COM 失败兜底有没有静默漏掉（典型："chart Activate 失败但代码继续走、用了模板默认值"——视觉看不出来，**只能从 pipeline trace 捞**）
- pipeline 重做 / 模板换代后想一键回归

**反模式**（容易被错误降级跳过 — 全部不成立）：
- ❌ "我有 ppt-visual-fidelity-check 就够了" → 错。SSIM 只看像素，**chart 数据是模板默认值（看上去正常）/ GPT 没调（fallback 文本和模板默认很像）这类问题 SSIM 给高分**
- ❌ "改下 diff_shape_detail.py 就行" → 错。它只覆盖 L2 格式，**L0 配对失败时它的 must_fix 全在错误的 shape 上跑**（昨天 apparel 就是这么漏的）
- ❌ "项目特化太重，每个项目都得写契约" → 错。无契约时全严格 + 默认 fuzzy 配对 + L2 几何兜底；契约只在你想**豁免某些字段 / 接 Excel 期望值**时才必要
- ❌ "smoke test 阶段也跑会刷屏" → 错。`--mode smoke` 自动豁免 GPT / 行为类规则

## 6 层验收覆盖什么

| 层 | 检查的是 | 典型暗坑 |
|---|---|---|
| **L0 配对** | shape 存在性 + 名字一致性 + 仅 A/仅 B 清单 | Clone 自动改名漏检（Chart 63 → Chart 8） |
| **L1 数据** | TextBox 文本、Chart series.Values、Table 单元格 vs 期望值 | chart series 是模板默认值、TextBox 文本取错来源 |
| **L2 格式** | 几何（L/T/W/H）、字号、fill 颜色、AutoSize | TextBox 高度差 100pt、AutoSize=0 vs 1 |
| **L3 染色** | character-run 级 font/color/bold 切换断言 | GPT 输出染色 bullet 缺失 |
| **L4 行为** | pipeline jsonl trace（COM 失败 / GPT 调用） | Chart Activate 失败但代码继续走、smoke 模式 GPT 没调走 fallback |
| **L5 视觉** | PNG 导出 + SSIM | 整页布局崩了 |

L0 是地基——它失败时 L1/L2/L3 都会失真（在错的 shape 上跑断言）。L4 是新增维度，需要 pipeline 主动落 trace。

## 调用

### 基本用法（最常用）

```powershell
python "C:\Users\<USER>\.claude\skills\ppt-acceptance-check\ppt_acceptance_check.py" `
    --new "v1.6.pptx" `
    --template "apparel-page13-14-template.pptx" `
    --slide-pairs "12:13,13:14" `
    --contract "acceptance/apparel.json" `
    --pipeline-trace "debug/apparel_trace.jsonl" `
    --out-dir "debug/acceptance-apparel/"
```

输出：`debug/acceptance-apparel/acceptance_report.md` + `.json`，exit code 0=PASS / 1=FAIL / 2=配置错。

### 只跑某些层（debug 用）

```powershell
# 只跑 L0 验证配对策略
python ".../ppt_acceptance_check.py" --new x.pptx --template y.pptx `
    --slide-pairs 12:13 --layers L0

# 跑 L0+L4，跳过格式 / 视觉
python ".../ppt_acceptance_check.py" --new x.pptx --template y.pptx `
    --slide-pairs 12:13 --layers L0,L4 --pipeline-trace trace.jsonl
```

### 桥接当前打开的 PPT（避开文件锁）

```powershell
# new 是用户正在编辑的（取 ActivePresentation）；template 从磁盘
python ".../ppt_acceptance_check.py" --active-new --template y.pptx `
    --slide-pairs 12:13 --contract acceptance.json
```

`--active-new` / `--active-template` 用 `GetActiveObject` 复用用户进程，**绝不 Close/Quit**。

### smoke 模式

```powershell
python ".../ppt_acceptance_check.py" --new x.pptx --template y.pptx `
    --slide-pairs 12:13 --contract acceptance.json --mode smoke
```

契约 `modes.smoke.rule_overrides` 里的规则会被改写 severity（典型：把 `gpt_must_be_called` 改成 tolerate，让 smoke 跑不报 GPT 必修）。

## 契约文件（项目特化外置）

无契约 → 全严格默认 + L2 几何兜底。要把项目规则写进契约 → 看 `examples/acceptance_contract.example.json` 的样板：

```json
{
  "version": 1,
  "data_sources": {"excel": "C:/path/to/source.xlsx"},
  "shape_pairing": {
    "rules": ["strip_clone_suffix", "ignore_chart_auto_renumber"],
    "manual_overrides": {"p13": {"Chart 8": "Chart 63"}}
  },
  "tolerances": {"geometry_px": 2.0, "ssim_threshold": 0.96, ...},
  "rules": [
    {"id": "chart63_temp_range", "shape": "Chart 63", "layer": "L1",
     "check": "chart_series_values",
     "expected_from": "excel:服装试穿问卷--紧身背心:AD,AE:range",
     "severity": "must_fix"}
  ],
  "modes": {"smoke": {"rule_overrides": {"gpt_must_be_called": "tolerate"}}}
}
```

### shape_pairing.rules（L0 配对策略）

| 策略 | 含义 |
|---|---|
| `strip_clone_suffix` | 去掉 `副本` / `Copy` / `(1)` 后缀再比 |
| `ignore_chart_auto_renumber` | Chart 8 vs Chart 63：按 type + 几何近似配对（PowerPoint 复制时会自动改编号） |
| `match_by_position_if_name_lost` | 兜底：按 L/T 几何近似配对（用之前先排除名字策略，否则误报多） |

`manual_overrides` 永远生效（在所有策略之前）。

### 支持的 check 类型

| 层 | check | 说明 |
|---|---|---|
| L1 | `text_equals` / `text_equals_computed` | 完全相等 |
| L1 | `text_contains` | 子串包含 |
| L1 | `chart_series_values` | chart series.Values vs expected（嵌套 list 或 `[min,max]` range） |
| L1 | `picture_present` | shape 存在即过 |
| L1 | `table_cell_equals` | 指定 row/col 单元格文本 |
| L2 | `geometry_within_tolerance` | L/T/W/H 在 `tolerances.geometry_px` 范围内 |
| L2 | `autosize_matches_template` | TextFrame.AutoSize 一致 |
| L2 | `font_size_within_tolerance` | 段落 0 字号在 `font_size_pt` 范围内 |
| L2 | `fill_color_equals` | shape.Fill.ForeColor.RGB 一致 |
| L3 | `has_color_runs` | `expected_min` 个非默认色 run |
| L3 | `has_bold_runs` | `expected_min` 个 bold run |
| L3 | `runs_match_template` | run 切换序列与模板对齐（⚠ 模板=旧、代码=新时不可用，会把"没动"和"改对"都算 PASS） |
| L3 | `runs_match_signature` | 与契约内嵌 `expected_runs` 严格对比，不依赖模板；适合同 shape 多字号/多颜色这类**意图超出模板原状态**的视觉契约。默认过滤纯 CR/空白 run（`ignore_whitespace_runs: true`） |
| L4 | `trace_event_present` | `expected_events` 必须全在 trace 中（且 `called != false`） |
| L4 | `no_trace_event` | `forbidden_events` 一个都不能出现 |
| L4 | `trace_event_count` | `event` 出现次数在 `[min_count, max_count]` |

### expected_from DSL（L1 用）

| 语法 | 示例 | 含义 |
|---|---|---|
| `hardcoded:<json>` | `hardcoded:"15~25℃"` | 字面值 |
| `excel:<sheet_kw>:<col>:mode` | `excel:问卷:AD:mode` | 该列众数 |
| `excel:<sheet_kw>:<col>:sum` | `excel:问卷:AE:sum` | 列求和 |
| `excel:<sheet_kw>:<col>:mean` | `excel:问卷:AE:mean` | 列均值 |
| `excel:<sheet_kw>:<col>:count_contains=X` | `excel:问卷:Z:count_contains=好评` | 子串计数 |
| `excel:<sheet_kw>:<col>:range` | `excel:问卷:AD:range` | `[min, max]` |
| `excel:<sheet_kw>:<col1>,<col2>:range` | `excel:问卷:AD,AE:range` | 两列拼起来再求 range |
| `excel:<sheet_kw>:<col1>,<col2>:mode` | `excel:问卷:AD,AE:mode` | 每列分别求 mode，返回 dict |

sheet_kw 走模糊匹配（`load_excel_rows` 的 fuzzy_keyword）。需要在 `data_sources.excel` 配 excel 路径。

### 三态 severity

| severity | 含义 | 对 exit code 贡献 |
|---|---|---|
| `must_fix` | 必修 | 任一违反 → exit 1 |
| `warn` | 记录不阻断 | 不影响 |
| `tolerate` | 豁免（条件或模式） | 不影响 |

`skip_if_trace`（仅 L1/L3 等用到 shape 的规则）支持 `<event>.called == false` 这种简单条件 —— 例如 GPT 没调时跳过染色检查。

## pipeline 接入 trace（L4 必需）

在你的 pipeline 里加几行：

```python
import sys
sys.path.insert(0, r"C:\Users\<USER>\.claude\skills\office-com-helpers")
from office_com_helpers import TraceLogger

with TraceLogger("debug/apparel_trace.jsonl") as trace:
    with trace.shape_write("Chart 63", "bar_stacked_temp_range", slide=13) as ev:
        try:
            chart.ChartData.Activate()
            ev["ok"] = True
        except Exception:
            trace.event("com_api_failed_but_continued", shape="Chart 63",
                        api="ChartData.Activate", attempts=3)
            ev["ok"] = False
    trace.event("gpt_strengths", called=False, reason="mc_gpt=n")
```

**渐进迁移**：不接入 trace 也能跑 L4，只是会**降级**（severity 全部当 warn，且报告里显式标 `degraded`）。

## 输出报告（acceptance_report.md）

报头先看「结论 PASS/FAIL + 必修/警告/容忍 计数」；再看「必修违反清单」（永远在最上）；再看「警告清单」/「容忍清单」/「详细清单（含通过项）」。

L5 视觉层的 PNG 落在 `<out_dir>/visual/new_<NNN>.png` + `template_<NNN>.png` 方便人审。

## 为新项目写 contract（80/20 指南）

最小契约（只解决 L0 + L4，其他全严格默认）：

```json
{
  "version": 1,
  "shape_pairing": {
    "rules": ["strip_clone_suffix", "ignore_chart_auto_renumber"],
    "manual_overrides": {}
  }
}
```

加 chart 数据断言：

```json
{
  "version": 1,
  "data_sources": {"excel": "..."},
  "rules": [
    {"id": "chart_X", "shape": "Chart 63", "layer": "L1",
     "check": "chart_series_values",
     "expected_from": "excel:问卷:AD,AE:range", "severity": "must_fix"}
  ]
}
```

加 GPT 调用断言：

```json
{
  "version": 1,
  "rules": [
    {"id": "gpt_called", "layer": "L4", "check": "trace_event_present",
     "expected_events": ["gpt_strengths", "gpt_drawbacks"],
     "severity": "must_fix", "scope": "production"}
  ],
  "modes": {
    "smoke": {"rule_overrides": {"gpt_called": "tolerate"}}
  }
}
```

## 跟其他 skill 的关系

| skill | 关系 |
|---|---|
| `ppt-visual-fidelity-check` | **已 deprecated**，本 skill 的 L5 完全吸收；存量项目还在用其函数则继续保留 |
| `office-com-helpers` | L4 用其 `TraceLogger`；本 skill 加载它的目录到 sys.path |
| `inspect-ppt-template` | 正交。开工前探查模板用 inspect-ppt-template，验收用 ppt-acceptance-check |
| `read-selected-shape` | 正交。审视具体 shape 时用 read-selected-shape；本 skill 是整批断言 |
| `pipeline-self-check-loop` | 本 skill 是它「Self-check」阶段的统一引擎 |

## 不要做

- ❌ 不要把本 skill 当成**自动修复工具** —— 它只断言，fail 了你自己（或 developer agent）去改 pipeline 代码
- ❌ 不要拿来代替 `inspect-ppt-template` —— 那个是「探查模板长啥样」（开工前），本 skill 是「验收成品长得对不对」（交付前）
- ❌ 不要为单次 bug 写 rule —— 单次 bug 改 pipeline 代码即可；rule 要为「这个项目永远不能出的错」服务
- ❌ 不要把 `data_sources.excel` 写成相对路径 —— pipeline 当前目录和 skill 跑的目录可能不同；写绝对路径
- ❌ 不要在 `--active-*` 模式下试图 `Close()` / `Quit()` —— 代码已守住，人为加回去会炸用户 PowerPoint 进程

## Out of Scope（明确不做）

- 自动修复
- 代码层 review（用 `/code-review`）
- Word / Excel 验收（v2 再说）
- 跨页业务流程检查（业务规则，不是验收）
- 模板探查（用 `inspect-ppt-template`）
