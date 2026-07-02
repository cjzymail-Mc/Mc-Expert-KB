# decision · self-compliance-probabilistic（规则遵守=概率裁判，可靠性归冗余层）

**决策**：AI 对"已入库规则"的 self-compliance（自觉遵守）本质是**概率裁判**——规则在场≠会执行，无法工程到 100%。**别为"提高激活率"建度量/监控/打分系统**（撞"不建监控系统"红线、且是朝概率爬山）。可靠性**正式归冗余层**，且分两档不可混：

| 档 | 组成 | 性质 |
|---|---|---|
| **确定性硬兜底** | hook exit-2 质量门 / 人工门 / 2-fail 熔断 | 真正扛可靠性；对齐 [[acceptance-guardrails]] 护栏②③（重试硬上限 + 审查者≠被审查者） |
| **概率软冗余** | team / mc-expert 陪审 | 另一个 LLM，降错率但**非确定保证、有成本、只在重大关口 fire**——别 over-credit 成"确定兜底" |

**软自律层保留但降格**：抽象规则绑成"看得见的具体动作扳机"（触发绑定）是**零成本边际改进**、覆盖陪审成本上够不到的高频低风险动作 → 留着，但**不当可靠机制、不度量、不朝其爬山**。软硬两层**互补非替代**（撤软扳机=高频 routine 错全压给有成本陪审，不现实）。

**日期**：2026-07-02（源 feature-05 续19；用户判定 + mc-expert 高置信复核）

**理由**：`feedback_verify_before_asserting` 明在库、在上下文，同一会话仍被违反两次（feature-05 续11 dogfood 实证）。想"验证并提高激活率"的原方向被判为追幻觉——self-compliance 是概率裁判，指望它→100% 正是 [[orchestrator-route]]「成熟修的是 bug，不会把概率裁判变成确定保证」否掉的；且"系统度量激活率"与"不建监控系统"红线内在冲突。放弃它反而更贴既有护栏，不推翻任何已封决策。

**何时复用此判断**：任何"某规则/规范 AI 老不遵守，要不要建机制强制/度量它"的评估。结论：软扳机零成本可留但别度量；真要可靠→上确定性硬兜底（hook/人工门/熔断），别指望 self-compliance、也别把 LLM 陪审当确定保证。

**代价（已接受、写明防回潮）**：放弃系统度量后，"触发绑定管不管用"永远只有轶事、无客观证据——用户已接受（"人无完人何况 claude"）。日后若有人想补度量，回读本卡。

**原档指针**：`Mc-emoji/[feature-05-loop-self-improvement]/plan05-应用端规则激活瓶颈.md`（已重构）+ `feature-05-progress.md` 续19；散见前身：[[orchestrator-route]]（概率≠确定）、[[acceptance-guardrails]]（审查者≠被审查者）、`Mc-emoji/.claude/auto-memory/llm-selfconfidence-not-l4-fuel.md`（别朝自信爬山）。

相关决策：[[orchestrator-route]]、[[acceptance-guardrails]]；偏好底座 [[../principles]]
