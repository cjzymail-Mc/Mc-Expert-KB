# -*- coding: utf-8 -*-
"""feature-05 capture hook launcher（防砖入口 · 部署到中央稳定层 ~/.claude/hooks）。

背景（2026-07-02 Q4-3 探针 + mc-expert 陪审）：UserPromptSubmit hook 退出码 2 = CC「阻断并擦除该
prompt」；而 `python 不存在.py` 恰好退出码 2 → 若直接注册指向高流动 feature 仓的 capture_hook.py，
脚本一旦移动/删除，3 账号×所有 repo×每条 prompt 全被阻断 = 全局变砖。

本 launcher 职责唯一：定位 feature 仓的 capture_hook.py，用 runpy 现读现跑（保住"改脚本即时生效" +
单解释器 + correction_core 单源不劈），**绝不让失败以 exit 2 逃到 CC**（exit 2 = 阻断+擦除 prompt = 砖）。

〔2026-07-02 用户要求：不静默〕捕获断链要**可见但不卡**——官方文档坐实 UserPromptSubmit hook 的
**exit 1（任何非 2 的非零码）= 非阻断**：transcript 显示 `<hook> hook error` 提示 + stderr 首行、
prompt 照常继续、不擦除。故：
  · 正常跑通 → exit 0（静默）
  · capture_hook.py **缺失** / 加载失败（import 错 / correction_core 丢等）→ stderr 报原因 + **exit 1**
    （每条 prompt 都提醒"捕获已停、请修"，绝不砖）。
连 launcher 本身丢（python 跑不起来 = exit 2/127）由注册命令的 `|| exit 1` 兜（见 deploy 脚本）。

CAPTURE_HOOK 路径由 deploy-capture-hook.ps1 部署时注入。**别手工编辑本文件**（保持死简单 = 永不因改动而丢）。
"""
import os, sys, runpy

CAPTURE_HOOK = r"D:\Downloads\Mc Claude Code Workshop\Mc-emoji\[feature-05-loop-self-improvement]\历史扫描\capture_hook.py"  # 部署时被替换为 capture_hook.py 绝对路径

if not os.path.exists(CAPTURE_HOOK):
    sys.stderr.write("[capture-hook] 逻辑脚本缺失，捕获已停，请修复或卸载 hook：%s\n" % CAPTURE_HOOK)
    sys.exit(1)  # 非阻断（≠2）：可见提示、不擦 prompt
try:
    runpy.run_path(CAPTURE_HOOK, run_name="__main__")  # __file__ 指向它 → SCRIPT_DIR/correction_core/out 全对
except SystemExit:
    pass   # capture_hook 内部恒 sys.exit(0) 的正常路径 → 落到下方 exit 0
except Exception as e:
    sys.stderr.write("[capture-hook] 入口加载失败，捕获已停，请修复 hook：%r\n" % e)
    sys.exit(1)  # import 错 / correction_core 丢等结构性断裂 → 可见提示、不砖
sys.exit(0)  # 正常跑通：静默成功

