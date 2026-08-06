---
name: pipeline-self-check-loop
description: 任何「AI 自动生成 Office / 报告 / 代码 → 交付前自检」类 pipeline 的标准三阶段循环模式：Build（生成）→ Self-check（结构性 + 视觉性自检）→ Deliver（达标交付 / 升级到人审）。在写 pipeline 前先读这个；遇到「AI 输出能跑但质量不稳定」时按这套结构改造。
---

# pipeline-self-check-loop

AI 驱动的自动化生产线最常踩的坑：**「能跑通 ≠ 输出合格」**。Build 之后没有自检环节，第一次跑出来就交给用户，每次都得用户人工挑刺。这个 skill 是把"AI 自驱迭代"落地的核心反射模式。

## 何时使用（命中任一就跑）

- 写一个「AI 输入 X → 输出 Y」的脚本 / pipeline 类项目
- 用户说「AI 跑出来的结果质量不稳定，每次都要我人工检查一遍」
- 已有 pipeline 跑通了 build 步骤，要加质量门禁
- 准备改造一个"输出即交付"的脚本为"输出 → 自检 → 交付"
- 任何包含「PPT 自动生成」「Word 模板填充」「Excel 报告自动化」「批处理 N 个文件」字样的 pipeline 类需求

**反模式**（容易被错误降级跳过 — 全部不成立）：
- ❌ "这是临时小脚本，跑一次就丢，不用搞自检" → 错。哪怕一次性脚本也要做结构性自检（10 秒内的事），免得人审找半天才发现一个空字段
- ❌ "用户只要 build 出文件就行，没让我自检" → 错。AI 自驱迭代的核心就是"build → self-check → 自动修复"闭环，不上自检 = 把人审成本全部转嫁给用户
- ❌ "自检会拖慢迭代" → 错。结构性自检 ≤ 10 秒，比"用户人审一轮 + 来回沟通 + 再跑一次"快一个数量级
- ❌ "没有标杆参考，没法做视觉自检" → 没关系，**结构性自检（2a）必做、视觉自检（2b）可选**，二者解耦
- ❌ "build 已经包含 assert / try-except 了，不算自检吗" → 错。assert 是防崩，自检是查交付质量，不在一个维度

**直接交付 build 输出 = 把人审成本转嫁给用户**。AI 不上自检循环就不算"自动化"。

## 三阶段循环

```
┌─────────────────────────────────────────────────────────────┐
│                                                             │
│   Build  ──→  Self-check  ──→  Deliver                      │
│     ▲             │                                         │
│     │             │ (issue found)                           │
│     │             ▼                                         │
│     └──── Auto-fix (≤ N 轮)                                  │
│                                                             │
│                  Self-check fail × N → 升级到人审            │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 阶段 1：Build —— 主体生成

- 走主流程：填充模板 / 生成 PPT / 写报告
- **失败时不直接退出**，记录 build 阶段的 issue 到结构化日志，让 Self-check 一并报告

### 阶段 2：Self-check —— 两类自检并行

#### 2a. 结构性自检（cheap，必做）

- 必填字段都填了吗？（白名单清单逐项核对）
- 表格行数对吗？模板里的"待染色"标记还残留吗？
- 文件大小 / 页数 / 段落数是否在合理范围？
- JSON schema 验证（如果 pipeline 有中间 JSON 产物）

```python
def structural_check(output_path) -> list[dict]:
    """Return issues. Empty list = pass."""
    issues = []
    if not Path(output_path).exists():
        issues.append({"severity": "严重", "dim": "存在性", "desc": "输出文件不存在"})
        return issues
    size_kb = Path(output_path).stat().st_size // 1024
    if size_kb < 10:
        issues.append({"severity": "严重", "dim": "大小", "desc": f"文件太小 {size_kb}KB"})
    # ... 业务相关检查
    return issues
```

#### 2b. 视觉性自检（expensive，可选）

- 用 `ppt-acceptance-check` skill 的 L5 视觉层（吸收自原 ppt-visual-fidelity-check）
- 对比"本次输出 vs 上次成功输出"或"本次输出 vs 标杆参考"
- SSIM < 0.85 → 视觉显著漂移，记录为 issue

**推荐**：直接调用 `ppt-acceptance-check` 主入口 + `--layers L5`，它已封装了 6 层验收，2b 视觉是其中一层：

```powershell
python "C:\Users\<USER>\.claude\skills\ppt-acceptance-check\ppt_acceptance_check.py" `
    --new "output.pptx" --template "reference.pptx" `
    --slide-pairs "5:5" --layers L5 --out-dir "debug/self-check/"
```

**库函数方式**（pipeline 内嵌时用）：`ppt_visual_check.py` 作为底层库函数保留在 `ppt-visual-fidelity-check/` 目录（SKILL.md 已删除，不再触发 skill），仍可 import：

```python
import sys
sys.path.insert(0, r"C:\Users\<USER>\.claude\skills\ppt-visual-fidelity-check")
from ppt_visual_check import slide_export_png, ssim_compare

# build 后导出关键页 PNG，和参考对比
score = ssim_compare("output_slide5.png", "reference_slide5.png")
if score < 0.85:
    issues.append({"severity": "中等", "dim": "视觉",
                   "desc": f"SSIM {score:.2f} < 0.85，视觉漂移"})
```

### 阶段 3：Deliver —— 三条出口

```python
issues = structural_check(out) + visual_check(out)

if not issues:
    return "DELIVER"                                  # 直接交付
elif fixable(issues) and attempt < MAX_RETRY:
    auto_fix(issues); return "RETRY"                  # 触发自动修复，重跑 build
else:
    write_report(issues, severity_map); return "ESCALATE"  # 升级到人审
```

| 出口 | 触发条件 | 后续动作 |
|---|---|---|
| **DELIVER** | issues 为空 | 写交付 manifest，记录这次产出 |
| **RETRY** | 有 issue 且 `fixable=True` 且 `attempt < N` | 自动修复后重跑 build；上限通常 **N=2 次**（防止死循环） |
| **ESCALATE** | 严重 issue / 修复轮次用完 / 不可自动修复 | 写 `self-check-report.md` 列出所有 issue 给人审 |

## 实现要点

### 1. 自检报告必须**结构化 + 人类可读**

参考 3rd-ppt-prj 的 `generate_self_check_report()`：

```python
def generate_self_check_report(issues, out_path, ssim_score=-1.0, attempts=1):
    lines = ["# Self-Check Report", ""]
    if issues:
        lines.append("| # | 维度 | 问题 | 严重度 | 状态 |")
        lines.append("|---|------|------|--------|------|")
        for i, iss in enumerate(issues, 1):
            lines.append(f"| {i} | {iss['dim']} | {iss['desc']} "
                         f"| {iss['severity']} | {iss.get('status', '-')} |")
    else:
        lines.append("无问题发现。")
    lines.append("\n## 总结")
    severe = sum(1 for i in issues if i['severity'] == '严重')
    medium = sum(1 for i in issues if i['severity'] == '中等')
    lines.append(f"- 自检轮次：{attempts}")
    lines.append(f"- 发现问题：{severe} 严重 / {medium} 中等")
    if ssim_score >= 0:
        lines.append(f"- 视觉相似度：SSIM {ssim_score:.2f}")
    Path(out_path).write_text("\n".join(lines), encoding="utf-8")
```

### 2. 自动修复上限 = 2 轮

**Why**：超过 2 轮还修不好 = 问题超出自动修复能力，再多轮也是浪费 token。第 3 轮起直接 ESCALATE。

### 3. severity 三档制

| severity | 含义 | 处理 |
|---|---|---|
| 严重 | 必须修才能交付（缺必填 / 文件损坏 / 视觉严重漂移） | 阻断交付 |
| 中等 | 可疑但能交付（轻微视觉差 / 边界值） | 报告但不阻断 |
| 提示 | 仅供参考（建议项） | 仅记录 |

### 4. 自检函数本身要**幂等 + 快**

- 不修改输出文件（自检只读）
- 单次自检 ≤ 10 秒（视觉自检除外）
- 不依赖外部网络（避免引入新的失败维度）

### 5. 被测链路含 AI 时：证据必须防模型 probe 后篡改

**触发**：pipeline 的被测链路本身包含 AI 模型 + 工具调用（AI-in-the-loop 的 probe / 验收）。
**不触发**：被测对象是静态模板 / 数据（纯文件填充类，2a/2b 足够）。

当被测链路里有 AI，"产生了证据文件" ≠ 证据可信——模型可能在 probe 之后调用 Bash / 工具把同一路径覆盖成退化内容，而 runner 只检查"有新文件"会表面 PASS。硬动作：

1. **证据通道对模型不可见**：证据路径用 hidden + 随机文件名，创建后不把路径放进对话；prompt / skill 明确要求证据产生后立即返回、不再调用工具。
2. **外部 schema 门 + 链路阳性与语义分离**：runner 不只看文件存在，校验固定字段数 / 必需字段 / 各 case 内容判据；plugin loaded / tool dispatched / evidence schema 先过，才允许判参数语义 PASS/FAIL。

相关（不复述，指针）：validator 自证能判对（正负样本分别证灵敏度 / 特异性、非空与期望计数是独立硬门）见 reflexes「阴性结论需阳性对照」；"模型 run-local 自报不是运行生命周期最高证据、外部 session 事件优先"是 pipeline 设计原则，此处仅指针。

## 与其他 skill 的协同

- `ppt-acceptance-check` —— Self-check 阶段 2b 的统一引擎（6 层验收，含 L5 视觉对比，吸收自原 ppt-visual-fidelity-check）
- `office-com-helpers` —— Self-check 时用 `com_get` 安全读取产物结构
- `read-selected-shape` —— ESCALATE 后用户手动调试时的取证工具
- `three-state-coloring-contract-word-only` —— 自检规则之一（**仅 Word**）：检查"待染色"标记是否全部消除

## 不要做

- ❌ 不要把 Build 和 Self-check 写到同一个函数里——它们必须解耦，自检要能独立重跑
- ❌ 不要让自动修复轮次无上限——必须有 `MAX_RETRY=2`
- ❌ 不要把"视觉自检失败"列为严重——SSIM 对文字差异不敏感，单凭它阻断交付会误伤
- ❌ 不要在 RETRY 路径上跳过 Build，直接重跑 Self-check——必须重新 Build（修复可能改了输入 / 中间产物）
