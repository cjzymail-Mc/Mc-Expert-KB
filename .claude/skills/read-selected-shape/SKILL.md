---
name: read-selected-shape
description: 读取 PowerPoint 中当前鼠标选中的 shape 的完整信息（COM 内部名、Left/Top/Width/Height 坐标、文本、字体、颜色、chart 数据、图片裁剪）。任何想知道「这个形状/矩形/文本框叫啥名」「L T W H 多少」「图表数据怎么存」「图片裁剪是多少」「微调坐标基准值」「shape 在选择窗格里的本地化名 vs COM 内部名对不上」的场景，优先用这个；底层 GetActiveObject 桥接，不会动用户文件。
---

# read-selected-shape

PPT 实时调试神器：把 PowerPoint 当前选中的 shape 完整信息打到 stdout，方便直接贴回对话。

## 何时使用（命中任一就跑）

- 用户说「帮我看下这个 shape 长什么样」「这个矩形/文本框/图表叫什么名字」「我刚选中的那个 shape 的坐标是多少」
- 用户说「L T W H 多少」「Left Top Width Height」「这个的位置/尺寸」
- 模板适配 / 微调位置前，需要拿到 shape 的 COM 内部名称（**注意**：和"选择窗格"显示的本地化名可能不同 —— 选择窗格显示"矩形 5"，COM 里可能叫 `Rectangle 5` / `Shape5` / 历史改过名的旧 ID）
- 调试图表类 shape：要看 ChartType / SeriesCollection / IsLinked 状态、ChartData 里到底存的什么数
- 调试图片类 shape：要看 CropLeft/CropTop/CropRight/CropBottom + 原生尺寸（很多模板的"看上去裁过"其实是 crop 不是缩放）
- 调试填充/边框：要看 RGB 颜色 / 透明度 / 边框粗细的精确值

**反模式**（容易被错误降级跳过 — 全部不成立）：
- ❌ "我用 inspect-ppt-template 全扫一遍能拿到所有 shape 信息" → 错。inspect 是文档级广扫（不含 chart 数据 / crop / 字体细节），具体某个 shape 的深度取证还得用 `read-selected-shape`
- ❌ "我自己写一段 win32com 读 shape 属性更快" → 错。本 skill 已处理 COM 属性的 try/except 兜底 + group 内 shape 判断，自己重写大概率漏 case

## 前置条件

1. 用户的 PowerPoint 已打开目标文件
2. 用户已经**在 PPT 里选中**一个或多个 shape（选中状态由用户人工操作，AI 不能代选）
3. Python 环境装好 `pywin32`（`pip install pywin32`）

## 调用方式

```powershell
# 系统真身（推荐写在 SKILL 文档里的规范路径）
python "C:\Users\<USER>\.claude\skills\read-selected-shape\read_selected_shape.py"
python "C:\Users\<USER>\.claude\skills\read-selected-shape\read_selected_shape.py" --full

# 项目入口 wrapper（如果项目里有 skills/read_selected_shape.py，可用相对路径）
python skills/read_selected_shape.py
python skills/read_selected_shape.py --full
```

两种调用等价。项目 wrapper 用 `runpy` 透传 argv 到系统真身，无功能差异，wall time ~+0 s。

## 两档输出模式

| 模式 | 触发 | 包含 | wall time（参考） |
|--|--|--|--|
| compact（默认） | 不带参数 | 几何 / 类型 / 文本段落级字体 / Fill+Line / Chart series 基础 / Picture crop | ~0.7 s |
| **full** | 加 `--full` | compact 全部 + run 级字体（Name/Ascii/FarEast/Size/Bold/Italic/Underline/Shadow/Color/Baseline）+ 段落 Align/SpaceWithin + Shadow + 3D（visible 时）+ Line.DashStyle/Style + Chart series 填充色 / Axes Min/Max / HasTitle / TitleText + Picture LinkFormat + Table 每格 text/merged | ~1.1 s |

## 输出字段速查

每个 shape 顶部固定打：
- `NAME` —— COM 内部名（最关键，写微调代码时用这个）
- `TYPE` —— MsoShapeType（13=Picture, 17=TextBox, 3=Chart, 19=Table 等）
- `POSITION` —— Left / Top / Width / Height（单位 point）
- `ROTATION / Z_ORDER / VISIBLE / HAS_TEXT_FRAME / HAS_CHART / HAS_TABLE / AUTO_SHAPE_TYPE`

按 shape 类型条件打：
- 有 TextFrame 时：每段文字（compact：段落级字体）/ run 级字体（--full）
- 有 Chart 时：ChartType / IsLinked / SeriesCollection 数据；--full 还打每 series 填充色 / Axes / Title
- 有 Picture 时：Crop 四边 + Brightness / Contrast；--full 还打 LinkFormat
- 有 Table 时：rows × cols；--full 还遍历每个 cell
- AutoShape / TextBox：Fill / Line；--full 还打 Shadow / 3D

## 失败兜底

- `PPT_NOT_ACTIVE` → 提示用户把 PowerPoint 打开并切到前台
- `NO_SELECTION` / `SELECTION_TYPE=0` → 提示用户先在 PPT 里点选一个 shape
- 单个属性读不到时 silent fallback 到 `""`，不会让整个脚本崩
