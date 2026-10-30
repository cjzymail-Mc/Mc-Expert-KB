# claude-glm — 本机共享入口

> 2026-10-30 用户指定：今后使用 claude-glm；此文件只接线，不复制项目规则或 KB 正文。

- 当前 Claude Code 客户端配置根由 `CLAUDE_CONFIG_DIR` 指定，本机 claude-glm 为 `C:/Users/xy198/.claude-glm`。客户端仍使用 Claude Code；模型运行身份按实际 provider/会话证据判断，不能因 `opus` 别名或 `.claude` 目录名冒充原生 Claude。
- 共享 skills、agents、commands 的物理母本是 `D:/Downloads/Mc Claude Code Workshop/Mc-Expert-repo/.claude/`；本机 `.claude-glm` 下对应目录已用 junction 指向它。仓库中的 `.claude/` 是资产格式，不是原生账号入口，保留目录名与单一真源。不要复制母本、重建 junction 或顺着链接递归删除。
- 用户已停用 hook：保留现有 hook 文件与 junction，不注册、不恢复 hook；本入口通过 CLAUDE.md 原生加载，不依赖 hook。
- 开始项目工作时遵循当前项目的 `AGENTS.md` / `CLAUDE.md` 与最新用户指令；若存在 `.claude/auto-memory/MEMORY.md`，读其薄索引（若已通过 harness 加载同一物理文件，不重复读）。技术问题按需查 `.claude/memory/MEMORY.md`，再读相关正文。memory 不覆盖当前契约与 STATE。
- harness 的 `projects/<project>/memory/` 仍是项目记忆，不是跨项目全局记忆；已有真实目录和 junction 都保留，先辨明实际目标再写。不得为接入口自动搬移、合并或覆盖既有记忆。
- 普通项目经验固化走 `/mc-update`；中央 KB 策展走 `/KB-update`；`/reflect` 仅在需要历史补漏时按选定会话或 pin 提候选，交前两者一次审核，不做例行全量巡检。只有用户请求才执行这些流程，发现入口不等于授权固化。
- 跨项目历史咨询或用户询问中央 KB 时，先读 `D:/Downloads/Mc Claude Code Workshop/Mc-Expert-repo/MEMORY.md`，再按索引查相关内容；需要 mc-expert 时遵守它的当前调用合同。无需先启动原生 Claude。
- 中央 KB 的 `.claude/auto-memory/` 是待审 inbox，即使由 harness 加载也不构成已生效知识；策展内容位于根 MEMORY.md 索引指向的 principles/reflexes/decisions/references。晋升继续走 KB-update 的人工审核。
