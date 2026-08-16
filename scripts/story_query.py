#!/usr/bin/env python3
"""story_query.py — 查设定 CLI（把「AI 找文件」换成「脚本出结果」）

用法（在书项目目录内，或加 --project）：
  story_query.py --context            续写状态卡（7 栏）
  story_query.py --character 名       角色动态快照 + 静态人物卡（若有）
  story_query.py --foreshadow [F001]  伏笔当前状态（全部或单条）
  story_query.py --timeline           时间线双视图（作者真相 / 读者已知）
  story_query.py --overrides          设定演进账本
  story_query.py --chapter N          第 N 章逐章变更记录
  story_query.py --patterns [钩子]    项目级写作模式记忆（全部或按 pattern-type 过滤）
  story_query.py --status             转发 pipeline.py status（进度单一真相源）
  story_query.py --grep 关键词        在书级设定文件里搜索（concept/世界观/契约/大纲/题材卡）

注：作者级技法库查看走 learn.py list --scope author（query 只读项目内设定）。
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import sys as _sys
from pathlib import Path

from _common import find_project_root, read_json


def root_of(args) -> Path | None:
    start = Path(args.project) if args.project else Path.cwd()
    return find_project_root(start, child=".story")


def show(path: Path) -> None:
    try:
        print(path.read_text(encoding="utf-8"))
    except OSError:
        print(f"（文件不存在：{path}）")


def show_patterns(root: Path, pattern_type: str | None) -> None:
    p = root / ".story" / "project_memory.json"
    data = read_json(p)
    if not isinstance(data, dict) or not data.get("patterns"):
        print("（项目级写作模式记忆为空）")
        return
    shown = 0
    for entry in data["patterns"]:
        pt = entry.get("pattern_type", "other")
        if pattern_type and pt != pattern_type:
            continue
        shown += 1
        print(
            f"[{pt}][{entry.get('importance', '?')}] {entry.get('description', '')}"
            f"（第{entry.get('source_chapter', '?')}章）"
        )
    if shown == 0:
        print(f"（无 {pattern_type} 类型记忆）")


def main() -> int:
    parser = argparse.ArgumentParser(description="查设定 CLI")
    parser.add_argument("--project", type=Path, default=None)
    parser.add_argument("--context", action="store_true")
    parser.add_argument("--character", type=str, default=None)
    parser.add_argument("--foreshadow", nargs="?", const="*")
    parser.add_argument("--timeline", action="store_true")
    parser.add_argument("--overrides", action="store_true")
    parser.add_argument("--chapter", type=int, default=None)
    parser.add_argument("--patterns", nargs="?", const="*", help="项目级模式记忆，可选按 pattern-type 过滤")
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--grep", type=str, default=None)
    args = parser.parse_args()

    root = root_of(args)
    if root is None:
        print("❌ 不在项目中")
        return 1

    if args.context:
        show(root / "tracking/context.md")
        return 0
    if args.character:
        show(root / "tracking/characters" / f"{args.character}.md")
        static = root / "characters" / f"{args.character}.md"
        if static.exists():
            print("\n--- 静态人物卡 ---")
            show(static)
        return 0
    if args.foreshadow is not None:
        text = (root / "tracking/foreshadows.md").read_text(encoding="utf-8")
        if args.foreshadow != "*":
            hit = [l for l in text.splitlines() if l.startswith(f"| {args.foreshadow} ")]
            print("\n".join(hit) if hit else f"（未找到伏笔 {args.foreshadow}）")
        else:
            print(text)
        return 0
    if args.timeline:
        show(root / "tracking/timeline/author-truth.md")
        print()
        show(root / "tracking/timeline/reader-known.md")
        return 0
    if args.overrides:
        show(root / "tracking/overrides.md")
        return 0
    if args.chapter is not None:
        p = root / "tracking/chapter-deltas" / f"第{args.chapter:03d}章.md"
        show(p)
        return 0
    if args.patterns is not None:
        show_patterns(root, None if args.patterns == "*" else args.patterns)
        return 0
    if args.status:
        here = Path(__file__).resolve().parent
        subprocess.run([_sys.executable, str(here / "pipeline.py"), "status"], cwd=str(root))
        return 0
    if args.grep:
        files = ["concept.md", "worldbuilding.md", "reader-contract.md", "outline.md", "题材卡.md"]
        total = 0
        for name in files:
            p = root / name
            if not p.exists():
                continue
            for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
                if args.grep in line:
                    print(f"{name}:{i}: {line.strip()}")
                    total += 1
        if total == 0:
            print(f"（「{args.grep}」在书级设定文件中未命中）")
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
