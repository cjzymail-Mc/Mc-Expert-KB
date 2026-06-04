#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PPT 视觉保真度检查工具.

两个核心函数（既可作 CLI 直接跑，也可 import 作库函数）：
  - slide_export_png(ppt_app, slide, out_path)
    把 PPT slide 通过 COM Copy → 剪贴板 → Pillow 导出 PNG，
    绕过 PowerPoint 原生 Export() 在加密 PPT 上的失败。

  - ssim_compare(img_path_a, img_path_b) -> float
    纯 Pillow 实现的 SSIM（无 numpy 依赖），返回 [0, 1] 相似度。
    -1.0 表示比对失败。

CLI 用法：
  # 单页（向后兼容）
  python ppt_visual_check.py --pptx-a a.pptx --pptx-b b.pptx --slide-index 5

  # 多页范围
  python ppt_visual_check.py --pptx-a a.pptx --pptx-b b.pptx --slide-indices "1-5,8"

  # 桥接当前打开的 PPT（避开文件锁；a 用当前打开的、b 从磁盘加载）
  python ppt_visual_check.py --active-a --pptx-b reference.pptx --slide-indices "12-14"

  # 两份都桥接（多份打开时配合 --pptx-a / --pptx-b 精确定位）
  python ppt_visual_check.py --active-a --pptx-a output.pptx \
                             --active-b --pptx-b reference.pptx --slide-index 5

来源：3rd-ppt-prj/pipeline/ppt_pipeline_common.py（2026-05-26 提为用户级 skill）
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path


def safe_print(*args, **kwargs):
    """print() that survives Windows cp1252 consoles."""
    end = kwargs.get("end", "\n")
    line = " ".join(str(a) for a in args)
    try:
        print(line, end=end)
    except UnicodeEncodeError:
        ascii_line = line.encode(sys.stdout.encoding or "ascii", "replace").decode(
            sys.stdout.encoding or "ascii"
        )
        print(ascii_line, end=end)


def slide_export_png(ppt_app, slide, out_path: str,
                     width: int = 1920, height: int = 1080) -> bool:
    """Export a single slide to PNG via clipboard → Pillow.

    Uses COM Copy → PIL.ImageGrab to bypass file-level encryption
    that affects PowerPoint's native slide.Export().

    Args:
        ppt_app: COM PowerPoint.Application instance (kept for signature compat).
        slide: COM Slide object (e.g. presentation.Slides(5)).
        out_path: where to save the PNG.
        width / height: legacy params, kept for compat (clipboard path doesn't honor them).

    Returns:
        True on success, False if export fails.
    """
    try:
        from PIL import ImageGrab
    except ImportError:
        safe_print("[WARN] slide_export_png: Pillow not installed (pip install Pillow)")
        return False
    try:
        slide.Copy()
        time.sleep(1.0)
        img = ImageGrab.grabclipboard()
        if img is None:
            safe_print("[WARN] slide_export_png: clipboard empty after Copy")
            return False
        img.save(str(out_path))
        return Path(out_path).exists()
    except Exception as e:
        safe_print(f"[WARN] slide_export_png failed: {e}")
        return False


def ssim_compare(img_path_a: str, img_path_b: str) -> float:
    """Compute structural similarity (SSIM) between two images.

    Pure Pillow implementation, zero numpy dependency.
    Returns a float in [0, 1] where 1.0 = identical.
    Falls back to -1.0 if comparison fails.
    """
    try:
        from PIL import Image
    except ImportError:
        safe_print("[WARN] Pillow not installed, SSIM skipped")
        return -1.0

    try:
        a = Image.open(img_path_a).convert("L")
        b = Image.open(img_path_b).convert("L")
        if a.size != b.size:
            b = b.resize(a.size, Image.LANCZOS)
        pixels_a = list(a.getdata())
        pixels_b = list(b.getdata())
        n = len(pixels_a)
        if n == 0:
            return -1.0

        mean_a = sum(pixels_a) / n
        mean_b = sum(pixels_b) / n
        var_a = sum((p - mean_a) ** 2 for p in pixels_a) / n
        var_b = sum((p - mean_b) ** 2 for p in pixels_b) / n
        cov = sum((pa - mean_a) * (pb - mean_b)
                  for pa, pb in zip(pixels_a, pixels_b)) / n

        C1 = (0.01 * 255) ** 2
        C2 = (0.03 * 255) ** 2
        num = (2 * mean_a * mean_b + C1) * (2 * cov + C2)
        den = (mean_a ** 2 + mean_b ** 2 + C1) * (var_a + var_b + C2)
        return num / den if den != 0 else 0.0
    except Exception as e:
        safe_print(f"[WARN] ssim_compare failed: {e}")
        return -1.0


def _parse_slides(spec: str) -> list[int]:
    """'1-5,8,10-12' -> [1,2,3,4,5,8,10,11,12]（去重 + 排序）"""
    out: list[int] = []
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            a, b = part.split("-", 1)
            out.extend(range(int(a), int(b) + 1))
        else:
            out.append(int(part))
    return sorted(set(out))


def _resolve_presentation(ppt_app, *, active: bool, pptx_path: str | None):
    """获取一份 Presentation 对象。

    Returns:
        (presentation, opened_by_us: bool)
        opened_by_us=True 表示由本函数 Open，需要在用完后 Close。
    """
    if active:
        if pptx_path:
            # 多份打开时按路径精确匹配 ActivePresentation 候选
            target = str(Path(pptx_path).resolve()).lower()
            for pres in list(ppt_app.Presentations):
                try:
                    if str(pres.FullName).lower() == target:
                        return pres, False
                except Exception:
                    continue
            raise RuntimeError(
                f"--active 模式找不到匹配 {pptx_path} 的已打开 PPT；"
                f"当前打开的：{[p.Name for p in ppt_app.Presentations]}"
            )
        # 无路径限定 → 取 ActivePresentation
        try:
            return ppt_app.ActivePresentation, False
        except Exception:
            raise RuntimeError("无 ActivePresentation；请在 PowerPoint 中打开演示文稿")
    # 文件模式
    if not pptx_path:
        raise RuntimeError("文件模式需要 --pptx-x 路径")
    pres = ppt_app.Presentations.Open(
        str(Path(pptx_path).resolve()),
        ReadOnly=True, WithWindow=True,
    )
    return pres, True


def _cli_export_and_compare(*, pptx_a, active_a, pptx_b, active_b,
                            slides: list[int],
                            tmp_dir: str = "tmp_visual_check") -> int:
    """两份 PPT 跨多页 SSIM。

    任一份可选文件模式或 --active 桥接。--active 模式下不 Quit/Close
    属于该份的资源（避免炸用户进程）。
    """
    import win32com.client

    tmp = Path(tmp_dir)
    tmp.mkdir(parents=True, exist_ok=True)

    use_active = active_a or active_b
    if use_active:
        try:
            ppt = win32com.client.GetActiveObject("PowerPoint.Application")
        except Exception as e:
            safe_print(f"[ERR] --active 模式但 PowerPoint 未运行: {e}")
            return 2
        app_opened_by_us = False
    else:
        # com-survival-reflexes R3：自动化场景永远 DispatchEx 起新进程
        ppt = win32com.client.DispatchEx("PowerPoint.Application")
        app_opened_by_us = True

    # 必须可见才能 Copy 拿到剪贴板位图
    try:
        ppt.Visible = True
    except Exception:
        pass

    pres_a = pres_b = None
    pres_a_opened = pres_b_opened = False
    try:
        pres_a, pres_a_opened = _resolve_presentation(
            ppt, active=active_a, pptx_path=pptx_a)
        pres_b, pres_b_opened = _resolve_presentation(
            ppt, active=active_b, pptx_path=pptx_b)

        results: list[tuple[int, float]] = []
        for sn in slides:
            if sn < 1 or sn > pres_a.Slides.Count:
                safe_print(f"[SKIP] slide {sn} 超出 a 的范围（共 {pres_a.Slides.Count} 页）")
                continue
            if sn > pres_b.Slides.Count:
                safe_print(f"[SKIP] slide {sn} 超出 b 的范围（共 {pres_b.Slides.Count} 页）")
                continue

            out_a = tmp / f"a_{sn:03d}.png"
            out_b = tmp / f"b_{sn:03d}.png"

            ok_a = slide_export_png(ppt, pres_a.Slides(sn), str(out_a))
            ok_b = slide_export_png(ppt, pres_b.Slides(sn), str(out_b))
            if not (ok_a and ok_b):
                safe_print(f"[SKIP] slide {sn} 导出失败")
                continue

            score = ssim_compare(str(out_a), str(out_b))
            results.append((sn, score))
            safe_print(f"  slide {sn}: SSIM = {score:.3f}  (a={out_a.name}  b={out_b.name})")
    except RuntimeError as e:
        safe_print(f"[ERR] {e}")
        return 2
    finally:
        # 只关 / 退我们自己开的
        if pres_a_opened and pres_a is not None:
            try:
                pres_a.Close()
            except Exception:
                pass
        if pres_b_opened and pres_b is not None:
            try:
                pres_b.Close()
            except Exception:
                pass
        if app_opened_by_us:
            try:
                ppt.Quit()
            except Exception:
                pass

    safe_print("")
    safe_print("=" * 60)
    if not results:
        safe_print("没有可对比的页面")
        return 1
    if len(results) == 1:
        safe_print(f"SSIM = {results[0][1]:.3f}")
    else:
        scores = [s for _, s in results]
        safe_print(f"对比页数：{len(results)}")
        safe_print(f"  平均 SSIM:  {sum(scores) / len(scores):.3f}")
        safe_print(f"  最低 SSIM:  {min(scores):.3f}  (slide {min(results, key=lambda x: x[1])[0]})")
        safe_print(f"  最高 SSIM:  {max(scores):.3f}  (slide {max(results, key=lambda x: x[1])[0]})")
    return 0


def main():
    parser = argparse.ArgumentParser(description="PPT 视觉保真度检查")
    parser.add_argument("--pptx-a", help="第一份 PPT 路径")
    parser.add_argument("--pptx-b", help="第二份 PPT 路径")
    parser.add_argument("--active-a", action="store_true",
                        help="第一份用当前打开的 PPT（多份打开时配合 --pptx-a 精确定位）")
    parser.add_argument("--active-b", action="store_true",
                        help="第二份用当前打开的 PPT（多份打开时配合 --pptx-b 精确定位）")
    parser.add_argument("--slide-index", type=int,
                        help="单页对比（向后兼容；推荐用 --slide-indices）")
    parser.add_argument("--slide-indices",
                        help="多页对比，语法 '1-5,8,10-12'")
    parser.add_argument("--tmp-dir", default="tmp_visual_check",
                        help="导出 PNG 的临时目录（默认 ./tmp_visual_check）")
    args = parser.parse_args()

    if not args.pptx_a and not args.active_a:
        safe_print("[ERR] 必须给 --pptx-a 或 --active-a 其中之一")
        return 2
    if not args.pptx_b and not args.active_b:
        safe_print("[ERR] 必须给 --pptx-b 或 --active-b 其中之一")
        return 2

    if args.slide_indices:
        slides = _parse_slides(args.slide_indices)
    elif args.slide_index:
        slides = [args.slide_index]
    else:
        slides = [1]

    if not slides:
        safe_print("[ERR] 未解析出任何 slide 编号")
        return 2

    return _cli_export_and_compare(
        pptx_a=args.pptx_a, active_a=args.active_a,
        pptx_b=args.pptx_b, active_b=args.active_b,
        slides=slides, tmp_dir=args.tmp_dir,
    )


if __name__ == "__main__":
    sys.exit(main() or 0)
