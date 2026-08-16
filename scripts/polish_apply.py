#!/usr/bin/env python3
"""polish_apply.py — 病句批量替换（story-polish 支线的落盘动作）

子代理挑出病句清单后，AI 逐条审定「采纳/跳过」，把采纳项写成清单文件，
本脚本对目标章节 draft.md 做精确替换并报告未命中。

清单格式（每行一条，空行与 # 开头忽略）：
  原文「…」→ 改写「…」
也可用 --json 传结构化清单（数组 [{chapter, original, rewrite}]）。

用法：
  polish_apply.py --project {书目录} --input 清单.txt [--dry-run]
  --dry-run 只报告每条是否唯一命中，不改文件。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from _common import find_project_root

PAIR_RE = re.compile(r"^原文「(.*)」→ 改写「(.*)」$")


def load_pairs_txt(path: Path) -> list[tuple[int | None, str, str]]:
    out = []
    current_chapter: int | None = None
    for line in path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        if s.startswith("## ") or s.startswith("# 第") and "章" in s:
            m = re.search(r"第(\d+)章", s)
            current_chapter = int(m.group(1)) if m else current_chapter
            continue
        m = PAIR_RE.match(s)
        if m:
            out.append((current_chapter, m.group(1), m.group(2)))
            continue
        # 兼容「original → rewrite」不带引号格式
        m2 = re.match(r"^(.+?)\s*→\s*(.+)$", s)
        if m2:
            out.append((current_chapter, m2.group(1).strip("「」"), m2.group(2).strip("「」")))
    return out


def apply_to_file(p: Path, pairs: list[tuple[str, str]], dry: bool) -> tuple[int, list]:
    t = p.read_text(encoding="utf-8")
    fixed = 0
    missed = []
    for old, new in pairs:
        c = t.count(old)
        if c == 1:
            if not dry:
                t = t.replace(old, new)
            fixed += 1
        else:
            missed.append((old[:40], c))
    if fixed and not dry:
        p.write_text(t, encoding="utf-8")
    return fixed, missed


def main() -> int:
    parser = argparse.ArgumentParser(description="病句批量替换")
    parser.add_argument("--project", type=Path, default=None)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    start = args.project if args.project else Path.cwd()
    root = find_project_root(start, child=".story")
    if root is None:
        print("❌ 不在书项目中（找不到 .story/）")
        return 1

    if args.input.suffix == ".json":
        try:
            data = json.loads(args.input.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            print(f"❌ 清单 JSON 不可读：{exc}")
            return 1
        items = []
        if not isinstance(data, list):
            print(f"❌ 清单 JSON 根应为数组，实际是 {type(data).__name__}")
            return 1
        for e in data:
            ch = e.get("chapter")
            try:
                items.append((int(ch) if ch is not None else None, str(e["original"]), str(e["rewrite"])))
            except (ValueError, KeyError, TypeError):
                print(f"⚠️ 跳过无效条目：{str(e)[:60]}")
    else:        items = load_pairs_txt(args.input)
    if not items:
        print("❌ 清单为空")
        return 1

    by_chapter: dict[int, list] = {}
    for ch, old, new in items:
        by_chapter.setdefault(ch, []).append((old, new))

    total_fixed = 0
    all_missed: list = []
    # 无章号条目：在全部已存在章节中搜唯一命中（跨章回退）
    orphan = by_chapter.pop(None, [])
    if orphan:
        draft_files = sorted((root / "chapters").glob("chapter-*/draft.md"))
        for old, new in orphan:
            unique_hits = [p for p in draft_files if p.read_text(encoding="utf-8").count(old) == 1]
            if len(unique_hits) == 1:
                ch = int(unique_hits[0].parent.name.split("-")[1])
                by_chapter.setdefault(ch, []).append((old, new))
            else:
                all_missed.append((None, old, -1))
    for ch, pairs in sorted(by_chapter.items(), key=lambda kv: kv[0] or 0):
        p = root / f"chapters/chapter-{ch:03d}/draft.md" if ch else None
        if p is None or not p.exists():
            print(f"⚠️ 第 {ch or '?'} 章：draft 不存在，跳过 {len(pairs)} 条")
            continue
        fixed, missed = apply_to_file(p, pairs, args.dry_run)
        total_fixed += fixed
        all_missed.extend((ch, o, c) for o, c in missed)
        print(f"{'[dry-run] ' if args.dry_run else ''}第 {ch:03d} 章：替换 {fixed}/{len(pairs)}")
    for ch, o, c in all_missed:
        print(f"  未命中（第{ch or '?'}章，出现{c}次）：{o}")
    print(f"{'[dry-run] 将' if args.dry_run else '已'}替换 {total_fixed} 处，未命中 {len(all_missed)} 处")
    return 0


if __name__ == "__main__":
    sys.exit(main())
