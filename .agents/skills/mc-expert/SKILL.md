---
name: mc-expert
description: 点名工程独立陪审，或既有工程审计合同要求委派时，按既定 profile 调用 mc-expert 并登记。
---

主 agent 从当前工作项目调用本技能。首次介入、从其他专家切回或跨日首次继续时，先在加载用户配置的 PowerShell 执行 `& '<本技能绝对目录>\daily-task.ps1' -Mode Ensure -InvocationSource <来源>`，检查共享的 Windows 17:00 计划并登记当前线程。新机默认用 `codex`；本机按已有回执用 `codex2`。仅在当前权限允许写入本机登记时执行。只读或登记需要额外权限时直接委派，从实际命名线程补收来源。来源填 automatic（主 agent 按任务选择）、explicit（用户明确要求这位顾问）或 continued（延续已介入的任务）。

使用 `spawn_agent` 选择角色 `mc-expert` 并交接本技能所属知识库的绝对根目录、用户目标、相关材料和本轮要解决的分歧。同一任务的后续反馈用 `followup_task` 接续原线程。顾问先读[判断库](../../mc-expert/judgment.md)，需要核对取舍时读[案例库](../../mc-expert/cases.md)。客户端尚未加载命名角色时，重开会话或使用已有的独立评审入口，并如实标注实际评审者和状态。按[角色配置](../../../.codex/agents/mc-expert.toml)和[既有评审合同](../../mc-expert-common/review-contract-v2.md)提供调用 envelope，选择 HISTORY 或 ENHANCED_FINAL。证据、最终签署权限和 verdict 均沿用既有合同。

主 agent 执行操作并交付。遇到有复用价值的纠正，核对用户原意、来源及实际结果，在现有权限内修准上述两份资料。尚未入库的反馈可在当前项目用同一脚本 `-Mode Record -Feedback <原意> -Subject <对象> -Outcome <实际结果或未决处> -Evidence <可共享摘要>` 登记。每日复盘会补读已调用线程中的相关增量；私有原始会话和路径留在本地。
