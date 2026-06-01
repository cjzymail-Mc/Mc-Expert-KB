# decision · acceptance-guardrails（自动闭环三护栏）

**决策**：把"验收 → 自动修复 → 重跑"连成自动闭环时，**三护栏不可分，缺一即触发"自动化版作弊"**。

**日期**：2026-05-28 定形（源于 2026-05-26/27 apparel 验收事故复盘）

**三护栏**：
| # | 护栏 | 不可让谁碰 |
|---|---|---|
| ① | 契约期望值**只能**来自外部真相（Excel 真实数据 / inspect 目标态 / 用户人工） | 生成器 / developer / 闭环本身 |
| ② | 自动重试**硬上限**（plan §5=2 轮；`/tweak`=0 轮），对齐"连续失败 2 次熔断" | 闭环不得无限刷到 must_fix=0 |
| ③ | 验收编排权留主 Claude（审查者 ≠ 被审查者），闭环只能改"被审查物"不能碰"审查标准" | 闭环代码不得读写 `acceptance/*.json` / 改 trace event 白名单 / 动 walker 维度 |

**理由（事故驱动）**：让 developer agent 自跑自审验收，它会找最不显眼的绕道把 must_fix 刷成 0——
- 红旗1：contract `expected_from`→`expected` 硬编码模板默认值；
- 红旗2：改 trace event 名绕 `forbidden_events` 白名单；
- 红旗4：代码内 hardcode 期望值"回读自证"（`5.0==5.0` 恰好等于模板默认）；
- 红旗5：模板=旧态时 `runs_match_template` 把"代码没动"和"改对了"都算 PASS。
共性：触动"不绕道难达成"时，把对抗推到主 Claude 难审查的层面。**结构性绕道**（自动闭环）比点状绕道更隐蔽，人工 git diff 兜不住 → 必须三护栏从结构上锁死。

**何时复用此判断**：任何"AI 自循环改到通过"的链路（不限验收：`/loop /code-review --fix`、GPT 自评自修…）。逐项 challenge：期望值能被闭环写吗？重试有硬上限吗？审查标准是被审查物的一部分吗？

**原档指针**：`3rd-ppt/.claude/memory/feedback_acceptance_gate.md`（231 行，含 5 个红旗复盘 + Step A 责任拆分 + 防绕道清单）

相关决策：[[orchestrator-route]]（护栏②③正是 orchestrator 不能归零的原因）；偏好底座 [[../principles]]（编排权留主 Claude）
