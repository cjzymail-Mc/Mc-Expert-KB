# cc-command-skill-resolution.md — Claude Code command/skill 同名解析

> 性质 = reference（factual），非 decision/reflex。
> **⚠️ 核实日期 2026-07-12 · feature-06 plan05 A 段 `today` 升 skill 实测**（CLI 版本见源 repo）。harness `/slash` 解析优先级行为，版本敏感、易过期——CC 若改 command/skill 解析优先级，回读本卡重评。
> 实现细节（today 入口壳删除过程）留源 repo，见文末指针。

## 决定性结论

- **同名 command + skill 时，`/slash` 直达 skill、绕过 command 入口壳**——入口壳成死代码（永不被调用）。command = `commands/<name>.md`；skill = `skills/<name>/SKILL.md`（frontmatter `name: <name>`）。
- → **升级 command→skill 时，别留同名入口壳**：要么删 command（`/name` 直达 skill，**不会"丢 slash 入口"**），要么仿 chop **错开命名**（command `chop` 路由到 skill `chop-task`，壳才有效）。
- 留同名壳 = 死代码 + 分叉风险（壳和 skill 两份，壳改了不生效，易误以为已更新）。

## 实证（推翻一个陪审判断）

`today` 从 `commands/today.md`（83 行自含）升级成 `skills/today/SKILL.md` 时，留了薄入口壳（9 行路由，首句"规范在 skill、用 Skill 工具调用 today"）。但 today command 与 skill **同名**，实测 `/today` **直接加载 SKILL.md 全文、入口壳根本没被调用**（skill 列表里同名条目只剩 skill 那条，command 壳消失）。最终删壳。

- **推翻的判断**：mc-expert 陪审 Q4 曾判「留壳**必要**——不留 /today slash 入口会消失、只能靠 model-driven 召回」。**实测推翻**：不留壳，/today slash **直接命中 skill**，入口没丢。该判断在「command+skill 同名」前提下不成立。

## 为什么 chop 没踩坑

chop 入口壳有效，因它**错开命名**：command `chop`（`/chop`）路由到 skill `chop-task`（**不同名**）→ `/chop` 命中 command、command 调 skill `chop-task`，链路成立。

## 原档指针

- 实测全过程 + 推翻陪审判断：`Mc-emoji/.claude/auto-memory/cc-command-skill-same-name-skill-wins.md`（feature-06 plan05 A 段，2026-07-12）。
- 关联 junction：同名 skill 经 user-scope junction 跨账号生效（同 plan05 A2 段翻案）→ 见 [[../reflexes]]「user-scope junction 路径是跨 repo 共享契约」。

相关：[[../reflexes]]（user-scope junction 同源）、[[cc-hooks-facts]]（同族 CC 机制事实）
