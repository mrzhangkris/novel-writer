#!/usr/bin/env python3
"""scaffold_outline.py — 大纲骨架生成器（确定性部分由脚本搭，AI 只填肉）

按 concept.md 的目标篇幅 + word-count.json 的每章字数推算出章数，
生成 outline.md 骨架：每章四字段（本章目标/场景安排/关键事件/章末钩子）
+ 新概念占位，以及结构标记/情绪曲线/伏笔规划/概念预算的空框架。
AI 只需填内容，不需要数章数、不需要写重复框架。

用法：
  scaffold_outline.py --project 书目录 [--chapters N] [--force]
  默认不覆盖已有 outline.md；--chapters 手动指定章数。

篇幅解析：concept.md 的「- 目标篇幅：」行，支持「约 3 万字」「15 万字起」「8 万字」
（万=10000；未命中时默认 30 章，提示手动 --chapters）。
"""

from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path

from _common import PIPELINE_FILE, read_json

DEFAULT_CHAPTERS = 30


def parse_total_words(root: Path) -> int | None:
    concept = root / "concept.md"
    if not concept.exists():
        return None
    for line in concept.read_text(encoding="utf-8").splitlines():
        m = re.search(r"目标篇幅[：:]\s*(.+)$", line)
        if not m:
            continue
        text = m.group(1)
        wm = re.search(r"(\d+(?:\.\d+)?)\s*万", text)
        if wm:
            return int(float(wm.group(1)) * 10000)
        zm = re.search(r"(\d+)\s*千", text)
        if zm:
            return int(zm.group(1)) * 1000
    return None


def per_chapter_range(root: Path) -> tuple[int, int] | None:
    pipe = read_json(root / PIPELINE_FILE)
    if not isinstance(pipe, dict):
        return None
    wc_file = Path(__file__).resolve().parent.parent / "references" / "word-count.json"
    try:
        wc = json.loads(wc_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    plat = wc.get(pipe.get("platform"))
    if not plat:
        return None
    cfg = plat.get(pipe.get("type") or "长篇小说")
    rng = cfg.get("每章") if isinstance(cfg, dict) else None
    return (int(rng[0]), int(rng[1])) if rng and len(rng) == 2 else None


def scaffold(chapters: int) -> str:
    lines = [
        "# 大纲（骨架，AI 填写内容）",
        "",
        "## 总纲（全书鸟瞰：一句话主线 + 卷/幕 + 关键转折 + 结局锚点，防跑偏）",
        "- 一句话主线：谁，想做什么，遇到什么阻碍，最终如何",
        "- 结构划分：（卷/幕/起承转合，短篇可只写起承转合）",
        "- 关键转折点：",
        "",
        "| 序号 | 位置 | 事件 | 作用 |",
        "|---|---|---|---|",
        "",
        "- 结局锚点：（结尾大方向，写的时候不断回看）",
        "",
        "## 章纲",
        "",
    ]
    for n in range(1, chapters + 1):
        lines.append(f"### 第{n}章：")
        lines.append("- 本章目标：")
        lines.append("- 场景安排：")
        lines.append("- 关键事件：")
        lines.append("- 章末钩子：")
        lines.append("- 新概念：")
        lines.append("")
    lines += [
        "## 结构标记",
        "- 起：第1章；承：待定；转：待定；合：待定",
        "",
        "## 情绪曲线",
        "- 待定（按章列情绪高低点，标注小爽/中爽/大爽分布，保证爽点密度）",
        "",
        "## 伏笔规划",
        "",
        "| 编号 | 内容 | 埋设章 | 计划回收章 | 类型 |",
        "|---|---|---|---|---|",
        "",
        "## 概念预算（防信息倾泻）",
        f"- 第1章：引入（≤3 个新概念）；第2-{chapters}章：每章 ≤2 个（可为 0）",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="大纲骨架生成器")
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--chapters", type=int, default=None)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    root = args.project
    if not (root / ".story").is_dir():
        print(f"❌ 不是书项目根：{root}")
        return 1

    out = root / "outline.md"
    if out.exists() and not args.force:
        print(f"⚠️  outline.md 已存在，不覆盖（--force 重建骨架）。先读现有大纲，勿重复脚手架。")
        return 1

    chapters = args.chapters
    if chapters is None:
        total = parse_total_words(root)
        rng = per_chapter_range(root)
        if total and rng:
            chapters = max(1, math.ceil(total / ((rng[0] + rng[1]) / 2)))
            print(f"📏 按篇幅 {total} 字 ÷ 每章约 {int((rng[0]+rng[1])/2)} 字 → {chapters} 章")
        else:
            chapters = DEFAULT_CHAPTERS
            print(f"⚠️  无法解析目标篇幅，默认 {chapters} 章（可用 --chapters 指定）")

    out.write_text(scaffold(chapters), encoding="utf-8")
    print(f"✅ outline.md 骨架已生成：{out}（{chapters} 章 × 四字段 + 空框架）")
    print("   下一步：novel-outline 子技能填写内容，advance outline 过闸")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
