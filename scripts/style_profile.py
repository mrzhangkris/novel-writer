#!/usr/bin/env python3
"""style_profile.py — 对标书文风量化蒸馏（story-long-analyze Stage 6 Step 4 固化）

把 style-profile-generator 里「Python 1-liner heredoc」的确定性统计固化为固定脚本：
句长分布 / 标点密度 / 段落结构 / 对话占比 / 情绪标记强度，输出可直接贴进
`deconstruct/{书名}/文风.md` 的「## 整体语感」量化节。锚点片段选择仍是 AI 判断。

用法：
  style_profile.py --input _style-sample.txt [--output 文风量化节.md] [--json]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from _textstat import cjk_len

SENT_END = "。！？!?…"
PUNCT = {"，", "。", "！", "？", "；", "：", "、", "…", "——", "「", "」"}
EMOTION_MARKERS = re.compile(r"！|!|？|\?|破防|泪|笑|怒|惊|慌|颤|抖|攥|冲|奔")


def sentences(text: str) -> list[str]:
    parts = re.split(rf"(?<=[{SENT_END}])", text)
    return [p.strip() for p in parts if p.strip()]


def profile(text: str) -> dict:
    lines = [l for l in text.splitlines() if l.strip()]
    dialogue_lines = [l for l in lines if l.strip().startswith("「")]
    total_cjk = cjk_len(text)

    # 句长分布
    sent_lens = [cjk_len(s) for s in sentences(text) if cjk_len(s) > 0]
    short = sum(1 for n in sent_lens if n < 15)
    mid = sum(1 for n in sent_lens if 15 <= n <= 30)
    long = sum(1 for n in sent_lens if n > 30)
    avg = round(sum(sent_lens) / len(sent_lens), 1) if sent_lens else 0

    # 标点密度（每千字）
    punct_count: dict[str, int] = {}
    for p in sorted(PUNCT):
        c = text.count(p)
        if c:
            punct_count[p] = c

    # 段落结构
    para_cjk = [cjk_len(l) for l in lines if not l.strip().startswith("「")]
    para_median = sorted(para_cjk)[len(para_cjk) // 2] if para_cjk else 0

    # 情绪标记强度（情绪标点+情绪动词 每千字）
    emotion_hits = len(EMOTION_MARKERS.findall(text))

    return {
        "sentence": {
            "total": len(sent_lens),
            "short_lt15_pct": round(100 * short / len(sent_lens), 1) if sent_lens else 0,
            "mid_15_30_pct": round(100 * mid / len(sent_lens), 1) if sent_lens else 0,
            "long_gt30_pct": round(100 * long / len(sent_lens), 1) if sent_lens else 0,
            "avg_len": avg,
        },
        "punctuation_per_kilo": {p: round(1000 * c / total_cjk, 1) for p, c in punct_count.items()},
        "paragraph": {
            "dialogue_line_pct": round(100 * len(dialogue_lines) / len(lines), 1),
            "median_cjk": para_median,
        },
        "emotion_markers_per_kilo": round(1000 * emotion_hits / total_cjk, 1) if total_cjk else 0,
    }


def render_md(p: dict) -> str:
    s = p["sentence"]
    d = p["paragraph"]
    lines = ["## 整体语感", ""]
    lines.append(
        f"- 句长分布：短句(<15字) {s['short_lt15_pct']}%、中句(15-30) {s['mid_15_30_pct']}%、"
        f"长句(>30) {s['long_gt30_pct']}%、平均句长 {s['avg_len']} 字。"
        f"confidence: high（数据由 style_profile.py 确定性测量）"
    )
    if p["punctuation_per_kilo"]:
        pts = "、".join(f"{k}{v}" for k, v in sorted(p["punctuation_per_kilo"].items(), key=lambda kv: -kv[1])[:6])
        lines.append(f"- 标点密度（/千字）：{pts}")
    lines.append(
        f"- 段落结构：对话行占比 {d['dialogue_line_pct']}%、叙述段中位 {d['median_cjk']} 字。"
    )
    lines.append(f"- 情绪标记强度：{p['emotion_markers_per_kilo']}/千字（情绪标点+情绪动词）")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="文风量化蒸馏")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    try:
        text = args.input.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"❌ 无法读取样本：{exc}")
        return 1
    p = profile(text)
    if args.json:
        print(json.dumps(p, ensure_ascii=False, indent=2))
        return 0
    md = render_md(p)
    if args.output:
        args.output.write_text(md, encoding="utf-8")
        print(f"✓ 量化节已写入 {args.output}")
    else:
        print(md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
