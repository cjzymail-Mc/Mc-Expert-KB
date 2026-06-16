# principles.md — 用户决策偏好卡

> 合成源：`3rd-ppt/user_profile` + `feedback_stability` + `feedback_output_style`
> + Agent-3 `feedback_doc_honesty_measured_vs_projected` + `feedback_golden_samples_admission_criterion`
> + `Mc-emoji/CLAUDE.md`（根 + .claude）。
> 用途：mc-expert 给建议前先读这张卡，确保对齐用户已确立的偏好，别重新辩论。

## 架构与控制

- **确定性 Python > LLM 委派**。能写死的工作流逻辑（流程执行 / 版本算术 / 状态跟踪 / 条件路由）一律 Python，**绝不**建议用 LLM 委派替换控制流。LLM 只干语义判断（标注增强 / prompt 改写 / 失败分析 / 代码修复）。
  - 用户原话："写死的 py 代码好处就是稳定可靠（毕竟稳定性最重要）"。
- **稳定 > 新颖**。成熟方案修 bug，不为"新"换路线。评估新功能/新路线时默认保守。
- **编排权留主 Claude**：审查者 ≠ 被审查者；LLM 自循环只能改"被审查物"，不能碰"审查标准"。
- 保留**固定菜单选项**给用户控制（工作模式 / max rounds 等），不要全自动黑箱。
- **少做（"好架构是少做出来的"）**：架构评审第一镜是"能不能不做/能不能更少"。"故意不做的事"清单和"做了的事"一样重要。现有结构落在甜区时**不加新抽象，直到出现具体痛点**（呼应 [[decisions/per-agent-memory-no]] 的"满足任一事故条件才引入"）。〔孤儿审计 2026-06-01 收割：3rd-ppt + Agent-3〕

## 文档诚实

- **预估 ≠ 实测**，严禁混写。预估写"预估/专家建议"，实测写"实测 + 具体数字 + 口径"。
- 实测打脸乐观预期时：第一反应**订正文档**（含已落地代码注释），不藏、不默默跳过。
- 结果不及预期 / 不确定时**停下来跟用户商量**（原话"不要硬干"），别硬推进到写结论。
- **机器自检 ≠ 人工验收**：COM/脚本自检只是装配质量门；汇报措辞必须区分「自检 PASS」vs「待你人工验收」，别混称。交验收时附产物路径 + 点明重点看哪几处。〔Agent-4，2026-06〕

## 入库/样本判据（可推广到 KB 自身）

- 样本/知识入库判据 = **新增对照价值**（引入新 schema 形态/对照点/边界条件），**不是** "verify PASS 即入"。
- 做**减法**：默认不入，只入引入新价值的；多一份 = 多一份维护负担，拉低信噪比。
- 三连问（任一"否"即不入）：① 引入既有库没有的形态/对照点？② 会被反复引用？③ 维护成本 < 新增价值？

## 交互风格

- 改代码**只说结论**：改了什么、为什么、结果如何；**不展示** old/new diff（省 token、防频繁 compact）。
- 简洁直接，不要冗长的"为什么"开头铺垫；结构化输出（表格/流程图）优先。
- **首次出现的英文缩略词**（KB/COM/DLP 等）括号给中文全称 + 一句解释。
- 主力 shell = PowerShell（Windows 10）；Bash 经 Git Bash 可用。

## 环境硬约束（详见 reflexes.md）

- **Office 文件（2026-06-15 起，新机器 Ldterm DLP 已解除）**：默认走 Python（openpyxl/python-docx/python-pptx）、文件默认明文；**遇加密文件 = 例外 → 跳过 + 记录 + 报告用户**，不 STOP/不换库硬试。COM 只留视觉渲染/导图/复杂染色，及回到 DLP 机器时的条件性回退。详见 reflexes.md「Office 文件路径」。
- 改 settings/配置文件**先备份 .bak**。
- 权限用**方案 A**（`Bash(*)/PowerShell(*)` 通配 allow + `rm/Remove-Item` 进 ask），**不主动开 bypassPermissions**。

相关：[[decisions/orchestrator-route]]、[[decisions/acceptance-guardrails]]、[[reflexes]]
