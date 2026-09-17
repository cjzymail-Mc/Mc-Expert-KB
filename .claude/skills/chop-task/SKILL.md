---
name: chop-task
description: 把原始任务改写成结构化施工合同并先走开工门禁。独立 /chop 从 chop-task.md 读取、让用户选择落点并打 consumed；也可由 team-task 以带参数的 contract-only 模式调用，改读 bounded source block、幂等追加 frozen 合同且跳过落点菜单/consumed。
argument-hint: "[caller=team-task ...]"
---

# chop（任务改写 + 开工门禁）

把“原始任务 → 门禁 → 结构化合同”固化成单一 KO/交底引擎。独立 `/chop` 行为不变；`caller=team-task` 时按 `$ARGUMENTS` 的严格契约运行，不靠自然语言猜 caller。

> **核心理念**（见同目录 `examples.md`）：从【人工拆解】转向【自动拆解】——**不替用户列步骤，而是写一份让 Claude 自己拆的 prompt**。给终态和参照物、补全局事实、第一里程碑就是拆解计划本身、把定不了的列成拍板点、首件验收逐级放量。
> **门禁理念**（见同目录 `kickoff-gate.md`）：产 prompt 前先核**信息充分性**——事实层缺口先问用户补，可推导层留执行期自拆，裁量层收敛成拍板点。

## 触发后立刻做

1. **先解析 `$ARGUMENTS` 再读输入**：
   - 无 `caller` = 独立模式：读 repo 根 `chop-task.md` 最后一个 `<!-- consumed ... -->` 之后的内容（无标记取全文）；缺文件/无新内容就停，不编任务。用户在对话直接贴文本时仍以对话为准。
   - `caller=team-task` = 被调用模式：必须且只允许 `caller/mode/run_id/source_block_id/source/output/profile/input_policy` 八键；固定 `mode=contract-only source=team-task.md output=team-task.md profile=auto`，`input_policy∈{initial,answered,continue-defaults}`。缺键、未知键、非法值一律 `CALL_CONTRACT_ERROR`，不读不写。输入只取 `funnel-gate.md` schema 中与指定 id 匹配的完整 source block（含 id/sha256/status），找不到/多于一块 fail-loud，禁止退化成整段读取。
2. **读 `examples.md` + `kickoff-gate.md`**；被调用模式另读 `../team-task/funnel-gate.md` 的问卷、合同块和幂等 schema。门禁全套照走，不因 caller 省略。

## 开工门禁：信息充分性自检（产 prompt 前必走，照 `kickoff-gate.md`）

3. **入口分诊**（gate §0）：把任务归类——单点改 / 从零新建 / 纯查询 → 跑廉价自检即可、**别拷问**；长链 → 走通用门；批量改既有结构化产物 → 通用门 + 批量铁律注入。
4. **八项交底自检 + 足量性自测**（gate §2）：逐项核信息在不在场，标出**事实层缺口**。
5. **补缺口**（gate §3 边界）：
   - **事实层缺口**（用户独有、执行期 inspect 也得不到）→ **用一条 prose 消息列清单请用户补**；开放事实**不要**塞 AskUserQuestion。
   - **可 inspect 的**（现状 / 模板异构 / 文件清单）→ **不问**，写进 prompt 让执行期盘点。
   - **裁量层** → 独立模式留到下面「列拍板点」用 AskUserQuestion；`contract-only` 被调用模式按 P4/P5 接管规则处理。
   - **轻任务信息已齐** → 直接产精简结构化 prompt，别拷问。
   - **被调用模式重缺口** → 写/复用 `team-progress/questionnaire-<run_id>.md`：FACT 缺口永不默认；仅 PREFERENCE+安全默认可在 `input_policy=continue-defaults` 时降级。仍缺阻断事实则返回 `NEED_INPUT questionnaire=<path>`，不产合同、不打阶段完成。

## 改写规则（产出一份结构化「自动拆解 prompt」）

按下面骨架改写，缺哪块补哪块，**不要替用户把任务拆成执行步骤**——拆步骤是 Claude 拿到 prompt 之后的活：

- **【终态】**：一句话说清"做完长什么样" + 拿谁当完整度参照物（标准项目 / 标准报告 / 成熟同类产物）。
- **【事实交底】**：补全局重要信息（数据真相 vs 骨架起点 / 素材位置 + 可动范围 / **资料是否已穷尽** / 业务规则 / **加密解密底座**）。
  - **若是「批量改既有结构化产物」类**（gate §4）：注入**避坑铁律**（探测先于讨论、禁抽样发现异构、盘历史层、plan 批准前不动手）+ **条件指针**（repo 若配「批量改造开工门禁」类 skill → 放量前走之：探测 → 5 要素 spec → 用户签字）；repo 无该 skill → 仍写明铁律实质、不报错。**不在此复刻四阶段 / 5 要素机器**（那是 repo 门禁 skill 的活，自标草案 v0）。
- **【红线】**：禁止出现的字眼 / 行为（如禁【替代】【推断】）+ 对外交付合规线。
- **【你的任务】**：固定句式——**先不动手**：盘点现状（多方对照）→ 拆阶段和步骤 → 每步写明判定规则 → 每阶段建议施工方式（team / subagent / 单干）→ 独立模式把定不了的列成**拍板点**问用户；`contract-only` 被调用模式则只保留阻断 FACT，普通裁量写推荐与依据。**第一个里程碑就是这份完整拆解计划，用户先验收 plan、批准后才执行，按里程碑交付。**
  - 若建议"单干"，提醒关键验收环节（如首次生成的 plan）务必让 **mc-expert** 带验收背景把关。
- **【验收】**：按**首件验收（first article inspection）逐级放量**写——最便宜环节（纯文本对照表 / 单份首件）拦住系统性错误再放量；每级只验该级**新增**的失败模式；末级"批量跑 + 只抽检红线项"。

## 列拍板点（裁量层；独立模式必做、被调用模式禁止越权）

**独立模式**：改写中自己定不了的裁量项（选哪个项目做首件 / 某阶段 team 还是单干 / 某业务规则边界）→ 收敛成**封闭选择题**（P1: A/B + 默认建议），用 **AskUserQuestion** 问。别替用户拍、别问开放题、别把定不了的当默认拍了。

**被调用模式**：`contract-only` 下不询问 A/B、team/solo 或队形；这些由 `team-task` P4/P5 的默认 B+AUTO、任务形状证据及用户入口时的显式覆盖统一接管。这里只为**不可默认的阻断 FACT**返回 `NEED_INPUT`；普通裁量项写推荐与依据进合同，不重复打扰用户。

## 落点分支（独立模式二选一；被调用模式固定落点）

prompt 定稿后按模式分支：

**被调用模式**：跳过落点 AskUserQuestion 与 `chop-task.md` consumed。按 `funnel-gate.md` 的唯一 schema 产最小/完整合同（marker 含 run_id/contract_id/source_block_id/status/profile），追加不覆盖。写前按 `run_id+source_block_id` 查重：已有 frozen 块就返回 `REUSED contract_id=<id>`，不得二次追加；否则返回 `FROZEN contract_id=<id> profile=<minimal|full>`。

**独立模式**：用 **AskUserQuestion** 让用户选落进哪个文件（**选定前不要写文件**）：

- **todays-task.md** → 单干 / subagent 执行路线（配 `/today`）。
- **team-task.md** → 风险增强执行路线（配 `/team-task`，会漏斗冻结合同；实际拓扑与 A/B 按 team-task 默认策略登记，仅认用户入口时的显式覆盖）。

选定后：
1. 以**带日期新块**追加到该文件末尾（Edit 追加，**不覆盖**原历史块）。写进 team-task.md 时放在「## 本次任务」之下/之内（`/team-task` 读的是「本次任务」段，确保读得到最新这份）。
2. **在 `chop-task.md` 末尾追加消费标记** `<!-- consumed YYYY-MM-DD -->`（非破坏性，防 stale 重读；**不清空文件**）。

```
## 产出：自动拆解 prompt（YYYY-MM-DD）

【终态】… 【事实交底】… 【红线】… 【你的任务】… 【验收】…
```

> 日期取系统当天（context 的 currentDate）。

## 汇报（必做）

1. 改写好的「自动拆解 prompt」全文。
2. 开工门禁补了哪些**事实缺口**（问了什么 / 用户答了什么）。
3. 拍板点清单（若有）。
4. 落进了哪个文件 + 绝对路径 + 块标题 + 已在 chop-task.md 打消费标记。

被调用模式的汇报只给状态码（`CALL_CONTRACT_ERROR|NEED_INPUT|FROZEN|REUSED`）+ run/source/contract/questionnaire 指针，不输出独立模式的落点菜单或 consumed 声明。

## 不要做

- ❌ 替用户把任务拆成执行步骤（那是执行期的活，本命令只产 prompt）。
- ❌ `chop-task.md` 无新内容时自己编任务。
- ❌ 漏掉「事实交底」里的加密/解密底座与"资料已穷尽"交底（最易踩的两坑）。
- ❌ 用 AskUserQuestion 采**开放事实**（它只配封闭拍板点）；也别把轻任务拷问一通。
- ❌ 把 repo 门禁的四阶段 / 5 要素机器 copy 进产出（只注入原则铁律 + 条件指针）。
- ❌ **破坏性清空** `chop-task.md`（用消费标记）；或落点写文件时覆盖原历史块。
- ❌ 独立模式没让用户二选一就擅自写文件；或被调用模式又弹落点菜单/打 consumed。
