# repo-map.md — 源 repo 地图 + 决策溯源

> 每 repo 一段（主题 + memory 路径 + 关键档案）。易变 domain 细节留原地，mc-expert 按需 `--add-dir` 直读，不复制进 KB。
> 路径基址：`D:\Technique Support\Claude Code Learning\`

## 3rd-ppt-prj — PPT 自动化生产线（最成熟蓝本）
- **主题**：win32com + GPT 的 PPT 分析/移植/修复流水线；orchestrator + ppt-acceptance 验收门；染色契约。
- **memory**：`3rd-ppt-prj/.claude/memory/`（25+）+ `auto-memory/`（4）+ `agents/` + `hooks/`
- **关键档案**：`project_orchestrator_upgrade.md`、`project_plan3_architecture.md`、`feedback_acceptance_gate.md`(231行)、`reference_agent_memory_design.md`、`feedback_conclusion_coloring.md`、`reference_pipeline_repair.md`

## [Agent-3 ...] Info Classifier — 信息分类/档案 archivist
- **主题**：docx/xlsx/pptx 模板填充 + mapping 三方同步 + archivist 归档分类；大量 COM/Office/Ldterm + 工作流反射。
- **memory**：`[Agent-3 ...]/.claude/memory/`（8）+ `auto-memory/`（24）
- **关键档案**：`feedback_doc_honesty_measured_vs_projected.md`、`feedback_golden_samples_admission_criterion.md`、`feedback_ui_fix_before_script_workaround.md`、`feedback_checkpoint_via_excel.md`、`feedback_docx_highlight_and_dual_gate.md`、`feedback_mapping_schema_change_3way_sync.md`

## Mc-emoji — Claude Code 学习/实验
- **主题**：CC 能力探索；权限系统实测（方案 A）；Agent Teams 教训；会话迁移工具；DLP/COM 硬规则。
- **memory**：根 `CLAUDE.md` + `.claude/CLAUDE.md`（硬规则）
- **关键档案**：`[feature-02-auto-Enter]/bypass-plan-discussion.md`、`settings-fix-plan.md`、`[feature-03-take-a-nap]/Mc未来思考3...ADV.md`、`grok-01/02-...chat.md`、`[feature-03-take-a-nap]/sub-plan-stage3-agentteam-spike.md`(Team spike：三角色工作流/落点规范/放权深度)、`grok+claude-03-...chat.md`
- **Agent Teams 机制事实**：KB 内 `references/agent-teams.md` —— 含 **「新手 FAQ」节**（2026-06-02，首次用 team 7 条入门：env=1 不自动组队/lead 一次性+progress.md/token 单账号/lead 放权深度/teammate 不能跑非 Claude 模型/team×worktree 正交/teammate 默认模型）

## 其他（按需）
- **[Agent-4] Wu Prj**：`skills/office-via-com.md`（COM 手册出处之一）
- **xiaoduo-Excel task**：Excel 任务
- **~/.claude/skills/**：14 全局 skill（office-com-helpers / inspect-*（ppt/excel/word）/ ppt-acceptance-check / excel-acceptance-check / ldterm-decrypt-images / pipeline-self-check-loop / com-survival-reflexes / read-selected-shape / team-task / claude-md-three-layer-refactor / **three-state-coloring-contract 已拆双子：`-word-only`（单通道 HighlightColorIndex）+ `-excel-only`（底纹+字色双通道，2026-06-04 落地）**…）

---

## 决策溯源子索引（step 6a · 轻量）

> 主题 → 承载 WHY/被否方案的 chat → 日期。decisions/ 卡片「原档指针」据此回指。
> ⚠️ 仅列蒸馏不全或含被否方案的；蒸馏充分的主题（如 acceptance 三护栏）memory 已自足，不强求 chat。

| 主题 | chat 出处 | 日期 |
|---|---|---|
| orchestrator 保留 vs Grok 委派（被否方案） | `3rd-ppt/【Mc-debug】/Mc-debug-1.md` L589「grok」段 | 2026-04 初 |
| 全局迭代收敛慢 → 改局部自检 | `Mc-debug-1.md` L493 + `Mc-debug-2.md` L2423 | 2026-04 |
| 三重混合机制 = 任务路由器（非三层加权） | `Mc-debug-5-三重混合机制.md` | 2026-04 |
| 多窗口/多 agent 工作流评估 | `Mc-emoji/[feature-03]/grok-01/02-...chat.md` | 2026-06-01 |
| Agent Team 入门实测（机制澄清/落点/放权/智谱混合否决） | `Mc-emoji/[feature-03]/grok+claude-03-...chat.md` + `sub-plan-stage3-agentteam-spike.md`；事实沉淀于 `references/agent-teams.md`「新手 FAQ」 | 2026-06-02 |

> 孤儿审计（step 6b，深读 6 个 ≥100KB 大档找未蒸馏决策）状态：**已执行 2026-06-01**。
> 结果：绝大多数已蒸馏 / 属域内细节。收割孤儿 2 个：
> - ✅ 候选 A「少做」原则 → 已入 `principles.md`（3rd-ppt Mc-debug-6 L1439/1598/1624）
> - ❌ 候选 B「主 Claude 即统一入口」（Agent-3 mc-debug5 L3156）→ **已否决，不入库**。仅 **fangcaixia 项目**成立（该 repo 生产必须 LLM 介入），**非普适**；且与 [[decisions/orchestrator-route]]「确定性 Python > LLM 委派」方向相反。强行入库会制造自相矛盾的伪决策。属域内细节，留 Agent-3/fangcaixia 原地。
