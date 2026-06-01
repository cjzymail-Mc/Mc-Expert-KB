# Mc-Expert KB — 索引

> 中央知识库（薄）。稳定层 = 人工策展快照，可修正、不污染源 repo。
> 易变 domain 细节不在此，留各源 repo（见 repo-map）。建于 2026-06-01（Stage 0）。

## 核心文档
- [principles.md](principles.md) — 用户决策偏好卡（确定性 Python > LLM / 稳定 > 新颖 / 文档诚实 / 入库判据 / 交互风格 / 环境约束）
- [reflexes.md](reflexes.md) — 跨 repo 硬反射（COM-only / Ldterm STOP / inspect-first / skills-first / UI-fix-first / 2-fail 熔断 / 不编辑产物 / Excel checkpoint / `-LiteralPath`），每条挂命中 repo
- [repo-map.md](repo-map.md) — 源 repo 地图 + 决策溯源子索引

## decisions/ — 跨 repo 已决决策（不重判，互链）
- [orchestrator-route](decisions/orchestrator-route.md) — 保留 Python orchestrator，瘦成 ~769 行薄 dispatcher，不归零
- [per-agent-memory-no](decisions/per-agent-memory-no.md) — 不引入约定式 per-agent memory（CC 上下文隔离≠记忆隔离）
- [acceptance-guardrails](decisions/acceptance-guardrails.md) — 自动闭环三护栏（外部真相/重试硬上限/编排权留主 Claude）

## Stage 0 状态
- ✅ 去重 / principles / decisions×3（含互链）/ reflexes / repo-map / 溯源子索引
- ✅ 孤儿审计（6 大档）— 收割「少做」原则入 principles；候选 B（统一入口）已否决（仅 fangcaixia 成立，非普适，与 orchestrator-route 冲突）
- ✅ Mc-emoji 收割（2026-06-01）— C1「先查再下结论」入 reflexes；C3「协作≠控制 / Agent Teams 边界」入 orchestrator-route
- ⏳ GitHub private remote + 首 push
- ROI 闸门（§5）：orchestrator 切片 ✅ + Agent Teams 回放 ✅（=C3）；PPT→HTML 回放待补（结论"加密底座永久保留"已在 Mc-emoji CLAUDE.md 教训）
