# reference · Claude vs Codex：跨会话 memory 加载机制差异

> 配合 [[dual-tool-single-source]] 决策卡：那条讲"知识只一份"，本卡讲两工具**读 memory 的机制层差异**（为什么单源之上仍要各配入口适配）。
> 性质 = reference（factual），核实日期 + 官方来源见文末。**产品快速演进、易过期**——涉及默认行为时回读重核。

## 核心差异（一句话）

- **Claude Code**：harness（宿主）**原生强送达**——会话一开，自动把 `MEMORY.md` 薄索引塞进 system prompt，模型不需"主动去读"。**送达 ≠ 强制遵守**（机械红线仍靠 permission/hook/validator）。
- **Codex CLI**：原生稳定加载的是 **`AGENTS.md` 指令链**（按目录层发现 + 拼接，默认 32KiB 上限，每 run 重建）。Codex **有** local Memories，但**默认关闭、是独立系统、不读 Claude 的 `.claude/auto-memory`**。→ Codex 要用 Claude 经验，须靠 `AGENTS.md` 里的**指针链**（软约束）。

→ **本质区别**：Claude 是"harness 把索引**送进**上下文"；Codex 是"AGENTS.md 送进上下文，但继续读 MEMORY.md/正文是 **agent 执行指令**（模型遵守指令才读，弱一层）"。

## 让 Codex 接近 Claude 的三候选（强度递增，默认选 A）

| 候选 | 机制 | 强度 | 何时上 |
|---|---|---|---|
| **A（软）** | `AGENTS.md` 顶部加指令"启动先读 MEMORY.md 索引 → 按需读正文" | 软·靠模型遵守，偶尔漏 | **默认**（实测够用） |
| B（中） | Codex `SessionStart` hook，会话开头自动注入索引/路由提示到 developer context | 更接近强送达，但带 trust/幂等/输出上限(~2500 token)/主题选择额外工程 | 仅 A 出现真实痛点时 |
| C（重） | promotion tool / 第二份 memory / runtime | — | 各 repo Constitution 多数已判禁区，不碰 |

## 别为理论完整性提前上 hook（5 痛点门槛）

**不要**因为"Claude 有、Codex 没有"就上候选 B（hook）。只有出现**真实痛点**（有复现记录/用户原话）才升：
1. 多次新 session 读了 `AGENTS.md` 仍不读 `MEMORY.md`；
2. 不同账号/模型/surface 对同一启动链表现显著不一致；
3. `/compact`、resume、切工作目录后稳定丢入口；
4. memory 规模扩大后索引路由频繁选错；
5. 需在无模型自主性前提下机械保证某段上下文被注入。

否则继续候选 A 软指针 + 偶发漏召回靠显式提示/`$pin` 兜底即可。**这条直接呼应 [[../principles]]「少做」+ [[self-compliance-probabilistic]]**（别为"提高激活率"建度量/监控，同理别为"理论完整"提前上工程）。

## 易踩的措辞坑（防自相矛盾）

- ❌ "Codex 完全没有 memory"——它有 local Memories（默认 off）；
- ❌ "Codex 完全读不到 Claude memory"——靠 AGENTS.md 指针链能走通（Mc-emoji 三路实测证伪）；
- ❌ "Codex 已原生获得与 Claude 完全相同的 memory harness"——不成立；
- ⚠️ 实测结论用词要分清"三路归因成立" vs "定级 `PARTIAL`"——单点对照跑通 ≠ 全量稳定可读，**外部效度别滑坡**。

## 实测定级

Mc-emoji 2026-07-19 Plan16 Wave 0 三路对照（盲测 / 负对照 / 正对照）PASS：Codex 实际按 `AGENTS.md → CLAUDE.md → MEMORY.md → 主题正文` 顺序读取，阳性指纹 = 答出项目私有正文文件名。→ **候选 A 够用**固化为 feature06 T4 闭口依据。但定级仍是**单点 `PARTIAL`**（1 条 memory × 1 模型 × 1 账号 × 1 次），不外推为所有 memory/模型/账号/surface 都稳定。

---

**核实日期**：2026-07-19（Mc-emoji Plan16 Wave 0 三路实测 + Anthropic/OpenAI 官方文档核对）。
**易过期**：CC/Codex 都在快速演进（auto-memory 加载范围、AGENTS.md 上限、local Memories 开关默认值都可能变）。涉及默认行为时回读重核。
**官方来源**：Anthropic `code.claude.com/docs/en/memory` + `context-window`；OpenAI `learn.chatgpt.com/docs/agent-configuration/agents-md` + `memories` + `hooks`。
**原档指针**（完整版 581 行，含 §4 差异对照表 / §5 实测架构 / §9 冷启动操作指南 / §12 hook 是否超禁区裁定）：`Mc-emoji/X-Claude与Codex-Memory加载机制区别-2026-07-19.md` + `.claude/auto-memory/codex-memory-load-harness-vs-soft-pointer.md`。**项目特定落点**（main-plan §4 禁区 / T4 边界 / Wave 0 细节）留 Mc-emoji feature06，不入本卡。

相关：[[dual-tool-single-source]]（知识单源决策）、[[self-compliance-probabilistic]]（别为激活率建度量，同理别为理论完整上 hook）、[[../reflexes]]（先查再下结论 + 阳性对照——三路实测即阳性对照实例）。
