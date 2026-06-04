---
name: inspect-ppt-template
description: 任何需要 AI 理解 .pptx 内部结构的场景（模板填充、参考样本对比、shape 名字反查、母版水印定位、改已有填充脚本）**开工前必须先跑**。用 win32com 探测 slides / shapes / masters / layouts，输出 inspect_report.json + .md，把 AI 对 pptx 的感知盲区一次性堵掉。支持 `--slides "12,13-14"` 页面过滤 + `--active` 桥接当前打开的 PowerPoint + `--full` 展开 paragraph / run 级字体字号颜色（同 shape 多字号/多颜色调研必开）。约能消除「教 AI 文档长啥样」环节 50% 的时间。
---

# inspect-ppt-template

**任何需要 AI 理解 .pptx 结构的场景的强制前置步骤**。AI 不缺判断力，缺感知能力——.pptx 是黑盒，AI 看不到 shape 的 COM 内部名、母版三联水印的位置、布局继承关系。这个 skill 就是被迫造的"探针"。

> docx 走 `inspect-word-template`（含染色三态分桶 + 占位符审计 + 合并单元格安全遍历）；
> xlsx 走 `inspect-excel-template`。三个 skill 职责单一，命名规则统一。

## 何时使用（强制触发，命中任一就跑）

**模板填充类**：
- 用户给了一个新 pptx 模板，要求 AI 写填充脚本 / 自动化生产线
- 用户说「这个模板长这样：……」但只提供了截图 / 截屏 / 文字描述
- 准备改一个已有的 pptx 填充脚本，但模板可能变过
- 准备写 `template_mapping.json` / `reference_mapping.json` 这类槽位定义
- 任何包含「PPT 自动生成」「PPT 模板填充」字样的需求

**结构反查 / 参考样本对比类**（容易被错误降级跳过 — 一样要跑！）：
- 用户提供一份人工制作的 pptx 作为"参考样本"，想让 AI 模仿/对比它的某些页面（例："你看 page12 vs page13+14 的差异"）
- 用户问"这个 shape 叫什么名字 / 在第几行第几列 / 母版上有没有同名 shape"
- 任何"对比两个版本 PPT 的页面结构"、"看模板第 N 页有哪些 shape"
- 准备对**当前正在用 PowerPoint 打开**的 ppt 做结构分析（用 `--active` 模式，见下）

**反模式**（这些都是 Claude 历史上错误降级跳过 skill 的借口，**全部不成立**）：
- ❌ "用户只想看几页，全扫多余" → 错。用 `--slides` 过滤即可
- ❌ "ppt 正在被用户打开，会冲突" → 错。用 `--active` 模式直接桥接到运行中的 PowerPoint，无文件锁
- ❌ "用户只是要对比参考样本，不是新模板填充" → 错。description 已显式覆盖参考样本对比/结构反查

**不跑这个 skill 直接开干 = 在猜文档**。猜错了之后调试成本远高于先跑探针的 30 秒。

## 调用方式

### 文件模式（默认，新进程 ReadOnly 打开）

```powershell
python "C:\Users\<USER>\.claude\skills\inspect-ppt-template\inspect_ppt_template.py" `
    --pptx "path\to\template.pptx" `
    --out-dir "path\to\output\"
```

### 实时模式（桥接当前打开的 PowerPoint，避开文件锁冲突）

```powershell
# 扫 ActivePresentation（前台 PPT 窗口）
python ".../inspect_ppt_template.py" --active --out-dir "out\"

# 多个 PPT 同时打开时，用 --pptx 精确定位
python ".../inspect_ppt_template.py" --active --pptx "x.pptx" --out-dir "out\"
```

`--active` 用 `GetActiveObject` 复用用户进程，**不会 Quit / 不会改文件**，专门解决"ppt 正在被编辑、不能用文件模式 Open"的场景。底层桥接同 `read-selected-shape` skill。

### 页面过滤（避免全扫噪音 / 用于多页对比）

```powershell
# 只扫指定页
python ".../inspect_ppt_template.py" --pptx "x.pptx" --slides "12,13-14" --out-dir "out\"
python ".../inspect_ppt_template.py" --active --slides "12-14" --out-dir "out\"
```

`--slides` 语法：`"12"` / `"12,13,14"` / `"12-14"` / `"1-5,8,10-12"`。

### 全字段模式（`--full`，展开 paragraph + run 级字段）

```powershell
python ".../inspect_ppt_template.py" --active --slides "9" --full --out-dir "out\"
```

默认输出每个 shape 只有 `text`（120 字截断字符串），看不出"同 shape 多字号 / 多颜色 / 同段多 run"这层结构。`--full` 模式给每个有 textframe 的 shape 多 dump 一份 `paragraphs[]`：

| 字段 | 用途 |
|---|---|
| `paragraphs[].text` | 该段文本（去尾 \r） |
| `paragraphs[].alignment` | 对齐 enum（2=center 等） |
| `paragraphs[].runs[].text` | run 文本 |
| `paragraphs[].runs[].size` | 字号（pt） |
| `paragraphs[].runs[].rgb` | 字色 RGB long（16777215=白） |
| `paragraphs[].runs[].bold` | -1=True / 0=False |
| `paragraphs[].runs[].italic` | -1=True / 0=False |
| `paragraphs[].runs[].font_name` | 字体名（识别 Arial vs 微软雅黑） |

**何时必开 --full**：
- 同 shape 内多字号 / 多颜色 / 同段多 run 样式差异调研（如 apparel 的 11pt + 24pt 数字标签）
- 给 acceptance contract 写 `runs_match_signature` 类断言前，要拿目标态 run 序列做参考
- 写自定义 `_write_*_label` 类多 run 工具函数前，先 dump 模板的 paragraph.Runs 结构

**不要开 --full 的场景**：扫全部 slide / 大模板时，run 详情会让 MD 报告膨胀十几倍。优先用 `--slides` 过滤到目标页再开 `--full`。

`--full` 与 read-selected-shape 的 `--full` 是同一约定：read-selected-shape 是"看选中那一个 shape"，inspect 是"按页批量扫"，正交。

### 参数总览

- `--pptx` / `--active` 至少给一个
- `--active` 桥接到运行中的 PowerPoint，省 `--pptx` 时取 ActivePresentation
- `--slides "a,b-c,..."` 仅扫指定 slide，省时省噪音
- `--full` 展开 paragraph + run 级字段（默认 off）
- `--out-dir` 自动 mkdir。本机若被 Ldterm 加密，**输出目录避开被监控的盘符**（参考 `ldterm-decrypt-images` skill）

输出：
- `inspect_report.json` —— 结构化数据，给后续编写 mapping 脚本的程序消费
- `inspect_report.md` —— 人类可读版本，AI 直接读这个写填充逻辑

## 输出内容（关键字段）

| 字段 | 用途 |
|---|---|
| `slides[].shapes[]` | 每页每个 shape 的 **COM 内部名**（关键，不是选择窗格显示的本地化名）、type、L/T/W/H、文本预览 |
| `slide_masters[]` | 母版上的 shape（**页脚三联水印通常在母版**，而不是 slide） |
| `custom_layouts[]` | 母版的自定义版式 + 含文字的 shape |

## 跟其他 skill 的关系

- 跑完 `inspect-ppt-template` 出报告后，可以再用 `read-selected-shape` skill 对感兴趣的具体 shape 做更深的取证（看字体 / 颜色 / chart 数据 / 图片裁剪）
- 加密文件场景：Ldterm 对 win32com 启动的 POWERPNT.EXE 是透明的（白名单），所以**本 skill 能直接处理 Ldterm 加密的 pptx**。若被 IRM/DLP 加密，先解密再跑
- 验收阶段用 `ppt-acceptance-check`（探针是开工前，验收是交付前，正交）。本 skill `--full` 输出的 paragraph/run 结构可以直接拷给 `ppt-acceptance-check` 的 `runs_match_signature` check 当 `expected_runs` 写契约

## 设计原则（看一眼避免误用）

1. **文件模式**：`ReadOnly=True` + `DispatchEx` 新进程，`finally` 里 Quit()，**永不改文件**
2. **实时模式（--active）**：`GetActiveObject` 复用用户进程，`opened_by_us=False`，**绝不 Close / 绝不 Quit**（动用户进程 = 用户当场炸 ppt）
3. **try/except 读 COM 属性**，不用 `getattr`（COM 对象 getattr 也会抛错，参考 `office-com-helpers` skill）
4. **文本截断 120 字符** —— 探针输出不应该把全文倾倒出来；要看具体 shape 全文，用 `read-selected-shape` 或自己另开脚本
5. **--slides 过滤** —— 多页大 ppt 全扫输出 noise 多，明确知道要看哪几页就用 `--slides` 收窄

## 不要做

- ❌ 不要在文件模式下扫**正在被用户打开编辑**的 pptx —— 会冲突；**改用 `--active`** 桥接
- ❌ 实时模式下不要试图调 `Quit() / Close()` —— 代码已经守住，但人为加回去就炸用户进程
- ❌ 不要跑完探针就直接开始猜 —— 必须**通读 inspect_report.md** 后再开始写 mapping / 对比
- ❌ 不要因为"只想看几页"就跳过 skill —— `--slides` 就是解药，30 秒省后面几小时
- ❌ 不要因为"用户给的是参考样本不是模板"就跳过 skill —— description 已明确覆盖参考样本对比
- ❌ 不要用本 skill 扫 docx —— 走 `inspect-word-template`，那个有染色三态 + 占位符审计 + 合并单元格安全遍历
