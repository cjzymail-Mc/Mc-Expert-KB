读取 todays-task.md,执行其中任务。

【强制门控】读完 todays-task.md 后,先做路由判断,再动手:
1. 任务是否匹配已有 role(builder/researcher/converter/archivist/pm)或 skill?
   - 是 → 立即调用对应 slash command,不要从零规划、不要自己先读项目文件
   - 否 → 进入下一步
2. 【team task 门】任务是否是「多步实现类、需要 plan→挑刺→实现→复审」的活,或要改多文件/有架构取舍、值得 planner/mc-expert/coder 小队?
   - 是 → **停下,不要自己建队、也不要自己直接开干**;向用户说明「此任务复杂度够 team,建议走 /team-task(原生 coder 小队)」+ 一句理由,等用户确认后再动。用户拍板走才进 team-task 流程(含第 0 步 A/B 驱动模式选择)。
   - 否(轻量任务,单点改动/查询) → 进入下一步,自己干
3. 【mc-expert 咨询门 · 中等档(team 与单干之间)】没够 team 门、本可自己干,但**你拿不准 / 犹豫不决**,或命中 mc-expert 任一触发条件——**重大技术选型 / 改核心文件(CLAUDE.md、本 repo 的 plan*.md / agent 定义 / 若是 KB repo 则含 principles·reflexes·repo-map·decisions·references)/ 同一问题已连续失败 2 次**——则**别完全单干**:先 `Task(subagent_type=mc-expert)` 咨询(带改动背景),拿到「历史依据+建议+风险+置信度」再动手或再收尾;mc-expert 置信度低时按其建议升级给用户。真正琐碎、无疑义的改动才直接自己干。
   - 注:本门是开工/收尾前的**自觉前门**;若本 repo 装了 mc-expert Stop-hook,收尾时还有 harness 兜底,两者互补——不要因为有 hook 就在该犹豫时跳过咨询。
4. 任务是否需要盘点多个相关文件(skills/agents/templates/pipeline 等)才能动手?
   - 是 → 派 1 个 Explorer subagent 一次性平行盘清楚,不要自己串行 Glob+Read
   - 否 → 自己直接动手

效率规则:
- todays-task.md 直接引用的文件(如 mc-debugN.md)和它在同一条消息里并行 Read;路径未知必须 Glob 时,Glob+Read 串行可接受
- 扫描/查找/盘点类只读动作派给 Explorer subagent(单点 1 个、多角度并行多个),不要自己 Glob/Grep 翻
- 写文件、改代码、跑命令仍由你自己执行,不委托 Explorer

通信规则:
- 不要复述 todays-task.md 内容,直接说"开始执行 X"后动手
- 收尾只报:完成了什么 / 卡点 / 下一步建议,不要列过程清单
