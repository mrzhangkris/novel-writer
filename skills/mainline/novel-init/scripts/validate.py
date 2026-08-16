#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""validate.py — 校验写作基础设施（.novel/）与书目录是否完整。

机制复用自 icestarx/story-workflow 的 validate_global_framework.py（文件存在性校验 + 退出码）。

用法：
  # 只校验基础设施
  python3 scripts/validate.py --root-dir ~/novels
  # 同时校验某本书
  python3 scripts/validate.py --root-dir ~/novels --book my-novel

退出码：0 = 结构完整；1 = 有缺失。
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

# setup.py 创建的基础设施文件
STORY_FILES = (
    ".novel/preferences.md",
    ".novel/style-anchor.md",
    ".novel/banned-words.txt",
    ".novel/active.md",
)

STORY_TEMPLATES = (
    "concept.md",
    "reader-contract.md",
    "worldbuilding.md",
    "character-card.md",
    "pacing.md",
)

# new.py 创建的书级文件
BOOK_FILES = (
    "concept.md",
    "reader-contract.md",
    "worldbuilding.md",
    "tracking/pacing.md",
)

BOOK_DIRS = (
    "characters",
    "outline",
    "chapters",
    "tracking",
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate .novel/ scaffold and book scaffold."
    )
    parser.add_argument("--root-dir", type=Path, required=True)
    parser.add_argument("--book", default=None, help="书目录名（可选，校验某本书）")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    root = args.root_dir
    errors: list[str] = []
    warnings: list[str] = []

    if not root.is_dir():
        errors.append(f"root directory not found: {root}")

    # 校验基础设施
    for relative in STORY_FILES:
        if not (root / relative).is_file():
            errors.append(f"missing file: {relative}")
    for name in STORY_TEMPLATES:
        if not (root / ".novel/templates" / name).is_file():
            errors.append(f"missing template: .novel/templates/{name}")

    # 校验书目录
    if args.book:
        book = root / args.book
        if not book.is_dir():
            errors.append(f"book directory not found: {args.book}")
        else:
            for relative in BOOK_DIRS:
                if not (book / relative).is_dir():
                    errors.append(f"missing dir: {args.book}/{relative}")
            for relative in BOOK_FILES:
                if not (book / relative).is_file():
                    errors.append(f"missing file: {args.book}/{relative}")

    result = {
        "valid": not errors,
        "root": str(root),
        "book": args.book,
        "errors": errors,
        "warnings": warnings,
    }
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        for error in errors:
            print("ERROR " + error)
        for warning in warnings:
            print("WARNING " + warning)
        if not errors:
            print(f"OK {root}" + (f" / {args.book}" if args.book else ""))
    raise SystemExit(0 if not errors else 1)


if __name__ == "__main__":
    main()
