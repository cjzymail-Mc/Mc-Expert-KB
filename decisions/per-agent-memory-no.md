# decision · per-agent-memory-no

**决策**：**不引入**约定式 per-agent memory（每个 agent 专属记忆子目录）。维持所有 agent 共享 `.claude/memory/` + `.claude/auto-memory/` 池。

**日期**：2026-04-29

**理由**：
- 专家说法"子 agent 有独立上下文 + 专属记忆"**部分错**：Claude Code **上下文隔离 ≠ 记忆隔离**。隔离的是 conversation / system prompt / tool access / model；**文件系统 memory 不隔离**，所有 agent 共享。
- 当前共享池**不污染**：memory 按需 Read（agent 只读 prompt 显式引用的文件）、auto-memory 索引精简、职责靠 prompt 隔离。
- 引入 per-agent memory 反带复杂度：每次写 memory 多一个"放哪"决策 + agent prompt 加"只读自己子目录"约束（易忘）+ curator 改造 + 移植多一层抽象。

**现状**：5 个 agent 共享池，引用关系健康（developer→染色规范、step3-builder→修复指引，该看的看了）。

**何时重新评估**（满足任一才引入）：出现具体"误用 memory"事故 / 某 agent 知识有强保密/强领域性 / auto-memory 索引膨胀回 10+ 条且多与单一 agent 相关。**当前都不满足。**

**原档指针**：`3rd-ppt/.claude/memory/reference_agent_memory_design.md`（含 5 维隔离真相表 + 未来设计草图）

相关决策：[[orchestrator-route]]（同期 plan3 agent 架构）；偏好底座 [[../principles]]（稳定 > 新颖、不为新增复杂度）
