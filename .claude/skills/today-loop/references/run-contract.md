# Claude `/today-loop` Run Contract v1

本合同是 Wave A 的 repo-local 候选。它约束一次 `/goal` 驱动的多-plan运行；不授权写外部 Claude 母本、全局配置、正式 memory 或其他 repo。

## 1. 冻结输入

启动前生成并由用户一次审核：

- `contract.json`：目标、边界、预算、人工门和终态证据。
- `plans.json`：有序 plan 列表及依赖，只读。
  - 每个 plan 的冻结字段：`id/title/depends_on/done_when/reference(可选)`。
  - `done_when`：做完长什么样——**结果状态，非动作清单**（如"X 文件存在且首字节为 50 4B"，不是"改 X 文件"）。它是 JURY 判 PASS 的 plan 级客观尺度（SKILL.md §3.5：reviewer 判 PASS 必须核对 done_when 是否满足，缺它不得判 PASS）。脚本 `init` 对 `done_when` 做**非空 fail-fast 校验**——缺失/空串/纯空白直接 reject（报 `PLAN_DONE_WHEN_MISSING`），在 hash 冻结前友好拦截；脚本只校验非空、不判语义质量（语义仍归 reviewer）。
  - `reference`：参照物路径或描述（标准样板/目标格式），长链/批量任务价值高，低风险单点可省略——**可选、缺省空串**，脚本不强制。
- `todays-task.md`：自然语言任务的规范化版本，只读。

`contract.json` 必填字段：

```json
{
  "schema_version": 1,
  "run_id": "unique-run-id",
  "mode": "autopilot",
  "objective": "one sentence objective",
  "plan_file": "repo-relative plans.json",
  "run_dir": "repo-relative run directory",
  "allowed_paths": ["repo-relative/path"],
  "read_only_paths": ["repo-relative/path"],
  "forbidden_actions": ["delete", "push", "external-delivery"],
  "human_gates": ["four-red-lines", "scope-expansion"],
  "budgets": {"max_plans": 3, "max_consecutive_failures": 2},
  "terminal_evidence": ["[repo-relative]/runs/<run_id>/state.json", "[repo-relative]/runs/<run_id>/events.jsonl", "[repo-relative]/runs/<run_id>/handoff.md"]
}
```

> **`terminal_evidence` 必须写 repo-relative 全路径（含 run 目录前缀），不能写裸文件名**（2026-07-21 修订，源 Phase 4 run `20260721-102151-phase4` 在 `complete` 步踩坑）。
> - 脚本 `complete`（`today-loop-state.ps1` 第 168 行）对每条 terminal_evidence 调 `ContractPath` 解析成 `$root/<路径>`，再要求 `IsUnder $run`（必须在 run_dir 内）。
> - 裸文件名 `state.json` 会被解析到 repo 根目录 `$root/state.json`，不在 run_dir 内 → 抛 `TERMINAL_EVIDENCE_OUTSIDE_RUN` → run 转 `wait_human`，且 hash 已冻结无法自救。
> - 正确写法：`[repo-relative]/.../runs/<run_id>/state.json` 这种带 run 目录前缀的全路径（与 Phase 1 fixture 脚本 `run-fixtures.ps1` 的写法一致）。
> - **变体二（2026-07-25 加，源 Wu Prj 首次跨 repo 实战踩坑）**：`terminal_evidence` 也不能指向 **run dir 外的真实交付物**——即便它在 `allowed_paths` 内、是任务的真实产物。如产物落在 `<repo>/Wu Prj Runbook/README.md`（run dir `mc-progress/loop-runs/<run_id>/` 之外、但属合法 allowed_path），`complete` 仍判 `IsUnder $run` 失败 → `TERMINAL_EVIDENCE_OUTSIDE_RUN`。**根因同变体一**：`complete` 要求 terminal_evidence 物理在 run dir 内，与"交付物落在哪"无关。**正确做法**：真实交付物落 run dir 外无妨，但在 **run dir 内放一份交付清单文件**（如 `deliverables.md`，列真实产物路径 + 存在性校验），把 `terminal_evidence` 指向这份 run dir 内的清单——既过 `IsUnder $run` 校验、又承载真实交付物指针。kickoff 写 contract 时 terminal_evidence 就该这么设计，别等 run 全 plan passed 后才发现 `complete` 卡壳（hash 已冻结无法自救，只能重置 state 重放 checkpoint 补登）。

硬约束：合同中的全部路径必须是 repo-relative（仓库相对路径），拒绝绝对路径；所有路径既做词法边界检查，也解析已存在祖先的 junction/symlink 真实目标，目标逃出 repo 即拒绝。`allowed_paths`、`forbidden_actions`、`human_gates`、`terminal_evidence` 不得为空，`read_only_paths` 必须显式提供；只读路径不得被可写路径覆盖。失败预算固定为 2，模型不得放宽；运行中新增权限硬依赖直接 `WAIT_HUMAN`，不得弹阻塞权限框。

> **`allowed_paths`/`read_only_paths` 是字面前缀目录语义，不支持 glob 通配符**（2026-07-22 修订，源首次实战踩坑）。
> - 脚本 `init`（`today-loop-state.ps1`）对 allowed_paths/read_only_paths 用 `IsUnder` 做**字面前缀匹配**（`$c -eq $p -or $c.StartsWith($p+[Sep])`），完全不认 `*`/`?`/`[` 通配符；`ContractPath`→`ResolveSafe` 碰到带 `**` 的目录会在 `Test-Path -LiteralPath` 处失败。
> - 写 `"allowed_paths": ["Debug/today-loop/run1/**"]` 会触发 `OUTSIDE_ALLOWED_PATHS`（preflight）或更早的解析失败，run 卡死 `wait_human` 且 hash 冻结无法自救。
> - **正确写法：要授权/约束整棵子树，写目录本身**（`"Debug/today-loop/run1"`），前缀匹配天然覆盖该目录下所有文件。
> - `init` 已加 glob meta-char 校验：allowed_paths/read_only_paths 含 `*`/`?` 时直接 reject 报 `CONTRACT_PATH_GLOB_UNSUPPORTED`（fail-loud，提示写字面目录），在 hash 冻结前友好拦截。

> **`human_gates` 只放机械动作名，不放语义概念**（2026-07-23 修订，源实战频停根因，plan 自主轴升级C2）。
> 脚本 `preflight-check`（`today-loop-state.ps1`）只做 `ProposedAction 字符串 == human_gates 项` **精确匹配**转 WAIT_HUMAN——即只有提交的 action 名（如 `delete`/`push`）等于数组某项才机械触发。
> 把 `route-decision`/`batch-after-single-verify`/`scope-expansion` 这类**语义概念**塞进 human_gates 是反模式：脚本精确匹配不上语义概念、**不会机械触发**，但模型读到 contract 列了它，会**过度自觉**把"我在做这类决策"当中途停的理由——这正是实战中 today-loop 频繁停的放大器。
> 正解：
> - **机械动作**（`delete`/`push`/`external-delivery` 等有对应 ProposedAction 调用点的）才进 human_gates（多数已被 `forbidden_actions` 覆盖）。
> - **路线二选一 / 批量前验证**这类语义决策，要么 kickoff 一次性问清（事实缺口收 kickoff，§2 step2/step6），要么靠 autopilot + mc-expert 默认推荐照办 + 攒收尾自主裁决清单（SKILL.md §3.0a）。
> - 四红线由独立纪律管（不进 human_gates，命中直接 redline）；scope 扩张由 contract 边界 + WAIT_HUMAN 管。
> - **如无对应机械 action 调用点，不为此扩建控制流**（codex 陪审第6点措辞）——语义门靠 SKILL.md 纪律 + 用户侧 contract 纪律，不靠脚本拦。

初始化把 `contract.json` 与 `plans.json` 的 SHA-256 写入 `state.json.frozen_inputs`。除 `show/recover` 外，每个动作先重算并比对；任一输入漂移都 fail closed。`allowed_paths/read_only_paths/forbidden_actions/human_gates/terminal_evidence` 全量持久化到 state，不靠后续聊天记忆。

## 2. 每轮恢复句

每个 `/goal` turn 开头必须先调用 `show`，并在对话中复述：

`run_id | run status | current plan | last verdict | consecutive failures | objective | allowed paths | human gates`

随后才允许 `select`。已 `passed` 的 plan 禁止重跑；存在 `running` plan 时恢复它，存在未验收证据时从 SELF_CHECK/JURY 续，不凭聊天记忆猜阶段。

## 3. 控制流

`SELECT → PREFLIGHT → BUILD → SELF_CHECK → JURY → CHECKPOINT`。

- 一个 turn 最多启动一个 plan。
- PREFLIGHT 必须调用 `preflight-check`，向状态机提交 repo-relative target 与 proposed action；脚本机械核对 allowed/read-only/reparse 边界、禁止动作和人工门。没有 `preflight_passed` event 就不能 advance 到 BUILD；越界由脚本直接转 `WAIT_HUMAN`。
- BUILD 调 `today-core`，caller context 固定为 `caller_id=today-loop`。
- SELF_CHECK 必须给出结构证据；JURY 必须由独立 reviewer 给出 `PASS | REWORK | WAIT_HUMAN`。JURY 没有通用 `advance` 出口；只有 `review-pass` 能校验 verdict 文件（PASS、plan id 匹配、reviewer 与 executor 不同）并进入 CHECKPOINT。
- reviewer 尚在运行或短轮询无结果是 `PENDING`，不算失败；hard deadline 后仍无有效 verdict 才进入 `WAIT_HUMAN`。
- PASS 只接受实际存在的 evidence 文件，且前置状态必须是 reviewer PASS + CHECKPOINT；成功会把连续失败清零。
- 第一次失败进入 REWORK；第二次连续失败进入 HALTED，不得第三次尝试。

## 4. 唯一终态

- `COMPLETE`：全部 plan 为 `passed`，并逐项确认 `terminal_evidence` 是 run dir 内实际存在的文件；默认必须含 handoff。
- `WAIT_HUMAN`：权限越界、显式人工门、无有效 reviewer verdict、schema 不可自愈。
- `HALTED`：两连败、四红线、不可恢复错误。

只有上述三态允许 `/goal` 结束。checkpoint 不是 Goal 终态；context 切换、三终态时才写完整 handoff。

## 5. 写入纪律

正式 `state.json` 只由 `today-loop-state.ps1` 写入；模型不得手改。每次迁移先向 `events.jsonl` append 带连续 `seq` 和完整 `state_after` 的可重放记录，再原子替换 state。若在两步之间中断，下一动作先从最后 event 恢复 state；event 缺号、损坏或 state 超前一律 fail closed。合同和 plans 在 run 中只读并受 hash 绑定。

---

## Changelog

- **2026-07-21**：修订 §1 的 `terminal_evidence` 示例（裸文件名 → repo-relative 全路径）+ 加防坑说明。源 Phase 4 run `20260721-102151-phase4` 在 `complete` 步踩坑：contract 照旧示例写了裸文件名 `state.json`，但脚本 `complete`（`today-loop-state.ps1` 第 168 行）用 `ContractPath` 把裸文件名解析到 repo 根 `$root/state.json`、要求 `IsUnder $run`，根目录不在 run_dir 内 → 抛 `TERMINAL_EVIDENCE_OUTSIDE_RUN` → run 转 wait_human 且 hash 冻结无法自救。一手核清：本示例原写法与脚本 complete 校验逻辑 + Phase 1 fixture 脚本写法（全路径）**三者长期不一致**，且 Phase 1 的 15 fixture 无阳性样本覆盖"裸文件名写法"（测试盲区），故从未被抓出。本次修订对齐三处、消除盲区。备份 `run-contract.md.bak-pre-terminal-evidence-fix-20260721`。
- **2026-07-22**：§1 加 `allowed_paths`/`read_only_paths` 不支持 glob 通配符的防坑说明 + 脚本 `init` 加 `CONTRACT_PATH_GLOB_UNSUPPORTED` fail-loud 校验。源 today-loop 首次实战（claude-glm 账号）：kickoff 时把 `"Debug/today-loop/run1/**"` 写进 allowed_paths，`IsUnder` 字面前缀匹配不认 `**`、`ResolveSafe` 的 `Test-Path -LiteralPath` 对带 `**` 目录失败 → run 在 preflight 卡死 `wait_human` 且 hash 冻结无法自救。一手核清：与 2026-07-21 terminal_evidence 裸文件名盲区**同性质**（contract 字段语义与脚本校验不符 + 15 fixture 无 glob 阳性样本）。本次：脚本 init 在 allowed/read_only 路径上 reject 含 `*`/`?` 的输入（fail-loud 友好化，hash 冻结前拦截）+ 补 F16 fixture 覆盖"glob 入参被 init 拒"。注意：`**` 是用户/kickoff 时自己写进 contract 的（run-contract 示例与 15 fixture 全写字面目录），故本修订是"脚本对合理输入 fail-loud + 文档说清语义"，非"文档曾误导"。母本脚本备份 `today-loop-state.ps1.bak-pre-glob-fail-loud-20260722`（Mc-Expert-repo）。
  - **校验集只含 `*`/`?`，不含 `[`（关键修订，同日）**：初版把方括号 `[` 也当 glob 字符类 reject，结果 16 个 fixture 中 14 个被误伤——因为本 repo 文件夹名 `[feature-07-codex-workshop-Adv]` 的方括号是**合法目录名字符**，不是 glob 通配符。`[` 在 Windows 路径里太常见（学习 repo 的 `[feature-XX-...]` 命名约定），无法可靠区分"目录名字符"与"glob 字符类"；而真正的 glob 字符类（`[abc]`）在 allowed_paths 语境极不可能出现。故收窄校验集为 `*`/`?`。呼应 memory `glob-bracket-dirname-needs-escaping`（方括号目录名在 Glob/Grep 里的兄弟坑）。F9（reparse 阳性对照）在 Mc-emoji repo fail 是环境前置（本 repo `.agents/skills/free` 是普通目录非 junction），与本次改动无关；在 `.agents/skills/` 为真 junction 的 repo F9 会 PASS。
- **2026-07-25**：§1 terminal_evidence 防坑说明加「变体二：run dir 外的真实交付物（即便在 allowed_paths 内）也不行」。源 today-loop 首次跨 repo 实战（Wu Prj，纯文件归档非 git repo）：kickoff 把 `terminal_evidence` 指向 run dir 外的真实产物 `Wu Prj Runbook/README.md`（属合法 allowed_path），run 全 plan passed 后 `complete` 仍判 `IsUnder $run` 失败 → `TERMINAL_EVIDENCE_OUTSIDE_RUN`，hash 冻结无法自救，只得重置 state 重放 4 plan checkpoint 补登。一手核清：与 2026-07-21 裸文件名变体**同根**（complete 要求 terminal_evidence 物理在 run dir 内），只是变体一指 repo 根、变体二指 allowed_path 内的 run dir 外路径——脚本不区分。**正解**：真实交付物落 run dir 外无妨，run dir 内放一份 `deliverables.md`（列产物路径+存在性校验）作 terminal_evidence。文档补变体二防坑说明（脚本逻辑未改——本属 contract 字段语义，kickoff 写对即可，非脚本 bug）。注意：本次 run 因 hash 已冻结、补登是重置+重放（evidence 均真实 mc-expert 陪审结论），非伪造；记录在此供后续 kickoff 设计 terminal_evidence 时避坑。
- **2026-07-25（同日·环境前置）**：SKILL.md §9 冷启动入口补「步骤 0：目标 repo 必须是 git 仓库」。源同一次 Wu Prj 实战：该 repo 无 `.git`，跑 `init` 直接 `REPO_ROOT_NOT_FOUND`（`RepoRoot` 函数硬依赖 `git rev-parse --show-toplevel`）。经用户拍板后 `git init` + 全源资料 `.gitignore`（DLP 工作电脑，源资料含受控资产严禁进版本库，git 只追踪过程文件）。一手核清：today-loop 全套文档此前零提及「repo 须 git」这个硬前置（脚本依赖、文档空白），本次补齐。关联：纯文件归档类 repo 上 git 要先 ignore 源资料，git 是本地版本控制不 push 不外泄、与 DLP 透明加密两套独立机制。
