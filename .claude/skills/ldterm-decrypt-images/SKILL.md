---
name: ldterm-decrypt-images
description: 通过 mspaint 白名单进程绕过 Ldterm 加密，把客户/同事用 Ldterm 加密发来的图片（PDF 截图 / 工艺图 / PPT 嵌入图）批量解密为标准 JPEG。任何 Windows Office 项目里遇到「图片打开是花屏」「Python 读图报错 / 像素错乱」「Office 能看但 Python / Pillow 读不到」时优先用这个。
---

# ldterm-decrypt-images

Ldterm 加密对策：批量 / 单张把加密图片解密成标准 JPEG。

## 何时使用

- 用户说「这批图打开是花屏 / 像素错乱」「Python 读不到 / Pillow 报错」「客户发来的资料图我看得到但传不出去」
- 收到了带 Ldterm 加密的 PDF 截图、工艺图、产品图、嵌入 PPT/Word 里的图
- AI 拿到图片路径但 `Image.open()` 失败、读出来全是噪点 / 灰块
- 准备走任何「图→Claude API」「图→OCR」「图→PPT 填充」流程前的预处理

## 原理（重要：先理解再用）

Ldterm 加密按**进程名**做白名单：
- `mspaint.exe` 在白名单 → 打开图能看到正常像素
- `python.exe` 不在白名单 → 直接读文件拿到加密数据

破解套路：
1. 用 mspaint 打开加密图（白名单进程拿到解密像素）
2. mspaint 把解密像素塞进剪贴板
3. Python 从剪贴板读 → 直接写新 JPEG = 标准未加密文件

**关键事实**：Ldterm 是按"写入路径"也可能加密的。如果输出目录恰好被 Ldterm 监控，写出来的 JPEG 也会被加密。这时换输出目录到 `C:\Temp\` 或非监控盘符。

## 两个脚本的选择

### `batch_decrypt_images.py` —— 批量自动跑

适用场景：一次解密一整个目录（10 张以上）
```powershell
# 全部跑
python "C:\Users\<USER>\.claude\skills\ldterm-decrypt-images\batch_decrypt_images.py"

# 只跑前 5 张（小批量测试）
python ".\batch_decrypt_images.py" --limit 5

# 只跑文件名含特定关键字的
python ".\batch_decrypt_images.py" --match "工艺,物性"
```

特性：
- 自动遍历当前目录 + 子目录所有 `.jpg/.jpeg/.png/.webp/.gif/.bmp/.tiff`
- 输出到 `./decrypted/` 子目录，保持原文件名 + 强制 `.jpg` 后缀
- **断点续跑**：已存在的输出文件自动跳过
- **2 次重试**：第二次失败时再加 1.5 秒等待
- **长边压到 1568px**（Claude API 推荐值，>1568 会被 API 自动 resize，浪费 token）
- 每张约 4-5 秒，**运行期间不要碰键盘鼠标**（Ctrl+A/Ctrl+C 模拟）

### `clip_to_jpg.py` —— 单张手动跑

适用场景：只处理 1-2 张，或想确认这台机器上方案能不能跑通
```powershell
# 1. 在 mspaint 里打开加密图
# 2. Ctrl+A → Ctrl+C
# 3. 运行：
python "C:\Users\<USER>\.claude\skills\ldterm-decrypt-images\clip_to_jpg.py" "C:\Temp\out.jpg"
```

特性：
- 带**自检**：写完后 `Image.open()` 回读，验证输出文件未被 Ldterm 加密
- 自检失败会提示换输出目录

## 失败兜底诊断

| 症状 | 可能原因 | 处理 |
|---|---|---|
| `找不到 mspaint 窗口` | mspaint 启动慢 / UAC 弹窗 | 加大 `MSPAINT_OPEN_WAIT_BASE`，关闭 UAC 弹窗 |
| `Ctrl+C 后剪贴板里没有位图` | mspaint 还没加载完图 / 焦点没到位 | 检查图片是否确实能在 mspaint 里看到；加大等待秒 |
| 写出后 `Image.open` 失败 | 输出路径也被 Ldterm 监控 | 换到 `C:\Temp\` 或外接盘 |
| 全部 OK 但内容看起来是黑色 | mspaint 实际打开时被 Ldterm 拒绝 | mspaint 不在白名单（罕见）；换看图软件 |

## 不要做

- ❌ 不要 `bypassPermissions` 跑这个（脚本会发模拟键盘事件，Claude 应该看着它跑）
- ❌ 不要在运行期间切走焦点（Ctrl+A/Ctrl+C 会发到错误的窗口）
- ❌ 不要把 `decrypted/` 输出目录放在被 Ldterm 监控的盘符
