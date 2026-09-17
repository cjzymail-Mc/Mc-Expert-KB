# mc-expert review contract v2（共享母本）

> 物理母本：`D:/Downloads/Mc Claude Code Workshop/Mc-Expert-repo/.agents/mc-expert-common/review-contract-v2.md`。Claude、原生 Codex、Codex-GLM 的 mc-expert 只做薄适配；增强终审口径以本文件为唯一权威。reviewer 只读，不实施修复。

## 1. 两种 profile

| `REVIEW_PROFILE` | 用途 | 能否给最终放行结论 |
|---|---|---|
| `HISTORY` | 开工前路线、历史约束、失败后换路、拆分建议 | 否；只能给咨询建议，末尾写 `FINAL_REVIEW=NOT_PERFORMED` |
| `ENHANCED_FINAL` | 对冻结后的最终产物做独立工程审计 | 是，但只有所有硬门闭合时可 `GO` |

不得用一次开工前 `HISTORY` 咨询冒充最终产物陪审。问题语义涉及“最终验收 / 是否可发布 / 是否 PASS / 是否 GO / 施工方案是否完整”却未显式给 `REVIEW_PROFILE=ENHANCED_FINAL` 时，返回 `ENHANCED_FINAL_REQUIRED`，不作放行判断。

## 2. 调用 envelope

所有新调用至少显式交齐：

```text
REVIEW_PROFILE: HISTORY | ENHANCED_FINAL
AUTHOR_RUNTIME: NATIVE_CODEX | CODEX_GLM | NATIVE_CLAUDE | CLAUDE_GLM | OTHER
REVIEW_TARGET: <精确文件路径、方案或范围>
PROJECT_MEMORY: <路径 + 相关完整段落> | NONE: <原因>
SEALED_DECISION_QUERY: <decision/关键词/问题> | NONE: <原因>
REVIEW_QUESTION: <一个且仅一个问题>
```

兼容边界：旧调用没有 `REVIEW_PROFILE/AUTHOR_RUNTIME` 时，只能按 `HISTORY + OTHER` 提供非放行咨询，并显式输出 `LEGACY_ENVELOPE=YES`；只要问题带最终放行语义，就必须 fail-loud 为 `ENHANCED_FINAL_REQUIRED`。

`ENHANCED_FINAL` 还必须交齐：

```text
RISK_CLASS: MEDIUM | HIGH
RISK_OWNER: USER
RUNTIME_POLICY: GLM_ALLOWED | NATIVE_ONLY
ARTIFACT_MANIFEST: <每个最终产物 path + SHA-256>
REQUIREMENTS: <冻结需求/施工授权 path + SHA-256 + 承重章节>
LIVE_BASELINE: <真实生效母本/配置/接口路径> | NONE: <原因>
VERIFICATION_EVIDENCE: <实际命令 + exit code + 原始输出/证据路径 + 阳性对照>
UNVERIFIED_SCOPE: NONE | <未验证项及原因>
```

缺字段、空值、占位符、产物不存在、hash 不符、需求未冻结、只有二手报告没有原始证据，统一返回：

```text
REVIEW_CONTRACT_INVALID missing=<字段>
BLOCKED_EVIDENCE reason=<原因>
```

## 3. 人工风险准入 + 机械升级阀

风险主判始终属于用户：`RISK_OWNER` 只能是 `USER`。一手 runtime 证据确认 `CODEX_GLM|CLAUDE_GLM` 且用户调用 `/team-task`，即按 2026-09-04 常设策略完成该冻结任务的 MEDIUM 风险评估；team-task 应在 progress 记录 `risk_source=USER_STANDING_POLICY_20260904`，不再重复询问。用户显式 MEDIUM/HIGH 则以显式值覆盖。该常设策略不扩给 `NATIVE_*|OTHER`：它们未显式分类仍等待用户。AI 只能因运行中新出现、超出入口授权的高后果事实把 `MEDIUM` 升为 `HIGH_SUSPECTED`，绝不能把用户的 `HIGH` 降为 `MEDIUM`。

### 3.1 路由矩阵

| author runtime | 用户风险 | 最低要求 |
|---|---|---|
| `CODEX_GLM / CLAUDE_GLM` | `MEDIUM` | 允许施工；最终必须 `ENHANCED_FINAL` |
| `CODEX_GLM / CLAUDE_GLM` | `HIGH` | 非法准入；`CUTOVER_NATIVE_REQUIRED`，不得继续给 GO |
| `NATIVE_CODEX / NATIVE_CLAUDE` | `HIGH` | 必须 `ENHANCED_FINAL` |
| `NATIVE_CODEX / NATIVE_CLAUDE` | `MEDIUM` | 普通任务不要求最终 mc-expert；需要路线咨询时用 `HISTORY`。命中高影响触发器才必须 `ENHANCED_FINAL` |
| `OTHER` | `HIGH` | `CUTOVER_NATIVE_REQUIRED`；必须先用一手证据确认并重登记为 `NATIVE_*`，不得仅凭 `NATIVE_ONLY` 标签继续 |
| `OTHER` | `MEDIUM` | 可按 `GLM_ALLOWED` 的较低权限路径执行；不得据此主张 native 身份 |
| 任意 | 未由用户分类 | `WAIT_USER_RISK_CLASSIFICATION` |

`RUNTIME_POLICY` 必须与风险一致：`HIGH -> NATIVE_ONLY`；`MEDIUM -> GLM_ALLOWED`。不一致即 `REVIEW_CONTRACT_INVALID field=RUNTIME_POLICY`。

### 3.2 MEDIUM 的高风险疑似否决器

用户标 `MEDIUM` 后，运行中新出现且**未被入口时冻结任务与用户授权覆盖**的下列高后果事实，任一命中都只能升级为 `HIGH_SUSPECTED` 并返回 `CUTOVER_NATIVE_REQUIRED`（GLM/OTHER）或要求原生增强终审；reviewer 不得自行降回：

1. 销毁性、不可逆或对外状态变更；
2. 权限、安全、凭据、生产配置或发布；
3. 不可逆真实数据写入/迁移/恢复/格式转换，或可回滚条件不能证明；
4. 未在冻结任务中明确授权的跨 repo 共享母本、junction、全局 skill/agent/hook/protocol 变更；
5. 高后果验收却没有可重复的机械 oracle（判定器）；
6. 架构、scope、done_when 或权威源尚未冻结；
7. 跨 runtime/provider/environment 的切换、发布或兼容承诺。

**受控可回滚例外（保持 MEDIUM）**：冻结范围内的 repo 数据写入若同时满足①原件或全量备份已验证可恢复，②写集明确并有 trace，③有确定性断言/机械 oracle，④适用的批量签字门已通过，⑤不触碰对外、DLP、权限/凭据或生产环境，则可由 GLM 在 `MEDIUM + GLM_ALLOWED + ENHANCED_FINAL` 下继续；不得仅因“真实数据写入”四字升标或再次询问用户。冻结任务已明确列出的共享资产改动且用户选择 GLM，同样视为入口已评估，但仍须备份、精确范围授权和 ENHANCED_FINAL。

复杂、文件多、耗时长本身不等于高风险；上述后果、可恢复性以及是否超出入口授权才是风险轴。

### 3.3 运行中动态升级

出现未获授权的范围扩大、外部事实无法核实、备份/恢复性失效、关键验收没有机械 verifier、同一 `failure_key` 达到入口协议的熔断阈值、独立 reviewer 阻断、最终 artifact hash 漂移时，当前准入失效：先停止相关动作，再按本矩阵重新路由。所有 live 任务入口的任务/方案熔断阈值统一为第 3 次同 key 失败；换建议、agent 或 session 不重置计数。COM 超时、reviewer transport 等基础设施重试仍按各自明确的局部阈值，不得与任务/方案预算混算。冻结任务内已知且受控可回滚的正常写入不属于动态升级。

## 4. ENHANCED_FINAL 强制审计面

reviewer 必须从**最终 artifact**与原始证据出发，不接收“作者已判断 GO”作为证据，不把历史合理性替代工程正确性。逐项给 `PASS_DYNAMIC / PASS_STATIC / FAIL / BLOCKED / N/A(reason)`：

1. **对象绑定**：实际审的是最终文件，不是摘要、旧稿或上游口述；记录 review 前后 SHA-256。
2. **身份与生命周期**：run/source/contract/artifact identity、创建/恢复/归档、终态与重入路径闭合。
3. **时序与权限**：谁在何时可读/写/授权/发布；检查先后顺序、TOCTOU（检查与使用间竞态）和 fail-closed。
4. **幂等与重试**：重复调用、断线重入、半完成状态、同一任务/方案第 3 次失败熔断不会重复写、跳门或假成功；基础设施局部重试阈值不串入任务 `failure_key`。
5. **执行者矩阵**：每条路径明确由谁执行、谁取证、谁独立终签；不存在“规范说要做但无人负责”。
6. **类型与笛卡尔积**：枚举 profile/runtime/risk/topology/status/input_policy 等组合，检查非法组合拒绝、合法组合有执行路径。
7. **接口与发现**：真实命令名、skill/agent discovery、参数、schema、junction/母本指向和消费者兼容。
8. **证据真实性**：打开实际 fixture/verifier，不按文件名猜能力；核对命令、exit code、raw output，并要求至少一个会失败的阳性对照。静态“源码里有 abort”不能冒充动态失败证据。

`PASS_STATIC` 不能满足冻结 done_when 中明确要求动态验证的条目。任何承重项 `FAIL/BLOCKED`、hash 失配、未声明的 `UNVERIFIED_SCOPE` 都不得 `GO`。

## 5. 独立性与跨栈边界

- reviewer 使用新上下文，只收冻结需求、最终 artifact、live baseline 与原始证据；不喂作者自评、上一个 reviewer 的 verdict 或期待答案。
- 同栈 mc-expert 是概率软冗余，不是确定性 verifier。确定性门由 schema、状态机、fixture、hash 和阳性对照承担。
- 最高后果任务（凭据/安全边界、不可逆真实数据、生产发布、跨账号全局母本切换）即使原生 Codex/Claude + mc-expert 已审，仍输出 `CROSS_STACK_REQUIRED`，需另一原生栈或用户最终签字。

## 6. 固定输出（ENHANCED_FINAL）

```text
REVIEW_PROFILE=ENHANCED_FINAL
AUTHOR_RUNTIME=<...>
ADMISSION=<ADMITTED | HIGH_SUSPECTED | CUTOVER_NATIVE_REQUIRED | CROSS_STACK_REQUIRED>
REVIEWED_ARTIFACT=<path> SHA256_BEFORE=<hash> SHA256_AFTER=<hash> HASH_VALIDITY=<VALID|CHANGED|MISMATCH>
REQUIREMENTS=<path> SHA256=<hash>
KB_INDEX=<path>
KB_EVIDENCE=<path | NONE: reason>

CHECKS
- object_binding: <status> <evidence>
- lifecycle_identity: <status> <evidence>
- timing_permissions: <status> <evidence>
- idempotency_retry: <status> <evidence>
- executor_matrix: <status> <evidence>
- type_cross_product: <status> <evidence>
- interface_discovery: <status> <evidence>
- fixture_truth: <status> <evidence>

FINDINGS
- P0/P1/P2: <位置 + 事实 + 影响 + 最小修复>

VERIFIED_COMMANDS=<实际命令、exit code、证据路径>
UNVERIFIED_SCOPE=<NONE | 列表>
VERDICT=<GO | GO_WITH_CHANGES | NO_GO | BLOCKED_EVIDENCE | CUTOVER_NATIVE_REQUIRED | CROSS_STACK_REQUIRED>
```

只有 `VERDICT=GO + HASH_VALIDITY=VALID + UNVERIFIED_SCOPE=NONE + 所有承重检查通过` 才是最终放行。`GO_WITH_CHANGES` 表示修后必须以新 hash 重审，不是有条件 PASS。
