---
name: office-com-helpers
description: Windows 上用 win32com 操作 PowerPoint / Excel / Word 的通用基础设施——Office 明文/密文检测+后端路由（detect_office_cipher，碰文件第一动作）、COM 属性安全访问（com_get / com_call）、UTF-8 安全 print（safe_print）、Excel 文件读取（含模糊 sheet 匹配、加密文件支持）、文本字数/行数 clamp、shape 是否在 group 内的判断、RGB 转 COM long。任何**开工写 win32com 脚本前先 grep 这里的函数清单**，能复用就别自己手撸——重复造 `try/except getattr` / `cp1252 safe print` / 模糊 sheet 匹配 / 8 字节加密检测 = 浪费时间且大概率漏 edge case。
---

# office-com-helpers

`com-survival-reflexes` 反射模式的**可执行实现**。直接 import 用，省下重复造轮子的时间。

## 何时使用（命中任一就跑）

- 准备写一个 win32com 操作 Office 的脚本（PPT / Excel / Word 都行）—— **开工前先 grep 函数清单**，能复用就别重写
- 准备读 Excel 数据（无论是不是 sheet 名模糊匹配场景）—— 直接用 `load_excel_rows`，免去自己写 COM 启停 + 关闭兜底
- 写脚本中需要 `print()` 中文 / 非 ASCII 字符 —— 直接用 `safe_print`，免得 Windows cp1252 控制台报 UnicodeEncodeError
- 老脚本踩到下面任一坑时，把对应 helper 换上来：
  - 读 `shape.ParentGroup` 抛 COM 异常（应该返回 None 才对）
  - `print()` 在 Windows cp1252 控制台 `UnicodeEncodeError`
  - Excel sheet 名拼写微小差异（"问卷sheet" vs "问卷 sheet"）就找不到
  - 文本溢出 PPT 形状边界，需要按字数/行数硬截断但要保留句子完整

**反模式**（容易被错误降级跳过 — 全部不成立）：
- ❌ "我就用一次 com_get，自己 try/except 两行就行" → 错。每个项目都"两行就行"的累积 = 重复代码满天飞，且漏 case：COM 不止 `pywintypes.com_error`，还可能抛 `AttributeError` / `TypeError`，本 skill 已统一兜底
- ❌ "safe_print 就是 print(.., errors='replace') 吧" → 错。它处理的是 `sys.stdout.encoding` 拿不到 / 是 None 时的兜底链，自己实现常漏一层
- ❌ "我读 Excel 直接用 openpyxl 就行" → 错。openpyxl 读不了加密 / IRM 文件；本 skill 的 `load_excel_rows` 走 COM 路径 + 三层模糊匹配，对加密文件透明
- ❌ "我自己写 clamp_text，就是截字符串而已" → 错。`clamp_text` 在最近的句子边界（。！？；，、空格）截，至少保留 50%，自己写大概率截在半个字 / 半个词中间

## 提供的函数

### Office 明文/密文检测 + 后端路由（碰 Office 文件的第一动作）

```python
from office_com_helpers import detect_office_cipher

route, reason = detect_office_cipher(r"D:\path\to\file.xlsx")
# route ∈ {"python", "com", "stop"}：
#   "python" → 首字节确认 50 4B 03 04 明文 → 可走 openpyxl/python-pptx/python-docx（快 5–20×）
#   "stop"   → 首字节确认 88 7D 1C Ldterm 密文 → STOP 报用户解密（COM 路径可无视，COM 能透明读）
#   "com"    → 未知 magic / 读取失败 → 保守回退 COM
# reason：人读的一句话，含首字节 hex

if route == "python":
    from openpyxl import load_workbook        # 仅在确认明文时才走 python 捷径
    wb = load_workbook(path)
elif route == "stop":
    raise SystemExit(reason)                  # 或：打印 reason 让用户先解密
else:
    ...                                       # 走原有 COM 路径
```

**为什么有这个**：本机 Ldterm 只对白名单 Office 进程的写加密，`python.exe` 写出是明文 → *已解密* 的 .xlsx/.pptx/.docx 可走 python 库提速 5–20×。但**不能假设文件默认解密**，碰文件**第一步永远先读 8 字节**判明文/密文。本函数把这个检测+路由收成一个 canonical 入口，密文时统一礼貌 STOP 而非让 python 崩。

> **cn/coder-api 链路例外**（第二套降级版 team，**已于 2026-06-18 归档作废** → `.claude/skills-archived/team-task-api/`；下为历史记录，主链路不受影响）：密文经 `run_cn_task.ps1` **确定性自动直穿 COM 读 helper，不停**（路由是脚本决策、非模型判断；COM 能透明读密文，无需人工解密）。**主环境 / 原 coder 链路仍 STOP 不变。** 出处见 `Mc-emoji/[feature-03-take-a-nap]/coder-api第二套team-实现交接spec.md` 拍板⑥。

> **前提注记（2026-09-11）**：当前开发机=实验环境**无加密**，本函数恒返 `python`（零误伤、无需关停）；下述 Ldterm 行为为**生产机画像**——产物落地加密机时自动武装。

**边界**（详见 `Mc-emoji/.claude/CLAUDE.md` 的「实测发现」卡）：① 是 fail-safe——任何不确定都回退 COM、绝不误判 python；② 仅覆盖"读/数据填充"，**视觉渲染/导 PNG/复杂染色仍走 COM**；③ python 明文输出仅限自用，对外交付物最终态仍要回 COM 出加密件；④ 单点实测（2026-06-03、当前 Ldterm 配置），不是永久保证。

### COM 安全访问

```python
from office_com_helpers import com_get, com_call, is_in_group

# 安全读 COM 属性（异常→default）
name = com_get(shape, "Name", default="?")
linked = com_get(chart, "ChartData.IsLinked", default=False)  # 注：只支持单层属性

# 安全调用 COM 方法
result = com_call(slide, "Export", path, "PNG", 1920, 1080)

# 判断 shape 是否在 group 内（COM 的 ParentGroup bug 兜底）
if is_in_group(shape):
    ...
```

### 安全 print

```python
from office_com_helpers import safe_print

safe_print("处理中：", chinese_filename)  # 不会因 cp1252 console 崩
```

### Excel COM 读取（含模糊 sheet 匹配 + 加密文件支持）

```python
from office_com_helpers import load_excel_rows

# 三层匹配策略：精确名 → 子串 "问卷" → 第一个 sheet
rows, matched_name, notes = load_excel_rows(
    excel_path=r"D:\path\to\source.xlsx",
    sheet_name="问卷sheet",
    fuzzy_keyword="问卷",  # 中间层的子串匹配关键字
)
# rows: List[List[Any]]，每行所有单元格的原始值（None 表示空格）
# matched_name: 实际匹配到的 sheet 名
# notes: 走了哪条 fallback 路径的说明（用于排查问题）
```

### 文本 clamp（防止 PPT 溢出版面）

```python
from office_com_helpers import clamp_text

text = clamp_text(
    "这是一段很长的文本……" * 100,
    max_chars=200,    # 最多 200 个字符
    max_lines=5,      # 最多 5 行
)
# 在最近的句子边界（。！？\n；，、空格）截断，至少保留 50%
```

### 杂项 helpers

```python
from office_com_helpers import (
    safe_text,   # None → ""，去首尾空白
    numeric,     # 转 float，失败返回 None
    to_rows,     # COM 返回的 tuple/scalar/list 都归一化为 List[List]
    hex_to_com_rgb,  # "FFAABB" → COM 用的 RGB long
)
```

## 导入方式

### 方式 A：sys.path 注入（最简单）

```python
import sys
sys.path.insert(0, r"C:\Users\<USER>\.claude\skills\office-com-helpers")
from office_com_helpers import com_get, safe_print, load_excel_rows
```

### 方式 B：复制到项目里（推荐生产用）

```powershell
Copy-Item "C:\Users\<USER>\.claude\skills\office-com-helpers\office_com_helpers.py" .\pipeline\
```

然后 `from pipeline.office_com_helpers import ...`。这样项目可独立分发，不依赖用户级 skill 目录。

## 设计原则（看一眼避免误用）

1. **绝不 raise**：所有 helper 用 try-except 兜底，失败返回 default 或空值。原因：COM 异常类型多变，一个个 catch 太累；helper 层吞掉异常 + 调用方自己判断空值。
2. **不持有 COM 对象**：传 obj 进来用完即返回，不缓存。避免 RPC 句柄过期 / 内存泄漏。
3. **`load_excel_rows` 永远 read-only 打开**：不会污染源文件。Excel 必须以 `Visible=False, DisplayAlerts=False` 启动，关闭时调 `wb.Close(False)` 不保存。
4. **`load_excel_rows` 模糊匹配的顺序固定**：精确 → 子串关键字 → 第一个 sheet。这个顺序经过 3rd-ppt-prj 实战验证，不要改。

## 不要做

- ❌ 不要把 `com_get` 当成万能：它只支持**单层属性**（`shape.Name`），不支持嵌套（`shape.TextFrame.TextRange.Text` 这种要分多步调用）
- ❌ 不要在循环里反复 `Dispatch("PowerPoint.Application")`：每次 Dispatch 都启动一个新进程实例；正确做法是循环外 `GetActiveObject` 或 Dispatch 一次
- ❌ 不要忘记 `excel.Quit()` 兜底：哪怕 `wb.Close()` 失败，`Quit()` 也要在 `finally` 里跑，否则 Excel 进程残留
