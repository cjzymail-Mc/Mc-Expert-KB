"""3 账号 auto-memory junction 一键配置（编排脚本）。

把 union merge → 补齐缺失账户的 projects 目录 → setup --apply → verify
四个阶段串成一条龙，幂等运行（重复跑不会破坏已有状态）。

阶段：
  A. 如果 .claude/auto-memory/ 没 .md，跑 memory_union_merge.py --apply
  B. 探测哪些账户缺 projects/<name>/，从已有账户复制（跳过 memory junction）
  C. 跑 memory_junction_setup.py --apply
  D. 跑 memory_junction_verify.py
  E. 输出手工验证指引（按用户要求，不替跑）

使用：
    python skills/memory_junction_one_shot.py
"""
import ctypes
import os
import re
import shutil
import stat
import subprocess
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

USERPROFILE = os.path.expandvars("%USERPROFILE%")

ACCOUNTS = {
    "mc": os.path.join(USERPROFILE, ".claude-mc"),
    "yk": os.path.join(USERPROFILE, ".claude"),
    "xh": os.path.join(USERPROFILE, ".claude-xh"),
}

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, "..", ".."))
TARGET_DIR = os.path.join(REPO_ROOT, ".claude", "auto-memory")


def detect_project_name():
    return re.sub(r"[^A-Za-z0-9-]", "-", REPO_ROOT).rstrip("-")


def is_junction(path):
    if not os.path.isdir(path):
        return False
    attrs = ctypes.windll.kernel32.GetFileAttributesW(path)
    if attrs == 0xFFFFFFFF:
        return False
    return bool(attrs & stat.FILE_ATTRIBUTE_REPARSE_POINT)


def _ignore_memory(_src, names):
    """copytree 时强制忽略 memory 子目录。
    无论 src 的 memory 是真实目录还是 junction 都跳过——
    target 的 memory 由 phase B 单独 makedirs 空目录，让 phase C 干净处理。"""
    return {"memory"} if "memory" in names else set()


def project_dir(account_key, project_name):
    return os.path.join(ACCOUNTS[account_key], "projects", project_name)


def run_subscript(label, script_name, *args):
    """跑 skills/<script_name>，原样透传输出，失败时 sys.exit。"""
    cmd = [sys.executable, os.path.join(SCRIPT_DIR, script_name), *args]
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    print(f"\n$ python skills/{script_name} {' '.join(args)}")
    result = subprocess.run(cmd, env=env)
    if result.returncode != 0:
        print(f"\n[FAIL] {label} 退出码 {result.returncode}，停止后续步骤")
        sys.exit(result.returncode)


def phase_a_union():
    print("\n" + "=" * 60)
    print("Phase A：union merge（合并 N 账号 memory 到 .claude/auto-memory/）")
    print("=" * 60)
    if os.path.isdir(TARGET_DIR):
        existing = [f for f in os.listdir(TARGET_DIR) if f.endswith(".md")]
        if existing:
            print(f"[skip] {TARGET_DIR} 已有 {len(existing)} 个 .md，跳过 union merge")
            return
    run_subscript("union merge", "memory_union_merge.py", "--apply")


def phase_b_copy(project_name):
    print("\n" + "=" * 60)
    print("Phase B：补齐缺失账户的 projects/<name>/ 目录")
    print("=" * 60)
    existing = [k for k in ACCOUNTS if os.path.isdir(project_dir(k, project_name))]
    missing = [k for k in ACCOUNTS if k not in existing]
    print(f"  已有：{existing}")
    print(f"  缺失：{missing}")

    if not missing:
        print(f"  [skip] 全部账户都有该项目目录")
        return

    if not existing:
        print(f"\n[FAIL] 没有任何账户有 projects/{project_name}/，无源可复制")
        print(f"       请先在任一账户用 Claude Code 打开此项目至少一次。")
        sys.exit(1)

    src_key = existing[0]
    src_proj = project_dir(src_key, project_name)
    print(f"  复制源：{src_key} → {src_proj}")

    for tgt_key in missing:
        tgt_proj = project_dir(tgt_key, project_name)
        print(f"\n  [{tgt_key}] 复制 → {tgt_proj}")
        os.makedirs(os.path.dirname(tgt_proj), exist_ok=True)
        shutil.copytree(src_proj, tgt_proj, ignore=_ignore_memory)
        # phase C 需要 memory 目录存在（真实目录）才能处理
        mem = os.path.join(tgt_proj, "memory")
        os.makedirs(mem, exist_ok=True)
        print(f"  [OK  ] 完成（包含空 memory/，等待 phase C mklink）")


def phase_c_setup():
    print("\n" + "=" * 60)
    print("Phase C：setup --apply（建 junction）")
    print("=" * 60)
    run_subscript("setup --apply", "memory_junction_setup.py", "--apply")


def phase_d_verify(project_name):
    print("\n" + "=" * 60)
    print("Phase D：verify（端到端写/删传播测试）")
    print("=" * 60)
    cmd = [sys.executable, os.path.join(SCRIPT_DIR, "memory_junction_verify.py")]
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    print(f"\n$ python skills/memory_junction_verify.py")
    result = subprocess.run(cmd, env=env)
    if result.returncode != 0:
        print(f"\n[WARN] verify 失败（returncode={result.returncode}）")
        print(f"       自动流程没把 3 账户都接上；请检查上方日志后再决定下一步。")
        return False
    return True


def phase_e_manual_hint(project_name):
    print("\n" + "=" * 60)
    print("Phase E：手工验证指引（按需执行）")
    print("=" * 60)
    print("  1. 在 .claude/auto-memory/ 新建一个 _check.md 文件（任意内容）")
    print("  2. 检查 3 个账户路径下 memory/ 是否都看到该文件：")
    for k in ACCOUNTS:
        p = os.path.join(project_dir(k, project_name), "memory", "_check.md")
        print(f'       Test-Path "{p}"')
    print("  3. 删掉 _check.md，再次确认 3 处都消失")


def main():
    project_name = detect_project_name()
    print(f"项目名：{project_name}")
    print(f"REPO_ROOT：{REPO_ROOT}")
    print(f"目标目录：{TARGET_DIR}")
    print(f"3 账号：{list(ACCOUNTS.keys())}")

    phase_a_union()
    phase_b_copy(project_name)
    phase_c_setup()
    verify_ok = phase_d_verify(project_name)
    phase_e_manual_hint(project_name)

    print("\n" + "=" * 60)
    if verify_ok:
        print("✓ 全自动流程完成，verify 已通过")
    else:
        print("⚠ 全自动流程完成，但 verify 未通过——见上方日志")
    print("=" * 60)
    return 0 if verify_ok else 1


if __name__ == "__main__":
    sys.exit(main())
