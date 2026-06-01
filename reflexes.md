# reflexes.md — 跨 repo 硬反射

> 反复命中、必须无条件遵守的硬反射。每条挂「命中 repo」——双 repo 命中 = 真·跨 repo 反射，不是单项目偶然。
> 域内细节（染色契约 / 槽位 / 具体 COM quirk）不在此，留各源 repo。

## 加密环境（Ldterm DLP）

- **COM-only**：Office（PPT/Excel/Word）读写必须走 win32com；**禁** python-pptx / openpyxl / olefile / docx 直碰加密文件。`win32com.Dispatch` = 启动白名单 Office 进程读明文。〔3rd-ppt + Agent-3〕
- **`88 7D 1C` = 加密 → 立即 STOP**：碰任何二进制先读 8 字节；命中加密 magic 就停，报路径+hex 等用户解密。**不推测、不绕路、不换库重试**。Ldterm 加密的是整个 .pptx/.docx/.xlsx 文件头，不只是嵌入图。〔3rd-ppt + Agent-3〕
- python 写出二进制后**核验首字节是明文 magic**（`%PDF`/`PK`/`PNG`）；纯文本豁免。〔Agent-3〕

## 动手前

- **inspect-first**：写脚本/改填充前先跑 inspect-*（ppt/excel/word）或先 Read 现有状态文件（_archive / todays-task / verify_report）。〔3rd-ppt + Agent-3〕
- **skills-first**：写 win32com 前先 grep office-com-helpers 函数清单，能复用别手撸；反复强调的技术路线沉淀成 skills/*.md 独立手册，别散在 CLAUDE.md。〔3rd-ppt + Agent-3〕
- **UI 一键能修先告知**：Office/系统级默认行为问题（图片压缩 / 字体回退 / 自动校对），第一回复先给 UI 开关路径；**别先上注册表 / COM 属性 hack / OOXML 改写**——Ldterm 封死脚本侧路径时绕路成本巨大，UI 一次设置成本为零。〔Agent-3，2026-05-11 浪费 1 小时教训〕

## 判断与求证

- **先查再下结论**：谈某 Claude Code flag/env/功能**存不存在**时，先 `claude --help` + WebSearch 官方文档核实，再下结论。知识截止日后的功能"我没听过" ≠ "它不存在"，别用过时知识判"幻觉"。反向同样成立：**功能真实 ≠ 能扛硬流程**——存在性和可靠性是两件事，都要分别求证。〔Mc-emoji，2026-06-01：曾两轮误判 Agent Teams 为幻觉〕

## 控制与失败

- **连续失败 2 次熔断**：单文件硬超时 20-30s，连续 2 次超时切「本机 .ps1 模式」；不在 sleep 循环里盲目重试。〔3rd-ppt〕
- **不直接编辑生成产物**：项目档案 md / metadata.yaml / output 都是 workflow 产物，缺字段**修 prompt+脚本**不修产物。〔3rd-ppt + Agent-3〕
- **fix-plan 执行后回填头部**：执行完 `fix-*.md` 立刻改头部 quote 块：状态→已执行 + 列交付物 + 列与原 plan 实战偏差；主体保留凝固态档案。〔Agent-3〕

## 交互

- **Checkpoint 走 Excel 不渲染 md 表**：mapping 决议 / 槽位对照 / 字段映射这类逐行签字场景必须 `start "" *.xlsx`；对话里只摘要 + 点特殊项，禁列全表（终端表格无下拉/筛选/留痕，滚屏即失）。〔Agent-3〕

## 环境/工具

- **PowerShell 含 `[]` 路径必须 `-LiteralPath`**：本项目所有 feature 在 `[featureNN-...]` 下，FS cmdlet 默认加 `-LiteralPath`，否则 `[]` 被当通配符报错。〔Agent-3 + 本次实测复现〕
- **改 settings/配置先 .bak**；权限用方案 A，不主动开 bypassPermissions。〔Mc-emoji〕

相关：偏好底座 [[principles]]；架构决策 [[decisions/orchestrator-route]] / [[decisions/acceptance-guardrails]]
