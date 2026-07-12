# 收尾 loop 判据（/today · /free · /team-task 三入口共用 · 单一指针）

> **定位**：被 `/today`、`/free`、`/team-task` 三入口收尾段**共同引用的判据单一来源**。
> 三入口各自的**控制流**（mc-update→pin→session-new 三段顺序、预判闸、跳过必给理由、掉线降级怎么走）留在各自命令、**只引本指针**；**判据**（什么算漏网纠正、PIN/DROP 怎么判、方案 a 去重、陪审 spawn 要素）集中本文件——**改判据只改这一处**，不三处逐字复制（v2 把判据逐字抄三份 = 维护毒药）。
>
> **节奏认知（sediment-two-tracks）**：pin 判据 0 次独立验证，本版只做"判据指针"轻量固化、**不抽完整 `skills/收尾loop/SKILL.md`**（只跑通 0 次就固化完整 skill 会过拟合单样本）。判据稳定 2-3 次独立任务后，本文件升完整 skill，届时三入口引 skill 指针、改判据仍只改一处。
>
> **gap（文档诚实）**：本版 = today/free/team-task **三入口同构验证版 + feature-05 补漏层**，耦合 capture_hook / pinned-candidates / mc-expert 陪审专门链，**非通用 loop 框架**。方向上该朝通用 skill，但 sediment-two-tracks 支持先做窄。
>
> 源 plan：`Hot-Fix/plan-today-收尾loop升级.md` v3（2026-07-10）。

---

## 1. 三层捕获架构：pin loop 填哪个空档

| 层 | 触发 | 机制 | 抓什么 | 落点 |
|---|---|---|---|---|
| capture_hook（**已有**） | 每条 prompt | 词表 + combo + error_actor ·**机械** | 有标志词 / 质疑×重复 / 施动门后的"错误" | `live-candidates.<session>.jsonl` |
| **收尾 pin loop（本判据）** | /today /free /team-task 收尾 | LLM 回顾 · 陪审 | **纯陈述式纠正**（零词、零 combo、未中断）= 词表真漏的 | `pinned-candidates.jsonl` |
| /pin（**已有**） | 用户手敲 | 人工 · 最高 tier · 绕词表 | 用户亲自点名 | `pinned-candidates.jsonl` |

- capture_hook 召回面比"只抓有标志词"宽：**三路**（`CORRECTION` 词表 / `combo_hit`=质疑词×重复标记 合取 / `error_actor_hit`+施动门）。源 `correction_core.py`。
- **真漏网 = 纯陈述式纠正**（例："你这段跑的是总成本，需求要的是边际"——零 CORRECTION 词、零 combo、未中断）。capture_hook 的 `detect()` 对此返回 `None` → 不落 live → **pin loop 是唯一兜底**。
- **不存在"零重叠"**：带标志词/combo 命中的纠正 capture_hook 已写 live；pin loop 不查 live 就会再写 pinned → 必靠**方案 a** 去重（§3）。

---

## 2. PIN / DROP 判据（陪审照此判）

一条候选**判 PIN**（落 `pinned-candidates.jsonl`）当且仅当：
1. **是真纠正**——AI 确实错 / 偏 / 漏，不是用户随口聊天、风格偏好、或提问。
2. **属"纯陈述式漏网"**——capture_hook 没抓到（本会话 live 里查无此条，见 §3）。
3. **有泛化价值**——纠正指向一个可复用的判据 / 反射 / 口径，不是一次性任务细节（"这个文件名拼错了"≠ 燃料；"你总把 X 当 Y"= 燃料）。

**判 DROP**（不入库）当：
- 不是真纠正（提问 / 确认 / 风格 / 一次性细节 / 用户自己的笔误）。
- live 已抓（capture_hook 已捕获，重 pin = 双写污染）。
- **认不准 → DROP 而非硬 pin**（pin.md 铁律：认不出纠正别硬造；宁可漏一条，不污染下游归纳）。

陪审输出 = **PIN/DROP 二态 + 一句依据**。
**禁附 confidence 概率分**（pin_capture.py 接口本就无 confidence 字段；夹带"PIN 0.8"会污染下游 Mc-emoji feature-05 消费——对照 verdict-log.jsonl"禁加 confidence 字段"铁律）。pin 是"零加工哑文件"，陪审只产 PIN/DROP，不产概率。

---

## 3. 去重 · 方案 a（pin 前必查 live，不碰脚本）

- 源码铁证：`pin_capture.py:36-48` 的 `load_existing_hashes()` **只读 `pinned-candidates.jsonl` 自身、不扫 `live-candidates.*.jsonl`** → 跨文件去重物理不存在。`capture_hook.py:202-209` 写 `live-candidates.<session>.jsonl`，两文件物理隔离。
- → **pin 前必做**：Grep / Read 本会话 `live-candidates.<本会话 session_id>.jsonl`（路径 `[feature-05-loop-self-improvement]/历史扫描/out/`），capture_hook 已抓的候选剔除、**不重 pin**。纯 LLM 自查，**不改脚本**。

---

## 4. 掉线降级（mc-expert 零正文 / Connection closed）

- **重试 1 次** → 仍失败 → 该候选**落 `Loops/review-queue.md` 交用户补判**（保留候选、不静默丢）。
- **不绕陪审硬 pin、不当场 DROP**：掉线时陪审还没判，DROP 是"审完"的态，不能因掉线等同漏判。
- **不原地连试 ≥2 次**：auto-memory `feedback_team_idle_zero_body` 实证——当次连掉 3 次空耗约 1/3 任务时间。

---

## 5. 陪审 spawn 五要素（mc-expert 不继承 lead 历史）

派 mc-expert 陪审的 prompt 必带：
1. 纠正原文
2. 被纠正的 AI 动作要点
3. live 是否已抓该条（去重结论）
4. 必要上下文（任务背景 / 产物）
5. **PIN/DROP 判据**（引本文件指针，不逐字抄）+ 红线："只给 PIN/DROP + 依据、不复述纠正、不顺势修错、**不附概率分**"

**批量化**：候选 ≥2 条 → 一次 spawn 全给、逐条判；单条才单发（借鉴 process-rd §3 subagent 粒度可粗化 + keygate"一次审多条"）。

**认知**：陪审 = **概率软冗余**，非确定性兜底（temp.md 实证拦约 75% 噪声，4 条样本统计意义弱）。要确定性入口只能上路线 C（Stop hook），本版未实现。

---

## 6. lead 调 pin_capture 前自校验 fail-loud

陪审输出**缺 PIN/DROP 判定 / 纠正原文 / 依据** → lead 凑不出 `--corr` / `--ai`，应**报错让陪审重出或落 review-queue，绝不硬凑参数 pin 一条错的**。
（注：改 `pin_capture.py` 本身加 fail-loud 属 Mc-emoji feature-05 域边界，不在本判据范围；本条只覆盖 lead 调用前的自校验。）

---

## 7. 报告路径（pin 段有动作时记一行 · 供漏跑频率观测）

pin / drop / 掉线降级 任一发生 → 在 **session-new 段产出的 plan** 里记一行汇总：`pin N / drop M / 降级 K 落 review-queue`。
**目的**：让"收尾漏跑 / 陪审掉线"频率可观测，供决定是否上路线 C（Stop hook 确定性兜底）。（KB `loops-and-automation` §3 loop 五件套之⑤报告路径。）

---

## 调用接口（pin_capture.py · 不改逻辑只调用）

```
python ".../[feature-05-loop-self-improvement]/历史扫描/pin_capture.py" \
  --corr "<纠正原文>" --ai "<被纠正的AI动作要点>" --note "<备注>" [--followup "<错因/想要啥>"]
```
- 自带**同文件内**去重（pinned-candidates.jsonl）；落 `out/pinned-candidates.jsonl`。
- **铁律**：认不出纠正别硬造；只捕获、不复述纠正、不顺势修错。

---

## 演进意图（防把首跑期严格门冻成永久税）

- **陪审退出阀**：pin 识别是 feature-05 补漏层**首次引入收尾** = novel 设计问题，本版"必经陪审"是首跑期正确姿态。收尾 loop 跑稳 N 轮、PIN/DROP 判据验证靠谱后，**用户可拍板砍 pin 陪审走 speed-mode**（pinned-candidates 直接落，对照 `feedback_speed_mode_after_proven_rounds`）。
- **判据升 skill**：判据稳定 2-3 次独立任务后，本文件升级为完整 `skills/收尾loop/SKILL.md`，届时三入口引 skill 指针、改判据只改一处。
- **路线 C**：Stop hook 确定性入口触发，仍为上线后第一优先跟进（本版未实现，见源 plan §路线C）。
