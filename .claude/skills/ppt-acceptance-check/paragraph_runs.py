#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Canonical paragraph-aware run walker.

权威定义：一份 shape 的排版真相。
  - Step 1a（acceptance skill 侧）: 生产者，writer  -> extract_paragraph_runs(shape)
  - Step 1b（pipeline 01_shape_detail.py）: import 后调用，consumer
  - acceptance layers/runs.py paragraphs_match_signature: import 后比对

设计原则
-------
* 轻量无重型依赖：只 import stdlib，不 import layers.common / layers.* 等验收机器。
  这样 pipeline 侧 sys.path 挂 skill 目录后可以直接 import，不会拖进整套验收框架。
* COM 安全：一律 try/except 读属性，不用 getattr()。
* 合并维度单一来源：MERGE_DIMS 常量控制段内 run 合并和跨模块比对两侧同步，
  任何地方想改合并维度只改这里（护栏 #1）。

输出结构
--------
[
  {
    "para_idx": 1,         # 1-based，对应 PPT 原生段落索引
    "alignment": int,      # ppAlignment 枚举值（COM 读失败时 None）
    "text": str,           # 整段文字（保留 \\n 段内软换行，不保留段间 \\r）
    "runs": [
      {
        "rgb":              int,   # COM RGB long（读失败时 None）
        "bold":             int,   # -1=True / 0=False / None
        "size":             float, # pt（读失败时 None）
        "italic":           int,   # -1=True / 0=False / None
        "font_name":        str,   # 读失败时 ""
        "underline":        int,   # -1=有下划线 / 0=无 / None（读失败）
        "baseline_offset":  float, # >0 上标 / <0 下标 / 0 正常 / None（读失败）
        "font_name_ascii":  str,   # 西文字体名，读失败时 ""
        "font_name_fareast":str,   # 中文字体名，读失败时 ""
        "text":             str,   # run 覆盖的文字
      },
      ...
    ],
  },
  ...
]

合并维度与断言维度说明（护栏 #1）
---------------------------------
* 只有在 merge_dims 中的维度才是 per-run 可靠可断言的：
  相邻字符合并时按 merge_dims 中的维度判等，因此 merge_dims 外的维度边界可能
  跨 run 被合并掉，该维度只保留 run 首字符的值，仅供参考。
* 若需对某维度做精确 per-run 断言，必须先把它加入 merge_dims（护栏 #1）。
  调用侧可通过 extract_paragraph_runs(shape, merge_dims=...) 覆盖默认值。
* 默认 MERGE_DIMS = ("rgb", "bold", "size")，向后兼容，不应轻易更改。

行的定义（护栏 #3）
-------------------
* \\r  = PPT 原生段落分隔符 → Paragraphs() 边界 → 本模块的"行"
* \\n  = 段内软换行 → 保留在 para["text"]，但不分割段落
* 纯空白 run（strip() == ""）丢弃：覆盖 \\r / \\n / 纯空格（见 _is_blank_run）
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

# ──────────────────────────────────────────────────────────────────
# 唯一维度常量（护栏 #1 单一来源）
#   * 控制段内相邻 run 的"是否合并"判断
#   * 也作为 paragraphs_match_signature 的默认 check_dims 参照
#   * 不包含 italic / font_name：合并时故意宽松；比对维度可由 rule 覆盖
# ──────────────────────────────────────────────────────────────────
MERGE_DIMS: tuple = ("rgb", "bold", "size")


def _is_blank_run(text: str) -> bool:
    """返回 True 表示该 run 文字在视觉上是空白（纯 \\r / \\n / 空格）。"""
    return not bool(text.strip())


def _read_char_attrs(ch) -> Dict[str, Any]:
    """从单字符 COM 对象安全读取所有需要的字体属性。"""
    result: Dict[str, Any] = {
        "rgb": None, "bold": None, "size": None,
        "italic": None, "font_name": "",
        "underline": None, "baseline_offset": None,
        "font_name_ascii": "", "font_name_fareast": "",
        "text": "",
    }
    try:
        result["text"] = str(ch.Text)
    except Exception:
        pass
    try:
        result["rgb"] = int(ch.Font.Color.RGB)
    except Exception:
        pass
    try:
        result["bold"] = int(ch.Font.Bold)
    except Exception:
        pass
    try:
        result["size"] = float(ch.Font.Size)
    except Exception:
        pass
    try:
        result["italic"] = int(ch.Font.Italic)
    except Exception:
        pass
    try:
        result["font_name"] = str(ch.Font.Name)
    except Exception:
        pass
    try:
        result["underline"] = int(ch.Font.Underline)
    except Exception:
        pass
    try:
        result["baseline_offset"] = float(ch.Font.BaselineOffset)
    except Exception:
        pass
    try:
        result["font_name_ascii"] = str(ch.Font.NameAscii)
    except Exception:
        pass
    try:
        result["font_name_fareast"] = str(ch.Font.NameFarEast)
    except Exception:
        pass
    return result


def _merge_key(attrs: Dict[str, Any], dims: tuple) -> tuple:
    """按 dims 提取合并判断 key（不含 text）。"""
    return tuple(attrs[d] for d in dims)


def _walk_paragraph_runs(
    para_tr,
    merge_dims: Optional[tuple] = None,
) -> List[Dict[str, Any]]:
    """在单个段落 TextRange 内逐字符扫描，按 merge_dims 合并相邻同样式字符。

    Parameters
    ----------
    para_tr    : PPT 段落 TextRange COM 对象
    merge_dims : 合并判断维度；None → 使用模块级 MERGE_DIMS

    返回 merged run 列表；纯空白 run 已丢弃。
    """
    dims = merge_dims if merge_dims is not None else MERGE_DIMS
    try:
        n = int(para_tr.Length)
    except Exception:
        return []
    if n <= 0:
        return []

    # 所有输出 key（含新扩展的 4 个）
    _ALL_KEYS = (
        "rgb", "bold", "size", "italic", "font_name",
        "font_name_ascii", "font_name_fareast", "underline", "baseline_offset",
    )

    runs: List[Dict[str, Any]] = []

    # 读首字符，初始化 accumulator
    first = _read_char_attrs(para_tr.Characters(1, 1))
    cur_key = _merge_key(first, dims)
    cur_text = first["text"]
    cur_attrs = first  # 记录整个 run 的非 text 字段（取第一字符的值）

    for i in range(2, n + 1):
        try:
            ch = para_tr.Characters(i, 1)
        except Exception:
            continue
        attrs = _read_char_attrs(ch)
        key = _merge_key(attrs, dims)

        if key == cur_key:
            # 相同样式 → 合并
            cur_text += attrs["text"]
        else:
            # 样式切换 → 提交当前 run
            if not _is_blank_run(cur_text):
                run_dict = {k: cur_attrs[k] for k in _ALL_KEYS}
                run_dict["text"] = cur_text
                runs.append(run_dict)
            # 启动新 run
            cur_key = key
            cur_text = attrs["text"]
            cur_attrs = attrs

    # 提交最后一个 run
    if not _is_blank_run(cur_text):
        run_dict = {k: cur_attrs[k] for k in _ALL_KEYS}
        run_dict["text"] = cur_text
        runs.append(run_dict)

    return runs


def extract_paragraph_runs(
    shape,
    merge_dims: Optional[tuple] = None,
) -> List[Dict[str, Any]]:
    """Canonical walker: 按 PPT 原生段落（\\r 分隔）切行，段内按 merge_dims 合并 runs。

    Parameters
    ----------
    shape      : COM Shape object（live，需打开的 PPT 实例）
    merge_dims : 段内 run 合并判断维度；None → 使用模块级 MERGE_DIMS。
                 护栏 #1：只有在 merge_dims 中的维度才是 per-run 可靠可断言的。

    Returns
    -------
    list of paragraph dicts（见模块 docstring 的输出结构）

    COM 安全：
      - 整函数 try/except 兜底，任何异常都返回 []
      - 逐属性 try/except 读，不用 getattr
    """
    eff_dims = merge_dims if merge_dims is not None else MERGE_DIMS
    result: List[Dict[str, Any]] = []
    try:
        # 检查 HasTextFrame：COM 返回 -1 表示 True
        try:
            has_tf = int(shape.HasTextFrame)
        except Exception:
            return result
        if has_tf != -1:
            return result

        tf = shape.TextFrame
        try:
            tr = tf.TextRange
        except Exception:
            return result

        try:
            para_count = int(tr.Paragraphs().Count)
        except Exception:
            return result

        for p_idx in range(1, para_count + 1):
            try:
                para = tr.Paragraphs(p_idx)
            except Exception:
                continue

            # 段落对齐方式（ppAlignment enum）
            alignment: Optional[int] = None
            try:
                alignment = int(para.ParagraphFormat.Alignment)
            except Exception:
                pass

            # 整段文字（保留 \n，不保留段间 \r）
            try:
                raw_text = str(para.Text)
                # \r 是段落分隔符噪音（来自 PPT 内部表示），从段内 text 里去掉
                para_text = raw_text.replace("\r", "")
            except Exception:
                para_text = ""

            # 段内 run 合并（透传 merge_dims）
            para_runs = _walk_paragraph_runs(para, merge_dims=eff_dims)

            result.append({
                "para_idx": p_idx,
                "alignment": alignment,
                "text": para_text,
                "runs": para_runs,
            })

    except Exception:
        return []

    return result
