#!/usr/bin/env python3
"""platform_review.py — 平台审稿脚本（确定性部分）

能做三件确定的事，其余判断项见 references/platform-review.md 自检清单：
1. 敏感词扫描（对照 references/platform-sensitive-words.txt，命中只警告语境自判）
2. 连接词密度（首先/其次/最后/总之/总的来说/一方面/另一方面…）
3. 句长突发性（burstiness 近似）：句长变异系数过低 = 句子长度过于均匀，AI 特征明显

用法：
  platform_review.py --chapter N [--project 书目录]   单章审
  platform_review.py --book [--project 书目录]        全书审（发布前）
"""

from __future__ import annotations

import argparse
import re
import statistics
from pathlib import Path

from _common import find_project_root

CONNECTORS = [
    "首先", "其次", "再次", "然后", "最后", "总之", "总的来说", "综上所述",
    "一方面", "另一方面", "与此同时", "由此可见", "不难发现", "换句话说",
    "总而言之", "与此同时", "值得注意的是", "与此同时", "因此", "于是",
]
# 句长变异系数低于此值 → 句子长度过于均匀（AI 特征）
CV_THRESHOLD = 0.55
# 连接词每千字密度上限
CONNECTOR_PER_1K = 3.0


def load_sensitive_words(skill_dir: Path) -> list[str]:
    p = skill_dir / "references" / "platform-sensitive-words.txt"
    if not p.exists():
        return []
    words = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("#") or line.startswith("##") or not line:
            continue
        words.extend(w.strip() for w in line.split(",") if w.strip())
    return words


def cjk_count(text: str) -> int:
    return len(re.findall(r"[\u4e00-\u9fff]", text))


def review_text(text: str, label: str, words: list[str], strict: bool = False) -> int:
    cjk = cjk_count(text)
    problems = 0

    # 1) 敏感词
    hits = sorted({w for w in words if w in text})
    if hits:
        problems += 1
        print(f"🔴 敏感词命中（{label}，语境自判）：{'、'.join(hits)}")

    # 2) 连接词密度
    connector_hits = [c for c in CONNECTORS if c in text]
    density = len(connector_hits) / max(cjk, 1) * 1000
    if density > CONNECTOR_PER_1K:
        problems += 1
        print(
            f"🟠 连接词密度偏高（{label}）：{density:.1f}/千字（上限 {CONNECTOR_PER_1K}/千字）"
            f"，命中：{'、'.join(sorted(set(connector_hits))[:6])}"
        )

    # 3) 句长突发性
    sents = [s for s in re.split(r"[。！？；\n]", text) if s.strip()]
    sent_lens = [cjk_count(s) for s in sents]
    if len(sent_lens) >= 10:
        mean = statistics.mean(sent_lens)
        sd = statistics.pstdev(sent_lens)
        cv = sd / mean if mean else 0
        if cv < CV_THRESHOLD:
            problems += 1
            print(
                f"🟠 句长过于均匀（{label}）：变异系数 {cv:.2f}（低于 {CV_THRESHOLD} 疑似 AI 特征），"
                f"平均句长 {mean:.1f} 字。建议长短句交错，关键处用短句砸。"
            )

    if problems == 0:
        print(f"✅ 平台确定性扫描通过（{label}）：敏感词/连接词密度/句长突发性均无异常")
    print("   判断项（AI 过一遍）：四类低质红线、细节密度、情感扁平、题材合规，见 references/platform-review.md")
    return 1 if (strict and problems) else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="平台审稿脚本")
    parser.add_argument("--chapter", type=int, default=None)
    parser.add_argument("--strict", action="store_true", help="命中即退出码 1（批量门禁用）；默认只告警、语境终判归 AI")
    parser.add_argument("--book", action="store_true")
    parser.add_argument("--project", type=Path, default=None)
    args = parser.parse_args()

    start = args.project if args.project else Path.cwd()
    root = find_project_root(start, child=".story")
    if root is None:
        print("❌ 不在项目中")
        return 1
    skill_dir = Path(__file__).resolve().parent.parent
    words = load_sensitive_words(skill_dir)

    rc = 0
    if args.book:
        bodies = []
        for p in sorted((root / "chapters").glob("chapter-*/draft.md")):
            bodies.append(p.read_text(encoding="utf-8"))
        if not bodies:
            print("❌ 未找到章节正文")
            return 1
        rc = review_text("\n".join(bodies), "全本", words, args.strict)
    elif args.chapter is not None:
        p = root / f"chapters/chapter-{args.chapter:03d}/draft.md"
        if not p.exists():
            print(f"❌ 章节正文不存在：{p}")
            return 1
        rc = review_text(p.read_text(encoding="utf-8"), f"第{args.chapter}章", words, args.strict)
    else:
        parser.print_help()
        return 1
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
