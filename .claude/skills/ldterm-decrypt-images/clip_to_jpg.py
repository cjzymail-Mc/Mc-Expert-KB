"""
剪贴板取图 → 落地为标准 JPEG（绕过 Ldterm 加密）

用法：
    1. 在 mspaint（或任何 Ldterm 白名单内的看图软件）中打开一张图
    2. Ctrl+A → Ctrl+C 复制到剪贴板
    3. 在终端运行：python clip_to_jpg.py <输出文件名>
       例：python clip_to_jpg.py decrypted/test1.jpg

脚本会：
  - 读取剪贴板位图（这是解密后的像素数据）
  - 等比缩放到最长边 2000px
  - 保存为标准 JPEG（quality=85）
  - 自检：Python 能否回读这个新文件（验证未被 Ldterm 二次加密）

来源：fangcaixia 工作流（2026-05-26 提为用户级 skill）
"""

import io
import sys
from pathlib import Path
from PIL import ImageGrab, Image

MAX_SIDE = 2000
JPEG_QUALITY = 85


def main():
    if len(sys.argv) < 2:
        print("用法: python clip_to_jpg.py <输出路径.jpg>")
        sys.exit(1)

    out_path = Path(sys.argv[1])
    out_path.parent.mkdir(parents=True, exist_ok=True)

    img = ImageGrab.grabclipboard()
    if img is None:
        print("ERR 剪贴板里没有图片。请在 mspaint 中 Ctrl+A → Ctrl+C 后再运行。")
        sys.exit(2)
    if isinstance(img, list):
        # 复制的是文件路径列表，不是位图
        print(f"ERR 剪贴板内容是文件路径，不是位图：{img}")
        print("    请在 mspaint 中打开图后用 Ctrl+A → Ctrl+C，而不是在资源管理器里复制文件。")
        sys.exit(3)

    print(f"剪贴板图像尺寸: {img.size[0]} x {img.size[1]}  mode={img.mode}")

    if img.mode != "RGB":
        img = img.convert("RGB")

    w, h = img.size
    if max(w, h) > MAX_SIDE:
        if w >= h:
            new_w, new_h = MAX_SIDE, int(h * MAX_SIDE / w)
        else:
            new_w, new_h = int(w * MAX_SIDE / h), MAX_SIDE
        img = img.resize((new_w, new_h), Image.LANCZOS)
        print(f"缩放到: {img.size[0]} x {img.size[1]}")

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=JPEG_QUALITY, optimize=True)
    out_path.write_bytes(buf.getvalue())

    # 自检：Python 能否回读自己写出的文件？
    try:
        check = Image.open(out_path)
        check.load()
        size_kb = out_path.stat().st_size // 1024
        print(f"OK  写出 {out_path}  ({check.size[0]}x{check.size[1]}, {size_kb}KB)")
        print("自检：Python 能正常读回这个 JPEG（说明未被 Ldterm 加密）。")
    except Exception as e:
        print(f"WARN 写出后回读失败：{e}")
        print("    很可能 Ldterm 在写入路径上也做了加密，需要换输出目录（如 C:\\Temp）。")


if __name__ == "__main__":
    main()
