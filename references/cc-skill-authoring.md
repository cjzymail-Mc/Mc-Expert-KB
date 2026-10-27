# cc-skill-authoring.md — Claude Code skill 编写机制事实（args 切分 + 占位符展开）

> 性质 = reference（factual），非 decision/reflex。
> **⚠️ 核实日期 2026-07-16 · Mc-emoji feature-05 plan11 args-probe-plugin 三组运行时 probe（裸多词 / quoted 多词 / 缺参）**。CLI 版本未随 probe 记录（probe 跑在 claude-glm 分发上）；**第二层系官方文档明文**（code.claude.com/docs/en/skills，见源 smoke-results §3），非仅 probe 单点。harness 参数切分与展开行为版本敏感、易过期——CC 若改 skill args 语义，回读本卡重评。
> 本卡收跨 skill 通用机制事实；domain 实现细节留源 repo（指针见文末）。

## 决定性结论

- **skill frontmatter 声明 `arguments: [mode, task]` 时，`args` 按 shell-style quoting 切位置参数**：
  - 裸传 `normal two word task` → 第二个 named 参数只得到 `two`（静默截断，不报错）。
  - 传 `normal "two word task"` → 完整得到 `two word task`。
  - 只传 `autopilot` → 第二参数为空（可用作 fail-loud 契约校验点）。
- → **caller 固定写法**：`args: '<mode> "<task>"'`；task 内含双引号时 caller 先写成 `\"`。
- **第二层（易漏，官方文档明文 + probe 双坐实）**：skill 正文里 `$ARGUMENTS`/`$0`/`$1` 及 frontmatter named placeholders **会被 harness 全文展开**——不只真正消费参数的代码行，**说明文字里的也会被换**。想展示字面量必须写 `\$ARGUMENTS` 转义（或改写成不含 `$...` 的措辞）；只有真实消费点保留未转义占位符。

## 新增/重构 skill-to-skill caller 时的动作序列

1. 先明确 positional schema；2. 多词字段 caller 侧 quoted；3. grep callee 全文区分真实消费点 vs 教学性占位符；4. 三组运行时 probe 验证（裸多词/quoted 多词/缺参）——不只静态审查。第 4 步即本卡回读触发器：下次任何 caller 改动跑 probe 时顺带回填新核实日期。

## 原档指针

- 证据：`Mc-emoji/[feature-05-loop-self-improvement]/output/plan11-phase2-refactor/args-probe-plugin/automation-logs/20260716-191842/case-map.tsv` + 同目录 evidence/ 两份 capture + `smoke-results.md`（live S1/S2 PASS，含官方文档对照 §3）。
- 源提案（含完整决策过程）：`Mc-emoji/.codex/memory-inbox/2026-07-16-claude-skill-args-quoting-and-literals.md`（07-19/08-06 两轮 mc-update 复核 + 2026-08-25 KB 收割落地）。

相关：[[cc-command-skill-resolution]]（同族 CC 机制事实）、[[cc-hooks-facts]]
