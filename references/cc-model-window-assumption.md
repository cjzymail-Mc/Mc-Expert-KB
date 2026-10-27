# cc-model-window-assumption.md — CC 模型窗口假设与 auto-compact 封顶（网关/自定义模型 ID）

> 性质 = reference（factual）。
> **⚠️ 核实 2026-08-18**（官方文档 code.claude.com/docs/en/model-config「Correct the window for a gateway or custom model ID」节 + /env-vars，双 URL 见源档；本机会话 JSONL 实证；CLI v2.1.215，行为分化自 v2.1.193）。CC 版本敏感、**易过期**——升版本或再遇「过频 compact」时回读本卡复核。
> 适用面：所有经网关别名模型 ID 跑 CC 的入口（本机四账号 claude-glm 等）。源 = Mc-emoji `temp.md`（2026-08-18 冷启动卡）。

## 决定性结论

- **CC 不认识的模型 ID（网关别名，如 glm-5.3）→ 按假设窗口 200K 做主动压缩**，且 **auto-compact window 会被该假设窗口封顶**（官方原文 "Claude Code caps the window at the model's context window"）——`CLAUDE_CODE_AUTO_COMPACT_WINDOW=400000` 实际被砍到 200K，×60% 阈值 = **~120K 就触发**（实测触发带 107.7K~121K，名义 240K 的一半；「claude-glm 过频 auto-compact」的根因即此，非模型问题）。
- **正解 = `CLAUDE_CODE_MAX_CONTEXT_TOKENS`**：官方专为网关/自定义 ID 留的声明变量——声明真实窗口后压缩按声明窗口继续（行为自 **v2.1.193** 分化）。**本机 claude-glm 已配置**（`~/.claude-glm/settings.json` env = 1000000，2026-09-18 核实在位；**行为复测待下次长链会话按 §复测判据验 JSONL**——配置在位 ≠ 触发水位已迁移，mc-expert 陪审 09-18 要求的诚实降格）。
- 两个坑：① 阈值百分比（`CLAUDE_AUTOCOMPACT_PCT_OVERRIDE`）**只能调低不能调高**；② window 设低于 200K 时「看起来生效」其实没撞封顶线，升上去才暴露（07-29 pilot 100K/150K「有效」之谜的解）。
- 备选 `CLAUDE_CODE_DISABLE_UNKNOWN_MODEL_WINDOW_ENFORCEMENT=1` 需 **v2.1.223+** 且语义相反（不再主动压缩、等 API 报 too-long 才压）——别用。

## 复测判据（防假阳性）

解析会话 JSONL：`subtype=compact_boundary` + `compactMetadata.preTokens`（**别裸搜 "compact" 字符串**，会假阳性）。PASS = 触发水位从 ~110K 带 → 约 220K~245K 带（内部记账 ≈ 名义 88%~100% 属正常）。

## 原档指针

- `Mc-emoji/temp.md`（2026-08-18：8.4MB 会话 JSONL 账目、因果链三步、三方案对比、官方两文档 URL、施工步骤与验收段）。

相关（CC 机制族）：[[cc-skill-authoring]]、[[cc-hooks-facts]]、[[cc-permissions]]、[[claude-codex-memory-difference]]
