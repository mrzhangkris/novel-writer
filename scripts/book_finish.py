#!/usr/bin/env python3
"""book_finish.py — 全书收尾批量执行器

写完最后一章后跑一次，把收尾动作全部串起来：
导出成书 → 全本平台审稿 → 账本终检 → 质量趋势汇总 → 提示全本通顺度修订。

用法：
  book_finish.py --project {书目录} [--title 书名]
"""

from __future__ import annotations

import argparse
import subprocess
import sys as _sys
import sys
from pathlib import Path

from _common import find_project_root


def run(script: str, *args: str, cwd: Path) -> int:
    here = Path(__file__).resolve().parent
    cmd = [_sys.executable, str(here / script), *args]
    print("  ▶ " + " ".join(str(c) for c in cmd))
    return subprocess.run(cmd, cwd=str(cwd)).returncode


def main() -> int:
    parser = argparse.ArgumentParser(description="全书收尾批量执行器")
    parser.add_argument("--project", type=Path, default=None)
    parser.add_argument("--title", type=str, default=None, help="书名（默认取项目名）")
    args = parser.parse_args()
    start = args.project if args.project else Path.cwd()
    root = find_project_root(start, child=".story")
    if root is None:
        print("❌ 不在书项目中（找不到 .story/）")
        return 1
    title = args.title or root.name
    out = root / f"成书-{title}.md"
    print(f"📕 《{title}》 全书收尾")

    rc = run("export_book.py", "--project", str(root), "--output", str(out), cwd=root)
    if rc != 0:
        return rc
    rc = run("platform_review.py", "--book", "--project", str(root), cwd=root)
    if rc != 0:
        return rc
    rc = run("tracking_commit.py", "check", "--project", str(root), cwd=root)
    if rc != 0:
        return rc
    rc = run("check_continuity.py", "--project", str(root), cwd=root)
    if rc != 0:
        return rc
    rc = run("quality_trend.py", "show", "--project", str(root), cwd=root)
    if rc != 0:
        return rc
    print()
    print("  ✅ 全书收尾完成。")
    print("  💡 建议补一轮通顺度修订：读 skills/branch/story-polish/SKILL.md，")
    print("     spawn 子代理逐章挑病句后批量替换（参看 .story/polish-report.md 记录格式）。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
