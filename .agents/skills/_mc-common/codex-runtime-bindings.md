# Codex runtime bindings（user-scope 共同口径）

本文件只保存多个 adapter 共用的 Codex 运行约束；业务步骤仍以各 Claude 母本或 Codex 原生 skill 为准。`today/free/mc-update/session-new` 每次执行先读本文件。

## 1. 母本定位

统一使用：

```powershell
pwsh -NoProfile -File (Join-Path (Join-Path $env:USERPROFILE '.agents\skills\_mc-common') 'resolve-master.ps1') -SkillName <name> -Cat
```

resolver 优先 `CLAUDE_SKILL_MASTER_DIR`，其次 sibling `Mc-Expert-repo`。`MASTER_NOT_FOUND` 或非零退出即停止；禁止硬编码绝对路径、静默使用旧副本或复制母本正文。

## 2. 经验 reviewer 与独立路由

全托管中，只有“普通模式本来会问用户、且会实质改变方案/范围/验收”的决策才进入 mc-expert；普通实现细节不逐项陪审。reviewer 必须只读、使用新上下文，并返回历史依据、明确推荐、风险与 `high/medium/low` 置信度。主 agent 采用 reviewer 的**明确推荐**，不是从多个选项里机械挑“置信度最高者”；低置信仍按“已封默认 > 历史成功率 > 易回滚”给出一个默认方案。命中四红线或合同人工门时不得自动采纳。

### 2.1 mc-expert user-scope profile 与调用合同（spawn 前硬门）

Codex personal custom agent 的固定入口是 `$env:USERPROFILE/.codex/agents/mc-expert.toml`。本机该目录由 junction 指向 Git 母本 `Mc-Expert-repo/.codex/agents/`；profile 不可读时返回 `REVIEW_PROFILE_UNAVAILABLE`，不得退回模型记忆或 repo-local 旧副本冒充 user-scope mc-expert。

主 agent 每次启动 reviewer 前必须先读取该 user-scope profile，并在 task prompt 中交齐以下四项；缺一时**不得 spawn**，直接返回 `REVIEW_CONTRACT_INVALID missing=<字段>`：

1. `REVIEW_TARGET`：精确文件路径、方案或范围；
2. `PROJECT_MEMORY`：已读取的相关项目 memory 路径 + 与本决策有关的完整段落；确无相关项时写 `NONE: <原因>`；
3. `SEALED_DECISION_QUERY`：要在中央 KB `decisions/` 核对的决策名、关键词或问题；确无相关项时写 `NONE: <原因>`；
4. `REVIEW_QUESTION`：一个且仅一个明确陪审问题。

调用方不得只写“帮我陪审”。当前 native surface 暴露 custom-agent selector 时，必须同时使用 `agent_type=mc-expert` 与 `fork_turns=none`；full-history fork 会继承父 agent type，不能再指定 custom agent。若 surface 只有通用 native child，task prompt 还必须要求 child 先完整读取 user-scope profile，再执行同一个四字段合同。两条路的报告都必须在“历史依据”中给出：

- `KB_INDEX=D:/Downloads/Mc Claude Code Workshop/Mc-Expert-repo/MEMORY.md`
- 至少一个实际读取的 `KB_EVIDENCE=<具体档案路径>`；确无相关档案时，明确写 `KB_EVIDENCE=NONE` 及检索范围。

只有档案路径可核验，才算“带 KB 陪审”；通用推理碰巧给出相同结论不算。KB 不可读时 reviewer 必须返回 `KB_UNAVAILABLE`，调用方按 reviewer unavailable 处理，不得把主 agent 自审冒充 KB 陪审。

每个 checkpoint 先检查当前 turn 的实际 callable surface：

- 有 native spawn/collaboration 工具：优先启动一个只读子代理。
- 无 native 工具或发生一次**终态 transport failure**：只有当前 Run Contract 明确声明、repo-local wrapper 已在 Goal 前验证、且 authorization pack 已批准时，才允许切换到只读、ephemeral 的 `codex exec` 独立子进程。它是等效独立 reviewer 路由，不冒充 native child。
- 两条路都未在合同内授权或验证失败：`BLOCKED_REVIEWER_UNAVAILABLE` / `WAIT_HUMAN`；主 agent 自审不是第三条路。

Native child 的等待状态必须分类：

- `Waiting for agents`、`No agents completed yet`、单次 bounded wait 超时且 child 仍为 active/running，均为 `PENDING`，不是 no reply、不是 spawn 失败、不得累计 transport attempt，也不得另启第二个 reviewer。
- spawn/launch 直接报错、child 终态为 failed/cancelled/interrupted、从启动起达到合同 hard deadline 仍无 `task_complete`、`task_complete` 空正文、schema 不合法或 provenance 缺失，才是终态 transport failure。
- 默认每 20–30 秒轮询一次，hard deadline 600 秒。第一次终态失败才启动一个 fresh attempt，并优先换路由；第二次终态失败转 `WAIT_HUMAN`，禁止第三次。
- 合格 native 证据至少含 agent/task id、`task_complete`、原始正文、规范化 verdict、route manifest 与 SHA-256。

历史会话或官方默认只能证明“曾经/通常可用”，不能替代当前 turn preflight。

## 3. PRE-GO AUTH GATE、权限与四红线

需要长时间无人值守的 Goal 必须先在**普通非 Goal 会话**完成一次 `PRE-GO AUTH GATE`：冻结并向用户展示 authorization pack，至少列出允许写路径、计划命令类别、只读外部源、可能的独立 reviewer 路由、禁止动作、不可自动关闭的人工门、意外权限处理和最终交付边界。pack 生成 SHA-256；用户发送带精确哈希的单条 `/goal ...` 即表示批准该版本。`/goal` 创建 active Goal 后会立即开跑，因此禁止再设计“第 1 条只建 Goal、第 2 条才执行”。

Goal 运行中：

- 只执行 authorization pack 已覆盖的动作；正常路径不得主动发起新的 approval request、Computer Use、Office GUI、第三方交互弹窗或范围外命令。
- 新出现但可延后的权限需求写入 `pending-human`，继续其他互不依赖的安全工作，并集中到最终人工门。
- 新权限若是继续执行的硬依赖，停止发起该动作并转 `WAIT_HUMAN`；不得换命令、换路径绕过。
- `auto_review` 只是意外权限请求的概率性后备，不扩大 sandbox、writable roots、network 或 protected paths，也不是“全程无弹窗”的保证。
- 销毁性/不可逆、对外交付或 Ldterm 明文合规、连失 2 次、推翻 KB 已封决策继续由 `AGENTS.md` 四红线即时停机；四红线不能被启动前预授权豁免。

## 4. Native child 与独立子进程

Native subagent 必须来自当前会话的 spawn/collaboration tool。`codex exec` 是独立进程，不继承 native agent 身份；仅可按第 2 节的冻结合同作为只读 reviewer fallback，或用于用户另行授权的独立 headless/视觉任务。两者的 route/provenance 必须诚实区分。

## 5. Finalizer exactly-once

- 上游执行器（`today`、`free`、将来的 `today-loop` 单-plan dispatch）决定是否进入 finalizer。
- 一旦进入，顺序固定为 `$mc-update → (pin 提案) → $session-new`；每段最多一次。**pin 段=产结构化提案清单 + 人工门批量落账，不在收尾链里调 `$pin` skill / pin_capture.py**（pin 解缠，见 today-core §2.1）；判别+陪审+去重+产提案是脑力活、跨 repo 可跑、不依赖 `$pin` 在场。
- 这三段是**已被用户显式启动的上游 skill 的授权子流程**，不是 standalone implicit invocation；子 skill 的 `allow_implicit_invocation:false` 继续阻止模型自行触发新入口。
- 上游调用三段时显式声明 `caller_id=finalizer`。`session-new` 看到该 caller 后必须跳过其内部 `$mc-update` 第 2 步（上游已经执行），只做主线回顾、幂等 handoff 与状态同步；手工 standalone `$session-new` 才执行自己的 `$mc-update`。
- 子 skill 不再次启动上游 finalizer；上游在 `session-new` 返回后直接结束当前单-plan 收尾。
- halt/无实质进展时跳过 mc-update 与 pin，session-new 只固化中断现场。
- `today-loop` 只有 PASS plan 要求 reset/finalizer 各一次；REWORK/HALTED/WAIT_HUMAN 可以在完整 finalizer 前终止，并按上一条只做必要 handoff。总 loop 不再追加第二套 finalizer。

## 6. 触发与失败口径

`today/free/mc-update/session-new/pin/today-loop` 均为 manual-only，`allow_implicit_invocation:false`。缺母本=`MASTER_NOT_FOUND`；缺合格 reviewer=`BLOCKED_REVIEWER_UNAVAILABLE`；授权哈希不符=`AUTHORIZATION_INVALID`；契约字段不全=`CONTRACT_INVALID`。任何一种都 fail-loud，不猜默认、不绕路。

