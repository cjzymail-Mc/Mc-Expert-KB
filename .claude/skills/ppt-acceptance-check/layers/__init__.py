"""ppt-acceptance-check 的 6 层验收。

每层暴露 `run(ctx)` 函数，返回 LayerResult。
  L0: pairing  —— shape 配对地基
  L1: data     —— 数据值（chart series / textbox text / picture / table）
  L2: format   —— 几何 / 字体 / 颜色 / autosize
  L3: runs     —— 染色 run 级断言
  L4: behavior —— pipeline trace（COM 失败 / GPT 调用）
  L5: visual   —— PNG + SSIM
"""
