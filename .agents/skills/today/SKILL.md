---
name: today
description: "[Codex adapter] 直读 Claude today 入口执行 todays-task.md；入口委托 today-core 时必须二次 resolve 并执行核心，显式交接 mode/task/caller_id。普通 TUI 用一次交互门，Goal 用初始 objective 的 TODAY_MODE 精确令牌，避免自动续接吞掉问询。Claude-only 机制替成 Codex 等价（user-scope mc-expert custom agent / auto_review / explorer / codex-failcount / pin 提案人工门 / $mc-update deferred-review），mode gate、reset、finalizer 各且仅一次。仅手工 $today 触发。"
---

# $today（Codex 直读母本 adapter）

> **工作方式**：先 shell 读 Claude today 入口；入口委托 `today-core` 时，必须再解析并完整读取 core，随后按入口 + core 执行。Claude-only 机制按下表替成 Codex 等价。**不复制母本正文；母本改动经 resolver 自动同步。**

## 第零步：读 repo 共同 binding（每次必做）

完整读取 `$env:USERPROFILE/.agents/skills/_mc-common/codex-runtime-bindings.md`。母本定位、native reviewer 当前 turn preflight、权限边界、finalizer exactly-once 与 fail-loud 状态均以该文件为共同单源；本 adapter 只保留 today 特有的 mode/Goal/contract 映射。

## 第一步：依次读 today 入口与 today-core（每次 $today 必做）

```powershell
pwsh -NoProfile -File (Join-Path (Join-Path $env:USERPROFILE '.agents\skills\_mc-common') 'resolve-master.ps1') -SkillName today -Cat
```

> resolve-master.ps1 优先读 `$env:CLAUDE_SKILL_MASTER_DIR`，其次 sibling `Mc-Expert-repo\.claude\skills\today\SKILL.md`；找不到 fail-loud（MASTER_NOT_FOUND exit 1），禁止静默用旧副本。换机设环境变量或换 sibling 路径。

当前 today 母本是薄入口并委托 `today-core`。读到该委托后，**必须立即执行第二次 resolver**：

```powershell
pwsh -NoProfile -File (Join-Path (Join-Path $env:USERPROFILE '.agents\skills\_mc-common') 'resolve-master.ps1') -SkillName today-core -Cat
```

today-core 找不到、读取失败或 contract 不完整时 fail-loud，停止执行；禁止只凭 today 入口、旧 adapter 残留或本地复制内容继续。若未来 today 母本不再委托 core，则按当时入口声明执行，不臆造二次调用。

完整流程来源：today §1 负责 mode gate；today-core §0 校验 contract、§1 执行调度、§2.1 收尾 `$mc-update → (pin 提案) → $session-new`、§2.2 连失 2 次熔断。Claude-only 机制按下表替换。

## 第二步：第0步全托管前置门（读母本后第一动作 · 必做 · 禁跳）

母本 §1 要二选一（普通/全托管），**选定前不动手**。Codex 无原生 AskUserQuestion；普通 TUI 与 active Goal 必须分两条入口处理，不能在 Goal 内用纯文本问题模拟阻塞。

### A. 普通 TUI `$today`

当前没有 active Goal 时，必须输出下面的问题并等待用户回答：

```
第0步·全托管门：本次 $today 走哪个模式？
  [1] 普通（默认）—— 决策点照常停下问你
  [2] 全托管 —— 自主跑到 4 红线，决策点走 mc-expert 经验陪审；权限升级另走 auto_review
选 1 或 2（回车默认 1）：
```

用户没明确选 2 就按 1（普通）执行。**严禁不问就开干**——母本 §1 硬门（选定前不动手），Codex 必须先输出上面问题、等用户答，才往下路由。

### B. active Goal 调 `$today`

Goal 会在 turn 结束后自动续接，纯文本问题不会形成可靠等待门。若 `get_goal.status=active`，禁止反复输出上述问题；改为检查 `get_goal.objective` 中由用户在初始 `/goal` 输入的精确独立令牌：

- `TODAY_MODE=1` → `mode=normal`
- `TODAY_MODE=2` → `mode=autopilot`

只允许恰好一个令牌。缺失、重复、冲突或无法读取 objective → fail-loud，保持零 run、零 reset、零任务写入；提示用户新建 `/goal` 并在初始文本中加入令牌。**不得**把 Goal internal context、自动续接次数、agent 自报或后补消息当作用户授权。

令牌存在时，它就是用户在 Goal 初始消息中的显式模式选择，不再弹第二次菜单。执行证据必须记录 `mode_selection_source=goal_objective` 与原始令牌；初始 `/goal` 消息不计入 `human_continuation_message_count`。

`/goal` 创建 active Goal 后会立即执行 objective，不存在可靠的“只创建但暂停”。若 caller 声明 full-unattended Run Contract，还必须在 Goal 前完成共同 binding 的 `PRE-GO AUTH GATE`，并让初始 objective 带唯一 `UNATTENDED_AUTH_SHA256=<64位小写哈希>`；哈希缺失/不符时零任务写入。禁止使用“两条消息：先建 Goal、再显式开工”。

### C. Goal 长任务的 compaction 取证（仅在验收合同要求时）

Goal 内 agent 的“未看到上下文压缩提示”不是权威否定证据。需要验收 compaction 时，按以下证据优先级收口：

1. run 内 checkpoint/events 与 agent 自报用于描述任务状态，但不得单独证明“未发生 compaction”。
2. 由独立的事后观察者只读检查原始 Codex session 生命周期事件；`compacted` / `context_compacted` 是运行面一手证据。无权访问或日志缺失时写 `unknown / not_verified`，不得写 `false`。
3. 观察到事件后，检查其后的第一批动作是否重新读取最近 checkpoint、events 与 workload state，并确认没有重跑已完成阶段；两者都成立才写 `checkpoint recovery verified`。
4. session 日志只作只读证据，不得修改；若它与已封存 run-local 自报冲突，新增事后裁决说明证据等级与边界，不回写原 run。

这条规则只约束要求 compaction 证明的长任务验收，不要求普通 `$today` 每次扫描用户级 session 目录，也不扩大 workspace 外读取权限。

## 第三步：交接 today-core contract（硬执行 · 缺一即停）

mode 选定后、进入执行调度前，在当前上下文显式冻结并校验：

1. `mode`：选 1 = `normal`，选 2 = `autopilot`。
2. `task`：普通 `$today` 读取 repo 根 `todays-task.md` 后提炼；`caller_id=today-loop` 时只取 loop `state.json` 的 active plan title/目标，不用根任务覆盖。不得为空。
3. `caller_id`：普通入口显式声明 `today`；只有已加载 `$today-loop`、active Goal 双令牌有效且台账恰有一个 running plan 时才允许声明 `today-loop`。
4. 按已读取的 today-core 执行；不得把 Claude `Skill(today-core, args: ...)` 当成 Codex 已自动完成的调用。

任一字段缺失或 mode 不在 `{normal, autopilot}` → 回报 `contract 不完整` 并停止，不硬凑默认值。`task` 多词/含引号时保留为单一逻辑字段，不让 shell quoting 拆散语义。

**Exactly-once 所有权**：

- mode gate 只由 today 入口 / 本 adapter 处理一次：普通 TUI 问一次，Goal 只消费一次 objective 令牌；today-core 不再问。
- `mode=autopilot` 的 Codex failcount reset 只由本 adapter 在进入 core 前执行一次；core §2.2 的 Claude reset 映射到这次已执行的 reset，不再重复。
- finalizer 只由 today-core §2.1 执行一次；core 返回后本 adapter 直接结束，不做二次 `$mc-update/(pin 提案)/$session-new`。

### `$today-loop` caller 的窄附加合同

- 初始 Goal objective 必须同时含唯一 `TODAY_LOOP_MODE=2` 与唯一 `TODAY_MODE=2`；full-unattended 合同还必须含与冻结 authorization pack 一致的唯一 `UNATTENDED_AUTH_SHA256`。仍由本 adapter 消费 `TODAY_MODE=2` 得出 autopilot，不另问 mode。
- 每个 plan 实际执行 Codex failcount reset 后，由 loop 台账记录 `record-reset`；重复即停。
- 单-plan finalizer 返回后，由 loop 台账记录 `record-finalizer`；本 adapter返回外层 SELECT/CHECKPOINT，不自行 complete 整个 Goal，也不追加总 finalizer。
- plan PASS/REWORK/WAIT_HUMAN 由外层依据 `$today` 产物和陪审结果写台账；模型不得直接编辑 state/events。

## Codex 机制映射表（母本 Claude 机制 → Codex 等价）

| 母本(Claude)机制 | Codex 替代 | 等级 |
|---|---|---|
| AskUserQuestion（today §1 第0步门） | 普通 TUI 输出一次问题等用户答；active Goal 消费初始 objective 的 `TODAY_MODE=1/2` 精确令牌，不在自动续接回合内假等待 | 模拟非原生 |
| 全托管“托管给 mc-expert”（today §1 / core §1、§2.1） | 按共同 binding 走独立只读 reviewer：native 优先；仅冻结合同明确授权时可用 isolated subprocess fallback | 独立效果等价，路由留痕不同 |
| 深度授权(B)权限后置门（today §1 红线①②类不中途发起） | Goal 前一次性 authorization pack + Goal 内不新增审批请求；`auto_review` 仅作意外后备 | 部分等价（路径不同） |
| Task(mc-expert)（core §1.1 门3 / §1.2 / §2.1） | 按共同 binding 依据 provider route 读取 `$env:USERPROFILE/.codex/agents/mc-expert.toml` 或 `.codex-glm/agents/mc-expert.toml`，显式选择 `agent_type=mc-expert` + `fork_turns=none` | user-scope custom agent，路由可验证 |
| Agent Teams（core §1.1 门2） | full-unattended 在 PRE-GO pack 先冻结是否分工、允许角色与并发上限；Goal 内只按已批拓扑执行，新增拓扑需求 `WAIT_HUMAN` | 不同形、预授权替代中途人门 |
| Explorer subagent（core §1.1 门4） | Codex 内置 explorer subagent | 等价 |
| autopilot_failcount.ps1（core §2.2） | `$env:USERPROFILE/.agents/skills/_mc-common/codex-failcount.ps1`（见下熔断节） | 部分等价 |
| pin_capture.py（core §2.1 pin 段） | finalizer 只产结构化 pin 提案清单并停人工门；用户审后由 LLM 批量调用共享 pin_capture.py 落账，不自动调 `$pin` skill | 分阶段等价（判别与落账解缠） |

母本凡含上表左列机制 → 按右列替代执行；母本通用逻辑（门控流程结构 / 收尾 loop 顺序 / 熔断阈值 2 / 4 红线）按母本原样。

> **机制口径（2026-07-27 修正）**：Codex 官方支持 personal custom agent（`~/.codex/agents/*.toml`），当前 native spawn surface 也暴露 `agent_type` selector；mc-expert 统一走 user-scope profile，并显式选择 `agent_type=mc-expert` + `fork_turns=none`（full-history fork 会继承父 agent type，不能同时指定 custom agent）。Codex multi-agent 与 Claude Agent Teams 仍不同形（无原生 team 拓扑/共享任务列表），门2继续停人工门、不偷换。

**母本 slash command 映射**（core §2.1 收尾 / §1.1 门2必看）：母本里的 Claude slash `/xxx` → Codex skill `$xxx`。core `/mc-update` → 调 `$mc-update`；pin 段 → 产结构化提案清单并停人工门（不自动调 `$pin` skill）；`/session-new` → 调 `$session-new`（含第 0 步主线回顾，纯 LLM 文本判断、不依赖 mc-expert）。

## mc-expert 经验陪审（全托管决策通道 · 硬执行 · 禁跳）

母本出现 `Task(mc-expert)`，或全托管执行途中出现普通模式本来会问用户、且会实质改变方案/范围/验收的决策点时，按共同 binding 执行。开工/中途咨询 prompt 必须交齐共同 binding §2.1 的 v2 六字段并写 `REVIEW_PROFILE=HISTORY`，要求 reviewer：① 按 provider route 读取并遵守唯一 user-scope profile 与共享 `review-contract-v2.md`；② 按仓库入口读取相关 memory/KB；③ 检查当前主线 anchor；④ 只读输出历史依据、明确推荐、风险与置信度；⑤ 低置信仍按“已封默认 > 历史成功率 > 易回滚”给一个默认推荐。主 agent 默认采纳该推荐，非按置信度数值机械选项；四红线/合同人工门除外。HISTORY 只做咨询，不得冒充最终验收；若本任务命中共同 binding §2.2 的增强终审触发器，最终另起 fresh `ENHANCED_FINAL`。

Native 路由出现 `No agents completed yet` 只记 `PENDING` 并继续 bounded poll，不计 transport failure。isolated subprocess 只有调用方冻结合同和 authorization pack 明确声明时才可作第二路；留痕必须区分 route，不得把它写成 native child。

## PRE-GO 授权与 auto_review 后备（深度授权部分等价）

today §1 第0步“全托管”在 Codex 的首选实现是：Goal 前冻结 authorization pack，一次展示全部预计权限/人工选择；用户用带哈希的单条 `/goal` 批准并开工。Goal 内只执行已批准动作，权限需求可延后则集中写 `pending-human`，是硬依赖则 `WAIT_HUMAN`，不得中途主动制造 approval 弹窗。

- **运行面**：workspace 内已授权动作直接跑；Computer Use、Office GUI、第三方登录/弹窗、网络安装、全局配置、外部写和交付默认排除在无人值守执行面。
- **后备**：config.toml 的 `approvals_reviewer="auto_review"` 只处理意外出现的原生权限请求，不扩大权限、不保证不弹窗，也不负责经验/方案决策。
- **确定性兜底**：销毁性删除/无备份覆盖、敏感目录、对外交付仍由 adapter 后置清单与四红线拦截；即使 reviewer 放行也不执行。

## 收尾 loop（today-core §2.1 → 调真实 Codex skill）

today-core §2.1 拥有唯一一次收尾，顺序为 `$mc-update → (pin 提案) → $session-new`。Codex 侧只有 mc-update 与 session-new 段调用对应 `$skill`；pin 段只生成提案、不得调用 `$pin` skill 或 pin_capture.py。adapter 只提供机制映射，不在 core 返回后重跑：

1. **`$mc-update`**：全托管收尾调 **deferred-review 模式**（mc-expert 预筛后直写 `status: proposed` + `review: deferred` 的 inbox proposal，在最终报告列出；**不**停在 interactive 列候选等用户——那样会死等、阻塞无人值守）。普通模式调 interactive 模式（列候选给用户审）。
2. **pin 提案**：收尾时若有用户当场纠正待 pin（本会话或上一会话遗留），完成判别、陪审与去重后产结构化 `PIN/DROP/DEGRADED` 清单，字段与 plan02 minimal schema 对齐，并交 `$session-new` 写入 handoff 供人工门批量落账；finalizer 不调 `$pin` skill / pin_capture.py。无待 pin 纠正则跳过。
3. **`$session-new`**：调 `$session-new`（含第 0 步主线回顾 + 产 plan + 状态文件更新 + 汇报）。重入幂等（本会话 plan 已存在→只更新主线/状态、不堆重复 plan）。

## 连失2次熔断（仅全托管，替代 today-core §2.2 · 硬执行 · 禁跳）

today-core §2.2 用 `autopilot_failcount.ps1`（Claude 路径），Codex 替换为：

- 唯一脚本路径：`$env:USERPROFILE/.agents/skills/_mc-common/codex-failcount.ps1`（2026-07-12 实测 `-Mode reset` 成功；旧写法从 repo cwd 不存在，禁引）。
- 用户在普通 TUI 明确选 2，或在 active Goal 初始 objective 明确写入唯一 `TODAY_MODE=2` 后，进入 today-core 前必须且只执行一次：`pwsh -NoProfile -File (Join-Path (Join-Path $env:USERPROFILE '.agents\skills\_mc-common') 'codex-failcount.ps1') -Mode reset`。
- 每个**语义任务步骤**结束判一次：确实失败 → `-Mode fail`；确实成功 → `-Mode reset`。不能只在口头里记。
- 见到 `AUTOPILOT_STOP` 或退出码 2 → **立即停、交用户、不再试第 3 次**。
- 默认计数文件 `%TEMP%\codex-failcount.json`（避 `~/.claude` + 监控盘）。脚本缺失/受限时降级到 repo `output/` 自维护 JSON、明确标注降级。

## 4 红线（全托管+普通都生效，today §1 / core §2.2）

①销毁性/不可逆（多文件删除/覆盖无备份——guard-delete hook 确定性兜底）②对外交付物/Ldterm 明文合规 ③连失2次 ④推翻 KB `decisions/` 已封决策 → **halt：不执行 + 落盘报告 + 上报**，不靠阻塞式权限框。guard hook + sandbox + auto_review 在 adapter 层之下多重兜底。

## Claude-only 诚实标注原则（plan02 §6 风险3）

母本含的 Claude-only 机制（Agent Teams / AskUserQuestion / Task(mc-expert) / Claude 原生 mc-expert），按映射表替代或停人工门，**不假装 Claude 原生**。全托管决策点统一标注“Codex user-scope `mc-expert` custom agent，读取共享 KB；非 Claude 原生 mc-expert”。pin finalizer 现只产提案并停人工门；人工批准后的批量落账仍复用两端共享的 pin_capture.py，不再标“Codex 无共享捕获链”。


