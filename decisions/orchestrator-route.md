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

## 补充（2026-06-01）：协作 ≠ 控制 —— 为何 Agent Teams 出现后 orchestrator.py 仍不可替

评估官方 Agent Teams 能否取代 orchestrator.py 后的结论（也是 ROI 闸门 #1 回放）：

- **Agent Teams 真实存在但官方自列不稳**（会话恢复/任务协调/关闭行为）；本机 Windows Terminal 跑不了 split-pane → 只能 in-process，而 **in-process 队员不能 `/resume`/`/rewind`**（会话一断队员全没）。官方明确反对长时间无人值守。
- **hooks（TeammateIdle/TaskCreated/TaskCompleted + exit 2 返工）是原生硬控制中间路**，能做"测试不过不许完成"的硬质量门，**但单事件无状态**——做不了"跨多次重试累计到 3"这类计数（要外部计数文件 = 迷你 orchestrator）。
- **核心判断**：协作（软/发散/对话）与控制（硬/确定/计数）是**正交**两件事。"失败恰好 3 次上报"是确定性计数器需求，LLM 会因 context 压缩丢计数、因"再试一次"倾向不在阈值硬停。**orchestrator.py 不是"成熟即扔的拐杖"**——成熟修的是 bug，不会把概率裁判变成确定保证（类比再强的人类团队也仍跑确定性 CI）。

→ 强化本卡主结论 + [[acceptance-guardrails]] 护栏②（重试硬上限）：确定性硬流程控制永久保留 Python。
原档：`Mc-emoji/.claude/CLAUDE.md` 2026-06-01 教训 + 续；`Mc-emoji/[feature-03]/grok-01/02-...chat.md` + `Mc未来思考3...ADV.md`

## ⚠️ 分层说明（2026-06-12）：本卡 ≠ [[../references/loops-and-automation]]

两者结论表面相反（本卡「保留 Python orchestrator」vs loops 卡「别写 orchestrator.py、用原生 hook+台账+命令内流程」），实为**不同层**，别混：

- **本卡的 orchestrator** = 3rd-ppt 的**确定性 PPT 生产管线执行器**（管线内部：版本算术 / 暂停点 / COM 集成 / 重试计数）——这一层留 Python。
- **loops 卡的"别写 orchestrator.py"** = **外层任务编排循环**（哪个项目 / 哪一步 / 派哪个 subagent）——这一层优先原生（slash command 内流程 + 台账续命 + hook 硬门），外部脚本仅为"跨 tick 累计计数"的最后手段。
- 一致的内核：**确定性硬控制（计数/停止/护栏）永远要确定性代码兜底**，两卡都守这条——分歧只在"外层编排循环要不要也写成 py"，答案是不必。

相关决策：[[acceptance-guardrails]]（三护栏锁薄度下限）、[[per-agent-memory-no]]（同期 agent 架构决策）；偏好底座 [[../principles]]；自动化分层 [[../references/loops-and-automation]]
