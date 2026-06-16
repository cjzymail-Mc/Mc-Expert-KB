# agent-teams.md — Claude Code Agent Teams 机制核实

> KB 事实手册。**核实日期：2026-06-01**（来源：官方文档 code.claude.com/docs/en/agent-teams + 本地 `claude --help`）。
> ⚠️ **易过期**：Agent Teams 仍是 **experimental**、env 开关、版本门控（v2.1.32+）——机制/字段/限制可能随版本变。引用前对照当前 `claude --version` 与官方文档复核。
> 用途：Stage 3「mc-expert 进 Agent Team」的前置事实，避免反复查询。

## 决定性结论（直接关系 KB 设计）

- **teammate 可引用任一 scope 的 subagent 定义：project / user / plugin / CLI。** 原文 *"reference a subagent type from any subagent scope: project, user, plugin, or CLI-defined"*。
- → **`mc-expert`（repo 内 `.claude/agents/`，project scope）无需重构成 user 级即可当 team 成员**。Stage 1 的位置决策存活到 Stage 3。
- **唯一约束 = discovery 不变**：project-scope 要被发现，team **lead 的 session 必须在 `Mc-Expert-repo` 内（或其下）启动**。想"从任意 repo 召集团队顺手带它"才需 user/plugin scope → 回到 3 账号 junction 痛点（"全局"~/.claude 仅覆盖 yk）。权衡未变，位置廉价可逆。

## 成员定义怎么生效

- spawn 时自然语言指定 agent type；该定义 **body 追加进 teammate system prompt（不替换）**，honor 其 `tools` allowlist + `model`。
- ⚠️ **`skills` / `mcpServers` frontmatter 当 teammate 时不生效**（teammate 从 project/user settings 加载 skills/MCP，同普通 session）。mc-expert 未用这俩 → 无影响。
- `SendMessage` + task 管理工具对 teammate **永远可用**，即便 `tools` 收窄。

## 自动对话机制

- **Mailbox（`SendMessage`）**：消息自动投递给收件人，lead 不需轮询；teammate 空闲自动通知 lead。点名发给单个 teammate；群发 = 每人各发一条。
- **共享 task list**：三态（pending / in-progress / completed）+ 任务依赖；依赖完成自动解锁。认领用文件锁防竞争。可要求 teammate 先 plan approval（lead 自主审批，可在 prompt 给审批标准）。

## 状态文件（自动生成，勿手改/预写，会被覆盖）

- team config：`~/.claude/teams/{team-name}/config.json` —— `members` 数组：每个 teammate 的 name / agent id / agent type。teammate 读此文件发现彼此。
- task list：`~/.claude/tasks/{team-name}/`。
- **无 project 级等价**：`.claude/teams/teams.json` 不被识别为配置，按普通文件处理。
- ⚠️ 注意这些 runtime 状态落在 `~/.claude` = yk 单账号；跨账号运行 team 时 state 也是 per-account。

## 启用 + 版本

- env `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`（shell 或 settings.json `"env"`）。
- 需 **v2.1.32+**。默认关闭。

## ⚠️ Windows 10 硬约束（本机相关）

- **split-pane 分屏 teammate 需 tmux 或 iTerm2；Windows Terminal / VS Code 集成终端 / Ghostty 不支持。** 本机走默认 **in-process 模式**（任意终端可用：`Shift+Down` 切 teammate、Enter 看其 session、Esc 打断、`Ctrl+T` 切 task list）。
- `teammateMode` 可在 `~/.claude/settings.json` 设 `"in-process"` / `"tmux"` / `"auto"`（默认 auto：在 tmux 内则分屏，否则 in-process）。

## 其它实验性限制

- 一次只能一个 team；无嵌套团队（teammate 不能再 spawn team/teammate，只有 lead 管理）。
- lead 固定：创建者终身为 lead，不可转让/提升 teammate 为 lead。
- in-process teammate **不能 `/resume`/`/rewind` 恢复**（恢复后 lead 会去找已不存在的 teammate → 让它重新 spawn）。
- 权限在 spawn 时定（继承 lead），spawn 后可改单个，但不能 spawn 时设 per-teammate。
- 清理必须由 lead 跑（`Clean up the team`），且需先 shutdown 所有 teammate。
- **崩溃/中断的 team 会在 `~/.claude/teams/{name}/config.json` 留残留状态 → 同名重建会撞车**；重启换个新 team-name（如 `excel-skill` → `excel-skill-2`）避开残留 config。〔Agent-4 mc-debug03 实测〕

## 新手 FAQ（2026-06-02 补，首次实测 + 官方文档核实）

> 来源：官方 `code.claude.com/docs/en/agent-teams` 全文 + 本机 `claude --version`(2.1.159)/`--help`。首次用 team 最典型的几个入门疑问，避免重查。

**Q1 · `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` 开了会自动组队 / 影响日常吗？`=1/2/3` 是数量吗？**
- **不自动组队**。官方原文：*"In both cases, you stay in control. **Claude won't create a team without your approval.**"* 触发只有两种、都要你点头：你主动要，或 Claude 提议→你确认。日常普通对话不会自动变 team。
- 这只是 **feature gate（能力解锁）**：不开连建都建不了，开了也只是待命、不主动触发 → **对不用 team 的日常工作基本无影响**。
- **`1` = 布尔开关（on），不是 team 数量**；文档通篇只给 `"1"`。数量另有硬限：**一次一队**（一个 lead 只能管一个 team），与 env 值无关。

**Q2 · lead 关掉后重启，是全新 team 吗？**
- 是。`lead 固定（终身绑创建会话）`+ `in-process teammate 不能 /resume/rewind` → **关掉=整队作废，下次启的是全新 team**。
- 兜底：在任务文件夹建 `progress.md`，**由 lead 当唯一写手**（teammate 每完成一步经 mailbox 汇报、lead 汇总落盘；只读角色保持只读不自己写文件）。续的是**工作内容/进度**，**续不回活 team 状态**（mailbox/task list 不恢复）。

**Q3 · team 的 token 算谁的？mc-migrate 能换账号付费吗？**
- 一个运行中的 CC 会话只认**一套登录凭据 = 一个账号**；teammate 是 in-process 实例、**共享 lead 进程的账号** → **整队 token 全记在 lead 登录的那一个账号上**。
- **mc-migrate 救不了**：它复制的是 `~/.claude/projects/` 的**聊天记录（会话历史）**，是"跨设备接着聊"，**不改哪个账号付费**。
- 想用另一账号 token：**另开一个会话用那账号登录 = 另一个独立 lead/team**（两窗口=两 team，可分担 token）。同一 team 内无法混账号。

**Q4 · lead 没有 agent md，怎么控制它的行为/放权深度？**
- lead 行为只有两个承载位（都是**软门**，靠遵守）：① **目标 repo 的 `CLAUDE.md`**（持久、每会话自动加载，写硬约定）；② **建队 prompt**（单次任务级）。
- 真·**硬门**只有两处：**permission settings**（harness 层卡工具调用）+ 对 teammate 要求 **plan approval**（lead 批了才动手；可在 prompt 给审批标准，如"只批含测试覆盖的 plan"）。
- 不放权：CLAUDE.md/prompt 写"每决策点停下问用户、coder 改动必须批 plan" + permission 不预批高风险；放权：写"lead 自主审批/派活，仅连失 2 次或高风险上报"。

**Q5 · teammate 能跑非 Claude 模型（智谱 GLM 等）吗？**
- **不能**。①CC 的「3P providers」仅 **Bedrock/Vertex/Foundry**，且都是**托管 Claude** 的云，不是跑 GLM 的口子；②teammate 的 `model` 只认 Claude 档位（sonnet/opus/haiku 别名或 Claude 全 ID；feature request #34821 求自定义别名=现不支持）；③provider 是**会话/进程级**设置，in-process teammate 共享 lead 进程 → **整队同一 backend，无法一队混 Anthropic+智谱**。
- 用智谱只能：(a) `ANTHROPIC_BASE_URL` 指 OpenAI 兼容网关换**整个会话**（实验性 team 跑非 Claude backend 无支持、脆）；(b) 跨工具手工编排（Continue+智谱，在 team 之外）。

**Q6 · team 和 worktree 什么关系？**
- **正交**。worktree=git 多工作目录/分支隔离；team=多 Claude 会话协作。可任意组合：worktree 内可跑 team 也可跑单会话；team 也可不开 worktree。多 feature 并行→开多 worktree（git 隔离），**是否每个配 team 看该 feature 是否需多 agent**，非必须。不同 worktree=不同会话=各自可有独立 team（不违反"一次一队"）。

**Q7 · teammate 默认用什么模型？怎么省 token？**
- teammate **不默认继承 lead 的 `/model`**；默认模型在 **`/config` 的「Default teammate model」**设（可选"跟 lead 当前模型"）。想让某 teammate 固定走 sonnet 省 token 在这里调，不必每次写进 prompt。

## 与 subagent 的取舍（一句话）

subagent = 单 session 内、只向主 agent 回报、主 agent 管全部、token 低；agent team = 各自独立 context、teammate 互发消息、共享 task list 自协调、token 显著更高。**需要互相讨论/挑战/自协调才上 team，否则用 subagent。**

## solo vs 冷启动 team（什么时候**别**起队，2026-06 实战）

- **握全量交接（team-progress 自足）+ 工作主体是直写代码 + 风险 COM 自检 → 优先 solo，别为"该用 team"另建冷启动 team。** spawn agent 每次冷启动、重推已有上下文，是最贵的路径；交接已自足时再起队 = 纯浪费。〔Agent-4 2026-06-03：旧 team 的 coder 正是冷启动卡死在 COM 阻塞，本会话 solo 反而两步跑通〕
- 判据（全中才 solo）：① 已握全量上下文（交接自足 / 决策全锁，不必重跑 planner/mc-expert）；② 工作主体直写代码 + 自检，编排复杂度低。**反之值得 team**：上下文需多源汇聚 / 需并行多角色 / 决策未定需 mc-expert 挑战。
- solo 也守 lead 职责：维护 team-progress 落盘、COM 套 20-30s 硬超时、连失 2 次 CUTOVER。
- **关键验收门：solo 干多级验收时，每个 L 门交用户前先派 `mc-expert` 带验收背景陪审**——实证抓到过 lead 漏的 chart `.rels` 红线；mc-expert 标「必须补的动作」按阻塞项处理。〔Agent-4 `keygate-mc-expert-jury`〕

相关：[[repo-map]]（Stage 3 指针）、[[decisions/orchestrator-route]]（编排权留主 Claude，team lead 不等于放权）、agent 本体 `.claude/agents/mc-expert.md`
