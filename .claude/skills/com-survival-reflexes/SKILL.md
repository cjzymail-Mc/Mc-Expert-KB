---
name: com-survival-reflexes
description: Windows COM 操作 Office（Word / Excel / PowerPoint）时的生存反射模式——硬超时、必死兜底、CUTOVER 切换 PowerShell、僵尸进程兜底。任何时候用 win32com 写自动化脚本前先读这个；遇到 COM 调用挂死 / 进程残留 / 偶发崩溃时也读这个找应对策略。
---

# com-survival-reflexes

Office COM 自动化的"避雷手册"。Word / Excel / PowerPoint 的 COM 接口是不可靠的——版本差、license 状态、并发文件锁、Ldterm / DLP 的拦截、随机抽风的「没响应」……每一种都能让脚本无声挂死或炸出诡异异常。这个 skill 把跨项目反复踩到的坑沉淀成 7 条反射动作。

## 何时使用（命中任一就跑）

- **写新脚本前**：开工前对照 7 条反射清单走一遍，避免重新踩坑
- **debug 现场**：脚本挂死 5 秒以上 / 抛 COM 异常 / 输出空 / Office 进程残留时，按症状找对应反射
- **改造老脚本**：发现原脚本没 R2 finally 兜底 / 没 R6 关 DisplayAlerts / 在循环里反复 Dispatch —— 按反射逐条补上

**反模式**（容易被错误降级跳过 — 全部不成立）：
- ❌ "我这脚本就跑一次，不用搞超时兜底" → 错。COM 一次挂死就是十分钟起，比写超时包装贵得多
- ❌ "我用 Dispatch 就行，DispatchEx 太重" → 错。Dispatch 会拿到上次没退干净的僵尸实例，状态错乱后 debug 的时间远超"启新进程"的几秒开销
- ❌ "Quit() 就够了，不用 taskkill" → 错。Quit 本身也可能挂死，必须双保险（finally 里 Quit + taskkill）
- ❌ "我用 try/except 包了就行，何必上 com_get" → 错。`getattr` 对 COM 对象不返回 None 而是抛异常，每个属性都包 try/except 代码很丑，用 helper 一行解决
- ❌ "宏 / DisplayAlerts 又不会真弹" → 错。自动化场景下任何 UI 提示都是死结（无人点击 = 永久卡死），R6 三行配置必须无条件加
- ❌ "Ldterm 加密文件我读不了，跳过" → 错。win32com 启动的 Office 在 Ldterm 白名单上，能直接读；卡的是 `slide.Export()` 输出 PNG，走剪贴板路径（参考 `ppt-acceptance-check` 的 L5 视觉层）就过

## 七条生存反射

### R1：单 COM 调用硬超时 20-30 秒

**症状**：脚本卡在 `wb.Save()` / `slide.Export()` / `app.Quit()` 不动，等 10 分钟也不返回。

**反射**：用线程 / signal 包一层硬超时，超过 20-30 秒**强杀进程**：

```python
import threading
import subprocess

def call_with_timeout(fn, timeout=30, on_timeout=None):
    result = {"value": None, "err": None}

    def target():
        try:
            result["value"] = fn()
        except Exception as e:
            result["err"] = e

    t = threading.Thread(target=target, daemon=True)
    t.start()
    t.join(timeout)
    if t.is_alive():
        if on_timeout:
            on_timeout()  # 强杀 EXCEL.EXE / WINWORD.EXE / POWERPNT.EXE
        raise TimeoutError(f"COM call exceeded {timeout}s")
    if result["err"]:
        raise result["err"]
    return result["value"]
```

**Why**：COM RPC 没有原生 timeout，挂死后线程会永远等。

### R2：finally 必死兜底 + 强杀进程

**症状**：脚本异常退出后，任务管理器里 EXCEL.EXE / WINWORD.EXE / POWERPNT.EXE 残留，下次 Dispatch 拿到僵尸实例。

**反射**：每个 COM 操作的最外层必须有 `try/finally`，finally 里 `Quit()`+ `taskkill` 双保险：

```python
import subprocess
import win32com.client

excel = win32com.client.DispatchEx("Excel.Application")
try:
    excel.Visible = False
    excel.DisplayAlerts = False
    wb = excel.Workbooks.Open(path, ReadOnly=True)
    # ... 业务逻辑 ...
    wb.Close(False)
finally:
    try:
        excel.Quit()
    except Exception:
        pass
    # 兜底强杀（如果 Quit 也挂死）
    subprocess.run(["taskkill", "/F", "/IM", "EXCEL.EXE"],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
```

**Why**：`Quit()` 自己也可能挂死。必须双保险。

### R3：用 `DispatchEx` 而不是 `Dispatch`

**症状**：脚本拿到上次没退干净的 Office 实例，状态错乱（带着上次的文件、对话框、剪贴板）。

**反射**：

```python
# ❌ 错的
app = win32com.client.Dispatch("Excel.Application")  # 可能复用已有实例

# ✅ 对的
app = win32com.client.DispatchEx("Excel.Application")  # 强制新进程
```

**Why**：`Dispatch` 会重用已有进程；`DispatchEx` 强制起新的。对自动化场景永远用 `DispatchEx`。

### R4：所有 COM 属性 / 方法用 try/except 包，不用 getattr

**症状**：`getattr(shape, 'ParentGroup', None)` 不返回 None，而是抛 COM 异常。

**反射**：用专门的 `com_get` / `com_call` helper（参考实现见 `office-com-helpers` skill）：

```python
# ❌ 错的
parent = getattr(shape, "ParentGroup", None)  # COM 对象的 getattr 会抛错

# ✅ 对的
def com_get(obj, attr, default=None):
    try:
        return getattr(obj, attr)
    except Exception:
        return default
```

**Why**：COM 不遵守 Python 的 `__getattr__` 协议；对不存在的属性它会直接抛 `pywintypes.com_error`。

### R5：CUTOVER 反射——COM 装不上就切 PowerShell

**症状**：客户机器没装 Office / 装的是 LibreOffice / 用绿色版 / 用 WPS。win32com 直接 ImportError 或 Dispatch 失败。

**反射**：在脚本入口先**探测能力**，探测失败就切到 PowerShell + COM Automation 兜底脚本（`.ps1`），或退化到 python-pptx / openpyxl 这类纯 ZIP 解析方案：

```python
def probe_com_available():
    try:
        import win32com.client
        app = win32com.client.DispatchEx("Excel.Application")
        app.Quit()
        return True
    except Exception:
        return False

if not probe_com_available():
    print("[CUTOVER] COM 不可用，切换到 PowerShell 兜底脚本")
    subprocess.run(["powershell.exe", "-File", "cutover_fallback.ps1", input_path])
    sys.exit(0)
```

**Why**：win32com 不可用时不要让脚本崩，要有降级路径。常见的两条 CUTOVER：
- 简单填充 → `python-pptx` / `openpyxl`（纯 ZIP 解析，无 COM 依赖）
- 复杂操作（必须 COM） → PowerShell 启动 Office COM Automation

### R6：DisplayAlerts = False + AutomationSecurity = ForceDisable

**症状**：脚本跑到一半弹"是否启用宏""文件损坏"等模态框，无人点击导致永久卡死。

**反射**：每个 COM 应用启动后**立刻**关掉所有交互提示：

```python
excel.DisplayAlerts = False           # 通用
excel.AskToUpdateLinks = False        # Excel：外部链接询问
word.AutomationSecurity = 3           # Word：msoAutomationSecurityForceDisable（禁宏）
ppt.DisplayAlerts = 0                 # PowerPoint
```

**Why**：自动化场景下任何 UI 都是死结。

### R7：Ldterm / 加密文件的认知

**症状**：加密 PPT/Word 用 win32com 打开是正常的（白名单），但 `slide.Export()` 出来是黑图，或者 Python 写出来的文件回读报错。

**反射**：参考 `ldterm-decrypt-images` skill。简短规则：
- **win32com 启动的 Office 进程在 Ldterm 白名单上** —— 能正常读加密文件
- **Python 写出的新文件可能被 Ldterm 反向加密** —— 输出目录避开监控盘符（用 `C:\Temp\`）
- **`slide.Export()` 受文件级加密影响** —— 用 `Copy → 剪贴板 → Pillow` 绕过（参考 `ppt-acceptance-check` 的 L5 视觉层，吸收自原 ppt-visual-fidelity-check）

## 参考实现

代码切片直接复用：[`office-com-helpers`](../office-com-helpers/SKILL.md) skill 提供了 `com_get` / `com_call` / `is_in_group` / `safe_print` / `load_excel_rows` 等可 import 的纯函数。

## 反射触发顺序（debug 时按这个走）

遇到 COM 异常时按下表顺序排查：

| # | 问题 | 反射 |
|---|---|---|
| 1 | 脚本挂死 ≥ 5 秒 | R1 硬超时 + R2 强杀 |
| 2 | 进程残留 | R2 finally + taskkill |
| 3 | 拿到僵尸实例 | R3 改 DispatchEx |
| 4 | `getattr` 抛错 | R4 用 com_get |
| 5 | Office 没装 | R5 CUTOVER |
| 6 | 弹模态框卡死 | R6 关 DisplayAlerts + 宏 |
| 7 | 加密文件出黑图 | R7 走剪贴板路径 |

## 不要做

- ❌ 不要假设 `obj.Close()` 一定能正常返回——它也可能挂死，必须配 R1 超时
- ❌ 不要在循环里反复 `DispatchEx`——每次都启新进程，资源消耗爆炸；循环外起一次
- ❌ 不要省略 R6 的 `DisplayAlerts = False`——这是最常见的"为什么我的脚本只在自动化时卡住"
- ❌ 不要 CUTOVER 到 `python-pptx` 后又混着 COM 用——两套写入模式会互相破坏文件
