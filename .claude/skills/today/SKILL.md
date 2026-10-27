---
name: today
description: 读取并执行 repo 根 todays-task.md 里的任务。仅当用户显式输入 /today 时触发，不做 model-driven 自动调用。
---

# today（读 todays-task.md 并执行 · 薄入口）

读取 todays-task.md,执行其中任务。

> **本 skill 是薄入口**(Phase 2 重构,2026-07-16):只负责**第 0 步问出 mode(普通/全托管)**,然后把 mode + 任务交给 `today-core` 执行。执行调度(门控/延伸/效率/通信)、收尾固化(mc-update→pin→session-new)、同一任务/方案第 3 次失败熔断的**正文全在 `today-core/SKILL.md`**——本 skill 不重复,改执行逻辑只改 today-core 一处。
>
> **为什么拆**(plan §3.1):today-core 是单 plan 公共执行内核,被 today(本 skill,单次入口)和将来的 today-loop(完整 loop,Phase 3)共用。today 负责"是不是 /today 触发 + 问 mode";today-core 负责"拿到 mode 后怎么执行"。caller contract 单源见 `Mc-emoji/[feature-05-loop-self-improvement]/output/plan11-phase1-contracts/today-core-caller-contract.md`。

---

## §1 决策门控 · 第 0 步全托管前置门(每次运行先问,先于一切路由)

用 AskUserQuestion 让用户二选一,选定前不动手;默认/安全档 = 否:
- 〔1 · 否(默认)〕普通 /today——today-core 里"该问你"的决策点照常停下问你。
- 〔2 · 是 · 全托管(与 /team-task 深度放权(B) 同原则:不确定也先跑)〕本次运行把**门 3 的中等档决策、外加简单任务执行途中临时冒出、本来要停下问你的决策点(见 today-core §1.2 全托管延伸)**托管给 mc-expert:其「建议」当作有约束力、直接照办继续,不再回头问你。**mc-expert 置信低/无先例时也不升级你**——它仍会给一个具体默认推荐(默认>成功率最高>最易回滚,见其铁律 2),直接采纳继续,把该裁决记进收尾「自主裁决」清单供你事后批量复盘。**仅 4 条红线才停下问你**:① 销毁性/不可逆操作(多文件删除/覆盖无备份——本就在 delete-guard 兜底层拦);② 对外交付物 / Ldterm 明文合规红线;③ 同一任务/方案第 3 次失败熔断(见 today-core §2.2);④ 推翻 KB `decisions/` 已封决策(注:"无先例"自走,但"要推翻已封决策"仍停)。**①②类会触发权限框的命令(rm/删除/无备份覆盖/伸 `~/.claude`·系统·敏感目录/对外)绝不在全托管自主流程中途发起——会死等缺席用户 + 死锁后台 agent;一律攒「待人工处理」后置到人工门,halt 走「不执行该命令 + 落盘报告 + 上报」、不靠阻塞式权限框(后置的是决策权,非后置着自己补做);forensic/排查也不例外。详见 KB `decisions/autopilot-defer-perm-to-human-gate`。**门 1/门 2/门 4 行为不变(尤其门 2 升级到 team 始终留给你)。**全托管压的是「循环内决策门」(门 3 中等档 + 途中临时决策点),不压「用户在 todays-task.md 里显式定义的交付/验收门」(如素材审核门 / 成品人工验收)——这些照常停下、产出给用户验收,全托管不替你跳过、也别把验收门误当循环决策吞掉。**
用户没明确选"是"就按"否"执行。仅对实验性、用户已自评安全的任务才该选"是"。

---

## §2 交给 today-core 执行

§1 问出 mode 后,用 Skill 工具调用 `today-core`,把 mode + 任务作为 args 传入:

```
Skill(skill: "today-core", args: '<mode> "<task>"')
```

- `<mode>` = `normal`(§1 选"否")或 `autopilot`(§1 选"是")。
- `<task>` = todays-task.md 里的任务简述；始终用双引号包成一个参数。task 内若含双引号，先写成 `\"`。详细内容 today-core 仍会 Read todays-task.md。

**调用后由 today-core 接管**:执行调度(门控/延伸/效率/通信, today-core §1)、收尾固化(mc-update→pin→session-new, today-core §2.1;其中 pin 段=产提案清单+人工门批量落账,**不自动调 `$pin` skill / pin_capture.py**)、第 3 次失败熔断(today-core §2.2)。**mode 贯穿 today-core 全程**(含收尾段——全托管"第四面",见 today-core §2.1),today 这一层不再重复执行逻辑。

**通道机制(不糊弄)**：`args` 是 Skill 工具的文本字符串通道（`\$ARGUMENTS`）；today-core frontmatter `arguments: [mode, task]` 按 shell-style quoting 解析，第一位置是 mode、第二位置是 task。多词 task 必须包双引号，不能裸传；详见 caller contract §3.1 字段→通道映射。

---

## §3 调用 today-core 后,today 的职责结束

today-core 跑完(执行 + 收尾 + 必要时熔断)后,本次 `/today` 结束。**不回 today 做二次收尾**——收尾三段已在 today-core §2.1 跑过,today 再跑就是重复。
