---
name: reflect
description: 乙-1 一键反思回路——增量挖历史纠正→Step B 归纳→mc-expert 陪审预过滤→产两轮合并签字桌，停在人工签字门（不自动入库任何规则）。L4 自进化回路的手动一键版；周期化去重靠分桶台账（终结类踢走/刹车类留着攒频次）。用户输入 /reflect 触发。管道代码与数据在 Mc-emoji/feature-05/历史扫描/，仅本机可跑。
---

# /reflect —— L4 改进回路（乙-1 一键版）

把乙-0 手动跑顺的 5 步固化成一条 skill。**你（主 agent）按序执行，跑到「签字桌就绪」为止就停手交用户**——签字是唯一入库门、永远人工，你不替签、不自动改 KB/memory/CLAUDE.md。

> 冷启动可自足：口径红线全在下面「红线」节；管道细节见 `Mc-emoji/[feature-05-loop-self-improvement]/历史扫描/README.md` + `feature-05-progress.md` 续21/续23/续24/续25。别翻对话历史。

## 术语（首现）
- **new_gold** = 本轮增量挖出、不在(基线∪台账终结类)里的候选纠正对（jsonl 一行一条）。
- **Step B 归纳** = LLM 读 new_gold 全文，聚簇成「自进化候选」，非机械脚本。
- **签字桌** = 候选 md 末尾的待判点表，每项带默认 + 【用户批注】空块，交用户逐条拍板。
- **分桶台账** = `processed_ledger.jsonl`，处理过的候选记录：终结类(成卡/已吸收/在库佐证/领域专属/无教训)下轮排除；刹车类(证据<3)留着累计到≥3件毕业。

## 前置自检（不过就停下报错，别硬跑）
1. `cd "D:/Downloads/Mc Claude Code Workshop/Mc-emoji/[feature-05-loop-self-improvement]/历史扫描"`。
2. 确认 `out/v2_baseline.jsonl`（基线，只读）+ `processed_ledger.jsonl`（台账）存在。基线不在 → 停报「基线缺失，先核实 out/ 结构」，别自动重建。
3. 确认中央 pin raw sink `D:/Downloads/Mc Claude Code Workshop/Mc-Expert-repo/.claude/auto-memory/pin/pinned-candidates.jsonl` 存在且可读；缺失 → 明确停报 `PIN_SINK_NOT_FOUND`，不得把 0 条冒充正常，也不得回退旧 feature-05 sink。
4. 记当天日期 `<date>`（YYYY-MM-DD）用于命名产物。

## Step 1 · 挖 + 去重（一条命令，机械、非破坏）
跑（**走 Git Bash / Bash 工具**，单行；别粘 PowerShell）：
```
python mine_corrections.py --incremental --pin-log "D:/Downloads/Mc Claude Code Workshop/Mc-Expert-repo/.claude/auto-memory/pin/pinned-candidates.jsonl" "C:/Users/xy198/.claude/projects" "C:/Users/xy198/.claude-xh/projects" "C:/Users/xy198/.claude-mc/projects"
```
- glm 账号不扫；3 个「（历史）」根不在扫描列内。
- diff = gold − (基线 ∪ 台账终结类)；刹车类仍冒头累计。记下末行 `rundir` + `new_gold=N`。
- **N=0 → 干净收尾**：本轮无新料，写一句进 progress，不产签字桌、不派陪审，结束。正常结果非失败。

## Step 2 · Step B 归纳（LLM 判断层）
读 `<rundir>/new_gold.jsonl` **全文逐条**（别只信计数），产 `分析结论-人工/自进化候选-增量归纳-<date>.md`，结构照 07-03 那份：5 区（真新/B区已吸收佐证/C区证据<3刹车/D区领域专属/E区无教训）+ 去重列 + 重犯列 + 每待判点【用户批注】空块。
**口径红线**：证据<3 不硬造；不夹带频率；已结晶进 plan/KB 的只登记佐证不回炉；陪审意见不算 gold。

## Step 3 · 陪审预过滤（派 mc-expert，独立复算非采信草稿）
派 mc-expert 直读 `<rundir>/new_gold.jsonl` 原文逐条重判，核：①真纠正有无误杀/E区有无高估；②重犯判定是否成立（可文件系统独立取证）；③抓草稿过度自信/未回核。dropped 落 `分析结论-人工/陪审预过滤-dropped-<date>.md`（每条附机器可复核依据）。陪审低置信项标「升用户拍板」，不替定。

## Step 4 · 签字桌就绪 = 终点（停手交用户）
候选 md 末尾并出签字桌：每项=摘要+默认(留空即采纳)+【用户批注】空块；有上轮未签项一并合并一次交清。
**到此停手**：不 commit 规则、不改 KB/memory/CLAUDE.md、不 push。汇报用大白话（做了啥/几条待签/净新规则几条），原文留 md 只给路径。

## Step 5 · 落账（签字桌就绪后）
- progress 新增续N：rundir + new_gold 数 + 归纳结论(真新/已吸收/E区分布 + 净新规则数) + 陪审结论 + 「等用户签字」。
- 用户签字后，按签字结果把本轮每条 hash + disposition(终结/刹车) 追加进台账（append-only 接口，幂等）：
  ```
  python mine_corrections.py --ledger-add <dedup_hash> <终结|刹车> "<日期+签字桌编号+一句去向>"
  ```
  刹车候选日后累计 ≥3 件毕业成卡时，对同 hash 再 append 一条「终结」即可（后写覆盖先写，别改旧行）。
- todays-task 指针更新。commit/push 不在本 skill 自动做——签字是里程碑，用户签完 + 有实质变更再 push。

## 🔒 红线
1. 唯一入库门 = 用户逐条签字；永不自动写 KB/memory/CLAUDE.md。
2. 非破坏：基线+顶层桶只读；台账 append-only；输出进带时间戳 rundir。
3. dropped 不静默丢（落盘+依据）。
4. 不建监控系统 / 不输 confidence 数（撞护栏①）。
5. 别再复盘燃料够不够（闸门②早满足，见 memory l4-fuel-gate2-already-met）。
5b. 「净新规则=0」≠「new_gold=0」，都可能正常：前者=挖到候选但都命中在库/证据不足/已吸收→净0（续23实证）；后者=没挖到新候选。都别判回路坏了。
6. 权限类命令后置人工门：只读挖掘+产md，不中途发起 rm/敏感/对外；真需要则攒「待人工处理」。
7. src.machine 字段 mojibake：别用它做跨机去重（靠 dedup_hash）。

## 收尾自检（交用户前对一遍）
- [ ] new_gold 全文读过（非只看计数）
- [ ] 候选 md 5 区 + 批注空块齐
- [ ] mc-expert 独立跑过、dropped 落盘带依据
- [ ] progress 续N + todays-task 指针更新
- [ ] 没有任何规则被自动入库、没 push
- [ ] 汇报是大白话、给了产物路径
