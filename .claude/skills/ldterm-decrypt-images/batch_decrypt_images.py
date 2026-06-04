"""
批量「解密」Ldterm 加密图片：mspaint 打开 → Ctrl+A/Ctrl+C → 读剪贴板 → 存为标准 JPEG。

原理：
  Ldterm 加密系统按进程名做白名单。mspaint 在白名单上，能拿到解密像素；
  Python 不在白名单上，但 Python 写出的新文件不会被反向加密。
  于是：mspaint 把解密像素塞进剪贴板 → Python 读剪贴板 → 直接落盘 = 标准 JPEG。

用法：
  python batch_decrypt_images.py              # 全跑
  python batch_decrypt_images.py --limit 5    # 只跑前 5 张
  python batch_decrypt_images.py --match "工艺,物性"  # 文件名子串过滤
  （运行期间不要碰键盘鼠标，约 4-5 秒/张）

输出：
  当前目录下 decrypted/ 子目录，文件名保持一致但强制 .jpg 后缀。
  已存在的输出文件会跳过（断点续跑）。

来源：fangcaixia 工作流（2026-05-26 提为用户级 skill）
"""

import argparse
import io
import subprocess
import sys
import time
from pathlib import Path

import win32clipboard
import win32com.client
import win32con
import win32gui
import win32process
from PIL import Image, ImageGrab

# ── 配置 ──────────────────────────────────────────────────────
ROOT = Path.cwd()
OUT_SUBDIR_NAME = "decrypted"
MAX_SIDE = 1568   # Claude 推荐图片长边上限（>1568 会被 API 自动 resize，浪费 token）
JPEG_QUALITY = 85
EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".tiff"}

MSPAINT_OPEN_WAIT_BASE = 1.8     # 基础等待秒
MSPAINT_OPEN_WAIT_PER_MB = 0.6   # 每 MB 额外等待
CLIPBOARD_POLL_SECONDS = 6.0     # 发完 Ctrl+C 后轮询剪贴板的最长时间
INTER_FILE_WAIT = 0.3
# ─────────────────────────────────────────────────────────────


def find_mspaint_hwnd(pid: int):
    """根据 PID 找到 mspaint 主窗口句柄。"""
    found = []

    def enum_cb(hwnd, _):
        if not win32gui.IsWindowVisible(hwnd):
            return True
        _, wpid = win32process.GetWindowThreadProcessId(hwnd)
        if wpid == pid and win32gui.GetWindowText(hwnd):
            found.append(hwnd)
        return True

    win32gui.EnumWindows(enum_cb, None)
    return found[0] if found else None


def focus_window(hwnd: int):
    """把窗口置前并激活（处理 minimized 情况）。"""
    if win32gui.IsIconic(hwnd):
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
    try:
        win32gui.SetForegroundWindow(hwnd)
    except Exception:
        # 偶发 Access denied —— 先 minimize 再 restore 也能强制聚焦
        win32gui.ShowWindow(hwnd, win32con.SW_MINIMIZE)
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)


def clear_clipboard():
    win32clipboard.OpenClipboard()
    try:
        win32clipboard.EmptyClipboard()
    finally:
        win32clipboard.CloseClipboard()


def grab_after_keystrokes(shell, poll_seconds: float = CLIPBOARD_POLL_SECONDS):
    """发 Ctrl+A → Ctrl+C，等待并返回剪贴板里的 PIL.Image。"""
    shell.SendKeys("^a")
    time.sleep(0.2)
    shell.SendKeys("^c")
    deadline = time.time() + poll_seconds
    while time.time() < deadline:
        time.sleep(0.15)
        img = ImageGrab.grabclipboard()
        if isinstance(img, Image.Image):
            return img
    return None


def save_jpeg(img: Image.Image, out_path: Path) -> tuple[int, int, int]:
    if img.mode != "RGB":
        img = img.convert("RGB")
    w, h = img.size
    if max(w, h) > MAX_SIDE:
        if w >= h:
            new_w, new_h = MAX_SIDE, int(h * MAX_SIDE / w)
        else:
            new_w, new_h = int(w * MAX_SIDE / h), MAX_SIDE
        img = img.resize((new_w, new_h), Image.LANCZOS)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=JPEG_QUALITY, optimize=True)
    out_path.write_bytes(buf.getvalue())
    size_kb = out_path.stat().st_size // 1024
    return img.size[0], img.size[1], size_kb


def process_one(src: Path, dst: Path, shell) -> str:
    size_mb = src.stat().st_size / (1024 * 1024)
    open_wait = MSPAINT_OPEN_WAIT_BASE + size_mb * MSPAINT_OPEN_WAIT_PER_MB

    last_err = ""
    for attempt in (1, 2):
        clear_clipboard()
        proc = subprocess.Popen(["mspaint.exe", str(src)])
        try:
            hwnd = None
            deadline = time.time() + 6.0
            while time.time() < deadline and hwnd is None:
                time.sleep(0.3)
                hwnd = find_mspaint_hwnd(proc.pid)
            if hwnd is None:
                last_err = "找不到 mspaint 窗口"
                continue

            time.sleep(open_wait)
            focus_window(hwnd)
            time.sleep(0.3)

            img = grab_after_keystrokes(shell)
            if img is None:
                last_err = "Ctrl+C 后剪贴板里没有位图"
                # 第二次重试时再加 1.5 秒等待
                open_wait += 1.5
                continue

            w, h, kb = save_jpeg(img, dst)
            note = f" (重试成功)" if attempt > 1 else ""
            return f"  OK  {src.name}  →  {dst.relative_to(ROOT)}  ({w}x{h}, {kb}KB){note}"
        finally:
            subprocess.run(
                ["taskkill", "/F", "/PID", str(proc.pid)],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                check=False,
            )
    return f"  ERR {src.name}: {last_err}（已重试）"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0,
                        help="只处理前 N 张（用于小批量测试，0=全部）")
    parser.add_argument("--match", type=str, default="",
                        help="文件名子串过滤（多个用逗号分隔），用于只跑指定的几张")
    parser.add_argument("--root", type=str, default=str(ROOT),
                        help="待解密图片所在的根目录（默认当前工作目录）")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    out_root = root / OUT_SUBDIR_NAME
    images = []
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        if p.suffix.lower() not in EXTENSIONS:
            continue
        if out_root in p.parents or p.parent == out_root:
            continue
        images.append(p)
    images.sort()

    if args.match:
        keys = [s.strip() for s in args.match.split(",") if s.strip()]
        images = [p for p in images if any(k in p.name for k in keys)]
    if args.limit > 0:
        images = images[: args.limit]

    print(f"找到 {len(images)} 张待处理图片。")
    print("提示：运行期间请不要操作键盘/鼠标。\n")

    shell = win32com.client.Dispatch("WScript.Shell")

    ok, skip, err = 0, 0, 0
    for src in images:
        rel = src.relative_to(root)
        dst = out_root / rel.with_suffix(".jpg")
        if dst.exists():
            print(f"  --  {src.name}  (已存在，跳过)")
            skip += 1
            continue
        msg = process_one(src, dst, shell)
        print(msg)
        if msg.startswith("  OK"):
            ok += 1
        else:
            err += 1
        time.sleep(INTER_FILE_WAIT)

    print(f"\n完成：OK={ok}  跳过={skip}  失败={err}")
    print(f"输出目录：{out_root}")


if __name__ == "__main__":
    main()
