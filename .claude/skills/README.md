# `.claude/skills/` — 自动化运行 skill（KB 单源 · git 版本化 · 3 账号共享）

这里放的是 **Claude 在自动化干活时会加载并调用的 skill**：COM/Office 读写、文档体检与验收、team 执行入口、染色契约等。它们是「跑流程必需的工具」。

- **物理本体唯一**，在本 KB repo 内、受 git 版本化（可溯可回滚）。
- 经 NTFS junction 共享给 3 个账号（`.claude` / `.claude-mc` / `.claude-xh`）——见 Mc-emoji 检修箱里的 `[skills-junction-3account]`。
- 这里的 `README.md` 不是 skill（无 SKILL.md / 不在子目录），Claude 不会把它当 skill 加载。

## 什么该进这里 / 什么不该

| 进这里（KB） | 不进这里（→ Mc-emoji `★ Skills ★` 检修箱） |
|---|---|
| 自动化**运行时**要 Claude 调的工具：`office-com-helpers`、`com-survival-reflexes`、`inspect-*`、`*-acceptance-check`、`team-task(-api)`、`three-state-coloring-*`、`ldterm-decrypt-images` 等 | 我（用户）**人工维护多账号环境**时手动跑的工具：junction 搭建/重定向、migrate、权限 bug 修复、备份等 |
| 跨 repo 复用、稳定、值得进 git 历史的「知识/能力」 | 一次性/检修性、不该污染 KB 历史的「运维脚手架」 |

> 判据一句话：**「跑业务流程要用的」进 KB；「修我自己这套多账号机器的」留检修箱。** 拿不准时默认不进 KB（呼应本 repo `decisions/kb-memory-boundary.md` 的「做减法」纪律）。

## 当前清单（16）

COM/Office 底座：`office-com-helpers` `com-survival-reflexes` `ldterm-decrypt-images`
文档体检/验收：`inspect-{excel,ppt,word}-template` `{excel,ppt}-acceptance-check` `ppt-visual-fidelity-check`(legacy，已被 `ppt-acceptance-check` 取代) `read-selected-shape` `pipeline-self-check-loop`
染色契约：`three-state-coloring-contract-{excel,word}-only`
team 执行：`team-task` `team-task-api`
文档工程：`claude-md-three-layer-refactor`

> 对照面（人工检修工具箱）：`Mc-emoji/--------- ★ Skills ★ ----------/README.md`
