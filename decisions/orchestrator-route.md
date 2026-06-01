# decision · orchestrator-route

**决策**：保留 Python orchestrator，模块化升级；**不**用 native Claude Code agent 委派替换。
之后（plan3）从 ~1700 行瘦成 ~769 行**薄 dispatcher**——但**不归零**。

**日期**：2026-04-01（保留决策）→ 2026-04-09（plan3 瘦身定形）

**理由（薄度边界由两类东西锁定）**：
1. **LLM 替不掉的确定性活**：版本算术 / 5 个交互暂停点 / Windows COM 集成 / 复杂条件路由 → 必须留 Python。orchestrator 本质是 1622 行工作流引擎，不是简单 router。
2. **三护栏锁死薄度下限**（见 [[acceptance-guardrails]]）：重试硬上限 + 审查权留主 Claude，必须由确定性代码保证，LLM 自己保证不了。

**现状**：plan3 = 3+1 step-based agents（step1-analyzer / step2-architect / step3-builder + transplant developer）+ 局部自检；orchestrator ~769 行薄 dispatcher；每步 Attempt1(Python)→自检→Attempt2(LLM 修)，每步 ≤2 次；`/tweak` 当前 0 轮重试（最安全态）。curator/developer agent 已归档（局部自检取代）。

**何时复用此判断**：任何"要不要把编排交给 LLM agent / orchestrator 能砍多薄"的评估。结论：能砍的是视觉创作/修复决策（交 step agent 局部自检），骨架（dispatch + 暂停点 + 版本算术）留 Python。

**原档指针**：
- 已蒸馏结论：`3rd-ppt/.claude/memory/project_orchestrator_upgrade.md` + `project_plan3_architecture.md`
- WHY + 被否方案（Grok 提议 native agent 委派替换）原始讨论 → `3rd-ppt/【Mc-debug】/Mc-debug-1.md` L589「grok」段
- "全局迭代为何收敛慢 → 改局部自检" → `Mc-debug-1.md` L493 + `Mc-debug-2.md` L2423

相关决策：[[acceptance-guardrails]]（三护栏锁薄度下限）、[[per-agent-memory-no]]（同期 agent 架构决策）；偏好底座 [[../principles]]
