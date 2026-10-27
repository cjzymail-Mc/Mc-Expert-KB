# reference · Claude Code 权限系统（实测事实手册）

> 配 `settings.local.json` 时跨 repo 复用的事实底本。来源：Mc-emoji `feature-02-auto-Enter` 实测 + `CLAUDE.md`。
> 性质 = reference（factual），非 decision/reflex。改 settings 前先读 + 先备份 `.bak`。

## 当前采用：方案 A
`Bash(*)/PowerShell(*)` 通配进 **allow** + `rm/Remove-Item` 进 **ask** 列表。
效果 = "几乎全通 + rm 仍弹确认"。备份在 `settings.local.json.bak`。**不主动开 bypassPermissions**。

## 6 个反直觉但实测确认的事实（改 settings 前必读）

1. **`bypassPermissions` 不支持"挖洞"**——它完全跳过 allow/deny/ask 三类规则，只保留 `rm -rf /` 和 `rm -rf ~` 两个硬编码兜底。想"几乎全跳但 rm 仍弹"**不能**用 bypass，要用方案 A。
2. **规则顺序 = `deny` → `ask` → `allow`（`ask` 优先级高于 `allow`）**——**2026-07-03 官方权限文档已明文确认**（原为"文档没明说但实测验证"，现升级为官方白纸黑字）。方案 A 就靠这个挖洞（allow 通配 + ask 拦 rm）。
3. **settings.json 不热重载**——改完必须**重启会话**才生效。
4. **`defaultMode` 必须放在 `permissions` 内部**，放外面 CC 不识别。
5. **`acceptEdits` 不覆盖所有 Bash/PowerShell**——只覆盖文件编辑 + 少数文件系统命令（mkdir/rm/mv 等）；`git push`/`curl`/`npm run` 这类仍弹确认。
6. **`ask` 是「命令串开头前缀匹配」，包进脚本/循环/管道即绕过（2026-06-02 双文件对照实测确认）**——`ask` 规则（如 `PowerShell(Remove-Item *)`）只匹配**命令串开头**。实测：裸 `Remove-Item <path>`（开头是 `Remove-Item`）→ **弹确认窗**；`$f=@(...); foreach{ Remove-Item $p }`（开头是 `$f =`）→ 命中 `PowerShell(*)` 的 allow → **静默执行、不弹窗**。即方案 A 的 rm 门只拦"裸的顶层删除"，**拦不住埋在脚本/循环/管道里的删除**（同理 `bash -c "...; rm ..."`）。**硬操作纪律：含销毁性删除时用逐条裸命令、别包脚本；多文件删除先停下请用户确认。** 详见 [[../../Mc-emoji 记忆]] feedback_destructive_delete_confirm。

## 2026-07-03 官方文档核实补强（3 subagent 核官方 permissions/hooks 文档 + 社区实战 + 本机实测）

> ⚠️ 核实 2026-07-03 · 官方权限文档 + 本机 CLI v2.1.159 实测。**版本敏感、易过期**——CC 若改权限模式/受保护路径语义，回读重评。

- **Windows 原生不支持沙箱**（官方原文 "Native Windows is not supported"，仅 macOS/Linux/WSL2）→ 官方"少弹窗+防删除"的沙箱正解在本机堵死，**方案 A + hook 是 Windows 原生唯一可行路线，不是权宜之计**（承重上面"方案 A"定位）。
- **内置「受保护路径」机制**：`.git`/`.claude`/`.vscode`/shell 配置等在除 `bypass` 外所有模式**不被 allow 规则自动放行**——免配置的第二层保险。**但本机 V1 实测：user-scope `~/.claude` 写入未被覆盖**（Write `.claude/hooks/*.ps1` 静默通过）→ 别以为受保护路径全包了，护 settings/hook 自身仍要自建覆写守卫（见 [[cc-hooks-facts]]）。
- **模式辨别（补充/收紧事实 #5）**：`dontAsk` = 未预批准的**静默拒绝**（非弹窗，不适合挖洞）；`auto`（v2.1.83+ 研究预览，分类器拦 `git reset --hard`/`git clean -fd`）方向对但官方自认 **17% 假阴性**、非人审替代 → 观望不采用；`acceptEdits` 会**自动放行工作目录内 Remove-Item**（比事实 #5 更松）→ 继续不用。
- **黑名单必被绕已被 CVE 坐实**（Flatt CVE-2025-66032、Adversa 50 子命令绕过，均已在近版修复）→ 共识：别靠 pattern 卡参数，靠 hook 做 AST 解析 + 分层防御。守卫守「防误操作」不守「故意混淆」是**正确边界**（追后者 = 无底洞）。

原档：`Mc-emoji/[feature-02-auto-Enter]/plan-权限守卫升级-2026-07-03.md`（3 subagent 调研全汇总 + guard-delete L3 四闸实现；实现细节留源 repo）。

## 2026-07-19 补：`auto` mode 与显式 `ask` 规则的优先级

> ⚠️ 核实 2026-07-19 · 官方 permission-modes 文档 + 本机 4 探针矩阵实测（CLI v2.1.207）。版本敏感、易过期。

- **显式 `ask` 规则压过 `auto` mode 放行**（官网原文 "Explicit ask rules still force a prompt"）：即使切到 `auto` mode 且其后台分类器想放行，`settings.local.json` 里 `ask: ["Bash(rm *)"]` 这类**显式规则仍强制弹框**。→ **rm 弹框的根因是 ask 规则，不是 auto 没激活**——别误判"rm 弹框 = auto 没激活 / 模型不支持 auto"，那是错诊断方向。
  - 本机 4 探针（glm-5.2 + auto on）：`rm -f`/`rmdir`（在 ask 列表）→ 弹框；`mkdir`/`Write 新文件`（不在 ask 列表）→ 静默通过。**但这只坐实「ask 压过 auto」这个根因，坐实不了「auto 激活/可用」**——见下条证据强度订正。
- ⚠️ **「glm-5.2 下 auto mode 实测可用」证据不足，降级为存疑**（2026-07-23 订正，原 07-19 写成"实测激活"是探针不锋利导致的过度断言）：两边都不能一锤定音——
  1. **探针不够锋利**：07-19 探针里 mkdir/Write 的"静默通过"在方案 A **全 allow 配置下本就该静默**（走 allow 规则、不需 auto），**无法区分「allow 放行」vs「auto 放行」**——这是阴性结论却没做阳性对照（违 [[../reflexes]]「阴性结论需阳性对照」）。要证 auto 激活，须先证明"这些命令是 auto 放行而非 allow 放行"，探针做不到。
  2. **关键场景未测**：auto 分类器对 glm-5.2 的 **rm 判断是否生效**根本没测（07-19 §7.2 自己已承认）——这是"glm 支持 auto"结论最脆的地方。
  3. **官网白名单不覆盖第三方**：官网 auto mode 模型清单只列 Claude 系列（Opus 4.6+/Sonnet 4.6+/Fable 5），glm-5.2 未列；但**不在清单 ≠ 不能用**（第三方走 OpenRouter/自定义 endpoint 官网本就不覆盖）——所以官网清单也**不能证伪** glm 支持 auto。
  - **结论**：「glm 是否支持 auto」须**隔离 repo + 真发 rm 的探针**才能定死，07-19 缺的就是这个。当前既不肯定也不否定。
- **删 guard 的主论证不依赖「glm 不支持 auto」**（2026-07-23 补，正解而非替代被订正措辞）：即使 auto 激活，**auto 分类器对 glm-5.2 的 rm 判断是否生效未测** → 删 guard = 拿掉**确定性**兜底换一个**对 glm rm 未验证的概率分类器**。**概率判断不可替代确定性兜底**（见 [[../decisions/self-compliance-probabilistic]]「可靠性归冗余层两档、别混」）。故保留 ask 门 + guard 作 rm 硬底线，auto mode 仅留作减扰非删除类命令。
- **要真让 auto 分类器接管 rm 判断**（而非 ask 门一视同仁弹框）= 从 `ask` 移除 `Bash(rm *)` → 让 auto 语义判断（官网承诺拦 glob rm / 会话前文件 / 递归变量删除、放行会话内具名产物）。但有**两个未验证风险**别贸然移除 ask 门：① auto 分类器是概率判断（非确定保证）；② auto 对第三方模型 rm 的分类是否生效未测（只测了非删除类命令静默）。现实路径 = **保留 ask 门作 rm 硬底线**，auto mode 留作减扰非删除类命令 + 未来验证后才评估移除 ask。

原档：`Mc-emoji/X-顽疾复盘-B模式中途rm反复犯-2026-07-19.md` §7（4 探针矩阵 + 官网原文）。auto mode 版本门槛细节（v2.1.142+ defaultMode 必须放 user settings / 模型清单 / fallback 阈值）留源 repo。

## 详细背景
`Mc-emoji/[feature-02-auto-Enter]/bypass-plan-discussion.md` + `settings-fix-plan.md`（给其他项目 Claude 改 settings 的指令文档）。

相关：[[../reflexes]]（"改 settings 先 .bak / 不开 bypass" 硬反射）、[[../principles]]
