#!/usr/bin/env python3
"""check_spec_copy.py — 细纲照搬检测（oh-story check-outline-copy 本地化轻量版）

检测正文 draft.md 是否把 spec.md 大纲要点/关键事件的句子逐字誊抄进正文
（连续重合 ≥15 字即判誊抄）。细纲是给作者的执行指令，正文照搬 = 写成
「成品散文的清单」，不是故事。

用法：
  check_spec_copy.py --project {书目录} --chapter N [--json]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from _common import find_project_root

MIN_OVERLAP = 15


def spec_sentences(spec_text: str) -> list[str]:
    """从 spec 的「大纲要点」节提取条目句子（去勾选符与注解）。"""
    out = []
    in_block = False
    for line in spec_text.splitlines():
        s = line.strip()
        if s.startswith("## 大纲要点"):
            in_block = True
            continue
        if in_block and s.startswith("## "):
            break
        if in_block and s.startswith("-"):
            s = re.sub(r"^-\s*\[[ x]\]\s*", "", s)
            s = re.sub(r"（.*?）", "", s)  # 去括号注解（AI 可能照抄注解也算）
            s = s.strip()
            if len(s) >= MIN_OVERLAP:
                out.append(s)
    return out


def longest_common(text: str, sentence: str) -> str:
    """两个字符串的最长公共子串（小文本暴力即可）。"""
    best = ""
    for i in range(len(sentence) - MIN_OVERLAP + 1):
        for j in range(len(sentence), i + len(best), -1):
            if sentence[i:j] in text:
                best = sentence[i:j]
                break
    return best


def main() -> int:
    parser = argparse.ArgumentParser(description="细纲照搬检测")
    parser.add_argument("--project", type=Path, default=None)
    parser.add_argument("--chapter", type=int, required=True)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    start = args.project if args.project else Path.cwd()
    root = find_project_root(start, child=".story")
    if root is None:
        print("❌ 不在书项目中")
        return 1
    spec = root / f"chapters/chapter-{args.chapter:03d}/spec.md"
    draft = root / f"chapters/chapter-{args.chapter:03d}/draft.md"
    if not spec.exists() or not draft.exists():
        print("❌ spec 或 draft 不存在")
        return 1
    text = draft.read_text(encoding="utf-8")
    hits = []
    for sent in spec_sentences(spec.read_text(encoding="utf-8")):
        lcs = longest_common(text, sent)
        if len(lcs) >= MIN_OVERLAP:
            hits.append({"spec": sent, "copied": lcs})
    if args.json:
        print(json.dumps({"chapter": args.chapter, "hits": hits}, ensure_ascii=False, indent=2))
        return 0
    if not hits:
        print(f"✓ 第 {args.chapter} 章无细纲照搬（正文与 spec 大纲要点无 ≥{MIN_OVERLAP} 字重合）")
        return 0
    print(f"⚠️ 第 {args.chapter} 章发现 {len(hits)} 处细纲照搬（spec 句子逐字出现在正文）：")
    for h in hits:
        print(f"  - spec「{h['spec'][:30]}…」→ 正文照搬「{h['copied']}」")
    print("  细纲是作者指令不是正文：把要点展开成场景/动作/对话，别逐字誊抄。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
