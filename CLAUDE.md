# CLAUDE.md — Mc-Expert-repo（中央 KB）操作手册

> 这是**给 KB 策展者**（当前常用入口为 claude-glm）的薄操作手册 / 导航卡，**不是 KB 内容副本**。
> 知识本身在各源文件，这里只放：定位 + 边界 + 导航 + 节奏。改动前先读 [MEMORY.md](MEMORY.md)。

## 这是什么

中央 KB 稳定层 = 跨 repo 经验的**人工策展快照**（薄、稳定、可修正、不污染源 repo）。易变 domain 细节不在此，留各源 repo（见 `repo-map.md` 指针）。`mc-expert`（`.claude/agents/`）按需读它给咨询。

## 策展边界（每次进 repo 先激活，详见 [decisions/kb-memory-boundary.md](decisions/kb-memory-boundary.md)）

- **内容层**（`principles` / `decisions` / `reflexes` / `repo-map` / `references`）= 策展成品，**只人工经入库判据闸门改**。
- **`.claude/auto-memory/` = 待审收件箱（inbox）**，不是内容。原始反馈先落这；**晋升进内容层走三连问判据 +「少做」克制，绝不自动 merge**。
- **入库判据**（`principles` 入库段）：① 引入新对照价值？② 会被反复引？③ 维护成本 < 价值？——任一"否"即不入。**默认不入**。
- KB 元进度（Stage / 已入 / 已否）记在 [MEMORY.md](MEMORY.md) 状态段，不另立机制。

## 导航（去哪读）

`MEMORY.md` = 总索引，先读它再按需进：`principles.md`(偏好) · `reflexes.md`(硬反射) · `repo-map.md`(源 repo 地图+溯源) · `decisions/`(已决决策，不重判) · `references/`(事实手册)。

## 策展节奏

- **先讨论清楚再动**（Stage 0 起的节奏）：重判据 / 边界 / 入库前先对齐，别闷头写。
- **先查再下结论**（[reflexes.md](reflexes.md)）：谈 CC flag/功能存不存在，先核实再说。
- **固化走 `/KB-update`**（不是通用 `/mc-update`）：本 repo 是策展稳定层，入库走三重判据闸门、auto-memory=待审 inbox。
- 这是 **D 盘独立 repo、不绑账号**；进 git 可版本化/回滚——保留这两个属性，别引回 junction 依赖。

> ⚠️ 本文件保持**薄**：只指针 + 边界 + 导航。任何 principles/reflexes/decisions 的内容**别复制进来**（会双份漂移，违 `reflexes` 的「别散在 CLAUDE.md」）。

## 本机客户端入口（2026-10-30）

启动 `claude-glm`；`/KB-update` 负责本 KB，普通工作 repo 用 `/mc-update`。共享入口说明见 [.claude/claude-glm-entry.md](.claude/claude-glm-entry.md)。该文件由 `~/.claude-glm/CLAUDE.md` 导入；skills/agents/commands/hooks 的现有 junction 与 KB 物理母本均保留。`.claude` 资产路径不表示必须启动原生 Claude。
