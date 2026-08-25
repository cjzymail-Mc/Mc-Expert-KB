---
name: free
description: 接下来这个任务走 mc-expert 陪审 + 深度授权(B)，完成阶段目标后请求用户审核介入。B 模式权限命令一律后置人工门（rm/伸敏感目录/对外不中途发起，攒待人工处理）；收尾走 mc-update→pin→session-new 微型 loop。仅当用户显式输入 /free 时触发，不做 model-driven 自动调用。
---

# free（mc-expert 陪审 + 深度授权(B)）

接下来这个任务走 mc-expert 陪审 + 深度授权(B)；
完成阶段目标后再请求用户审核介入。

> 注：2026-07-22 项目权限层已转向 Claude Code **auto-mode**（classifier 自动判断），原「第 3 层 guard-delete hook + .b-mode-active 标记」路线已撤销（hook 注册从 settings 删除，标记机制无消费者）。/free 不再写/清任何标记文件。rm 顽疾兜底当前 = 纯纪律层（本节「权限命令后置人工门」+ memory `feedback-no-rm-midflight-defer-to-human-gate`）。转向详情见 feature-07 `修正rm顽疾-2026-07-22/` 决策卡与 settings 修改记录。

【B 自主流程中途 · 权限命令一律后置人工门】
- rm/删除/无备份覆盖、伸进 `~/.claude`·系统/敏感目录、对外交付——这类会触发权限框的命令，**绝不在 B 自主流程中途发起**（会死等缺席用户 + 死锁后台 agent，比报错更坏）。
- 一律攒进「待人工处理」清单，收尾一次性列给用户批量处理。forensic/排查也不例外（别用含 `rm`/伸敏感目录的命令去查问题）。
- 4 条红线仍 halt，但走「**不执行该命令 + 落盘报告 + halt 上报**」，**不靠阻塞式权限框**。后置的是决策权，不是后置着自己偷偷补做。
- 依据：KB `decisions/autopilot-defer-perm-to-human-gate`（源 2026-06-20 8h 死锁事故）。

【收尾 · 微型 loop：mc-update → pin → session-new（完成阶段目标·请求用户介入时）】

完成阶段目标（含任务收尾）、准备请求用户审核介入时，按 **mc-update → pin → session-new** 顺序跑一遍收尾固化，省掉用户手敲 `/mc-update`、`/pin`、`/session-new`。机制同 `/today`、`/team-task` 的收尾微型 loop（先预判、再决策、选"是"后 Skill 自动调用；mc-update→pin→session-new 顺序；两层判断边界——只判"要不要启动"、启动后写不写归 mc-update/pin_capture/session-new 自己；失败/未完成跳 mc-update 和 pin、留 session-new），下面只写 /free 的差异与边界：

1. **去重（避免重复跑）**：若本次任务**已在 `/today` 或 `/team-task` 入口下**跑（它们各自带收尾 loop），以那边为准、**不触发本 loop**。本 loop 只接管"没走那两个入口的普通任务"（纯对话干活、或本就没经 today/team-task 的活）。
2. **决策口径——B 自判，不弹用户**：/free 全程 B（深度授权），收尾的 mc-update / **pin** / session-new 决策也走 B——**不弹你**，由 mc-expert 代判（`Task(mc-expert)` 按共享 `review-contract-v2.md` 交齐 v2 六字段且固定 `REVIEW_PROFILE=HISTORY`，带任务背景/产物判"要不要跑 / 有无漏网纠正"→ 照办跑或跳），逐条记进收尾交付汇报的「自主裁决」清单（同 `/today` 全托管分支口径）。**pin 段预判闸判"无漏网纠正迹象"可直接跳**（事实判断非偷懒）；有迹象则派 mc-expert 陪审、PIN/DROP 判据见下指针。HISTORY 不抵扣命中增强触发器后的 fresh `ENHANCED_FINAL` 终审。注：收尾固化不弹你 ≠ 任务成果不给你审——**成果本身**仍按本 command 第 2 行交你审核，两件事分开。
3. **pin 段判据指针**：PIN/DROP 判据、方案 a 去重（pin 前查 live）、掉线降级、陪审 spawn 五要素、lead 自校验 fail-loud——**全见 KB `Mc-Expert-repo/references/收尾loop判据.md`**（单一来源，本命令不抄；三入口引同一份）。控制流（预判闸→识别→去重→陪审→掉线降级→落账+报告行）同 `/today`。
4. **熔断**：本 command 不带计数脚本；任务中途 halt 交用户 / 无实质进展 → 跳 mc-update 和 pin、session-new 仍走，且不让 mc-expert 给 mc-update 续命（同 today/team-task 口径）。
5. **session-new 段幂等**：重入前查本会话 plan 是否已存在，存在则跳过、不堆重复/空 plan（同 today/team-task 口径）。
