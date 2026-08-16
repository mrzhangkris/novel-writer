#!/usr/bin/env python3
"""export_book.py — 合成出书脚本

按章顺序拼接正文，剥离 <!-- --> 元标注，产出干净成书稿。

用法：
  export_book.py --project {书项目根} --output {成书稿路径}
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

COMMENT_RE = re.compile(r"<!--.*?-->", flags=re.DOTALL)


def find_chapter_files(root: Path) -> list[Path]:
    chapters_dir = root / "chapters"
    if not chapters_dir.is_dir():
        return []
    entries: list[Path] = []
    for path in chapters_dir.iterdir():
        if path.is_file() and path.suffix == ".md":
            entries.append(path)
        elif path.is_dir():
            draft = path / "draft.md"
            if draft.exists():
                entries.append(draft)

    def chapter_key(path: Path) -> tuple:
        text = path.parent.name + path.name
        numbers = [int(n) for n in re.findall(r"\d+", text)]
        return (numbers[0] if numbers else 0, text)

    return sorted(entries, key=chapter_key)


def strip_comments(text: str) -> str:
    return COMMENT_RE.sub("", text)


def export_book(root: Path, output: Path) -> int:
    files = find_chapter_files(root)
    if not files:
        print("❌ 未找到章节正文（chapters/ 下无 .md 或 chapter-NNN/draft.md）")
        return 1

    parts = [strip_comments(f.read_text(encoding="utf-8")).strip() for f in files]
    book = "\n\n".join(parts) + "\n"
    output.write_text(book, encoding="utf-8")
    leftover = len(COMMENT_RE.findall(book))
    print(f"✅ 成书稿已生成：{output}")
    print(f"   章节数：{len(files)}，总字符数：{len(book)}，残留元标注：{leftover}")
    if leftover:
        print("⚠️  仍有残留 <!-- --> 标注（可能嵌套异常），请检查")
        return 1
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="合成出书（剥离元标注）")
    parser.add_argument("--project", type=Path, required=True, help="书项目根")
    parser.add_argument("--output", type=Path, required=True, help="成书稿输出路径")
    args = parser.parse_args()
    return export_book(args.project, args.output)


if __name__ == "__main__":
    sys.exit(main())
