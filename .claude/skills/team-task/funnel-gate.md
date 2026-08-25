# team-task funnel gate（P0-P6 单一细则）

> 本文件只承载漏斗状态、问卷、合同块与路由判据；执行法律仍以 `SKILL.md` 为准。所有 ID/状态字段逐字写盘，禁止靠会话记忆补。
> 风险准入与增强终审共享权威：`D:/Downloads/Mc Claude Code Workshop/Mc-Expert-repo/.agents/mc-expert-common/review-contract-v2.md`；本文件只保存 team-task 的状态投影，不复制八面审计正文。

## 1. P0：source、run 与归档

### 1.1 source block

用户可直接在 `team-task.md` 的「本次任务」写零散 prompt。P0 把最后一段尚未标记的非空原文**只加包围标记、不改正文**：

```md
<!-- team-task-source id="src-1234abcd" sha256="1234abcd…" status="open" -->
<用户零散 prompt 原文>
<!-- /team-task-source -->
```

- hash = source 原文 UTF-8、CRLF→LF、只裁掉首尾空行后的 SHA-256；`id=src-<前8位>`。
- 已有显式 source 必须恰好一对起止标记，id/hash 与重算一致。一个 id 多块、标记嵌套、frozen 后正文变化均 fail-loud。
- 若最新 source 已有 frozen contract 且相应 progress 为终态，又没有新的未标记非空原文，则报告“没有新任务”，不得重跑旧合同。
- legacy 首跑只包装「本次任务」中排除既有 `team-task-contract` 后的活跃原文；无法无歧义区分历史与本轮时停问，不吞整份文件。

### 1.2 run identity 与初始化顺序

`run_id=YYYYMMDD-HHmmss-<source_sha前8位>`；重入复用盘上 run_id，不重新生成。顺序固定：

| 现有根 team-progress | 动作 | 是否可写新 run |
|---|---|---|
| 同 run_id + source_block_id，ACTIVE | 按阶段续跑；再核 contract_id | 是，限当前 run |
| COMPLETE / WAIT_HUMAN / HALTED | 先复制到 `team-progress/team-progress-NNN.md` 并验证，再初始化 | 是 |
| 非空且无合法终态、或 identity 不一致 | KO `OLD_RUN_UNCLOSED` | 否 |
| 不存在/空骨架 | 直接初始化 | 是 |

归档失败不得重置根文件。`WAIT_HUMAN` 是合法归档终态，但新任务启动前必须把待人工项浮给用户；若它仍阻断新任务则按旧 run 未收口处理。

### 1.3 team-progress 头与骨架

```md
# team-progress
> run_id: 20260825-120000-1234abcd
> source_block_id: src-1234abcd
> contract_id: pending
> run_status: ACTIVE
> author_runtime: pending
> risk_class: pending
> risk_owner: pending
> runtime_policy: pending
> risk_escalation: NONE
> 漏斗: P0✓ P1· P2· P3· P4· P5· P6·
> P1已核事实: pending

## 漏斗默认·待确认
## 自主裁决(B)
## OPEN_BLOCKERS
## PENDING_HUMAN_NONBLOCKING
## 进度日志
## 当前现状
## 下一步
## 卡点
## 收尾复盘
- 漂移苗头与纠正来源 + 陪审触发/跳过原因：
```

阶段只可单向推进；P2 可停在 NEED_INPUT，P6 才可把 run_status 改为终态。重入矩阵：P1✓不重查；P2 NEED_INPUT 只回收问卷；P3✓须找到匹配 frozen contract；P4/P5✓须找到五字段路由记录，否则退回该阶段，不凭文字猜。

### 1.4 P0.5 人工风险准入

P1 前必须把下列 envelope 落入 progress；它随后是 frozen contract 的承重字段：

```text
author_runtime=NATIVE_CODEX|CODEX_GLM|NATIVE_CLAUDE|CLAUDE_GLM|OTHER
risk_class=MEDIUM|HIGH
risk_owner=USER
runtime_policy=GLM_ALLOWED|NATIVE_ONLY
risk_escalation=NONE|HIGH_SUSPECTED
runtime_evidence=<当前 provider/config 一手证据或 USER_CONFIRMED>
```

机械规则：

1. 风险分类只能由用户给出；缺失即 `WAIT_USER_RISK_CLASSIFICATION`。AI 可把 MEDIUM 标 `HIGH_SUSPECTED`，不可把 HIGH 降级。
2. `MEDIUM` 只能配 `GLM_ALLOWED`，`HIGH` 只能配 `NATIVE_ONLY`；不一致即 `RISK_ENVELOPE_INVALID`。
3. `CODEX_GLM|CLAUDE_GLM + HIGH` → `CUTOVER_NATIVE_REQUIRED`，P1-P6 不得开始。GLM+MEDIUM 命中共享 contract §3.2 任一机械疑似否决器，也标 `HIGH_SUSPECTED` 并停；不得靠加厚同栈陪审继续。
4. runtime 不从模型自称/文风猜。没有稳定一手 route 时由用户确认并记 `USER_CONFIRMED`；unknown 不静默当原生。
5. 风险与 runtime 在 run 内冻结；运行中命中动态升级条件时当前授权失效，回到用户重新分类/切原生门，不在原 B 授权内偷扩。

## 2. P2：问卷协议

路径固定为 `team-progress/questionnaire-<run_id>.md`；同 run 只一份。格式：

```md
---
run_id: 20260825-120000-1234abcd
source_block_id: src-1234abcd
status: OPEN
created_at: 2026-08-25T12:00:00+08:00
---

## Q01
type: FACT
required: true
blocking: true
default: null
question: <一次说清>
answer:

## Q02
type: PREFERENCE
required: false
blocking: false
default: <安全默认>
question: <一次说清>
answer:
```

机械规则：

1. `type∈{FACT,PREFERENCE}`；FACT 必须 `default:null`。scope、done_when、权限、外部真相身份即使写成 PREFERENCE 也按 FACT 阻断。
2. `input_policy=initial`：生成/复用 OPEN 问卷并返回 NEED_INPUT；不得当场默认。
3. `answered`：逐题读 answer；任何 blocking 空答继续 NEED_INPUT。全部阻断题有答后置 `status: ANSWERED`。
4. `continue-defaults`：只给空答 PREFERENCE 填 default，并在 team-progress「漏斗默认·待确认」逐条记录；FACT 仍空则保持 OPEN/NEED_INPUT。若剩余项全闭合，置 `status: DEFAULTED`。
5. 无墙钟 timeout；半填只处理未答项，不整份作废。合同冻结后问卷只可 ANSWERED/DEFAULTED；新 run 发现旧问卷标 SUPERSEDED，不覆盖。

## 3. P3：合同 profile、标记与幂等

profile=full 只在任一硬触发成立：多依赖检查点、多个执行体存在实质依赖/交接、跨会话接力；否则 minimal。profile 只调合同厚度，不降四态/负例/独立门。

```md
<!-- team-task-contract run_id="20260825-120000-1234abcd" contract_id="ctr-89abcdef" source_block_id="src-1234abcd" status="frozen" profile="minimal" -->
### 冻结合同（2026-08-25）
<合同正文>
<!-- /team-task-contract -->
```

- `contract_id=ctr-<合同正文规范化 SHA-256 前8位>`；起止标记成对。
- 写前按 `run_id+source_block_id` 搜索：0 块才追加；1 块且 frozen 返回 REUSED；>1 块或字段不一致 fail-loud。
- minimal 必含：终态、本轮做/不做、允许写/只读/禁止、红线、P0.5 风险 envelope、至少一条带验证的 done_when。
- full 使用 SKILL 附录 7 块；原 source block 永不覆盖/删除。P3 完成后 progress 的 contract_id 必须与块一致。

## 4. P4：二轴路由（不得合成一个总分）

### 4.1 coordination_score → 实际拓扑

每轴只取 0/1/2，并把证据路径写在表旁；判不动标 `SUBJECTIVE`，A 必问，B 也须在 P5 前让用户看到推荐依据。

| 轴 | 0 | 1 | 2 |
|---|---|---|---|
| C1 可分所有权 | 单一串行改面 | 2 个近独立改面 | ≥2 个清晰文件/模块所有权且需协调 |
| C2 规划不确定性 | repo 有完全同构先例 | 有相似先例需局部裁量 | 无先例/多方案/核心接口设计 |
| C3 依赖图 | 单检查点 | 2-3 串行检查点 | ≥4 或存在多前置依赖 |
| C4 交接需求 | 单执行体可闭合 | reviewer 事件即可 | 多执行体有实质交接/共享状态 |

映射：0-2→T3；3-5→T2；6-8→T1；边界疑义取更高协作档。硬覆盖：C2=2 且涉及核心接口→至少 T1；C1=0 且 C3≤1→不得只因风险高升 T1。用户可手动覆盖，记录原因。

### 4.2 assurance_profile → 复核强度

以下任一命中即 ENHANCED，否则 BASE：用户风险 HIGH；核心文件/公共 schema/API；共享母本/junction/全局 skill·agent·hook·protocol；数据迁移或恢复；权限/安全/生产发布/对外交付；真实数据不可逆风险；语义/视觉残差无法机械证明；同路径已有假 PASS/范围漂移；runtime=GLM/other/unknown；跨 repo/runtime/environment 接力。

ENHANCED 只增加 coverage map、负例、未判范围、独立/必要跨栈或人工终签；**不得据此增加常驻实现者或改 coordination_score**。

### 4.3 T4-AUTO 的记录

T4 是 `routing_mode=AUTO`，实际拓扑仍是 T1/T2/T3。P5 后必须有：

```text
routing_mode=AUTO|MANUAL
recommended_topology=T1|T2|T3
realized_topology=T1|T2|T3
assurance_profile=BASE|ENHANCED
drive_mode=A|B
author_runtime=NATIVE_CODEX|CODEX_GLM|NATIVE_CLAUDE|CLAUDE_GLM|OTHER
risk_class=MEDIUM|HIGH
risk_owner=USER
runtime_policy=GLM_ALLOWED|NATIVE_ONLY
risk_escalation=NONE|HIGH_SUSPECTED
```

AUTO 默认令 realized=recommended；lead 后续因新证据改变 realized 时，先更新 P4 证据与留痕。A 模式须用户确认变更；B 可自主改但不能降低已命中的 assurance_profile。

## 5. P5/P6 硬线速查

- B 前置：frozen contract + OPEN_BLOCKERS 空 + 阻断 FACT 全闭合；`continue-defaults` 不是 B 授权。
- T2 没有常驻 planner，但负例/四态取证门必须一次性 planner；spawn 失败不得让 coder/mxp 自报替代。
- 关键终签、迁移、权限/发布、schema/API 冻结独立复核失败 → `PENDING_INDEPENDENT_REVIEW / WAIT_HUMAN / BLOCKED`，不可 PASS。
- ENHANCED 终签必须 fresh 一次性 mc-expert 按共享 `review-contract-v2.md` 执行 `ENHANCED_FINAL`；常驻 reviewer/开工前 HISTORY 不抵扣。只认 `GO + HASH_VALIDITY=VALID + UNVERIFIED_SCOPE=NONE + 八面全过`；修后新 hash 必须重审。
- 收尾先写 run_status 终态，再按 SKILL 的 mc-update→pin→session-new 预判 loop；下个 run 的 P0 才归档。
