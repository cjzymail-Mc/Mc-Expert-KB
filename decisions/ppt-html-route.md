# decision · PPT→HTML 换路线（COM 两角色拆分）

**决策**：评估"PPT 生产从 COM 换到 HTML/CSS 路线"时——COM 有**两个角色，HTML 只杀得掉第一个**：

| COM 角色 | 能否被 HTML/CSS 取代 |
|---|---|
| ① **视觉创作**（多 run 染色 / 字体接管 / 渐变阴影 / chart 密度） | ✅ 可被 HTML/CSS 取代 |
| ② **加密文件 I/O 底座**（读加密模板 / 产可分发 .pptx / 补 chart / 导验收 PNG） | ❌ **加密强制，永久保留** |

**日期**：2026-05-29

**理由**：本机 Ldterm DLP 按进程名白名单透明加密，非白名单进程（python.exe）碰加密 Office 文件只拿到密文。`win32com` 的本质就是借白名单 Office 进程读明文——这个 I/O 底座 HTML 替不了。"逃离 COM"只能逃它的**视觉创作**角色。

**何时复用此判断**：任何"PPT/Office 生产换 COM-free 路线"的评估。结论：
- **永远别建议** `python-pptx` 装配 / COM-free 导出 / SVG→DrawingML 直写——非白名单进程碰不了加密文件，且 python-pptx 被硬规则禁。
- HTML 路线最多接管视觉创作；产 .pptx / 读加密模板 / 导 PNG 这条 I/O 链必须留 COM。

**原档指针**：`Mc-emoji/.claude/CLAUDE.md` 教训（2026-05-29）；完整路线讨论（含两次自我更正）→ `Mc-emoji/[feature-03]/Mc未来思考2：切换路线的可能性（ppt-html）.md` 05-29 三张卡

相关：[[../reflexes]]（COM-only 硬反射 = 本决策的执行层）、[[../references/cc-permissions]]；偏好底座 [[../principles]]
