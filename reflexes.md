# reflexes.md — 跨 repo 硬反射

> 反复命中、必须无条件遵守的硬反射。每条挂「命中 repo」——双 repo 命中 = 真·跨 repo 反射，不是单项目偶然。
> 域内细节（染色契约 / 槽位 / 具体 COM quirk）不在此，留各源 repo。

## Office 文件路径（2026-06-15 起：新机器，Ldterm DLP 已解除）

> ⚠️ **环境翻转**：旧机器是 Ldterm DLP（按进程名白名单的透明加密）→ 默认密文 → COM-only 铁律。**新机器 DLP 已解除**，前提"默认所有 Office 文件都加密"**不再成立**。下面是新机器的反射；旧铁律降级为历史/条件性回退（见末条）。

- **默认走 Python**：Office（PPT/Excel/Word）读写**默认** python-pptx / openpyxl / python-docx，文件默认当**明文**处理；不再默认 COM。〔2026-06-15 环境变更〕
  - **两条独立理由都指向"默认 Python"**：① 新机器 DLP 已解除（2026-06-15）；② 即便在 DLP 机器，只要文件已**手工预解密**，走 COM 反而帮倒忙——COM `SaveAs` 会把明文**反向加密回去**（输出 `88 7D 1C`），污染下游 Python 读取。〔Agent-4 CLAUDE.md §2，2026-06-09 拍板〕
- **遇加密文件 = 例外 → 跳过 + 记录 + 报告用户**：碰二进制先读 8 字节；**非明文 magic**（`PK`/`%PDF`/`PNG` 等）即视为加密 → **跳过该文件、记下路径、汇报给用户**，**不 STOP 死等、不换库硬试、不绕路**。加密已是少数特例，不是常态。〔2026-06-15〕
- **COM 仍保留的窄场景**：视觉渲染 / 导 PNG / 复杂染色 / 必须 COM 的产物；以及**条件性回退**——若又回到 DLP 机器，恢复旧铁律（COM-only + `88 7D 1C` STOP + 写后核明文）。
- python 写出二进制后核验首字节是明文 magic（`%PDF`/`PK`/`PNG`）；纯文本豁免。〔Agent-3，仍有效〕
- 〔历史〕**源 repo（3rd-ppt / Agent-3 / Agent-4）满地的 COM-only、`88 7D 1C` STOP 记忆都写于 Ldterm DLP 机器，属环境特定，不是新机器上的普适反射**——读源 repo 记忆时按此折算。

## 动手前

- **inspect-first**：写脚本/改填充前先跑 inspect-*（ppt/excel/word）或先 Read 现有状态文件（_archive / todays-task / verify_report）。〔3rd-ppt + Agent-3〕
- **skills-first**：写 win32com 前先 grep office-com-helpers 函数清单，能复用别手撸；反复强调的技术路线沉淀成 skills/*.md 独立手册，别散在 CLAUDE.md。〔3rd-ppt + Agent-3〕
- **UI 一键能修先告知**：Office/系统级默认行为问题（图片压缩 / 字体回退 / 自动校对），第一回复先给 UI 开关路径；**别先上注册表 / COM 属性 hack / OOXML 改写**——Ldterm 封死脚本侧路径时绕路成本巨大，UI 一次设置成本为零。〔Agent-3，2026-05-11 浪费 1 小时教训〕

## 判断与求证

- **先查再下结论**：谈某 Claude Code flag/env/功能**存不存在**时，先 `claude --help` + WebSearch 官方文档核实，再下结论。知识截止日后的功能"我没听过" ≠ "它不存在"，别用过时知识判"幻觉"。反向同样成立：**功能真实 ≠ 能扛硬流程**——存在性和可靠性是两件事，都要分别求证。〔Mc-emoji，2026-06-01：曾两轮误判 Agent Teams 为幻觉〕
  - **泛化到一切事实性断言**（不止 CC 功能）：某文件是不是 junction / 某字段是否一致 / 某值是否笔误——先读文件/跑工具/等实证再断言，**不把「理论上应该」当已确认**。抽象规则不 fire，改绑**可见动作扳机**（命中即停先取证）：① 要输出事实论断 → 先读/搜/跑（**含交付宣称**：正要说『能用 / 双击即用 / 搞定了』但没在目标环境实测过 → 停，先实测一遍再宣称。〔Mc-emoji feature-05，2026-07-03 两 bat 未测就宣称"双击即用"被拉回〕）；② 要引 spec/规格/契约判据 → 回读原文那段、不凭印象；③ 要输出阴性结论 → 先做阳性对照（见下条）；④ **自己正要写「理论上应该/应该是/大概率/我记得/按理说」= 未核实信号词，写到它就停**。〔Mc-emoji feature-05，2026-07-01 同会话违反两次后拍板〕
- **阴性结论需阳性对照**：做「有没有发生 X」的检测时（无泄漏/无 bug/没复现），阴性结果**只有先证明探针本身能检出阳性后才作数**，否则很可能是探针失灵的假阴性。下「没问题」前自问「若这事真发生了，我的探针检得出来吗？」——没把握先喂一个已知阳性样本验探针灵敏度。〔Mc-emoji feature-05，2026-06-29：记事本探针测「按键泄漏」多轮显示零泄漏，补阳性对照才发现记事本根本收不到注入键、之前全是假阴性〕

## 控制与失败

- **连续失败 2 次熔断**：单文件硬超时 20-30s，连续 2 次超时切「本机 .ps1 模式」；不在 sleep 循环里盲目重试。〔3rd-ppt〕
- **不直接编辑生成产物**：项目档案 md / metadata.yaml / output 都是 workflow 产物，缺字段**修 prompt+脚本**不修产物。〔3rd-ppt + Agent-3〕
- **fix-plan 执行后回填头部**：执行完 `fix-*.md` 立刻改头部 quote 块：状态→已执行 + 列交付物 + 列与原 plan 实战偏差；主体保留凝固态档案。〔Agent-3〕

## 交互

- **Checkpoint 走 Excel 不渲染 md 表**：mapping 决议 / 槽位对照 / 字段映射这类逐行签字场景必须 `start "" *.xlsx`；对话里只摘要 + 点特殊项，禁列全表（终端表格无下拉/筛选/留痕，滚屏即失）。〔Agent-3〕

## 环境/工具

- **PowerShell 含 `[]` 路径必须 `-LiteralPath`**：本项目所有 feature 在 `[featureNN-...]` 下，FS cmdlet 默认加 `-LiteralPath`，否则 `[]` 被当通配符报错。〔Agent-3 + 本次实测复现〕
- **改 settings/配置先 .bak**；权限用方案 A，不主动开 bypassPermissions。〔Mc-emoji〕
- **Git Bash 里 `python3` 是 WindowsApps stub，exit 49 静默失败**（不报错、无输出）——跑脚本/校验一律用 `python`；原生 python 不认 `/tmp`，临时文件走 Windows 路径（`tempfile.gettempdir()`）。〔Agent-4〕
- **user-scope junction 路径是跨 repo 共享契约**：`~/.claude/` 下 commands/skills/agents 的脚本经 junction 给所有源 repo/账号共享（`$env:USERPROFILE\.claude\...` 借同一份物理文件，一处改处处见效——红利与代价同源）；**改其位置 / 删 / 改名前，grep 必须含所有源 repo**（不只扫当前 repo 或母本 repo），否则漏掉借用者、挪了断跨 repo 调用。〔Mc-emoji feature-06 plan05，2026-07-12：autopilot_failcount.ps1 被 Wu Prj sub-plan-16 跨 repo 硬编码调用，险当 today 私有挪走，幸 mc-expert 跨 repo 扫到〕

相关：偏好底座 [[principles]]；架构决策 [[decisions/orchestrator-route]] / [[decisions/acceptance-guardrails]]
