---
name: auto-memory-index-hook-convention
description: auto-memory 的 MEMORY.md 索引钩子该写多长、含不含溯源、★ 该不该用——写法判据（跨 repo 通用）
metadata:
  type: reference
  status: 核实 2026-08-05
---

# auto-memory MEMORY.md 索引钩子写法规范

> 适用：所有 repo 的 `~/.claude*/projects/<repo-hash>/memory/MEMORY.md`（Claude Code 原生 auto-memory，每会话注入 system prompt）。
> 不适用：memory **正文文件**（按需加载，不常驻，写法不受此约束）。
>
> 核实日期：2026-08-05。源 = 2026-07-29 Mc-emoji MEMORY.md 瘦身 + mc-expert 陪审。**易过期**：auto-memory 加载机制随 Claude Code 版本演进（见 [[claude-codex-memory-difference]]），若钩子不再每会话注入或召回机制变更，本判据需复核。

## 核心职责：索引钩子 = 相关性触发器

钩子的唯一作用：让 Claude 扫到这一行时判断「这条 memory 跟当前任务相关吗」→ 相关才 Read 正文。
**因此钩子要的是"能触发相关性判断的关键词 + 强度信号"，不是正文摘要。** 溯源、事故叙事、版本演进细节回正文看。

## 三类"源 XXX"内容必须区分（瘦身时别一刀切）

| 类型 | 例子 | 处理 |
|---|---|---|
| **纯溯源**（事故日期 / plan 编号 / Phase 名） | "源 2026-07-19 plan18 Wave C""源 07-01 覆盖 v1_gold 事故""(源 feature-04 Phase6 验收实测)" | **删**——回正文看 |
| **频次 / 强度信号** | "用户无数次""反复发作""用户第 N 次追问""反复踩坑彻底纠正" | **留**——这是"这条特别重要、Claude 容易忘"的相关性触发，删了降召回 |
| **互斥避坑指针** | "别读成'燃料为空'→见 xxx""与 guard-delete-hook-pops 互补" | **留**——防 Claude 误判方向，跨卡防误读 |

## ★ 符号：保留，是承重语义标记不是装饰

KB 体系（today-core SKILL.md / references/* 等）已把 `★` 赋予"承重 / 硬反射 / 已封决策"语义。
- ★ 在标题里是 Claude 扫 N 条时的**视觉相关性加权信号**——★ 条目天然更易被选中（防漏召回硬反射）
- ★ 是用户翻 MEMORY.md 的**检索心智锚**
- **删 ★ 省不了几个 token（仅 3 字节 UTF-8），纯亏。** 瘦身时 ★ 一律保留。

## 重叠互引：单一权威收口

多条 memory 讲同一主题时（如 rm/auto-mode 顽疾簇、CC hook 机制族），按 [[kb-memory-boundary]]「单一权威收口」：
- **权威卡**写完整决策 / 机制；其他卡**降成指针**（`→见 [[权威卡]]`），别每条都重复展开。
- 但要注意**正交关系别误并**：机制事实卡（如"settings 热重载 / classifier / hook 三边界"）vs 项目决策卡（如"rm 转向 auto-mode"）是正交两件事，不能把机制卡降级成决策卡的指针——只把"随决策失效的子项"收成指针。

## 带订正段的卡：保守保留（最大安全垫）

钩子里带"★订正（日期）/ ★补段"的卡，订正的往往是**曾经错的认知**（Claude 会带着旧错回来）。这类订正段：
- 哪怕钩子偏长，**也别为省 token 砍**——砍了下次 Claude 又踩旧认知的坑。
- 典型：plan04「七层是个人框架非官方架构」订正、L4 燃料闸门「反复纠正」、settings「热重载无需重启」订正。

## 瘦身前后必做：召回自检（阳性对照）

瘦身是"省 token"的阴性结论，必须配"该召回的还在"的阳性对照（呼应 reflexes「阴性结论需阳性对照」）：
- 挑 5-6 个典型任务 prompt（如"改 today skill""删 runs/*""评估 codex hook"）
- 人工判断瘦身后哪些条目该被 Claude 选中，对比瘦身前后是否一致
- **召回率不降才算瘦身成功**，否则是"省了 token 丢了相关性"的假成功

## 实测数据（2026-07-29 Mc-emoji）

- MEMORY.md：15854 → 14248 字符（省 ≈460 token/轮），54 条记录零丢失
- 实际省的比预估少：因撤了"删 ★"策略 + 订正卡不动 + 保留频次 / 避坑信号——**这是对的取舍（保召回优先于省 token）**
- 真正大头不在索引底座（~9K token），在"会话累积的对话历史"——治本是"完成任务就新开 session"，精简底座是治标（但有每轮复利）

---
相关：[[kb-memory-boundary]]（memory 两层分治 / 单一权威收口的决策层）/ [[claude-codex-memory-difference]]（MEMORY.md 加载机制，本判据成立的机制前提）/ reflexes「阴性结论需阳性对照」（召回自检的方法论依据）
