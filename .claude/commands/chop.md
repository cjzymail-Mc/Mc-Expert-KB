`/chop` = `/chop-task` 的主入口（两者等价）。**规范定义在 `skills/chop-task/SKILL.md`，别在这里另起一套流程**（避免与 skill 分叉）。

立即用 **Skill 工具调用 `chop-task`** 并完整执行其 SKILL.md：

1. 读当前 repo 根 `chop-task.md`，取最后一个 `<!-- consumed ... -->` 标记之下的新内容为原始任务（无标记取全文）；空则停下让用户先写，别自己编。
2. 走开工门禁信息充分性自检（入口分诊 → 八项交底 → 足量性自测）：事实层缺口用 prose 列清单问用户补，可 inspect 的留执行期，裁量层留拍板点。
3. 按「自动拆解」骨架产出结构化 prompt（终态 / 事实交底 / 红线 / 你的任务 / 验收）。
4. AskUserQuestion 让用户选落点（todays-task.md / team-task.md），带日期块追加；在 chop-task.md 末尾打 `<!-- consumed YYYY-MM-DD -->` 消费标记（非破坏性）。
